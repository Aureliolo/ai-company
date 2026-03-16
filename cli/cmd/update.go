package cmd

import (
	"context"
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

	ok, err := confirmUpdate(fmt.Sprintf("Update CLI from %s to %s?", result.CurrentVersion, result.LatestVersion))
	if err != nil {
		return "", err
	}
	if !ok {
		return version.Version, nil
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
// Strips the "v" prefix and maps dev/empty/invalid to "latest".
// Validates the tag at the trust boundary (version may come from the
// GitHub Releases API); compose.Generate also validates downstream.
func targetImageTag(ver string) string {
	tag := strings.TrimPrefix(ver, "v")
	if tag == "" || tag == "dev" {
		return "latest"
	}
	if !isValidImageTag(tag) {
		return "latest"
	}
	return tag
}

// isValidImageTag checks that tag matches [a-zA-Z0-9][a-zA-Z0-9._-]*.
func isValidImageTag(tag string) bool {
	if len(tag) == 0 {
		return false
	}
	first := tag[0]
	if !isAlphaNum(first) {
		return false
	}
	for i := 1; i < len(tag); i++ {
		c := tag[i]
		if !isAlphaNum(c) && c != '.' && c != '_' && c != '-' {
			return false
		}
	}
	return true
}

func isAlphaNum(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
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

	ok, err := confirmUpdate(fmt.Sprintf("Update container images from %s to %s?", state.ImageTag, tag))
	if err != nil {
		return err
	}
	if !ok {
		return nil
	}

	if err := pullAndPersist(ctx, cmd, info, state, tag, safeDir, effectiveVersion); err != nil {
		return err
	}

	updatedState := state
	updatedState.ImageTag = tag
	return restartIfRunning(cmd, info, safeDir, updatedState)
}

// confirmUpdate prompts the user to confirm an update action.
// Returns (true, nil) if non-interactive (auto-accept) or user confirms.
func confirmUpdate(title string) (bool, error) {
	if !isInteractive() {
		return true, nil
	}
	proceed := true // default yes
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().Title(title).Value(&proceed),
	))
	if err := form.Run(); err != nil {
		return false, err
	}
	return proceed, nil
}

// pullAndPersist regenerates compose.yml, pulls images, and persists config.
// If any step fails, the previous compose.yml is restored (or removed if it
// did not exist before) so that the on-disk state remains consistent.
func pullAndPersist(ctx context.Context, cmd *cobra.Command, info docker.Info, state config.State, tag, safeDir, effectiveVersion string) error {
	out := cmd.OutOrStdout()

	// Back up existing compose.yml for rollback on failure.
	composePath := filepath.Join(safeDir, "compose.yml")
	backup, backupErr := os.ReadFile(composePath)
	backupExists := backupErr == nil

	rollback := func() {
		if backupExists {
			_ = os.WriteFile(composePath, backup, 0o600)
		} else {
			_ = os.Remove(composePath)
		}
	}

	if err := regenerateCompose(state, tag, safeDir, effectiveVersion); err != nil {
		rollback()
		return err
	}

	_, _ = fmt.Fprintf(out, "Pulling container images (%s)...\n", tag)
	if err := composeRun(ctx, cmd, info, safeDir, "pull"); err != nil {
		rollback()
		return fmt.Errorf("pulling images: %w", err)
	}

	// Persist config only after successful pull so a failed pull
	// doesn't leave state claiming images are at the new version.
	updatedState := state
	updatedState.ImageTag = tag
	if err := config.Save(updatedState); err != nil {
		rollback()
		return fmt.Errorf("saving config: %w", err)
	}
	return nil
}

// regenerateCompose writes a new compose.yml for the given image tag.
// effectiveVersion overrides the stale in-memory version.Version after
// selfupdate.Replace so the compose header reflects the new CLI version.
func regenerateCompose(state config.State, tag, safeDir, effectiveVersion string) error {
	updatedState := state
	updatedState.ImageTag = tag
	params := compose.ParamsFromState(updatedState)
	params.CLIVersion = effectiveVersion
	composeYAML, err := compose.Generate(params)
	if err != nil {
		return fmt.Errorf("generating compose file: %w", err)
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if err := os.WriteFile(composePath, composeYAML, 0o600); err != nil {
		return fmt.Errorf("writing compose file: %w", err)
	}
	return nil
}

// restartIfRunning checks if containers are running and offers a restart.
func restartIfRunning(cmd *cobra.Command, info docker.Info, safeDir string, state config.State) error {
	ctx := cmd.Context()
	out := cmd.OutOrStdout()

	psOut, err := docker.ComposeExecOutput(ctx, info, safeDir, "ps", "-q")
	if err != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(),
			"Warning: could not check container status: %v\nIf containers are running, restart manually: synthorg stop && synthorg start\n", err)
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
