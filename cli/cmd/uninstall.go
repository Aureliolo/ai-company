package cmd

import (
	"context"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/completion"
	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"
)

var uninstallCmd = &cobra.Command{
	Use:   "uninstall",
	Short: "Stop containers, remove data, and uninstall SynthOrg",
	RunE:  runUninstall,
}

func init() {
	rootCmd.AddCommand(uninstallCmd)
}

func runUninstall(cmd *cobra.Command, _ []string) error {
	if !isInteractive() {
		return fmt.Errorf("uninstall requires an interactive terminal (destructive operation)")
	}

	ctx := cmd.Context()
	dir := resolveDataDir()
	out := ui.NewUI(cmd.OutOrStdout())
	errUI := ui.NewUI(cmd.ErrOrStderr())

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}

	// Stop containers and optionally remove volumes.
	info, dockerErr := docker.Detect(ctx)
	if dockerErr != nil {
		errUI.Warn(fmt.Sprintf("Docker not available, cannot stop containers: %v", dockerErr))
	} else {
		if err := stopAndRemoveVolumes(cmd, info, safeDir, out); err != nil {
			return err
		}
		// Offer to remove SynthOrg container images.
		if err := confirmAndRemoveImages(cmd, info, out, errUI); err != nil {
			return err
		}
	}

	// Remove data directory.
	if err := confirmAndRemoveData(cmd, safeDir); err != nil {
		return err
	}

	// Remove shell completion snippets for all supported shells
	// (user may have installed completions for multiple shells).
	sp := out.StartSpinner("Removing shell completions...")
	for _, shell := range []completion.ShellType{
		completion.Bash, completion.Zsh, completion.Fish, completion.PowerShell,
	} {
		if err := completion.Uninstall(ctx, shell); err != nil {
			errUI.Warn(fmt.Sprintf("Could not remove %s completions: %v", shell, err))
		}
	}
	sp.Success("Shell completions removed")

	// Optionally remove CLI binary.
	if err := confirmAndRemoveBinary(cmd, safeDir); err != nil {
		return err
	}

	out.Blank()
	out.Success("SynthOrg uninstalled.")
	return nil
}

func stopAndRemoveVolumes(cmd *cobra.Command, info docker.Info, dataDir string, out *ui.UI) error {
	ctx := cmd.Context()

	var removeVolumes bool
	form := huh.NewForm(
		huh.NewGroup(
			huh.NewConfirm().
				Title("Remove Docker volumes? (ALL DATA WILL BE LOST)").
				Description("This removes the persistent database and memory data.").
				Value(&removeVolumes),
		),
	)
	if err := form.Run(); err != nil {
		return err
	}

	downArgs := []string{"down"}
	if removeVolumes {
		downArgs = append(downArgs, "-v")
	}

	sp := out.StartSpinner("Stopping containers...")
	if err := composeRunQuiet(ctx, info, dataDir, downArgs...); err != nil {
		sp.Error("Failed to stop containers")
		return fmt.Errorf("stopping containers: %w", err)
	}
	msg := "Containers stopped"
	if removeVolumes {
		msg += " and volumes removed"
	}
	sp.Success(msg)

	return nil
}

// confirmAndRemoveImages offers to remove SynthOrg container images.
// Lists images deduplicated by Docker ID with digest info for identification.
func confirmAndRemoveImages(cmd *cobra.Command, info docker.Info, out, errUI *ui.UI) error {
	ctx := cmd.Context()

	// List all SynthOrg images with deduplication by Docker ID.
	imageRef := "ghcr.io/aureliolo/synthorg-*"
	allOut, err := docker.RunCmd(ctx, info.DockerPath, "images",
		"--filter", "reference="+imageRef,
		"--format", "{{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.ID}}\t{{.Digest}}")
	if err != nil {
		errUI.Warn(fmt.Sprintf("Could not list images: %v", err))
		return nil
	}

	type imageEntry struct {
		display string
		id      string
	}
	var images []imageEntry
	seen := make(map[string]bool)
	for _, line := range strings.Split(strings.TrimSpace(strings.ReplaceAll(allOut, "\r\n", "\n")), "\n") {
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "\t", 5)
		if len(parts) < 5 {
			continue
		}
		repo, tag, sizeStr, id, digest := parts[0], parts[1], parts[2], parts[3], parts[4]
		if !isValidDockerID(id) || seen[id] {
			continue
		}
		seen[id] = true
		display := buildImageDisplay(repo, tag, digest, sizeStr)
		images = append(images, imageEntry{display: display, id: id})
	}

	if len(images) == 0 {
		out.Success("No SynthOrg images found locally.")
		return nil
	}

	var lines []string
	for _, img := range images {
		lines = append(lines, img.display)
	}
	out.Box("SynthOrg Images", lines)
	out.Blank()

	var removeImages bool
	form := huh.NewForm(
		huh.NewGroup(
			huh.NewConfirm().
				Title(fmt.Sprintf("Remove %d image(s)?", len(images))).
				Value(&removeImages),
		),
	)
	if err := form.Run(); err != nil {
		return err
	}
	if !removeImages {
		return nil
	}

	// Remove images one at a time for granular feedback.
	var removed int
	for _, img := range images {
		_, rmiErr := docker.RunCmd(ctx, info.DockerPath, "rmi", "--force", img.id)
		if rmiErr != nil {
			out.Warn(fmt.Sprintf("%-12s skipped (in use)", img.id))
		} else {
			out.Success(fmt.Sprintf("%-12s removed", img.id))
			removed++
		}
	}
	if removed > 0 {
		out.Success(fmt.Sprintf("Removed %d image(s)", removed))
	}

	return nil
}

func confirmAndRemoveData(cmd *cobra.Command, dataDir string) error {
	var removeData bool
	form := huh.NewForm(
		huh.NewGroup(
			huh.NewConfirm().
				Title(fmt.Sprintf("Remove config directory? (%s)", dataDir)).
				Value(&removeData),
		),
	)
	if err := form.Run(); err != nil {
		return err
	}
	if !removeData {
		return nil
	}
	dir := filepath.Clean(dataDir)
	if err := rejectUnsafeDir(dir); err != nil {
		return err
	}
	return removeDataDir(cmd, dir)
}

// rejectUnsafeDir refuses to remove root, home, relative, UNC share roots, or drive roots.
func rejectUnsafeDir(dir string) error {
	if dir == "" || dir == "." || !filepath.IsAbs(dir) {
		return fmt.Errorf("refusing to remove %q -- must be an absolute path", dir)
	}
	home, homeErr := os.UserHomeDir()
	isHomeDir := false
	if homeErr == nil {
		home = filepath.Clean(home)
		if runtime.GOOS == "windows" {
			isHomeDir = strings.EqualFold(dir, home)
		} else {
			isHomeDir = dir == home
		}
	}
	vol := filepath.VolumeName(dir)
	// Only reject UNC share roots (e.g. \\server\share), not arbitrary
	// paths under a UNC share (e.g. \\server\share\synthorg\data).
	isUNCRoot := vol != "" &&
		(strings.HasPrefix(vol, `\\`) || strings.HasPrefix(vol, "//")) &&
		(dir == vol || dir == vol+`\` || dir == vol+"/")
	isDriveRoot := len(dir) == 3 && dir[1] == ':' && (dir[2] == '\\' || dir[2] == '/')
	if dir == "/" || isHomeDir || isDriveRoot || isUNCRoot {
		return fmt.Errorf("refusing to remove %q -- does not look like an app data directory", dir)
	}
	return nil
}

// removeDataDir removes the data directory. On Windows, if the running
// binary lives inside the directory, it removes everything except the binary.
func removeDataDir(cmd *cobra.Command, dir string) error {
	out := ui.NewUI(cmd.OutOrStdout())
	execPath, execErr := os.Executable()
	if execErr != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: cannot resolve executable path: %v\n", execErr)
	}
	if execErr == nil {
		if resolved, err := filepath.EvalSymlinks(execPath); err == nil {
			execPath = resolved
		}
	}
	if execErr == nil && runtime.GOOS == "windows" && isInsideDir(execPath, dir) {
		if err := removeAllExcept(dir, execPath); err != nil {
			return fmt.Errorf("removing config directory: %w", err)
		}
		out.Success(fmt.Sprintf("Removed contents of %s (binary skipped -- still running)", dir))
	} else {
		if err := os.RemoveAll(dir); err != nil {
			return fmt.Errorf("removing config directory: %w", err)
		}
		out.Success(fmt.Sprintf("Removed %s", dir))
	}
	return nil
}

// confirmAndRemoveBinary asks to remove the CLI binary. On Windows, spawns
// a detached process that waits for the current process to exit, then
// deletes the binary and cleans up empty parent directories.
func confirmAndRemoveBinary(cmd *cobra.Command, dataDir string) error {
	var removeBinary bool
	form := huh.NewForm(
		huh.NewGroup(
			huh.NewConfirm().
				Title("Remove CLI binary?").
				Description("You can reinstall later from GitHub Releases.").
				Value(&removeBinary),
		),
	)
	if err := form.Run(); err != nil {
		return err
	}

	if !removeBinary {
		return nil
	}

	execPath, err := os.Executable()
	if err != nil {
		return fmt.Errorf("finding executable: %w", err)
	}
	// Resolve symlinks so we remove the actual binary.
	if resolved, err := filepath.EvalSymlinks(execPath); err == nil {
		execPath = resolved
	}

	if runtime.GOOS != "windows" {
		return removeUnixBinary(cmd, execPath)
	}
	return scheduleWindowsCleanup(cmd, execPath, dataDir)
}

func removeUnixBinary(cmd *cobra.Command, execPath string) error {
	out := ui.NewUI(cmd.OutOrStdout())
	if err := os.Remove(execPath); err != nil {
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: could not remove binary: %v\n", err)
		out.Hint(fmt.Sprintf("Manually remove: %s", execPath))
	} else {
		out.Success("CLI binary removed")
	}
	return nil
}

// scheduleWindowsCleanup writes a temporary .bat file that waits for the
// current process to exit, then deletes the binary, empty parent dirs,
// and the .bat file itself. Uses a temp .bat instead of inline cmd /c
// because goto/labels don't work in single-line cmd /c commands.
func scheduleWindowsCleanup(cmd *cobra.Command, execPath, dataDir string) error {
	out := ui.NewUI(cmd.OutOrStdout())
	pid := os.Getpid()
	binDir := filepath.Dir(execPath)

	// Write cleanup script to a temp .bat file next to the binary
	// (same filesystem, survives after this process exits).
	batContent := fmt.Sprintf(
		"@echo off\r\n"+
			"for /L %%%%i in (1,1,30) do (\r\n"+
			"  tasklist /fi \"PID eq %d\" 2>nul | find \"%d\" >nul || goto :cleanup\r\n"+
			"  timeout /t 1 /nobreak >nul\r\n"+
			")\r\n"+
			"goto :done\r\n"+
			":cleanup\r\n"+
			"del /f /q \"%s\"\r\n"+
			"rmdir \"%s\" 2>nul\r\n"+
			"rmdir \"%s\" 2>nul\r\n"+
			":done\r\n"+
			"del /f /q \"%%~f0\"\r\n",
		pid, pid,
		execPath,
		binDir,
		dataDir,
	)

	batFile, err := os.CreateTemp(binDir, "synthorg-cleanup-*.bat")
	if err != nil {
		return fallbackManualCleanup(cmd, execPath, err)
	}
	batPath := batFile.Name()
	if _, err := batFile.WriteString(batContent); err != nil {
		_ = batFile.Close()
		_ = os.Remove(batPath)
		return fallbackManualCleanup(cmd, execPath, err)
	}
	if err := batFile.Close(); err != nil {
		_ = os.Remove(batPath)
		return fallbackManualCleanup(cmd, execPath, err)
	}

	// Spawn detached -- use context.Background so parent context
	// cancellation doesn't kill the cleanup process.
	c := exec.CommandContext(context.Background(), "cmd.exe", "/c", batPath) //nolint:noctx // intentionally detached
	c.SysProcAttr = windowsDetachedProcAttr()
	if err := c.Start(); err != nil {
		_ = os.Remove(batPath)
		return fallbackManualCleanup(cmd, execPath, err)
	}

	// Detach -- don't wait for the cleanup process.
	_ = c.Process.Release()

	out.Success("CLI binary will be removed automatically after exit")
	return nil
}

func fallbackManualCleanup(cmd *cobra.Command, execPath string, cause error) error {
	out := ui.NewUI(cmd.OutOrStdout())
	out.Warn(fmt.Sprintf("Could not schedule automatic cleanup: %v", cause))
	escaped := strings.ReplaceAll(execPath, "'", "''")
	out.Hint(fmt.Sprintf("To finish cleanup after exit, run: powershell -Command \"Remove-Item -LiteralPath '%s'\"", escaped))
	return nil
}

// isInsideDir reports whether child is inside (or equal to) parent.
// On Windows, the comparison is case-insensitive (NTFS is case-insensitive).
// Note: strings.ToLower is correct for ASCII paths; non-ASCII Unicode paths
// on NTFS could require full Unicode case-folding (golang.org/x/text/cases),
// but Windows user profile and app-data paths are overwhelmingly ASCII.
func isInsideDir(child, parent string) bool {
	child = filepath.Clean(child)
	parent = filepath.Clean(parent)
	// Case-fold on Windows so that C:\Foo and C:\foo are treated as equal.
	if runtime.GOOS == "windows" {
		child = strings.ToLower(child)
		parent = strings.ToLower(parent)
	}
	rel, err := filepath.Rel(parent, child)
	if err != nil {
		return false
	}
	return !strings.HasPrefix(rel, "..")
}

type walkEntry struct {
	path  string
	isDir bool
}

// removeAllExcept removes all files and directories under root except the
// file at except (and its ancestor directories up to root). The root
// directory itself is preserved. Entries are removed deepest-first so
// that empty directories are cleaned up.
func removeAllExcept(root, except string) error {
	root = filepath.Clean(root)
	except = filepath.Clean(except)

	// Case-fold for comparison on Windows (NTFS is case-insensitive).
	exceptCmp := except
	if runtime.GOOS == "windows" {
		exceptCmp = strings.ToLower(except)
	}

	var entries []walkEntry
	err := filepath.WalkDir(root, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		cleanPath := filepath.Clean(path)
		// Skip root itself -- we only remove contents, not the root directory.
		if cleanPath == root {
			return nil
		}
		cmpPath := cleanPath
		if runtime.GOOS == "windows" {
			cmpPath = strings.ToLower(cleanPath)
		}
		if cmpPath == exceptCmp {
			return nil // skip the excluded file
		}
		entries = append(entries, walkEntry{path: path, isDir: d.IsDir()})
		return nil
	})
	if err != nil {
		return err
	}

	// Remove in reverse order (deepest first). Directory removal failures
	// are expected for ancestors of the excluded file (non-empty); other
	// errors (files, permission-denied dirs) are collected and reported.
	var errs []error
	for i := len(entries) - 1; i >= 0; i-- {
		if err := os.Remove(entries[i].path); err != nil {
			if entries[i].isDir && isInsideDir(except, entries[i].path) {
				continue // expected: ancestor of excluded file is non-empty
			}
			errs = append(errs, err)
		}
	}
	return errors.Join(errs...)
}
