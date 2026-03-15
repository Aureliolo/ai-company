package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/compose"
	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/health"
	"github.com/Aureliolo/synthorg/cli/internal/selfupdate"
	"github.com/Aureliolo/synthorg/cli/internal/version"
	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"
)

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update CLI binary and pull new container images",
	RunE:  runUpdate,
}

func init() {
	rootCmd.AddCommand(updateCmd)
}

func runUpdate(cmd *cobra.Command, _ []string) error {
	effectiveVersion, err := updateCLI(cmd)
	if err != nil {
		return err
	}
	return updateContainerImages(cmd, effectiveVersion)
}

// updateCLI checks for a new CLI release and optionally applies it.
// Returns the effective CLI version (the new version if updated, or the
// current version if not).
func updateCLI(cmd *cobra.Command) (string, error) {
	ctx := cmd.Context()
	out := cmd.OutOrStdout()

	// Warn on dev builds.
	if version.Version == "dev" {
		_, _ = fmt.Fprintln(out, "Warning: running a dev build — update check will always report an update available.")
	}

	_, _ = fmt.Fprintln(out, "Checking for updates...")
	result, err := selfupdate.Check(ctx)
	if err != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: could not check for updates: %v\n", err)
		return version.Version, nil
	}

	if !result.UpdateAvail {
		_, _ = fmt.Fprintf(out, "CLI is up to date (%s)\n", result.CurrentVersion)
		return version.Version, nil
	}

	_, _ = fmt.Fprintf(out, "New version available: %s (current: %s)\n", result.LatestVersion, result.CurrentVersion)

	if isInteractive() {
		proceed := true // default yes
		form := huh.NewForm(huh.NewGroup(
			huh.NewConfirm().
				Title(fmt.Sprintf("Update CLI from %s to %s?", result.CurrentVersion, result.LatestVersion)).
				Value(&proceed),
		))
		if err := form.Run(); err != nil {
			return "", err
		}
		if !proceed {
			return version.Version, nil
		}
	} else {
		_, _ = fmt.Fprintf(out, "Non-interactive mode: auto-applying update to %s\n", result.LatestVersion)
	}

	_, _ = fmt.Fprintln(out, "Downloading...")
	binary, err := selfupdate.Download(ctx, result.AssetURL, result.ChecksumURL, result.SigstoreBundURL)
	if err != nil {
		return "", fmt.Errorf("downloading update: %w", err)
	}

	if err := selfupdate.Replace(binary); err != nil {
		return "", fmt.Errorf("replacing binary: %w", err)
	}
	_, _ = fmt.Fprintf(out, "CLI updated to %s\n", result.LatestVersion)
	return result.LatestVersion, nil
}

// targetImageTag converts a CLI version string to a Docker image tag.
// Strips the "v" prefix and maps dev/empty to "latest".
func targetImageTag(ver string) string {
	tag := strings.TrimPrefix(ver, "v")
	if tag == "" || tag == "dev" {
		return "latest"
	}
	return tag
}

// updateContainerImages offers to update container images to match the
// given CLI version. Skips if images already match.
func updateContainerImages(cmd *cobra.Command, effectiveVersion string) error {
	ctx := cmd.Context()
	out := cmd.OutOrStdout()

	tag := targetImageTag(effectiveVersion)

	dir := resolveDataDir()
	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}

	// Check if container images already match the target version.
	if state.ImageTag == tag {
		_, _ = fmt.Fprintf(out, "Container images already at %s\n", tag)
		return nil
	}

	info, err := docker.Detect(ctx)
	if err != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: Docker not available, skipping image update: %v\n", err)
		return nil
	}

	// Ask before pulling.
	if isInteractive() {
		proceed := true // default yes
		form := huh.NewForm(huh.NewGroup(
			huh.NewConfirm().
				Title(fmt.Sprintf("Update container images from %s to %s?", state.ImageTag, tag)).
				Value(&proceed),
		))
		if err := form.Run(); err != nil {
			return err
		}
		if !proceed {
			return nil
		}
	} else {
		_, _ = fmt.Fprintf(out, "Non-interactive mode: updating container images to %s\n", tag)
	}

	// Update config and regenerate compose file before pulling.
	state.ImageTag = tag
	params := compose.ParamsFromState(state)
	composeYAML, err := compose.Generate(params)
	if err != nil {
		return fmt.Errorf("generating compose file: %w", err)
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if err := os.WriteFile(composePath, composeYAML, 0o600); err != nil {
		return fmt.Errorf("writing compose file: %w", err)
	}
	if err := config.Save(state); err != nil {
		return fmt.Errorf("saving config: %w", err)
	}

	_, _ = fmt.Fprintf(out, "Pulling container images (%s)...\n", tag)
	if err := composeRun(ctx, cmd, info, safeDir, "pull"); err != nil {
		return fmt.Errorf("pulling images: %w", err)
	}

	// Check if containers are running and offer restart.
	psOut, err := docker.ComposeExecOutput(ctx, info, safeDir, "ps", "-q")
	if err != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: could not check container status: %v\n", err)
		return nil
	}

	if psOut == "" {
		return nil
	}

	if !isInteractive() {
		_, _ = fmt.Fprintln(out, "Non-interactive mode: skipping restart. Run 'synthorg stop && synthorg start' to apply new images.")
		return nil
	}

	restart, err := confirmRestart()
	if err != nil {
		return err
	}
	if !restart {
		return nil
	}

	_, _ = fmt.Fprintln(out, "Restarting...")
	if err := composeRun(ctx, cmd, info, safeDir, "down"); err != nil {
		return fmt.Errorf("stopping containers: %w", err)
	}
	if err := composeRun(ctx, cmd, info, safeDir, "up", "-d"); err != nil {
		return fmt.Errorf("restarting containers: %w", err)
	}

	// Health check after restart.
	_, _ = fmt.Fprintln(out, "Waiting for backend to become healthy...")
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort)
	if err := health.WaitForHealthy(ctx, healthURL, 90*time.Second, 2*time.Second, 5*time.Second); err != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: health check did not pass after restart: %v\n", err)
	} else {
		_, _ = fmt.Fprintln(out, "Containers restarted with new images and healthy.")
	}

	return nil
}

func confirmRestart() (bool, error) {
	restart := true // default yes
	form := huh.NewForm(
		huh.NewGroup(
			huh.NewConfirm().
				Title("Containers are running. Restart with new images?").
				Value(&restart),
		),
	)
	if err := form.Run(); err != nil {
		return false, err
	}
	return restart, nil
}
