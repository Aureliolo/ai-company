package cmd

import (
	"context"
	"fmt"
	"path/filepath"
	"strings"
	"time"

	"charm.land/huh/v2"
	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/images"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

// checkInstallationHealth detects inconsistent state between config and the
// actual Docker/filesystem state (e.g. after a partial uninstall). Returns
// (abort, recovered, error): abort=true if the user declined recovery,
// recovered=true if recovery was chosen (caller should force refresh).
func checkInstallationHealth(cmd *cobra.Command, state config.State) (bool, bool, error) {
	issues := detectInstallationIssues(cmd.Context(), state)
	if len(issues) == 0 {
		return false, false, nil
	}

	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())
	out.Warn("Installation appears incomplete:")
	for _, issue := range issues {
		_, _ = fmt.Fprintf(cmd.OutOrStdout(), "  - %s\n", issue)
	}

	abort, err := promptHealthRecover(cmd)
	if err != nil {
		return false, false, err
	}
	if abort {
		return true, false, nil
	}
	return false, true, nil
}

// detectInstallationIssues checks config, secrets, compose, and Docker
// images for inconsistencies. Returns a list of human-readable issues.
func detectInstallationIssues(ctx context.Context, state config.State) []string {
	var issues []string

	if !fileExists(config.StatePath(state.DataDir)) {
		issues = append(issues, "config.json is missing (no previous init)")
	}
	if state.JWTSecret == "" {
		issues = append(issues, "JWT secret is not configured")
	}
	if state.SettingsKey == "" {
		issues = append(issues, "settings encryption key is not configured")
	}

	safeDir, err := safeStateDir(state)
	if err != nil {
		issues = append(issues, fmt.Sprintf("data directory path issue: %v", err))
	} else if !fileExists(filepath.Join(safeDir, "compose.yml")) {
		issues = append(issues, "compose.yml is missing")
	}

	if state.ImageTag != "" {
		// Use a shorter timeout for health check Docker calls to avoid
		// blocking the update flow if Docker is unresponsive.
		healthCtx, cancel := context.WithTimeout(ctx, 15*time.Second)
		defer cancel()

		// Docker unavailability is handled gracefully by updateContainerImages
		// (warns and skips). Only check images when Docker is reachable.
		info, dockerErr := docker.Detect(healthCtx)
		if dockerErr == nil {
			if missing := detectMissingImages(healthCtx, info, state); len(missing) > 0 {
				issues = append(issues, fmt.Sprintf("container images missing locally for version %s: %s",
					state.ImageTag, strings.Join(missing, ", ")))
			}
		}
	}

	return issues
}

// promptHealthRecover asks the user whether to recover or run init.
// Returns (true, nil) if the user chose to abort.
func promptHealthRecover(cmd *cobra.Command) (bool, error) {
	opts := GetGlobalOpts(cmd.Context())
	if !opts.ShouldPrompt() {
		if opts.Yes {
			return false, nil // --yes: auto-recover (default is yes)
		}
		_, _ = fmt.Fprintln(cmd.OutOrStdout(),
			"\nNon-interactive mode: run 'synthorg init' to restore a clean installation.")
		return true, nil
	}

	var doRecover bool
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Recover by pulling images and regenerating compose?").
			Description("Choose 'No' to run 'synthorg init' for a fresh setup instead.").
			Value(&doRecover),
	))
	if err := form.Run(); err != nil {
		return false, err
	}
	if !doRecover {
		_, _ = fmt.Fprintln(cmd.OutOrStdout(), "Run 'synthorg init' to restore a clean installation.")
		return true, nil
	}
	return false, nil
}

// detectMissingImages checks which SynthOrg service images are missing locally
// for the given state. Uses docker image inspect which works with both
// digest-pinned (@sha256:...) and tag-based (:tag) references.
//
// Precondition: caller must have verified Docker is reachable (e.g. via
// docker.Detect). Only inspect errors that occur while the context is still
// valid are treated as missing images; context cancellation or timeout errors
// are ignored to avoid false positives.
func detectMissingImages(ctx context.Context, info docker.Info, state config.State) []string {
	var missing []string
	for _, svc := range images.ServiceNames(state.Sandbox) {
		ref := images.RefForService(svc, state.ImageTag, state.VerifiedDigests)
		_, err := images.InspectID(ctx, info.DockerPath, ref)
		if err != nil {
			if ctx.Err() != nil {
				// Context expired or cancelled -- can't reliably determine
				// image state, so don't report as missing.
				return missing
			}
			missing = append(missing, svc)
		}
	}
	return missing
}
