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
	Short: "Factory-reset: wipe all data and re-open the setup wizard",
	Long: `Destroy all SynthOrg data (database, memory, settings) and restart
with a clean slate. The setup wizard opens automatically after the reset.

Before wiping, you are offered the option to create a backup and save
it to a local path. Requires an interactive terminal.`,
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
	if _, err := os.Stat(composePath); errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("compose.yml not found in %s -- run 'synthorg init' first", safeDir)
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

	if err := wc.ensureRunning(); err != nil {
		return err
	}

	if err := wc.offerBackup(); err != nil {
		if errors.Is(err, errWipeCancelled) {
			return nil
		}
		return err
	}

	return wc.confirmAndWipe()
}

// confirmAndWipe asks for final confirmation, then stops containers,
// removes volumes, starts fresh, and opens the setup wizard.
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

	wc.out.Blank()
	if err := pullStartAndWait(wc.ctx, wc.info, wc.safeDir, wc.state, wc.out, wc.errOut); err != nil {
		return err
	}

	wc.out.Blank()
	setupURL := fmt.Sprintf("http://localhost:%d/setup", wc.state.WebPort)
	wc.out.Success("Factory reset complete")
	wc.out.Hint(fmt.Sprintf("Opening %s", setupURL))
	if err := openBrowser(wc.ctx, setupURL); err != nil {
		wc.errOut.Warn(fmt.Sprintf("Could not open browser: %v", err))
		wc.errOut.Hint(fmt.Sprintf("Open %s manually in your browser.", setupURL))
	}

	return nil
}

// confirmWipe prompts for final destructive-action confirmation.
func (wc *wipeContext) confirmWipe() (bool, error) {
	var confirmed bool
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("This will destroy ALL data (database, memory, settings). Continue?").
			Description("This cannot be undone.").
			Affirmative("Yes, wipe everything").
			Negative("Cancel").
			Value(&confirmed),
	))
	form.WithInput(wc.cmd.InOrStdin())
	form.WithOutput(wc.cmd.OutOrStdout())
	if err := form.Run(); err != nil {
		if isUserAbort(err) {
			return false, nil // treat Ctrl-C as "Cancel"
		}
		return false, fmt.Errorf("confirmation prompt: %w", err)
	}
	return confirmed, nil
}

// ensureRunning checks whether the SynthOrg stack is running. If not, it
// starts the stack (pull, verify, up, health-wait) so the backup API is
// available before wiping.
func (wc *wipeContext) ensureRunning() error {
	psOut, err := docker.ComposeExecOutput(wc.ctx, wc.info, wc.safeDir, "ps", "--format", "json")
	if err != nil || isEmptyPS(psOut) {
		wc.out.Hint("Containers are not running -- starting them for backup...")
		wc.out.Blank()
		if err := verifyAndPinImages(wc.ctx, wc.cmd, wc.state, wc.safeDir, wc.out, wc.errOut); err != nil {
			return err
		}
		wc.out.Blank()
		return pullStartAndWait(wc.ctx, wc.info, wc.safeDir, wc.state, wc.out, wc.errOut)
	}

	// Containers exist but backend may not be healthy yet.
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", wc.state.BackendPort)
	if err := health.WaitForHealthy(wc.ctx, healthURL, 30*time.Second, 2*time.Second, 5*time.Second); err != nil {
		wc.errOut.Warn(fmt.Sprintf("Backend not healthy -- backup may not be available: %v", err))
	}
	return nil
}

// offerBackup prompts whether to create a backup, and if so, creates one
// via the backend API and copies the archive to a local path.
func (wc *wipeContext) offerBackup() error {
	wantBackup, err := wc.promptForBackup()
	if err != nil {
		return err
	}
	if !wantBackup {
		return nil
	}

	savePath, err := wc.promptSavePath()
	if err != nil {
		return err
	}

	return wc.createAndCopyBackup(savePath)
}

// promptForBackup asks whether the user wants a backup before wiping.
func (wc *wipeContext) promptForBackup() (bool, error) {
	var wantBackup bool
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Create a backup before wiping? (recommended)").
			Description("Saves your current data so you can restore later.").
			Affirmative("Yes").
			Negative("No, skip").
			Value(&wantBackup),
	))
	form.WithInput(wc.cmd.InOrStdin())
	form.WithOutput(wc.cmd.OutOrStdout())
	if err := form.Run(); err != nil {
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
	pathForm := huh.NewForm(huh.NewGroup(
		huh.NewInput().
			Title("Save backup to").
			Description("Path for the backup archive").
			Value(&savePath),
	))
	pathForm.WithInput(wc.cmd.InOrStdin())
	pathForm.WithOutput(wc.cmd.OutOrStdout())
	if err := pathForm.Run(); err != nil {
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

// createAndCopyBackup creates a backup via the API and copies it locally.
func (wc *wipeContext) createAndCopyBackup(savePath string) error {
	sp := wc.out.StartSpinner("Creating backup...")
	manifest, err := createBackupViaAPI(wc.ctx, wc.state)
	if err != nil {
		sp.Error("Backup failed")
		wc.errOut.Warn(fmt.Sprintf("Could not create backup: %v", err))
		return wc.askContinueWithoutBackup()
	}
	sp.Success("Backup created")

	sp = wc.out.StartSpinner("Copying backup to local path...")
	if err := copyBackupFromContainer(wc.ctx, wc.info, wc.safeDir, manifest.BackupID, savePath); err != nil {
		sp.Error("Failed to copy backup")
		wc.errOut.Warn(fmt.Sprintf("Could not copy backup locally: %v", err))
		return wc.askContinueWithoutBackup()
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
	return f.Close()
}

// askContinueWithoutBackup prompts whether to proceed with the wipe even
// though the backup failed. Returns nil to continue, or errWipeCancelled
// to abort the wipe cleanly.
func (wc *wipeContext) askContinueWithoutBackup() error {
	var proceed bool
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().
			Title("Backup failed. Continue with wipe anyway?").
			Description("All data will be lost without a backup.").
			Affirmative("Yes, continue").
			Negative("Cancel").
			Value(&proceed),
	))
	form.WithInput(wc.cmd.InOrStdin())
	form.WithOutput(wc.cmd.OutOrStdout())
	if err := form.Run(); err != nil {
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

		// Skip symlinks to prevent following links outside the source.
		if d.Type()&fs.ModeSymlink != 0 {
			return nil
		}

		rel, err := filepath.Rel(srcDir, path)
		if err != nil {
			return err
		}
		if rel == "." {
			return nil
		}

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
	})

	// Close tar then gzip; errors.Join reports all errors.
	errTar := tw.Close()
	errGzip := gw.Close()
	return errors.Join(walkErr, errTar, errGzip)
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
