package cmd

import (
	"context"
	"fmt"
	"io"
	"math"
	"strconv"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/images"
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
// update command prints a cleanup hint (5 GB decimal, matching Docker's
// output format which uses decimal units via parseDockerSize).
const hintThresholdBytes = 5e9

// autoCleanupOldImages removes old SynthOrg images after a successful update,
// keeping only the current (just pulled) and previous (what was running before)
// image sets. This is best-effort: failures are logged as warnings but do not
// fail the update command. Called only when state.AutoCleanup is true.
func autoCleanupOldImages(cmd *cobra.Command, info docker.Info, state config.State, previousIDs map[string]bool) {
	ctx := cmd.Context()
	out := ui.NewUI(cmd.OutOrStdout())
	errOut := cmd.ErrOrStderr()

	// Build the keep set: current IDs (just pulled) + previous IDs.
	currentIDs, err := collectCurrentImageIDs(ctx, info, state)
	if err != nil {
		_, _ = fmt.Fprintf(errOut, "Warning: could not determine current image IDs, skipping auto-cleanup: %v\n", err)
		return
	}

	keepIDs := mergeKeepIDs(currentIDs, previousIDs)

	// Find images not in the keep set.
	old, err := listNonCurrentImages(ctx, errOut, info, keepIDs)
	if err != nil {
		_, _ = fmt.Fprintf(errOut, "Warning: could not list images for auto-cleanup: %v\n", err)
		return
	}
	if len(old) == 0 {
		return
	}

	out.Blank()
	out.Step(fmt.Sprintf("Auto-cleaning %d old image(s)...", len(old)))

	var freedB float64
	var removed int
	for _, img := range old {
		if ctx.Err() != nil {
			_, _ = fmt.Fprintf(errOut, "Warning: auto-cleanup interrupted\n")
			break
		}
		_, rmiErr := docker.RunCmd(ctx, info.DockerPath, "rmi", img.id)
		if rmiErr != nil {
			if isImageInUse(rmiErr) {
				out.Warn(fmt.Sprintf("%-12s skipped (in use)", img.id))
			} else {
				out.Warn(fmt.Sprintf("%-12s skipped: %v", img.id, rmiErr))
			}
		} else {
			out.Success(fmt.Sprintf("%-12s removed", img.id))
			removed++
			freedB += img.sizeB
		}
	}

	if removed > 0 && freedB > 0 {
		out.Success(fmt.Sprintf("Freed %s (%d image(s) removed)", formatBytes(freedB), removed))
	} else if removed > 0 {
		out.Success(fmt.Sprintf("Removed %d image(s)", removed))
	}
}

// mergeKeepIDs combines current and previous image ID sets into a single
// keep set for auto-cleanup.
func mergeKeepIDs(current, previous map[string]bool) map[string]bool {
	keep := make(map[string]bool, len(current)+len(previous))
	for id := range current {
		keep[id] = true
	}
	for id := range previous {
		keep[id] = true
	}
	return keep
}

// hintOldImages prints a passive hint about old images after a successful
// update, but only when the total old image size exceeds hintThresholdBytes.
// Replaces the former interactive cleanup prompt.
func hintOldImages(cmd *cobra.Command, info docker.Info, state config.State) {
	out := ui.NewUI(cmd.OutOrStdout())
	old, err := findOldImages(cmd.Context(), cmd.ErrOrStderr(), info, state)
	if err != nil || len(old) == 0 {
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
// from state) and the uninstall command (with nil currentIDs to list all).
func listNonCurrentImages(ctx context.Context, errOut io.Writer, info docker.Info, currentIDs map[string]bool) ([]oldImage, error) {
	all, listErr := images.ListLocal(ctx, info.DockerPath)
	if listErr != nil {
		_, _ = fmt.Fprintf(errOut, "Note: could not list images for cleanup: %v\n", listErr)
		return nil, listErr
	}

	var old []oldImage
	seen := make(map[string]bool)
	for _, img := range all {
		id := img.ID
		// currentIDs may be nil (when listing all images); reading a nil map
		// returns the zero value (false), which is the intended behavior.
		if !isValidDockerID(id) || currentIDs[id] || seen[id] {
			continue
		}
		seen[id] = true

		display := buildImageDisplay(img.Repository, img.Tag, img.Digest, img.Size, id)
		sizeB := parseDockerSize(img.Size)
		old = append(old, oldImage{display: display, id: id, sizeB: sizeB})
	}
	return old, nil
}

// buildImageDisplay creates a readable display string for an image.
// Prefers tag, falls back to digest short form, then Docker short ID.
func buildImageDisplay(repo, tag, digest, size, id string) string {
	// Strip the full image prefix and re-add "synthorg-" for readable display
	// (e.g. "synthorg-backend:0.4.6" instead of the full GHCR path).
	short := "synthorg-" + strings.TrimPrefix(repo, images.RepoPrefix)

	label := short
	switch {
	case tag != "" && tag != "<none>":
		label += ":" + tag
	case digest != "" && digest != "<none>":
		// Show first 16 chars of the digest hash for identification.
		d := strings.TrimPrefix(digest, "sha256:")
		if len(d) > 16 {
			d = d[:16]
		}
		label += "@" + d
	case id != "":
		// No tag or digest -- use Docker short ID for disambiguation.
		label += " (" + id + ")"
	}

	return fmt.Sprintf("%-40s %s", label, size)
}

// collectCurrentImageIDs resolves Docker image IDs for the services at the
// current version. Uses docker image inspect which works with both
// digest-pinned (@sha256:...) and tag-based (:tag) references.
// Returns an error if any service ID cannot be resolved (to avoid
// accidentally deleting current images).
func collectCurrentImageIDs(ctx context.Context, info docker.Info, state config.State) (map[string]bool, error) {
	services := images.ServiceNames(state.Sandbox)

	currentIDs := make(map[string]bool, len(services))
	for _, svc := range services {
		ref := images.RefForService(svc, state.ImageTag, state.VerifiedDigests)
		id, err := images.InspectID(ctx, info.DockerPath, ref)
		if err != nil {
			return nil, fmt.Errorf("resolving image ID for %s: %w", svc, err)
		}
		if id == "" {
			return nil, fmt.Errorf("no image ID found for %s (image may not be pulled)", svc)
		}
		// Store both the full ID (sha256:...) and the short 12-char ID.
		// docker images --format {{.ID}} returns short IDs, while
		// docker image inspect returns full IDs with sha256: prefix.
		currentIDs[id] = true
		short := strings.TrimPrefix(id, "sha256:")
		if len(short) >= 12 {
			currentIDs[short[:12]] = true
		}
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
		{"KB", 1e3},
		{"B", 1},
	}

	for _, m := range multipliers {
		if strings.HasSuffix(s, m.suffix) {
			numStr := strings.TrimSuffix(s, m.suffix)
			if v, err := strconv.ParseFloat(strings.TrimSpace(numStr), 64); err == nil {
				if math.IsNaN(v) || math.IsInf(v, 0) {
					return 0
				}
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
