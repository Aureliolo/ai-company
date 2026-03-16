package cmd

import (
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/compose"
	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/health"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/Aureliolo/synthorg/cli/internal/verify"
	"github.com/Aureliolo/synthorg/cli/internal/version"
	"github.com/spf13/cobra"
)

var startCmd = &cobra.Command{
	Use:   "start",
	Short: "Pull images and start the SynthOrg stack",
	RunE:  runStart,
}

func init() {
	rootCmd.AddCommand(startCmd)
}

func runStart(cmd *cobra.Command, args []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if _, err := os.Stat(composePath); errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("compose.yml not found in %s — run 'synthorg init' first", safeDir)
	}

	out := ui.NewUI(cmd.OutOrStdout())
	errOut := ui.NewUI(cmd.ErrOrStderr())

	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}
	out.Success(fmt.Sprintf("Docker %s, Compose %s", info.DockerVersion, info.ComposeVersion))

	// Check minimum versions.
	for _, w := range docker.CheckMinVersions(info) {
		errOut.Warn(w)
	}

	// Verify container image signatures before pulling.
	if !skipVerify {
		out.Step("Verifying container image signatures...")
		results, err := verify.VerifyImages(ctx, verify.VerifyOptions{
			Images: verify.BuildImageRefs(state.ImageTag, state.Sandbox),
			Output: cmd.OutOrStdout(),
		})
		if err != nil {
			return fmt.Errorf("image verification failed: %w\n  Use --skip-verify for air-gapped environments", err)
		}

		// Pin verified digests in compose file.
		if err := pinDigestsInCompose(state, results, safeDir); err != nil {
			return fmt.Errorf("pinning verified digests: %w", err)
		}

		// Cache verified digests in config.
		state.VerifiedDigests = digestPinMap(results)
		if err := config.Save(state); err != nil {
			errOut.Warn(fmt.Sprintf("Could not cache verified digests: %v", err))
		}
	} else {
		errOut.Warn("Image verification skipped (--skip-verify). Containers are NOT verified.")
	}

	// Pull images.
	out.Step("Pulling images...")
	if err := composeRun(ctx, cmd, info, safeDir, "pull"); err != nil {
		return fmt.Errorf("pulling images: %w", err)
	}

	// Start containers.
	out.Step("Starting containers...")
	if err := composeRun(ctx, cmd, info, safeDir, "up", "-d"); err != nil {
		return fmt.Errorf("starting containers: %w", err)
	}

	// Wait for health.
	out.Step("Waiting for backend to become healthy...")
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort)
	if err := health.WaitForHealthy(ctx, healthURL, 90*time.Second, 2*time.Second, 5*time.Second); err != nil {
		errOut.Error("Containers are running but health check failed.")
		errOut.Hint("Run 'synthorg doctor' for diagnostics.")
		return fmt.Errorf("health check did not pass: %w", err)
	}

	out.Success("SynthOrg is running!")
	out.KeyValue("API", fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort))
	out.KeyValue("Dashboard", fmt.Sprintf("http://localhost:%d", state.WebPort))
	return nil
}

// pinDigestsInCompose regenerates the compose file with digest-pinned image
// references from the verified results.
func pinDigestsInCompose(state config.State, results []verify.VerifyResult, safeDir string) error {
	params := compose.ParamsFromState(state)
	params.CLIVersion = version.Version
	params.DigestPins = digestPinMap(results)

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

// digestPinMap converts verification results to a map of image name → digest
// for use in compose generation.
func digestPinMap(results []verify.VerifyResult) map[string]string {
	pins := make(map[string]string, len(results))
	for _, r := range results {
		if r.Ref.Digest != "" {
			pins[r.Ref.Name()] = r.Ref.Digest
		}
	}
	return pins
}

func composeRun(ctx context.Context, cobraCmd *cobra.Command, info docker.Info, dir string, args ...string) error {
	fullArgs := make([]string, 0, len(info.ComposeCmd)-1+len(args))
	fullArgs = append(fullArgs, info.ComposeCmd[1:]...)
	fullArgs = append(fullArgs, args...)

	c := exec.CommandContext(ctx, info.ComposeCmd[0], fullArgs...)
	c.Dir = dir
	c.Stdout = cobraCmd.OutOrStdout()
	c.Stderr = cobraCmd.ErrOrStderr()
	return c.Run()
}
