package cmd

import (
	"context"
	"fmt"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"
)

var cleanupCmd = &cobra.Command{
	Use:   "cleanup",
	Short: "Remove old container images to free disk space",
	Long: `Remove old SynthOrg container images that are no longer needed.

After updates, previous image versions remain on disk. This command
identifies images that don't match the current version and offers to
remove them individually.`,
	RunE: runCleanup,
}

func init() {
	rootCmd.AddCommand(cleanupCmd)
}

func runCleanup(cmd *cobra.Command, _ []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	out := ui.NewUI(cmd.OutOrStdout())

	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}

	old, err := findOldImages(ctx, cmd.ErrOrStderr(), info, state)
	if err != nil {
		return fmt.Errorf("finding old images: %w", err)
	}
	if len(old) == 0 {
		out.Success("No old images found -- nothing to clean up")
		return nil
	}

	displayOldImages(out, old)

	removedAny, err := confirmAndCleanup(ctx, cmd, info, out, old)
	if err != nil {
		return err
	}

	// Hint about auto-cleanup when images were removed and flag is not enabled.
	if removedAny && !state.AutoCleanup {
		out.Blank()
		out.Hint("Tip: run 'synthorg config set auto_cleanup true' to clean up old images automatically after updates.")
	}
	return nil
}

// displayOldImages renders the image list with total size.
func displayOldImages(out *ui.UI, old []oldImage) {
	var totalB float64
	lines := make([]string, 0, len(old))
	for _, img := range old {
		lines = append(lines, img.display)
		totalB += img.sizeB
	}
	out.Box("Old Images", lines)
	out.Blank()

	if totalB > 0 {
		out.KeyValue("Total", formatBytes(totalB))
		out.Blank()
	}
}

// confirmAndCleanup prompts the user and removes approved images.
// Returns (true, nil) when at least one image was removed.
func confirmAndCleanup(ctx context.Context, cmd *cobra.Command, info docker.Info, out *ui.UI, old []oldImage) (bool, error) {
	if !isInteractive() {
		out.Hint("Non-interactive mode: run interactively to remove, or use 'docker rmi <id>'.")
		return false, nil
	}

	var remove bool
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title(fmt.Sprintf("Remove %d old image(s)?", len(old))).
			Value(&remove),
	))
	if err := form.WithInput(cmd.InOrStdin()).WithOutput(cmd.OutOrStdout()).Run(); err != nil {
		return false, err
	}
	if !remove {
		return false, nil
	}

	// Remove images one at a time without --force (gentle cleanup -- only
	// removes untagged/unused images; tagged images need 'synthorg uninstall').
	var freedB float64
	var removed int
	for _, img := range old {
		if ctx.Err() != nil {
			return removed > 0, ctx.Err()
		}
		_, rmiErr := docker.RunCmd(ctx, info.DockerPath, "rmi", img.id)
		if rmiErr != nil {
			if isImageInUse(rmiErr) {
				out.Warn(fmt.Sprintf("%-12s skipped (in use)", img.id))
			} else {
				out.Error(fmt.Sprintf("%-12s failed: %v", img.id, rmiErr))
			}
		} else {
			out.Success(fmt.Sprintf("%-12s removed", img.id))
			removed++
			freedB += img.sizeB
		}
	}

	out.Blank()
	if removed > 0 && freedB > 0 {
		out.Success(fmt.Sprintf("Freed %s (%d image(s) removed)", formatBytes(freedB), removed))
	} else if removed > 0 {
		out.Success(fmt.Sprintf("Removed %d image(s)", removed))
	}
	if skipped := len(old) - removed; skipped > 0 {
		out.Hint(fmt.Sprintf("%d image(s) skipped (stop containers first to remove)", skipped))
	}

	return removed > 0, nil
}

// isImageInUse checks if a docker rmi error indicates the image is in use
// or has dependents, rather than a real failure (permissions, network, etc.).
func isImageInUse(err error) bool {
	msg := err.Error()
	return strings.Contains(msg, "image is being used") ||
		strings.Contains(msg, "conflict") ||
		strings.Contains(msg, "dependent child images") ||
		strings.Contains(msg, "image is referenced")
}
