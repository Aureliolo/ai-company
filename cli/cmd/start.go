package cmd

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
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

var (
	startNoWait   bool
	startTimeout  string
	startNoPull   bool
	startDryRun   bool
	startNoDetach bool
	startNoVerify bool
)

var startCmd = &cobra.Command{
	Use:   "start",
	Short: "Pull images and start the SynthOrg stack",
	Example: `  synthorg start              # pull, verify, and start
  synthorg start --no-pull    # start without pulling images
  synthorg start --dry-run    # preview what would happen
  synthorg start --no-detach  # run in foreground (stream logs)`,
	RunE: runStart,
}

func init() {
	startCmd.Flags().BoolVar(&startNoWait, "no-wait", false, "skip health check after start")
	startCmd.Flags().StringVar(&startTimeout, "timeout", "90s", "health check timeout (e.g. 90s, 2m)")
	startCmd.Flags().BoolVar(&startNoPull, "no-pull", false, "skip image verification and pull")
	startCmd.Flags().BoolVar(&startDryRun, "dry-run", false, "show what would happen without executing")
	startCmd.Flags().BoolVar(&startNoDetach, "no-detach", false, "run in foreground (stream logs, Ctrl+C to stop)")
	startCmd.Flags().BoolVar(&startNoVerify, "no-verify", false, "skip image signature verification (alias for --skip-verify)")
	startCmd.GroupID = "core"
	rootCmd.AddCommand(startCmd)
}

func runStart(cmd *cobra.Command, _ []string) error {
	if err := validateStartFlags(cmd); err != nil {
		return err
	}
	healthTimeout, parseErr := time.ParseDuration(startTimeout)
	if parseErr != nil {
		return fmt.Errorf("invalid --timeout %q: %w", startTimeout, parseErr)
	}
	if !startNoWait && healthTimeout <= 0 {
		return fmt.Errorf("invalid --timeout %q: must be > 0", startTimeout)
	}

	ctx := cmd.Context()
	opts := GetGlobalOpts(ctx)
	if startNoVerify {
		opts.SkipVerify = true
		cmd.SetContext(SetGlobalOpts(ctx, opts))
		ctx = cmd.Context()
	}

	state, err := config.Load(opts.DataDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}
	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if _, err := os.Stat(composePath); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return fmt.Errorf("compose.yml not found in %s -- run 'synthorg init' first", safeDir)
		}
		return fmt.Errorf("checking compose.yml: %w", err)
	}

	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())
	errOut := ui.NewUIWithOptions(cmd.ErrOrStderr(), opts.UIOptions())

	if startDryRun {
		return printStartDryRun(out, state, opts)
	}
	return startContainers(cmd, ctx, state, safeDir, out, errOut, healthTimeout)
}

func validateStartFlags(cmd *cobra.Command) error {
	if startNoDetach && startNoWait {
		return fmt.Errorf("--no-detach and --no-wait are incompatible (foreground mode has no health check to skip)")
	}
	if startNoDetach && cmd.Flags().Changed("timeout") {
		return fmt.Errorf("--no-detach and --timeout are incompatible")
	}
	return nil
}

func printStartDryRun(out *ui.UI, state config.State, opts *GlobalOpts) error {
	out.KeyValue("Image tag", state.ImageTag)
	out.KeyValue("Backend port", strconv.Itoa(state.BackendPort))
	out.KeyValue("Web port", strconv.Itoa(state.WebPort))
	out.KeyValue("Sandbox", strconv.FormatBool(state.Sandbox))
	out.KeyValue("Skip verify", strconv.FormatBool(opts.SkipVerify || startNoPull))
	out.KeyValue("Skip pull", strconv.FormatBool(startNoPull))
	out.KeyValue("Detached", strconv.FormatBool(!startNoDetach))
	out.KeyValue("Health check", strconv.FormatBool(!startNoWait && !startNoDetach))
	out.Step("Dry run -- no changes made")
	return nil
}

func startContainers(cmd *cobra.Command, ctx context.Context, state config.State, safeDir string, out, errOut *ui.UI, healthTimeout time.Duration) error {
	out.Logo(version.Version)

	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}
	out.InlineKV(
		"Docker", info.DockerVersion+" "+ui.IconSuccess,
		"Compose", info.ComposeVersion+" "+ui.IconSuccess,
	)
	out.Blank()

	for _, w := range docker.CheckMinVersions(info) {
		errOut.Warn(w)
	}

	if !startNoPull {
		if err := verifyAndPinImages(ctx, cmd, state, safeDir, out, errOut); err != nil {
			return err
		}
		out.Blank()
		if err := pullServicesLive(ctx, info, safeDir, state, out); err != nil {
			return err
		}
	}

	if startNoDetach {
		out.Step("Starting in foreground mode (Ctrl+C to stop)...")
		return composeRun(ctx, cmd, info, safeDir, "up")
	}

	return startDetached(ctx, info, safeDir, state, out, errOut, healthTimeout)
}

func startDetached(ctx context.Context, info docker.Info, safeDir string, state config.State, out, errOut *ui.UI, healthTimeout time.Duration) error {
	sp := out.StartSpinner("Starting containers...")
	if err := composeRunQuiet(ctx, info, safeDir, "up", "-d"); err != nil {
		sp.Error("Failed to start containers")
		return fmt.Errorf("starting containers: %w", err)
	}
	sp.Success("Containers started")

	if !startNoWait {
		sp = out.StartSpinner("Waiting for backend to become healthy...")
		healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort)
		if err := health.WaitForHealthy(ctx, healthURL, healthTimeout, 2*time.Second, 5*time.Second); err != nil {
			sp.Error("Health check failed")
			errOut.HintError("Run 'synthorg doctor' for diagnostics.")
			return fmt.Errorf("health check did not pass: %w", err)
		}
		sp.Success("Backend healthy")
	} else {
		out.Step("Health check skipped (--no-wait)")
	}

	out.Blank()
	out.Box("Ready", []string{
		fmt.Sprintf("  %-12s http://localhost:%d/api/v1/health", "API", state.BackendPort),
		fmt.Sprintf("  %-12s http://localhost:%d", "Dashboard", state.WebPort),
	})
	return nil
}

// pullStartAndWait pulls images, starts containers, and waits for health.
func pullStartAndWait(ctx context.Context, info docker.Info, safeDir string, state config.State, out, errOut *ui.UI) error {
	if err := pullServicesLive(ctx, info, safeDir, state, out); err != nil {
		return err
	}

	sp := out.StartSpinner("Starting containers...")
	if err := composeRunQuiet(ctx, info, safeDir, "up", "-d"); err != nil {
		sp.Error("Failed to start containers")
		return fmt.Errorf("starting containers: %w", err)
	}
	sp.Success("Containers started")

	sp = out.StartSpinner("Waiting for backend to become healthy...")
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort)
	if err := health.WaitForHealthy(ctx, healthURL, 90*time.Second, 2*time.Second, 5*time.Second); err != nil {
		sp.Error("Health check failed")
		errOut.HintError("Run 'synthorg doctor' for diagnostics.")
		return fmt.Errorf("health check did not pass: %w", err)
	}
	sp.Success("Backend healthy")
	return nil
}

// serviceNames returns the list of compose service names for the current config.
func serviceNames(state config.State) []string {
	names := []string{"backend", "web"}
	if state.Sandbox {
		names = append(names, "sandbox")
	}
	return names
}

// pullServicesLive pulls each compose service concurrently, showing
// per-service progress in a live-updating box.
func pullServicesLive(ctx context.Context, info docker.Info, safeDir string, state config.State, out *ui.UI) error {
	services := serviceNames(state)
	lb := out.NewLiveBox("Pull Images", services)
	defer lb.Finish()

	var (
		mu      sync.Mutex
		pullErr error
	)
	var wg sync.WaitGroup
	for i, svc := range services {
		wg.Add(1)
		go func(idx int, name string) {
			defer wg.Done()
			err := composeRunQuiet(ctx, info, safeDir, "pull", name)
			if err != nil {
				lb.UpdateLine(idx, ui.IconError)
				mu.Lock()
				pullErr = errors.Join(pullErr, fmt.Errorf("pulling %s: %w", name, err))
				mu.Unlock()
			} else {
				lb.UpdateLine(idx, ui.IconSuccess)
			}
		}(i, svc)
	}
	wg.Wait()

	return pullErr
}

// verifyAndPinImages verifies image signatures (unless --skip-verify) and
// pins the verified digests in the compose file and config.
func verifyAndPinImages(ctx context.Context, _ *cobra.Command, state config.State, safeDir string, out, errOut *ui.UI) error {
	if GetGlobalOpts(ctx).SkipVerify {
		errOut.Warn("Image verification skipped (--skip-verify). Containers are NOT verified.")
		return nil
	}

	sp := out.StartSpinner("Verifying container image signatures...")

	// Buffer verify output -- we'll render results in a box instead.
	var buf bytes.Buffer
	verifyCtx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()
	results, err := verify.VerifyImages(verifyCtx, verify.VerifyOptions{
		Images: verify.BuildImageRefs(state.ImageTag, state.Sandbox),
		Output: &buf,
	})
	if err != nil {
		sp.Error("Image verification failed")
		if isTransportError(err) {
			errOut.HintError("Use --skip-verify for air-gapped environments")
		}
		return fmt.Errorf("image verification failed: %w", err)
	}
	sp.Stop()
	renderVerifyBox(out, results)

	pins, err := digestPinMap(results)
	if err != nil {
		return fmt.Errorf("digest pin map: %w", err)
	}

	if err := writeDigestPinnedCompose(state, pins, safeDir); err != nil {
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
func writeDigestPinnedCompose(state config.State, digestPins map[string]string, safeDir string) error {
	params := compose.ParamsFromState(state)
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

// digestPinMap converts verification results to a map of image name -> digest
// for use in compose generation. Returns an error if any result has an empty
// digest -- after successful verification all digests must be resolved.
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

// renderVerifyBox displays image verification results in a bordered box.
// Shared by start.go and update.go verification flows.
// Uses plain glyph constants (not ANSI-styled icons) because Box()
// sanitizes content with stripControlStrict which removes ESC bytes.
func renderVerifyBox(out *ui.UI, results []verify.VerifyResult) {
	boxLines := make([]string, 0, len(results))
	for _, r := range results {
		sigIcon := ui.IconSuccess
		slsaIcon := ui.IconSuccess
		if !r.ProvenanceVerified {
			slsaIcon = ui.IconWarning
		}
		boxLines = append(boxLines, fmt.Sprintf("  %-12s sig %s  slsa %s",
			r.Ref.Name(), sigIcon, slsaIcon))
	}
	out.Box("Verify Images", boxLines)
}

// composeRun runs a docker compose command with output forwarded to the
// Cobra command's stdout/stderr.
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

// composeRunQuiet runs a docker compose command with output captured in
// a buffer. On error, the sanitized output is included in the error message.
// Used when a spinner is shown and Docker's verbose output should be hidden.
func composeRunQuiet(ctx context.Context, info docker.Info, dir string, args ...string) error {
	fullArgs := make([]string, 0, len(info.ComposeCmd)-1+len(args))
	fullArgs = append(fullArgs, info.ComposeCmd[1:]...)
	fullArgs = append(fullArgs, args...)

	var buf bytes.Buffer
	c := exec.CommandContext(ctx, info.ComposeCmd[0], fullArgs...)
	c.Dir = dir
	c.Stdout = &buf
	c.Stderr = &buf
	if err := c.Run(); err != nil {
		output := sanitizeCLIOutput(buf.String())
		if output != "" {
			return fmt.Errorf("%w: %s", err, output)
		}
		return err
	}
	return nil
}

// sanitizeCLIOutput strips control characters from external CLI output
// before including it in error messages, preserving only printable text
// and newlines for readability.
func sanitizeCLIOutput(s string) string {
	s = strings.Map(func(r rune) rune {
		if (r < 0x20 && r != '\n') || r == 0x7F || (r >= 0x80 && r <= 0x9F) {
			return -1
		}
		return r
	}, s)
	return strings.TrimSpace(s)
}
