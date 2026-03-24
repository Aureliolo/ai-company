package cmd

import (
	"archive/tar"
	"compress/gzip"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/health"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"
)

// errWipeCancelled is a sentinel error used to signal that the user cancelled
// the wipe operation. Callers convert this to a clean (nil) exit.
var errWipeCancelled = errors.New("wipe cancelled by user")

// wipeContext bundles the shared dependencies for the wipe workflow,
// reducing parameter passing across the multi-step operation.
type wipeContext struct {
	ctx     context.Context
	cmd     *cobra.Command
	state   config.State
	info    docker.Info
	safeDir string
	out     *ui.UI
	errOut  *ui.UI
}

var wipeCmd = &cobra.Command{
	Use:   "wipe",
	Short: "Factory-reset: wipe all data with optional backup and restart",
	Long: `Destroy all SynthOrg data (database, memory, settings) and start
with a clean slate. You are prompted at each step:

  1. Whether to create a backup (default: yes)
  2. Whether to start containers for the backup (if needed)
  3. Where to save the backup archive (if backing up)
  4. Final confirmation before wiping
  5. Whether to start containers after the wipe (default: yes)

Requires an interactive terminal.`,
	RunE: runWipe,
}

func init() {
	rootCmd.AddCommand(wipeCmd)
}

func runWipe(cmd *cobra.Command, _ []string) error {
	if !isInteractive() {
		return fmt.Errorf("wipe requires an interactive terminal (destructive operation)")
	}

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
	if _, err := os.Stat(composePath); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return fmt.Errorf("compose.yml not found in %s -- run 'synthorg init' first", safeDir)
		}
		return fmt.Errorf("cannot access compose.yml in %s: %w", safeDir, err)
	}

	out := ui.NewUI(cmd.OutOrStdout())
	errOut := ui.NewUI(cmd.ErrOrStderr())

	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}

	wc := &wipeContext{
		ctx:     ctx,
		cmd:     cmd,
		state:   state,
		info:    info,
		safeDir: safeDir,
		out:     out,
		errOut:  errOut,
	}

	if err := wc.offerBackup(); err != nil {
		if errors.Is(err, errWipeCancelled) {
			return nil
		}
		return err
	}

	return wc.confirmAndWipe()
}

// confirmAndWipe asks for final confirmation, stops containers, removes
// volumes, and optionally restarts the stack.
func (wc *wipeContext) confirmAndWipe() error {
	confirmed, err := wc.confirmWipe()
	if err != nil {
		return err
	}
	if !confirmed {
		wc.out.Hint("Wipe cancelled.")
		return nil
	}

	sp := wc.out.StartSpinner("Stopping containers and removing volumes...")
	if err := composeRunQuiet(wc.ctx, wc.info, wc.safeDir, "down", "-v"); err != nil {
		sp.Error("Failed to stop containers")
		return fmt.Errorf("stopping containers: %w", err)
	}
	sp.Success("Containers stopped and volumes removed")

	startAfter, err := wc.promptStartAfterWipe()
	if err != nil {
		return err
	}

	if startAfter {
		if err := wc.startContainers(); err != nil {
			wc.errOut.Warn(fmt.Sprintf("Could not restart containers: %v", err))
			startAfter = false // fall through to manual-start hint
		}
	}

	wc.out.Blank()
	wc.out.Success("Factory reset complete")

	if startAfter {
		setupURL := fmt.Sprintf("http://localhost:%d/setup", wc.state.WebPort)
		wc.out.Hint(fmt.Sprintf("Opening %s", setupURL))
		if err := openBrowser(wc.ctx, setupURL); err != nil {
			wc.errOut.Warn(fmt.Sprintf("Could not open browser: %v", err))
			wc.errOut.Hint(fmt.Sprintf("Open %s manually in your browser.", setupURL))
		}
	} else {
		wc.out.Hint("Run 'synthorg start' when you're ready to set up again.")
	}

	return nil
}

// runForm configures a huh form with the wipe context's I/O streams and runs it.
func (wc *wipeContext) runForm(form *huh.Form) error {
	return form.
		WithInput(wc.cmd.InOrStdin()).
		WithOutput(wc.cmd.OutOrStdout()).
		Run()
}

// confirmWipe prompts for final destructive-action confirmation.
func (wc *wipeContext) confirmWipe() (bool, error) {
	var confirmed bool
	err := wc.runForm(huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("This will destroy ALL data (database, memory, settings). Continue?").
			Description("This cannot be undone.").
			Affirmative("Yes, wipe everything").
			Negative("Cancel").
			Value(&confirmed),
	)))
	if err != nil {
		if isUserAbort(err) {
			// Wipe has NOT happened yet, so Ctrl-C is equivalent to
			// choosing "Cancel" -- return false without errWipeCancelled
			// since the caller already handles the !confirmed path.
			return false, nil
		}
		return false, fmt.Errorf("confirmation prompt: %w", err)
	}
	return confirmed, nil
}

// containersRunning reports whether the SynthOrg stack has at least one
// container. A non-nil error indicates that Docker itself could not be
// reached (as opposed to containers simply being stopped).
func (wc *wipeContext) containersRunning() (bool, error) {
	psOut, err := docker.ComposeExecOutput(wc.ctx, wc.info, wc.safeDir, "ps", "--format", "json")
	if err != nil {
		return false, fmt.Errorf("checking container status: %w", err)
	}
	return !isEmptyPS(psOut), nil
}

// startContainers verifies, pulls, and starts the stack, then waits for
// the backend to become healthy.
func (wc *wipeContext) startContainers() error {
	wc.out.Blank()
	if err := verifyAndPinImages(wc.ctx, wc.cmd, wc.state, wc.safeDir, wc.out, wc.errOut); err != nil {
		return err
	}
	wc.out.Blank()
	return pullStartAndWait(wc.ctx, wc.info, wc.safeDir, wc.state, wc.out, wc.errOut)
}

// waitForBackendHealth waits for the backend to become healthy.
// Returns an error if the health check times out.
func (wc *wipeContext) waitForBackendHealth() error {
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", wc.state.BackendPort)
	return health.WaitForHealthy(wc.ctx, healthURL, 30*time.Second, 2*time.Second, 5*time.Second)
}

// offerBackup prompts whether to create a backup, and if so, ensures
// containers are running (prompting if needed), then creates the backup
// via the backend API and copies the archive to a local path.
func (wc *wipeContext) offerBackup() error {
	wantBackup, err := wc.promptForBackup()
	if err != nil {
		return err
	}
	if !wantBackup {
		return nil
	}

	ready, err := wc.ensureRunningForBackup()
	if err != nil {
		return err
	}
	if !ready {
		return nil // user chose to skip backup via askContinueWithoutBackup
	}

	savePath, err := wc.promptSavePath()
	if err != nil {
		return err
	}

	if err := wc.checkOverwrite(savePath); err != nil {
		return err
	}

	return wc.createAndCopyBackup(savePath)
}

// ensureRunningForBackup checks whether containers are running. If not,
// it prompts the user before starting them. If the user declines, it
// falls through to askContinueWithoutBackup (backup cannot proceed
// without running containers). Returns true when the backend is ready
// for a backup, or false when the user chose to skip the backup.
func (wc *wipeContext) ensureRunningForBackup() (bool, error) {
	running, err := wc.containersRunning()
	if err != nil {
		wc.errOut.Warn(fmt.Sprintf("Could not check container status: %v", err))
		if err := wc.askContinueWithoutBackup(
			"Could not check container status. Continue with wipe anyway?",
		); err != nil {
			return false, err
		}
		return false, nil
	}
	if running {
		if err := wc.waitForBackendHealth(); err != nil {
			wc.errOut.Warn(fmt.Sprintf("Backend not healthy: %v", err))
			if err := wc.askContinueWithoutBackup(
				"Backend is not healthy. Continue with wipe anyway?",
			); err != nil {
				return false, err
			}
			return false, nil
		}
		return true, nil
	}

	startOK, err := wc.promptStartForBackup()
	if err != nil {
		return false, err
	}
	if !startOK {
		if err := wc.askContinueWithoutBackup(
			"Backup requires running containers. Continue with wipe anyway?",
		); err != nil {
			return false, err
		}
		return false, nil
	}

	if err := wc.startContainers(); err != nil {
		wc.errOut.Warn(fmt.Sprintf("Could not start containers for backup: %v", err))
		if err := wc.askContinueWithoutBackup(
			"Could not start containers for backup. Continue with wipe anyway?",
		); err != nil {
			return false, err
		}
		return false, nil
	}
	return true, nil
}

// promptStartForBackup asks whether to start containers so a backup
// can be created.
func (wc *wipeContext) promptStartForBackup() (bool, error) {
	startOK := true
	err := wc.runForm(huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Containers are not running. Start them for backup?").
			Affirmative("Yes").
			Negative("No, skip backup").
			Value(&startOK),
	)))
	if err != nil {
		if isUserAbort(err) {
			wc.out.Hint("Wipe cancelled.")
			return false, errWipeCancelled
		}
		return false, fmt.Errorf("start prompt: %w", err)
	}
	return startOK, nil
}

// promptForBackup asks whether the user wants a backup before wiping.
func (wc *wipeContext) promptForBackup() (bool, error) {
	wantBackup := true
	err := wc.runForm(huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Create a backup before wiping? (recommended)").
			Description("Saves your current data so you can restore later.").
			Affirmative("Yes").
			Negative("No, skip").
			Value(&wantBackup),
	)))
	if err != nil {
		if isUserAbort(err) {
			wc.out.Hint("Wipe cancelled.")
			return false, errWipeCancelled
		}
		return false, fmt.Errorf("backup prompt: %w", err)
	}
	return wantBackup, nil
}

// promptSavePath asks the user for a local path to save the backup archive.
func (wc *wipeContext) promptSavePath() (string, error) {
	homeDir, err := os.UserHomeDir()
	if err != nil {
		homeDir = os.TempDir()
	}
	defaultPath := filepath.Join(homeDir, fmt.Sprintf("synthorg-backup-%s.tar.gz", time.Now().Format("20060102-150405")))

	savePath := defaultPath
	if err := wc.runForm(huh.NewForm(huh.NewGroup(
		huh.NewInput().
			Title("Save backup to").
			Description("Path for the backup archive").
			Value(&savePath),
	))); err != nil {
		if isUserAbort(err) {
			wc.out.Hint("Wipe cancelled.")
			return "", errWipeCancelled
		}
		return "", fmt.Errorf("save path prompt: %w", err)
	}
	savePath = strings.TrimSpace(savePath)
	if savePath == "" {
		savePath = defaultPath
	}

	// Expand leading ~ or ~/ to the user's home directory.
	if savePath == "~" {
		savePath = homeDir
	} else if strings.HasPrefix(savePath, "~/") || strings.HasPrefix(savePath, "~\\") {
		savePath = filepath.Join(homeDir, savePath[2:])
	}

	savePath = filepath.Clean(savePath)
	absPath, err := filepath.Abs(savePath)
	if err != nil {
		return "", fmt.Errorf("resolving save path: %w", err)
	}
	return absPath, nil
}

// checkOverwrite warns and prompts if the save path already exists.
// Note: there is an inherent TOCTOU race between this check and the
// eventual write (in tarDirectory or docker compose cp). For a local CLI
// tool this is acceptable -- the race requires a co-located malicious
// process, and resolving it would require restructuring both write paths.
func (wc *wipeContext) checkOverwrite(path string) error {
	_, err := os.Stat(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil // file does not exist -- safe to write
		}
		return fmt.Errorf("cannot access save path: %w", err)
	}
	var overwrite bool
	err = wc.runForm(huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title(fmt.Sprintf("File already exists: %s. Overwrite?", filepath.Base(path))).
			Affirmative("Yes, overwrite").
			Negative("Cancel").
			Value(&overwrite),
	)))
	if err != nil {
		if isUserAbort(err) {
			wc.out.Hint("Wipe cancelled.")
			return errWipeCancelled
		}
		return fmt.Errorf("overwrite prompt: %w", err)
	}
	if !overwrite {
		wc.out.Hint("Wipe cancelled.")
		return errWipeCancelled
	}
	return nil
}

// createAndCopyBackup creates a backup via the API and copies it locally.
func (wc *wipeContext) createAndCopyBackup(savePath string) error {
	sp := wc.out.StartSpinner("Creating backup...")
	manifest, err := createBackupViaAPI(wc.ctx, wc.state)
	if err != nil {
		sp.Error("Backup failed")
		wc.errOut.Warn(fmt.Sprintf("Could not create backup: %v", err))
		return wc.askContinueWithoutBackup("Backup failed. Continue with wipe anyway?")
	}
	sp.Success("Backup created")

	sp = wc.out.StartSpinner("Copying backup to local path...")
	if err := copyBackupFromContainer(wc.ctx, wc.info, wc.safeDir, manifest.BackupID, savePath); err != nil {
		sp.Error("Failed to copy backup")
		wc.errOut.Warn(fmt.Sprintf("Could not copy backup locally: %v", err))
		wc.errOut.Hint("The backup exists in the container but will be lost after wipe.")
		return wc.askContinueWithoutBackup("Backup failed. Continue with wipe anyway?")
	}
	sp.Success(fmt.Sprintf("Backup saved to %s", savePath))

	return nil
}

// createBackupViaAPI triggers a manual backup and returns the manifest.
func createBackupViaAPI(ctx context.Context, state config.State) (backupManifest, error) {
	body, statusCode, err := backupAPIRequest(
		ctx, state.BackendPort, http.MethodPost, "", nil,
		60*time.Second, state.JWTSecret,
	)
	if err != nil {
		return backupManifest{}, fmt.Errorf("backup API request: %w", err)
	}
	if statusCode < 200 || statusCode >= 300 {
		msg := apiErrorMessage(body, "backup failed")
		return backupManifest{}, fmt.Errorf("backup API error: %s", sanitizeAPIMessage(msg))
	}

	data, err := parseAPIResponse(body)
	if err != nil {
		return backupManifest{}, fmt.Errorf("parsing backup response: %w", err)
	}

	var manifest backupManifest
	if err := json.Unmarshal(data, &manifest); err != nil {
		return backupManifest{}, fmt.Errorf("parsing backup manifest: %w", err)
	}
	return manifest, nil
}

// copyBackupFromContainer copies the backup archive from the backend
// container to a local path. It tries the compressed archive first,
// then falls back to the uncompressed directory.
func copyBackupFromContainer(ctx context.Context, info docker.Info, safeDir, backupID, localPath string) error {
	// Validate backup ID format (12 hex chars).
	if !isValidBackupID(backupID) {
		return fmt.Errorf("invalid backup ID: %s", backupID)
	}

	// Try compressed archive first (default).
	archiveName := backupID + "_manual.tar.gz"
	containerSrc := "backend:/data/backups/" + archiveName
	err := composeRunQuiet(ctx, info, safeDir, "cp", containerSrc, localPath)
	if err == nil {
		return nil
	}

	// Fall back to uncompressed directory -- copy to a temp dir, then
	// tar it locally so the user gets a single file either way.
	dirName := backupID + "_manual"
	containerSrc = "backend:/data/backups/" + dirName + "/."
	tmpDir, mkErr := os.MkdirTemp("", "synthorg-backup-*")
	if mkErr != nil {
		return fmt.Errorf("creating temp dir: %w", mkErr)
	}
	defer func() { _ = os.RemoveAll(tmpDir) }()

	if err := composeRunQuiet(ctx, info, safeDir, "cp", containerSrc, tmpDir+"/"); err != nil {
		return fmt.Errorf("copying backup from container: %w", err)
	}

	// The user expects a single file at localPath.
	return tarDirectory(tmpDir, localPath)
}

// tarDirectory creates a tar.gz archive of the contents of srcDir at dstPath.
func tarDirectory(srcDir, dstPath string) error {
	entries, err := os.ReadDir(srcDir)
	if err != nil {
		return fmt.Errorf("reading backup dir: %w", err)
	}
	if len(entries) == 0 {
		return fmt.Errorf("backup directory is empty")
	}

	dstPath = filepath.Clean(dstPath)
	f, err := os.OpenFile(dstPath, os.O_WRONLY|os.O_CREATE|os.O_TRUNC, 0o600)
	if err != nil {
		return fmt.Errorf("creating archive: %w", err)
	}

	if err := createTarGz(f, srcDir); err != nil {
		_ = f.Close()
		_ = os.Remove(dstPath)
		return err
	}
	if err := f.Close(); err != nil {
		_ = os.Remove(dstPath)
		return fmt.Errorf("finalising archive: %w", err)
	}
	return nil
}

// askContinueWithoutBackup prompts whether to proceed with the wipe even
// though the backup could not be created. The title parameter customises
// the prompt to match the reason (e.g. user declined, Docker unreachable,
// container start failure). Returns nil to continue, or errWipeCancelled
// to abort the wipe cleanly.
func (wc *wipeContext) askContinueWithoutBackup(title string) error {
	var proceed bool
	err := wc.runForm(huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title(title).
			Description("All data will be lost without a backup.").
			Affirmative("Yes, continue").
			Negative("Cancel").
			Value(&proceed),
	)))
	if err != nil {
		if isUserAbort(err) {
			wc.out.Hint("Wipe cancelled.")
			return errWipeCancelled
		}
		return fmt.Errorf("continue prompt: %w", err)
	}
	if !proceed {
		wc.out.Hint("Wipe cancelled.")
		return errWipeCancelled
	}
	return nil
}

// promptStartAfterWipe asks whether to start containers after the wipe.
// Ctrl-C is treated as "No" because the wipe has already completed.
func (wc *wipeContext) promptStartAfterWipe() (bool, error) {
	startAfter := true
	err := wc.runForm(huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Start containers now?").
			Description("Opens the setup wizard for a fresh start.").
			Affirmative("Yes").
			Negative("No").
			Value(&startAfter),
	)))
	if err != nil {
		if isUserAbort(err) {
			return false, nil // wipe already done, treat Ctrl-C as "No"
		}
		return false, fmt.Errorf("start-after-wipe prompt: %w", err)
	}
	return startAfter, nil
}

// isEmptyPS returns true if docker compose ps output indicates no containers.
// Handles both JSON array format (Compose v2.21+) and NDJSON (older versions).
func isEmptyPS(output string) bool {
	trimmed := strings.TrimSpace(output)
	if trimmed == "" {
		return true
	}
	// JSON array format (Compose v2.21+).
	if strings.HasPrefix(trimmed, "[") {
		var arr []json.RawMessage
		return json.Unmarshal([]byte(trimmed), &arr) == nil && len(arr) == 0
	}
	// NDJSON: any non-empty line means at least one container.
	return false
}

// openBrowser opens a URL in the default browser. Only localhost HTTP(S)
// URLs are permitted to prevent arbitrary command execution.
func openBrowser(ctx context.Context, rawURL string) error {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return fmt.Errorf("invalid URL %q: %w", rawURL, err)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return fmt.Errorf("refusing to open URL with scheme %q -- only http and https are allowed", parsed.Scheme)
	}
	host := parsed.Hostname()
	if host != "localhost" && host != "127.0.0.1" {
		return fmt.Errorf("refusing to open URL with host %q -- only localhost and 127.0.0.1 are allowed", host)
	}

	// Use the re-serialized URL, not the raw input string, to ensure
	// only the normalized, validated URL is passed to the OS launcher.
	normalizedURL := parsed.String()

	var c *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		c = exec.CommandContext(ctx, "rundll32", "url.dll,FileProtocolHandler", normalizedURL)
	case "darwin":
		c = exec.CommandContext(ctx, "open", normalizedURL)
	default:
		c = exec.CommandContext(ctx, "xdg-open", normalizedURL)
	}
	if err := c.Start(); err != nil {
		return fmt.Errorf("starting browser: %w", err)
	}
	go func() { _ = c.Wait() }() // reap child, prevent zombie
	return nil
}

// createTarGz writes a gzip-compressed tar archive of srcDir's contents to w.
// Symlinks are skipped to prevent following links outside the source directory.
func createTarGz(w io.Writer, srcDir string) error {
	gw := gzip.NewWriter(w)
	tw := tar.NewWriter(gw)

	walkErr := filepath.WalkDir(srcDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.Type()&fs.ModeSymlink != 0 {
			return nil // skip symlinks
		}
		rel, err := filepath.Rel(srcDir, path)
		if err != nil {
			return err
		}
		if rel == "." {
			return nil
		}
		return writeTarEntry(tw, path, rel, d)
	})

	// Close tar then gzip; errors.Join reports all errors.
	errTar := tw.Close()
	errGzip := gw.Close()
	return errors.Join(walkErr, errTar, errGzip)
}

// writeTarEntry writes a single directory or file entry into the tar writer.
// It normalizes the path, validates against traversal, and strips host identity.
func writeTarEntry(tw *tar.Writer, path, rel string, d fs.DirEntry) error {
	fi, err := d.Info()
	if err != nil {
		return fmt.Errorf("stat %s: %w", rel, err)
	}

	header, err := tar.FileInfoHeader(fi, "")
	if err != nil {
		return fmt.Errorf("creating tar header for %s: %w", rel, err)
	}

	// Normalize path and validate against traversal.
	cleanRel := filepath.ToSlash(filepath.Clean(rel))
	if strings.HasPrefix(cleanRel, "..") {
		return fmt.Errorf("refusing to archive path with traversal component: %s", rel)
	}
	header.Name = cleanRel

	// Strip host identity to avoid information disclosure and permission
	// mismatch when the archive is restored on a different machine.
	header.Uid = 0
	header.Gid = 0
	header.Uname = ""
	header.Gname = ""

	if err := tw.WriteHeader(header); err != nil {
		return fmt.Errorf("writing tar header for %s: %w", rel, err)
	}

	if d.IsDir() {
		return nil
	}

	return addFileToTar(tw, path, rel)
}

// addFileToTar copies a single file into the tar writer.
func addFileToTar(tw *tar.Writer, path, rel string) error {
	f, err := os.Open(path)
	if err != nil {
		return fmt.Errorf("opening %s: %w", rel, err)
	}

	_, copyErr := io.Copy(tw, f)
	if err := f.Close(); err != nil && copyErr == nil {
		return fmt.Errorf("closing %s: %w", rel, err)
	}
	if copyErr != nil {
		return fmt.Errorf("writing %s to archive: %w", rel, copyErr)
	}
	return nil
}

// isUserAbort returns true if the error is a huh user-abort (Ctrl-C/Esc).
func isUserAbort(err error) bool {
	return errors.Is(err, huh.ErrUserAborted)
}
