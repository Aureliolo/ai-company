package cmd

import (
	"context"
	"fmt"
	"strings"

	"charm.land/huh/v2"
	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

var (
	cleanupDryRun bool
	cleanupAll    bool
	cleanupKeep   int
)

var cleanupCmd = &cobra.Command{
	Use:   "cleanup",
	Short: "Remove old container images to free disk space",
	Long: `Remove old SynthOrg container images that are no longer needed.

After updates, previous image versions remain on disk. This command
identifies images that don't match the current version and offers to
remove them individually.`,
	Example: `  synthorg cleanup              # interactive cleanup of old images
  synthorg cleanup --dry-run    # list images without removing
  synthorg cleanup --all --yes  # remove ALL SynthOrg images non-interactively
  synthorg cleanup --keep 2     # keep 2 most recent previous versions`,
	RunE: runCleanup,
}

func init() {
	cleanupCmd.Flags().BoolVar(&cleanupDryRun, "dry-run", false, "list images without removing")
	cleanupCmd.Flags().BoolVar(&cleanupAll, "all", false, "include ALL SynthOrg images, not just old ones")
	cleanupCmd.Flags().IntVar(&cleanupKeep, "keep", 0, "keep N most recent previous versions (0=remove all)")
	cleanupCmd.GroupID = "lifecycle"
	rootCmd.AddCommand(cleanupCmd)
}

func validateCleanupFlags() error {
	if cleanupKeep < 0 {
		return fmt.Errorf("invalid --keep %d: must be >= 0", cleanupKeep)
	}
	return nil
}

func runCleanup(cmd *cobra.Command, _ []string) error {
	if err := validateCleanupFlags(); err != nil {
		return err
	}

	ctx := cmd.Context()
	opts := GetGlobalOpts(ctx)

	state, err := config.Load(opts.DataDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())
	errOut := ui.NewUIWithOptions(cmd.ErrOrStderr(), opts.UIOptions())

	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}

	var old []oldImage
	if cleanupAll {
		// --all: include ALL SynthOrg images (same as uninstall).
		old, err = listNonCurrentImages(ctx, errOut.Writer(), info, nil)
	} else {
		old, err = findOldImages(ctx, cmd.ErrOrStderr(), info, state)
	}
	if err != nil {
		return fmt.Errorf("finding images: %w", err)
	}
	if len(old) == 0 {
		out.Success("No images found -- nothing to clean up")
		if !state.AutoCleanup {
			out.HintTip("Run 'synthorg config set auto_cleanup true' to clean up automatically after updates.")
		}
		return nil
	}

	// --keep: preserve N most recent (remove from the end of the list,
	// Docker returns images in most-recent-first order).
	if cleanupKeep > 0 && len(old) > cleanupKeep {
		old = old[cleanupKeep:]
	} else if cleanupKeep > 0 {
		out.Success(fmt.Sprintf("Only %d image(s) found, keeping all (--keep %d)", len(old), cleanupKeep))
		return nil
	}

	displayOldImages(out, old)

	if cleanupAll {
		out.HintGuidance("--all includes current images. Running containers will prevent removal.")
	}

	if cleanupDryRun {
		out.HintNextStep(fmt.Sprintf("Dry run: %d image(s) would be removed", len(old)))
		return nil
	}

	removedAny, err := confirmAndCleanup(ctx, cmd, info, out, old)
	if err != nil {
		return err
	}

	// Hint about auto-cleanup when images were removed and flag is not enabled.
	if removedAny && !state.AutoCleanup {
		out.Blank()
		out.HintTip("Tip: run 'synthorg config set auto_cleanup true' to clean up old images automatically after updates.")
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
	opts := GetGlobalOpts(ctx)
	if !opts.ShouldPrompt() && !opts.Yes {
		out.HintNextStep("Non-interactive mode: run interactively or use --yes to remove, or use 'docker rmi <id>'.")
		return false, nil
	}

	// --yes auto-confirms; otherwise prompt interactively.
	remove := opts.Yes
	if !remove {
		form := huh.NewForm(huh.NewGroup(
			huh.NewConfirm().
				Title(fmt.Sprintf("Remove %d old image(s)?", len(old))).
				Value(&remove),
		))
		if err := form.WithInput(cmd.InOrStdin()).WithOutput(cmd.OutOrStdout()).Run(); err != nil {
			return false, err
		}
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
		out.HintError(fmt.Sprintf("%d image(s) skipped (stop containers first to remove)", skipped))
	}
	if removed > 0 {
		out.HintGuidance("Use --keep N to preserve N recent previous versions.")
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
