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
	if abort, healthErr := checkInstallationHealth(cmd, state); healthErr != nil {
		return healthErr
	} else if abort {
		return nil
	}

	// Migrate: generate settings encryption key if missing (pre-v0.3.9 installs).
	// 32 bytes -> 44-char URL-safe base64 = valid Fernet key.
	if state.SettingsKey == "" {
		key, genErr := generateSecret(32)
		if genErr != nil {
			return fmt.Errorf("generating settings encryption key: %w", genErr)
		}
		state.SettingsKey = key
		if saveErr := config.Save(state); saveErr != nil {
			return fmt.Errorf("saving updated config: %w", saveErr)
		}
		out := ui.NewUI(cmd.OutOrStdout())
		out.Success("Generated settings encryption key for this installation.")
	}

	// Regenerate compose.yml from the current template to pick up any
	// template changes (new env vars, hardening tweaks, service config).
	applied, err := refreshCompose(cmd, state)
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
		return updateContainerImages(cmd, state, true)
	}

	return updateContainerImages(cmd, state, false)
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
// Returns a *childExitError if the child exits non-zero, so the caller
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
// and asks the user to approve. Returns true if compose is up to date or
// changes were applied; false if the user declined.
func refreshCompose(cmd *cobra.Command, state config.State) (bool, error) {
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
		return true, nil // no compose.yml on disk -- nothing to refresh
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
	`(?i)^\s*\w*(SECRET|PASSWORD|TOKEN|API_KEY|CREDENTIALS|ENCRYPTION_KEY|SETTINGS_KEY)\w*\s*:`,
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
// current CLI version. Skips if images already match. When preserveCompose
// is true, only image references are patched in the existing compose
// instead of regenerating from the template.
func updateContainerImages(cmd *cobra.Command, state config.State, preserveCompose bool) error {
	ctx := cmd.Context()
	out := cmd.OutOrStdout()

	tag := targetImageTag(version.Version)

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

	if err := pullAndPersist(ctx, cmd, info, state, tag, safeDir, preserveCompose); err != nil {
		return err
	}

	updatedState := state
	updatedState.ImageTag = tag
	if err := restartIfRunning(cmd, info, safeDir, updatedState); err != nil {
		return err
	}

	// Offer to remove old images after a successful upgrade.
	return cleanupOldImages(cmd, info, updatedState)
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
			_ = os.WriteFile(composePath, backup, 0o600)
		} else {
			_ = os.Remove(composePath)
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

	out.Step(fmt.Sprintf("Pulling container images (%s)...", tag))
	if err := composeRun(ctx, cmd, info, safeDir, "pull"); err != nil {
		rollback()
		return fmt.Errorf("pulling images: %w", err)
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

	out.Step("Verifying container image signatures...")
	verifyCtx, cancel := context.WithTimeout(ctx, 120*time.Second)
	defer cancel()
	results, err := verify.VerifyImages(verifyCtx, verify.VerifyOptions{
		Images: verify.BuildImageRefs(tag, state.Sandbox),
		Output: out.Writer(),
	})
	if err != nil {
		if isTransportError(err) {
			errOut.Hint("Use --skip-verify for air-gapped environments")
		}
		return nil, fmt.Errorf("image verification failed: %w", err)
	}
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
		repo := "ghcr.io/aureliolo/synthorg-" + name
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
		_, _ = fmt.Fprintf(out, "Dashboard: http://localhost:%d\n", state.WebPort)
	}

	return nil
}

// checkInstallationHealth detects inconsistent state between config and the
// actual Docker/filesystem state (e.g. after a partial uninstall). Returns
// (true, nil) if the user chose to abort, (false, nil) to continue.
func checkInstallationHealth(cmd *cobra.Command, state config.State) (bool, error) {
	ctx := cmd.Context()
	out := ui.NewUI(cmd.OutOrStdout())

	safeDir, err := safeStateDir(state)
	if err != nil {
		return false, err
	}

	var issues []string

	// 1. Missing config.json (Load returned defaults).
	if !fileExists(config.StatePath(state.DataDir)) {
		issues = append(issues, "config.json is missing (no previous init)")
	}

	// 2. Missing secrets.
	if state.JWTSecret == "" {
		issues = append(issues, "JWT secret is not configured")
	}
	if state.SettingsKey == "" {
		issues = append(issues, "settings encryption key is not configured")
	}

	// 3. Missing compose.yml.
	composePath := filepath.Join(safeDir, "compose.yml")
	if !fileExists(composePath) {
		issues = append(issues, "compose.yml is missing")
	}

	// 4. Missing Docker images for the configured tag.
	if state.ImageTag != "" {
		info, dockerErr := docker.Detect(ctx)
		if dockerErr == nil {
			if missing := detectMissingImages(ctx, info, state); len(missing) > 0 {
				issues = append(issues, fmt.Sprintf("container images missing locally for %s (%s)",
					state.ImageTag, strings.Join(missing, ", ")))
			}
		}
	}

	if len(issues) == 0 {
		return false, nil
	}

	out.Warn("Installation appears incomplete:")
	for _, issue := range issues {
		_, _ = fmt.Fprintf(cmd.OutOrStdout(), "  - %s\n", issue)
	}

	if !isInteractive() {
		_, _ = fmt.Fprintln(cmd.OutOrStdout(),
			"\nNon-interactive mode: run 'synthorg init' to restore a clean installation.")
		return true, nil
	}

	var recover bool
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Recover by pulling images and regenerating compose?").
			Description("Choose 'No' to run 'synthorg init' for a fresh setup instead.").
			Value(&recover),
	))
	if err := form.Run(); err != nil {
		return false, err
	}
	if !recover {
		_, _ = fmt.Fprintln(cmd.OutOrStdout(), "Run 'synthorg init' to restore a clean installation.")
		return true, nil
	}
	return false, nil
}

// detectMissingImages checks which SynthOrg service images are missing locally
// for the given state's image tag.
func detectMissingImages(ctx context.Context, info docker.Info, state config.State) []string {
	services := []string{"backend", "web"}
	if state.Sandbox {
		services = append(services, "sandbox")
	}

	var missing []string
	for _, svc := range services {
		ref := fmt.Sprintf("ghcr.io/aureliolo/synthorg-%s:%s", svc, state.ImageTag)
		idsOut, err := docker.RunCmd(ctx, info.DockerPath, "images",
			"--filter", "reference="+ref,
			"--format", "{{.ID}}")
		if err != nil || strings.TrimSpace(idsOut) == "" {
			missing = append(missing, svc)
		}
	}
	return missing
}

// cleanupOldImages offers to remove non-current SynthOrg images after a
// successful upgrade. Identifies current images by their Docker image ID
// (handles both tagged and digest-pinned references).
func cleanupOldImages(cmd *cobra.Command, info docker.Info, state config.State) error {
	ctx := cmd.Context()
	out := cmd.OutOrStdout()

	// Collect IDs of the just-pulled (current) images.
	currentIDs := make(map[string]bool)
	services := []string{"backend", "web"}
	if state.Sandbox {
		services = append(services, "sandbox")
	}
	for _, svc := range services {
		ref := fmt.Sprintf("ghcr.io/aureliolo/synthorg-%s:%s", svc, state.ImageTag)
		idOut, err := docker.RunCmd(ctx, info.DockerPath, "images",
			"--filter", "reference="+ref,
			"--format", "{{.ID}}")
		if err != nil {
			continue
		}
		for _, id := range strings.Fields(strings.TrimSpace(idOut)) {
			currentIDs[id] = true
		}
	}

	// List ALL SynthOrg images (any tag, including <none>).
	imageRef := "ghcr.io/aureliolo/synthorg-*"
	allOut, err := docker.RunCmd(ctx, info.DockerPath, "images",
		"--filter", "reference="+imageRef,
		"--format", "{{.Repository}}:{{.Tag}} ({{.Size}})\t{{.ID}}")
	if err != nil {
		return nil // non-fatal
	}

	type oldImage struct {
		display string
		id      string
	}
	var old []oldImage
	seen := make(map[string]bool)
	for _, line := range strings.Split(strings.TrimSpace(allOut), "\n") {
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "\t", 2)
		if len(parts) < 2 {
			continue
		}
		display, id := parts[0], parts[1]
		if currentIDs[id] || seen[id] {
			continue
		}
		seen[id] = true
		old = append(old, oldImage{display: display, id: id})
	}

	if len(old) == 0 {
		return nil
	}

	_, _ = fmt.Fprintln(out, "\nOld SynthOrg images found locally:")
	for _, img := range old {
		_, _ = fmt.Fprintf(out, "  %s\n", img.display)
	}

	if !isInteractive() {
		_, _ = fmt.Fprintln(out, "Non-interactive mode: skipping image cleanup. Remove manually with 'docker rmi'.")
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

	ids := make([]string, len(old))
	for i, img := range old {
		ids[i] = img.id
	}
	rmiArgs := append([]string{"rmi", "--force"}, ids...)
	if _, rmiErr := docker.RunCmd(ctx, info.DockerPath, rmiArgs...); rmiErr != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: some images could not be removed: %v\n", rmiErr)
	} else {
		_, _ = fmt.Fprintf(out, "Removed %d old image(s).\n", len(old))
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
