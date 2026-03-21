package cmd

import (
	"context"
	"fmt"
	"io"
	"strconv"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

// oldImage holds display info, Docker ID, and raw size for a non-current
// SynthOrg image.
type oldImage struct {
	display string  // human-readable line (repo, digest short, size)
	id      string  // Docker short ID (12 hex chars)
	sizeB   float64 // image size in bytes (0 if unparseable)
}

// hintThresholdBytes is the minimum total size of old images before the
// update command prints a cleanup hint (5 GB).
const hintThresholdBytes = 5 * 1024 * 1024 * 1024

// hintOldImages prints a passive hint about old images after a successful
// update, but only when the total old image size exceeds hintThresholdBytes.
// Replaces the former interactive cleanup prompt.
func hintOldImages(cmd *cobra.Command, info docker.Info, state config.State) {
	out := ui.NewUI(cmd.OutOrStdout())
	old, _ := findOldImages(cmd.Context(), cmd.ErrOrStderr(), info, state)
	if len(old) == 0 {
		return
	}

	var totalB float64
	for _, img := range old {
		totalB += img.sizeB
	}

	if totalB < hintThresholdBytes {
		return
	}

	out.Blank()
	out.Hint(fmt.Sprintf("%d old image(s) using %s. Run 'synthorg cleanup' to free space.",
		len(old), formatBytes(totalB)))
}

// findOldImages lists SynthOrg images whose Docker ID does not match
// any current service image. Deduplicates by Docker ID. Returns nil
// if current image IDs cannot be reliably determined.
func findOldImages(ctx context.Context, errOut io.Writer, info docker.Info, state config.State) ([]oldImage, error) {
	currentIDs, err := collectCurrentImageIDs(ctx, info, state)
	if err != nil {
		_, _ = fmt.Fprintf(errOut, "Note: could not determine current image IDs, skipping cleanup: %v\n", err)
		return nil, err
	}

	return listNonCurrentImages(ctx, errOut, info, currentIDs)
}

// listNonCurrentImages lists all SynthOrg images that are not in the
// currentIDs set. Used by both findOldImages (which resolves current IDs
// from state) and the cleanup command.
func listNonCurrentImages(ctx context.Context, errOut io.Writer, info docker.Info, currentIDs map[string]bool) ([]oldImage, error) {
	imageRef := "ghcr.io/aureliolo/synthorg-*"
	// Include size in bytes for threshold calculations and digest for display.
	allOut, listErr := docker.RunCmd(ctx, info.DockerPath, "images",
		"--filter", "reference="+imageRef,
		"--format", "{{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.ID}}\t{{.Digest}}")
	if listErr != nil {
		_, _ = fmt.Fprintf(errOut, "Note: could not list images for cleanup: %v\n", listErr)
		return nil, listErr
	}

	var old []oldImage
	seen := make(map[string]bool)
	for _, line := range strings.Split(strings.TrimSpace(strings.ReplaceAll(allOut, "\r\n", "\n")), "\n") {
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "\t", 5)
		if len(parts) < 5 {
			continue
		}
		repo, tag, sizeStr, id, digest := parts[0], parts[1], parts[2], parts[3], parts[4]
		if !isValidDockerID(id) || currentIDs[id] || seen[id] {
			continue
		}
		seen[id] = true

		// Build a human-readable display string.
		display := buildImageDisplay(repo, tag, digest, sizeStr)
		sizeB := parseDockerSize(sizeStr)
		old = append(old, oldImage{display: display, id: id, sizeB: sizeB})
	}
	return old, nil
}

// buildImageDisplay creates a readable display string for an image.
// Prefers tag, falls back to digest short form, then Docker ID.
func buildImageDisplay(repo, tag, digest, size string) string {
	// Strip the registry prefix for brevity.
	short := strings.TrimPrefix(repo, "ghcr.io/aureliolo/")

	label := short
	if tag != "" && tag != "<none>" {
		label += ":" + tag
	} else if digest != "" && digest != "<none>" {
		// Show first 16 chars of the digest hash for identification.
		d := strings.TrimPrefix(digest, "sha256:")
		if len(d) > 16 {
			d = d[:16]
		}
		label += "@" + d
	}

	return fmt.Sprintf("%-40s %s", label, size)
}

// collectCurrentImageIDs resolves Docker image IDs for the services at the
// current version. Uses docker image inspect which works with both
// digest-pinned (@sha256:...) and tag-based (:tag) references.
// Returns an error if any service ID cannot be resolved (to avoid
// accidentally deleting current images).
func collectCurrentImageIDs(ctx context.Context, info docker.Info, state config.State) (map[string]bool, error) {
	services := []string{"backend", "web"}
	if state.Sandbox {
		services = append(services, "sandbox")
	}

	currentIDs := make(map[string]bool, len(services))
	for _, svc := range services {
		ref := imageRefForService(svc, state)
		idOut, err := docker.RunCmd(ctx, info.DockerPath, "image", "inspect", ref, "--format", "{{.ID}}")
		if err != nil {
			return nil, fmt.Errorf("resolving image ID for %s: %w", svc, err)
		}
		id := strings.TrimSpace(idOut)
		if id == "" {
			return nil, fmt.Errorf("no image ID found for %s (image may not be pulled)", svc)
		}
		currentIDs[id] = true
	}
	return currentIDs, nil
}

// parseDockerSize converts Docker's human-readable size strings (e.g.
// "646MB", "85.8MB", "1.2GB") to bytes. Returns 0 if unparseable.
func parseDockerSize(s string) float64 {
	s = strings.TrimSpace(s)
	s = strings.ReplaceAll(s, ",", "") // some locales use comma separators

	multipliers := []struct {
		suffix string
		mult   float64
	}{
		{"TB", 1e12},
		{"GB", 1e9},
		{"MB", 1e6},
		{"kB", 1e3},
		{"B", 1},
	}

	for _, m := range multipliers {
		if strings.HasSuffix(s, m.suffix) {
			numStr := strings.TrimSuffix(s, m.suffix)
			if v, err := strconv.ParseFloat(strings.TrimSpace(numStr), 64); err == nil {
				return v * m.mult
			}
			return 0
		}
	}
	return 0
}

// formatBytes formats a byte count as a human-readable string (e.g. "1.2 GB").
func formatBytes(b float64) string {
	switch {
	case b >= 1e12:
		return fmt.Sprintf("%.1f TB", b/1e12)
	case b >= 1e9:
		return fmt.Sprintf("%.1f GB", b/1e9)
	case b >= 1e6:
		return fmt.Sprintf("%.1f MB", b/1e6)
	case b >= 1e3:
		return fmt.Sprintf("%.1f kB", b/1e3)
	default:
		return fmt.Sprintf("%.0f B", b)
	}
}

// isValidDockerID checks that id looks like a Docker short ID (12 hex chars).
// Docker's --format {{.ID}} returns short IDs only; long digests are not
// produced by this format template.
func isValidDockerID(id string) bool {
	return len(id) == 12 && isAllHex(id)
}

// isAllHex reports whether every byte in s is a hexadecimal digit (0-9, a-f, A-F).
func isAllHex(s string) bool {
	for i := range len(s) {
		c := s[i]
		if (c < '0' || c > '9') && (c < 'a' || c > 'f') && (c < 'A' || c > 'F') {
			return false
		}
	}
	return true
}
