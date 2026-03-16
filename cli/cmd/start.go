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
	if err := verifyAndPinImages(ctx, cmd, state, safeDir, out, errOut); err != nil {
		return err
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

// verifyAndPinImages verifies image signatures (unless --skip-verify) and
// pins the verified digests in the compose file and config.
func verifyAndPinImages(ctx context.Context, cmd *cobra.Command, state config.State, safeDir string, out, errOut *ui.UI) error {
	if skipVerify {
		errOut.Warn("Image verification skipped (--skip-verify). Containers are NOT verified.")
		return nil
	}

	out.Step("Verifying container image signatures...")
	// Bound OCI registry calls to prevent indefinite hangs.
	verifyCtx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()
	results, err := verify.VerifyImages(verifyCtx, verify.VerifyOptions{
		Images: verify.BuildImageRefs(state.ImageTag, state.Sandbox),
		Output: cmd.OutOrStdout(),
	})
	if err != nil {
		if isTransportError(err) {
			errOut.Hint("Use --skip-verify for air-gapped environments")
		}
		return fmt.Errorf("image verification failed: %w", err)
	}

	pins, err := digestPinMap(results)
	if err != nil {
		return fmt.Errorf("digest pin map: %w", err)
	}

	if err := writeDigestPinnedCompose(state, pins, safeDir, version.Version); err != nil {
		return fmt.Errorf("pinning verified digests: %w", err)
	}

	state.VerifiedDigests = pins
	if err := config.Save(state); err != nil {
		errOut.Warn(fmt.Sprintf("Could not cache verified digests: %v", err))
	}
	return nil
}

// writeDigestPinnedCompose generates and writes a compose file with digest-pinned
// image references. Shared by start.go and update.go verification flows.
//
// Uses atomic write (temp file + rename) to prevent a partial write from
// corrupting the compose file if the process is interrupted.
func writeDigestPinnedCompose(state config.State, digestPins map[string]string, safeDir, cliVersion string) error {
	params := compose.ParamsFromState(state)
	params.CLIVersion = cliVersion
	params.DigestPins = digestPins

	composeYAML, err := compose.Generate(params)
	if err != nil {
		return fmt.Errorf("generating compose file: %w", err)
	}

	return atomicWriteFile(filepath.Join(safeDir, "compose.yml"), composeYAML, safeDir)
}

// atomicWriteFile writes data to targetPath via a temp file + rename to prevent
// partial writes on crash. tmpDir must be on the same filesystem as targetPath.
func atomicWriteFile(targetPath string, data []byte, tmpDir string) error {
	tmp, err := os.CreateTemp(tmpDir, ".compose-*.yml.tmp")
	if err != nil {
		return fmt.Errorf("creating temp file: %w", err)
	}
	tmpPath := tmp.Name()

	// Clean up temp file on any error path.
	defer func() {
		if tmpPath != "" {
			_ = os.Remove(tmpPath)
		}
	}()

	if _, err := tmp.Write(data); err != nil {
		_ = tmp.Close()
		return fmt.Errorf("writing compose file: %w", err)
	}
	if err := tmp.Sync(); err != nil {
		_ = tmp.Close()
		return fmt.Errorf("syncing compose file: %w", err)
	}
	if err := tmp.Close(); err != nil {
		return fmt.Errorf("closing compose file: %w", err)
	}

	// Set permissions before rename so the target is never world-readable.
	if err := os.Chmod(tmpPath, 0o600); err != nil {
		return fmt.Errorf("setting compose file permissions: %w", err)
	}

	if err := os.Rename(tmpPath, targetPath); err != nil {
		return fmt.Errorf("replacing compose file: %w", err)
	}
	tmpPath = "" // prevent deferred removal of the now-renamed file

	// Best-effort directory fsync to ensure the rename is persisted.
	// Ignored on platforms that don't support Sync on directories (Windows).
	if dir, err := os.Open(filepath.Dir(targetPath)); err == nil {
		_ = dir.Sync()
		_ = dir.Close()
	}
	return nil
}

// digestPinMap converts verification results to a map of image name → digest
// for use in compose generation. Returns an error if any result has an empty
// digest — after successful verification all digests must be resolved.
func digestPinMap(results []verify.VerifyResult) (map[string]string, error) {
	pins := make(map[string]string, len(results))
	for _, r := range results {
		if r.Ref.Digest == "" {
			return nil, fmt.Errorf("image %s has no resolved digest after verification", r.Ref.Name())
		}
		pins[r.Ref.Name()] = r.Ref.Digest
	}
	return pins, nil
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
