package cmd

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"strings"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/compose"
	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/health"
	"github.com/Aureliolo/synthorg/cli/internal/selfupdate"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/Aureliolo/synthorg/cli/internal/verify"
	"github.com/Aureliolo/synthorg/cli/internal/version"
	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"
)

var updateCmd = &cobra.Command{
	Use:   "update",
	Short: "Update CLI, refresh compose template, and pull new container images",
	RunE:  runUpdate,
}

func init() {
	rootCmd.AddCommand(updateCmd)
}

func runUpdate(cmd *cobra.Command, _ []string) error {
	if err := updateCLI(cmd); errors.Is(err, errReexec) {
		// Binary was replaced. Re-exec the new binary so compose refresh
		// and image pull use the new embedded template and logic.
		return reexecUpdate(cmd)
	} else if err != nil {
		return err
	}

	// Load state once and thread through both steps to avoid
	// double config.Load and TOCTOU gaps between them.
	dir := resolveDataDir()
	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	// Detect dirty installation state (e.g. after partial uninstall).
	// When recovery is chosen, force compose + image refresh even if the
	// stored version matches the target (artifacts may be missing).
	abort, recovered, healthErr := checkInstallationHealth(cmd, state)
	if healthErr != nil {
		return healthErr
	}
	if abort {
		return nil
	}

	// Regenerate compose.yml from the current template to pick up any
	// template changes (new env vars, hardening tweaks, service config).
	// In recovery mode, also generate a missing compose.yml from the template.
	applied, err := refreshCompose(cmd, state, recovered)
	if err != nil {
		return err
	}
	if !applied {
		// User declined compose changes. New images may not work with
		// old compose (e.g. missing env vars). Let them force it.
		_, _ = fmt.Fprintln(cmd.OutOrStdout(),
			"Warning: new images may not work correctly with your current compose configuration.")
		forceImages := false
		ok, confirmErr := confirmUpdateWithDefault(
			"Still update container images? (Only image references in compose.yml will be updated, template changes will not be applied.)",
			forceImages,
		)
		if confirmErr != nil {
			return confirmErr
		}
		if !ok {
			_, _ = fmt.Fprintln(cmd.OutOrStdout(), "Image update skipped. Run 'synthorg init' then 'synthorg update' when ready.")
			return nil
		}
		// User insisted -- update images but preserve their compose.
		return updateContainerImages(cmd, state, true, recovered)
	}

	return updateContainerImages(cmd, state, false, recovered)
}

// errReexec is a sentinel error returned by updateCLI when the binary was
// replaced and the new binary should be re-executed to continue the update.
// The caller (runUpdate) handles this by spawning the new binary.
var errReexec = errors.New("cli updated, re-exec required")

// updateCLI checks for a new CLI release and optionally applies it.
// Returns errReexec if the binary was replaced (caller must re-exec).
func updateCLI(cmd *cobra.Command) error {
	ctx := cmd.Context()
	out := cmd.OutOrStdout()

	// Warn on dev builds.
	if version.Version == "dev" {
		_, _ = fmt.Fprintln(out, "Warning: running a dev build -- update check will always report an update available.")
	}

	_, _ = fmt.Fprintln(out, "Checking for updates...")
	result, err := selfupdate.Check(ctx)
	if err != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: could not check for updates: %v\n", err)
		return nil
	}

	if !result.UpdateAvail {
		_, _ = fmt.Fprintf(out, "CLI is up to date (%s)\n", result.CurrentVersion)
		return nil
	}

	_, _ = fmt.Fprintf(out, "New version available: %s (current: %s)\n", result.LatestVersion, result.CurrentVersion)

	ok, err := confirmUpdate(fmt.Sprintf("Update CLI from %s to %s?", result.CurrentVersion, result.LatestVersion))
	if err != nil {
		return err
	}
	if !ok {
		return nil
	}

	_, _ = fmt.Fprintln(out, "Downloading...")
	binary, err := selfupdate.Download(ctx, result.AssetURL, result.ChecksumURL, result.SigstoreBundURL)
	if err != nil {
		return fmt.Errorf("downloading update: %w", err)
	}

	if err := selfupdate.Replace(binary); err != nil {
		return fmt.Errorf("replacing binary: %w", err)
	}
	_, _ = fmt.Fprintf(out, "CLI updated to %s\n", result.LatestVersion)
	_, _ = fmt.Fprintf(out, "Release notes: %s/releases/tag/v%s\n",
		version.RepoURL, strings.TrimPrefix(result.LatestVersion, "v"))

	// Signal the caller to re-exec the new binary so the rest of the
	// update (compose refresh, image pull) uses the new embedded template.
	return errReexec
}

// ChildExitError carries the exit code from a re-exec'd child process.
// The program entrypoint inspects this via ChildExitCode to call os.Exit
// with the child's code instead of printing a generic error message.
type ChildExitError struct {
	Code int
}

func (e *ChildExitError) Error() string {
	return fmt.Sprintf("re-launched CLI exited with code %d", e.Code)
}

// ChildExitCode extracts the exit code from err if it is a ChildExitError.
// Returns (code, true) if found, (0, false) otherwise.
func ChildExitCode(err error) (int, bool) {
	var ce *ChildExitError
	if errors.As(err, &ce) {
		return ce.Code, true
	}
	return 0, false
}

// reexecUpdate spawns the new binary with the same arguments so the rest
// of the update (compose refresh, image pull) uses the new embedded template.
// The CLI update step already ran, so the new binary will see "up to date"
// and proceed directly to compose + images.
//
// Arguments are reconstructed from known flag values rather than forwarding
// raw os.Args to avoid silently propagating unexpected flags.
//
// Returns a *ChildExitError if the child exits non-zero, so the caller
// can propagate the exit code rather than printing a generic error.
func reexecUpdate(cmd *cobra.Command) error {
	_, _ = fmt.Fprintln(cmd.OutOrStdout(), "Re-launching updated CLI to continue...")

	execPath, err := os.Executable()
	if err != nil {
		return fmt.Errorf("finding executable path: %w", err)
	}
	// Resolve symlinks to match the pattern in uninstall.go --
	// selfupdate.Replace writes to the resolved path.
	if resolved, resolveErr := filepath.EvalSymlinks(execPath); resolveErr == nil {
		execPath = resolved
	} else {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: could not resolve executable symlink: %v\n", resolveErr)
	}

	// Reconstruct args from known flags instead of forwarding os.Args
	// to avoid silently propagating unexpected flags.
	reArgs := []string{"update"}
	if dataDir != "" {
		reArgs = append(reArgs, "--data-dir", dataDir)
	}
	if skipVerify {
		reArgs = append(reArgs, "--skip-verify")
		_, _ = fmt.Fprintln(cmd.ErrOrStderr(), "Warning: --skip-verify is being carried forward to the re-launched CLI.")
	}

	c := exec.CommandContext(cmd.Context(), execPath, reArgs...)
	c.Stdin = os.Stdin
	c.Stdout = cmd.OutOrStdout()
	c.Stderr = cmd.ErrOrStderr()

	if runErr := c.Run(); runErr != nil {
		// Preserve the child's exit code so the parent can propagate it.
		var exitErr *exec.ExitError
		if errors.As(runErr, &exitErr) {
			return &ChildExitError{Code: exitErr.ExitCode()}
		}
		return fmt.Errorf("re-launching updated CLI: %w", runErr)
	}
	return nil
}

// refreshCompose regenerates compose.yml from the current embedded template.
// If the regenerated compose differs from what is on disk, it shows the diff
// and asks the user to approve. When force is true (recovery mode), a missing
// compose.yml is generated from the template without prompting.
// Returns true if compose is up to date or changes were applied; false if
// the user declined.
func refreshCompose(cmd *cobra.Command, state config.State, force bool) (bool, error) {
	out := cmd.OutOrStdout()

	safeDir, err := safeStateDir(state)
	if err != nil {
		return false, err
	}

	composePath := filepath.Join(safeDir, "compose.yml")
	existing, fresh, err := loadAndGenerate(composePath, state)
	if err != nil {
		return false, err
	}
	if existing == nil {
		if !force {
			return true, nil // no compose.yml on disk -- nothing to refresh
		}
		// Recovery mode: compose.yml is missing, generate from template.
		// loadAndGenerate returns (nil, nil, nil) when the file is absent,
		// so we must generate the content explicitly.
		params := compose.ParamsFromState(state)
		params.DigestPins = state.VerifiedDigests
		generated, genErr := compose.Generate(params)
		if genErr != nil {
			return false, fmt.Errorf("generating compose.yml during recovery: %w", genErr)
		}
		if wErr := atomicWriteFile(composePath, generated, safeDir); wErr != nil {
			return false, fmt.Errorf("writing compose.yml during recovery: %w", wErr)
		}
		_, _ = fmt.Fprintln(out, "Generated compose.yml from template.")
		return true, nil
	}

	if bytes.Equal(existing, fresh) {
		_, _ = fmt.Fprintln(out, "Compose configuration is up to date.")
		return true, nil
	}

	// If only the version comment on line 1 changed, auto-apply silently.
	if isVersionCommentOnly(existing, fresh) {
		if err := atomicWriteFile(composePath, fresh, safeDir); err != nil {
			return false, fmt.Errorf("writing updated compose: %w", err)
		}
		_, _ = fmt.Fprintln(out, "Compose configuration is up to date.")
		return true, nil
	}

	return applyComposeDiff(cmd, composePath, existing, fresh, safeDir)
}

// isVersionCommentOnly returns true if existing and fresh differ only in their
// first line (the "# Generated by SynthOrg CLI ..." version comment).
func isVersionCommentOnly(existing, fresh []byte) bool {
	_, existingRest, ok1 := bytes.Cut(existing, []byte("\n"))
	_, freshRest, ok2 := bytes.Cut(fresh, []byte("\n"))
	return ok1 && ok2 && bytes.Equal(existingRest, freshRest)
}

// loadAndGenerate reads the existing compose and generates a fresh one from
// the template. Returns (nil, nil, nil) if no compose.yml exists on disk.
func loadAndGenerate(composePath string, state config.State) ([]byte, []byte, error) {
	existing, err := os.ReadFile(composePath)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil, nil, nil
		}
		return nil, nil, fmt.Errorf("reading existing compose: %w", err)
	}

	params := compose.ParamsFromState(state)
	params.DigestPins = state.VerifiedDigests
	fresh, err := compose.Generate(params)
	if err != nil {
		return nil, nil, fmt.Errorf("generating compose from template: %w", err)
	}
	return existing, fresh, nil
}

// applyComposeDiff shows the diff between existing and fresh compose,
// asks the user to approve, and writes the fresh compose if approved.
// Returns true if applied, false if declined.
func applyComposeDiff(cmd *cobra.Command, composePath string, existing, fresh []byte, safeDir string) (bool, error) {
	out := cmd.OutOrStdout()

	diff := lineDiff(string(existing), string(fresh))
	_, _ = fmt.Fprintln(out, "Compose template has changed:")
	_, _ = fmt.Fprintln(out, diff)

	ok, err := confirmUpdate("Apply compose configuration changes?")
	if err != nil {
		return false, err
	}
	if !ok {
		_, _ = fmt.Fprintln(out, "Compose changes skipped.")
		return false, nil
	}

	if err := atomicWriteFile(composePath, fresh, safeDir); err != nil {
		return false, fmt.Errorf("writing updated compose: %w", err)
	}
	_, _ = fmt.Fprintln(out, "Compose configuration updated.")
	return true, nil
}

// secretKeyPattern matches YAML lines containing known sensitive keys.
// Used by lineDiff to redact sensitive values before displaying.
// Covers common secret naming conventions to prevent leaking credentials
// in terminal scrollback or CI logs when the compose template changes.
var secretKeyPattern = regexp.MustCompile(
	`(?i)^\s*\w*(SECRET|PASSWORD|TOKEN|API_KEY|CREDENTIALS|ENCRYPTION_KEY|SETTINGS_KEY|PRIVATE_KEY|CERT)\w*\s*:`,
)

// lineDiff produces a bag-based diff showing added (+) and removed (-) lines
// between two strings. Lines containing secret keys are redacted.
//
// Note: this uses multiset membership, not positional diffing. Reordered
// lines are not reported as changes. This is acceptable for compose files
// where the user approves structural additions/removals, not reorderings.
func lineDiff(oldText, updated string) string {
	oldLines := strings.Split(oldText, "\n")
	newLines := strings.Split(updated, "\n")

	newSet := make(map[string]int, len(newLines))
	for _, l := range newLines {
		newSet[l]++
	}

	oldSet := make(map[string]int, len(oldLines))
	for _, l := range oldLines {
		oldSet[l]++
	}

	var b strings.Builder
	for _, l := range oldLines {
		if newSet[l] > 0 {
			newSet[l]--
			continue
		}
		b.WriteString("  - ")
		b.WriteString(redactSecret(l))
		b.WriteByte('\n')
	}
	for _, l := range newLines {
		if oldSet[l] > 0 {
			oldSet[l]--
			continue
		}
		b.WriteString("  + ")
		b.WriteString(redactSecret(l))
		b.WriteByte('\n')
	}
	return b.String()
}

// redactSecret replaces secret values with [REDACTED] in diff output.
// Uses the regex submatch end position to find the colon reliably,
// rather than scanning from the start of the line.
func redactSecret(line string) string {
	loc := secretKeyPattern.FindStringIndex(line)
	if loc != nil {
		// loc[1] is past the trailing ":", so the key + colon is line[:loc[1]].
		return line[:loc[1]] + " [REDACTED]"
	}
	return line
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
	if !config.IsValidImageTag(tag) {
		return "latest"
	}
	return tag
}

// updateContainerImages offers to update container images to match the
// current CLI version. Skips if images already match unless forceRefresh
// is true (recovery mode -- images may be missing despite matching tag).
// When preserveCompose is true, only image references are patched in the
// existing compose instead of regenerating from the template.
func updateContainerImages(cmd *cobra.Command, state config.State, preserveCompose bool, forceRefresh bool) error {
	ctx := cmd.Context()
	out := cmd.OutOrStdout()

	tag := targetImageTag(version.Version)

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}

	// Check if container images already match the target version.
	if state.ImageTag == tag && !forceRefresh {
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

	if err := pullAndPersist(ctx, cmd, info, state, tag, safeDir, preserveCompose); err != nil {
		return err
	}

	updatedState := state
	updatedState.ImageTag = tag
	restarted, restartErr := restartIfRunning(cmd, info, safeDir, updatedState)
	if restartErr != nil {
		return restartErr
	}

	// Show a hint about old images if they exceed the size threshold.
	// Actual cleanup is deferred to 'synthorg cleanup' to avoid removing
	// images that might still be referenced by other containers.
	if restarted {
		hintOldImages(cmd, info, updatedState)
	}
	return nil
}

// confirmUpdate prompts the user to confirm an update action.
// Returns (true, nil) if non-interactive (auto-accept) or user confirms.
// Default is yes.
func confirmUpdate(title string) (bool, error) {
	return confirmUpdateWithDefault(title, true)
}

// confirmUpdateWithDefault prompts the user with a configurable default.
func confirmUpdateWithDefault(title string, defaultVal bool) (bool, error) {
	if !isInteractive() {
		return defaultVal, nil
	}
	proceed := defaultVal
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().Title(title).Value(&proceed),
	))
	if err := form.Run(); err != nil {
		return false, err
	}
	return proceed, nil
}

// pullAndPersist verifies images, updates compose, pulls, and persists config.
// If any step fails, the previous compose.yml is restored. When
// preserveCompose is true, only image references are patched in the
// existing compose instead of regenerating from the template.
func pullAndPersist(ctx context.Context, cmd *cobra.Command, info docker.Info, state config.State, tag, safeDir string, preserveCompose bool) error {
	out := ui.NewUI(cmd.OutOrStdout())

	// Back up existing compose.yml for rollback on failure.
	composePath := filepath.Join(safeDir, "compose.yml")
	backup, backupErr := os.ReadFile(composePath)
	backupExists := backupErr == nil

	rollback := func() {
		if backupExists {
			if wErr := os.WriteFile(composePath, backup, 0o600); wErr != nil {
				_, _ = fmt.Fprintf(cmd.ErrOrStderr(),
					"Warning: failed to restore compose.yml backup: %v\n", wErr)
			}
		} else {
			if rErr := os.Remove(composePath); rErr != nil && !errors.Is(rErr, os.ErrNotExist) {
				_, _ = fmt.Fprintf(cmd.ErrOrStderr(),
					"Warning: failed to clean up compose.yml: %v\n", rErr)
			}
		}
	}

	errOut := ui.NewUI(cmd.ErrOrStderr())

	// Verify + write compose atomically: compose.yml is only updated after
	// verification succeeds (or when --skip-verify explicitly skips it).
	digestPins, err := verifyAndPinForUpdate(ctx, state, tag, safeDir, preserveCompose, out, errOut)
	if err != nil {
		rollback()
		return err
	}

	if err := pullServicesLive(ctx, info, safeDir, state, out); err != nil {
		rollback()
		return err
	}

	// Persist config only after successful pull so a failed pull
	// doesn't leave state claiming images are at the new version.
	updatedState := state
	updatedState.ImageTag = tag
	updatedState.VerifiedDigests = digestPins
	if err := config.Save(updatedState); err != nil {
		rollback()
		return fmt.Errorf("saving config: %w", err)
	}
	return nil
}

// verifyAndPinForUpdate runs image verification and updates the compose
// file with new image references. When preserveCompose is true, only
// image lines are patched; otherwise the full compose is regenerated.
func verifyAndPinForUpdate(ctx context.Context, state config.State, tag, safeDir string, preserveCompose bool, out *ui.UI, errOut *ui.UI) (map[string]string, error) {
	updatedState := state
	updatedState.ImageTag = tag

	if skipVerify {
		errOut.Warn("Image verification skipped (--skip-verify). Containers are NOT verified.")
		if err := writeOrPatchCompose(updatedState, nil, safeDir, preserveCompose); err != nil {
			return nil, err
		}
		return nil, nil
	}

	sp := out.StartSpinner("Verifying container image signatures...")
	verifyCtx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()
	var buf bytes.Buffer
	results, err := verify.VerifyImages(verifyCtx, verify.VerifyOptions{
		Images: verify.BuildImageRefs(tag, state.Sandbox),
		Output: &buf,
	})
	if err != nil {
		sp.Error("Image verification failed")
		if isTransportError(err) {
			errOut.Hint("Use --skip-verify for air-gapped environments")
		}
		return nil, fmt.Errorf("image verification failed: %w", err)
	}
	sp.Stop()
	renderVerifyBox(out, results)
	out.Blank()

	pins, err := digestPinMap(results)
	if err != nil {
		return nil, fmt.Errorf("digest pin map: %w", err)
	}

	if err := writeOrPatchCompose(updatedState, pins, safeDir, preserveCompose); err != nil {
		return nil, err
	}
	return pins, nil
}

// writeOrPatchCompose either regenerates compose from the template or
// patches only image references in the existing file.
func writeOrPatchCompose(state config.State, digestPins map[string]string, safeDir string, preserveCompose bool) error {
	if !preserveCompose {
		return writeDigestPinnedCompose(state, digestPins, safeDir)
	}
	return patchComposeImageRefs(state.ImageTag, digestPins, state.Sandbox, safeDir)
}

// imageLinePattern matches Docker image references in compose YAML.
// Handles both digest-pinned (repo@sha256:...) and tag-based (repo:tag).
var imageLinePattern = regexp.MustCompile(
	`(\s+image:\s+)ghcr\.io/aureliolo/synthorg-(backend|web|sandbox)[\S]*`,
)

// patchComposeImageRefs updates only the image references in an existing
// compose.yml without regenerating from the template. This preserves the
// user's compose configuration while allowing image updates.
//
// Returns an error if no image references were found or if not all expected
// services (backend, web, and optionally sandbox) were patched -- this
// prevents config.Save from advancing state when compose is unpatched.
func patchComposeImageRefs(tag string, digestPins map[string]string, sandboxEnabled bool, safeDir string) error {
	composePath := filepath.Join(safeDir, "compose.yml")
	existing, err := os.ReadFile(composePath)
	if err != nil {
		return fmt.Errorf("reading compose for image patching: %w", err)
	}

	replaced := make(map[string]bool)
	patched := imageLinePattern.ReplaceAllStringFunc(string(existing), func(match string) string {
		sub := imageLinePattern.FindStringSubmatch(match)
		if len(sub) < 3 {
			return match
		}
		prefix := sub[1] // e.g. "    image: "
		name := sub[2]   // e.g. "backend"
		repo := imageRepoPrefix + name
		replaced[name] = true

		if d, ok := digestPins[name]; ok && d != "" {
			return prefix + repo + "@" + d
		}
		return prefix + repo + ":" + tag
	})

	if len(replaced) == 0 {
		return fmt.Errorf("no synthorg image references found in %s -- compose may be manually edited; run 'synthorg init' to regenerate", composePath)
	}

	// Backend and web are always required; sandbox only when enabled.
	required := []string{"backend", "web"}
	if sandboxEnabled {
		required = append(required, "sandbox")
	}
	for _, svc := range required {
		if !replaced[svc] {
			return fmt.Errorf("image reference for %q not found in %s -- compose may be manually edited; run 'synthorg init' to regenerate", svc, composePath)
		}
	}

	return atomicWriteFile(composePath, []byte(patched), safeDir)
}

// restartIfRunning checks if containers are running and offers a restart.
// Returns (true, nil) when containers were restarted and passed health checks.
// Returns (false, nil) when restart was skipped or health check failed.
func restartIfRunning(cmd *cobra.Command, info docker.Info, safeDir string, state config.State) (bool, error) {
	ctx := cmd.Context()
	out := cmd.OutOrStdout()

	psOut, err := docker.ComposeExecOutput(ctx, info, safeDir, "ps", "-q")
	if err != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(),
			"Warning: could not check container status: %v\nIf containers are running, restart manually: synthorg stop && synthorg start\n", err)
		return false, nil
	}
	if psOut == "" {
		return false, nil
	}

	if !isInteractive() {
		_, _ = fmt.Fprintln(out, "Non-interactive mode: skipping restart. Run 'synthorg stop && synthorg start' to apply new images.")
		return false, nil
	}

	restart, err := confirmRestart()
	if err != nil {
		return false, err
	}
	if !restart {
		return false, nil
	}

	uiOut := ui.NewUI(out)

	sp := uiOut.StartSpinner("Stopping containers...")
	if err := composeRunQuiet(ctx, info, safeDir, "down"); err != nil {
		sp.Error("Failed to stop containers")
		return false, fmt.Errorf("stopping containers: %w", err)
	}
	sp.Success("Containers stopped")

	sp = uiOut.StartSpinner("Starting containers...")
	if err := composeRunQuiet(ctx, info, safeDir, "up", "-d"); err != nil {
		sp.Error("Failed to start containers")
		return false, fmt.Errorf("restarting containers: %w", err)
	}
	sp.Success("Containers started")

	sp = uiOut.StartSpinner("Waiting for backend to become healthy...")
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort)
	if err := health.WaitForHealthy(ctx, healthURL, 90*time.Second, 2*time.Second, 5*time.Second); err != nil {
		sp.Warn(fmt.Sprintf("Health check did not pass after restart: %v", err))
		return false, nil
	}
	sp.Success("Backend healthy")
	uiOut.KeyValue("Dashboard", fmt.Sprintf("http://localhost:%d", state.WebPort))
	return true, nil
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
