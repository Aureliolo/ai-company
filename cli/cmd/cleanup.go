package cmd

import (
	"fmt"

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

	// Find old images by comparing Docker IDs against current service images.
	old, err := findOldImages(ctx, cmd.ErrOrStderr(), info, state)
	if err != nil {
		return fmt.Errorf("finding old images: %w", err)
	}

	if len(old) == 0 {
		out.Success("No old images found -- nothing to clean up.")
		return nil
	}

	// Show old images with details.
	var totalB float64
	var lines []string
	for _, img := range old {
		lines = append(lines, img.display)
		totalB += img.sizeB
	}
	out.Box("Old Images", lines)
	out.Blank()

	totalLabel := formatBytes(totalB)
	if totalB > 0 {
		out.KeyValue("Total", totalLabel)
		out.Blank()
	}

	// Confirm removal.
	if !isInteractive() {
		out.Hint("Non-interactive mode: run interactively to remove, or use 'docker rmi <id>'.")
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

	// Remove images one at a time for granular feedback.
	var freedB float64
	var removed int
	for _, img := range old {
		_, rmiErr := docker.RunCmd(ctx, info.DockerPath, "rmi", img.id)
		if rmiErr != nil {
			out.Warn(fmt.Sprintf("%-12s skipped (in use)", img.id))
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

	return nil
}
