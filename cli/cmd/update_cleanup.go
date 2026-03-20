package cmd

import (
	"context"
	"fmt"
	"io"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"
)

// oldImage holds display info and Docker ID for a non-current SynthOrg image.
type oldImage struct {
	display string
	id      string
}

// cleanupOldImages offers to remove non-current SynthOrg images after a
// successful upgrade. Identifies current images by their Docker image ID
// (handles both tagged and digest-pinned references).
func cleanupOldImages(cmd *cobra.Command, info docker.Info, state config.State) error {
	old, _ := findOldImages(cmd.Context(), cmd.ErrOrStderr(), info, state)
	if len(old) == 0 {
		return nil
	}

	out := cmd.OutOrStdout()
	_, _ = fmt.Fprintln(out, "\nOld SynthOrg images found locally:")
	for _, img := range old {
		_, _ = fmt.Fprintf(out, "  %s\n", img.display)
	}

	return promptAndRemoveImages(cmd, info, old)
}

// findOldImages lists SynthOrg images that don't match the current version.
// Returns nil if current image IDs cannot be reliably determined.
func findOldImages(ctx context.Context, errOut io.Writer, info docker.Info, state config.State) ([]oldImage, error) {
	currentIDs, err := collectCurrentImageIDs(ctx, info, state)
	if err != nil {
		_, _ = fmt.Fprintf(errOut, "Note: could not determine current image IDs, skipping cleanup: %v\n", err)
		return nil, err
	}

	imageRef := "ghcr.io/aureliolo/synthorg-*"
	allOut, listErr := docker.RunCmd(ctx, info.DockerPath, "images",
		"--filter", "reference="+imageRef,
		"--format", "{{.Repository}}:{{.Tag}} ({{.Size}})\t{{.ID}}")
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
		parts := strings.SplitN(line, "\t", 2)
		if len(parts) < 2 {
			continue
		}
		display, id := parts[0], parts[1]
		if !isValidDockerID(id) || currentIDs[id] || seen[id] {
			continue
		}
		seen[id] = true
		old = append(old, oldImage{display: display, id: id})
	}
	return old, nil
}

// collectCurrentImageIDs resolves Docker image IDs for the services at the
// current version. Returns an error if any service ID cannot be resolved
// (to avoid accidentally deleting current images).
func collectCurrentImageIDs(ctx context.Context, info docker.Info, state config.State) (map[string]bool, error) {
	services := []string{"backend", "web"}
	if state.Sandbox {
		services = append(services, "sandbox")
	}

	currentIDs := make(map[string]bool, len(services))
	for _, svc := range services {
		ref := fmt.Sprintf("ghcr.io/aureliolo/synthorg-%s:%s", svc, state.ImageTag)
		idOut, err := docker.RunCmd(ctx, info.DockerPath, "images",
			"--filter", "reference="+ref,
			"--format", "{{.ID}}")
		if err != nil {
			return nil, fmt.Errorf("resolving image ID for %s: %w", svc, err)
		}
		ids := strings.Fields(strings.TrimSpace(idOut))
		if len(ids) == 0 {
			return nil, fmt.Errorf("no image ID found for %s (image may not be pulled)", svc)
		}
		for _, id := range ids {
			currentIDs[id] = true
		}
	}
	return currentIDs, nil
}

// promptAndRemoveImages asks the user and removes old images.
func promptAndRemoveImages(cmd *cobra.Command, info docker.Info, old []oldImage) error {
	if !isInteractive() {
		_, _ = fmt.Fprintln(cmd.OutOrStdout(), "Non-interactive mode: skipping image cleanup. Remove manually with 'docker rmi'.")
		return nil
	}

	var remove bool
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title(fmt.Sprintf("Remove %d old image(s)?", len(old))).
			Value(&remove),
	))
	if err := form.Run(); err != nil {
		return err
	}
	if !remove {
		return nil
	}

	ids := make([]string, 0, len(old))
	for _, img := range old {
		ids = append(ids, img.id)
	}
	rmiArgs := make([]string, 0, 1+len(ids))
	rmiArgs = append(rmiArgs, "rmi")
	rmiArgs = append(rmiArgs, ids...)
	if _, rmiErr := docker.RunCmd(cmd.Context(), info.DockerPath, rmiArgs...); rmiErr != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: some images could not be removed: %v\n", rmiErr)
	} else {
		_, _ = fmt.Fprintf(cmd.OutOrStdout(), "Removed %d old image(s).\n", len(old))
	}
	return nil
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
