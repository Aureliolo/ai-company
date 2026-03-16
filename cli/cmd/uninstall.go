package cmd

import (
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
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
	out := cmd.OutOrStdout()

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
		_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: Docker not available, cannot stop containers: %v\n", dockerErr)
	} else {
		if err := stopAndRemoveVolumes(cmd, info, safeDir); err != nil {
			return err
		}
	}

	// Remove data directory.
	if err := confirmAndRemoveData(cmd, safeDir); err != nil {
		return err
	}

	// Optionally remove CLI binary.
	if err := confirmAndRemoveBinary(cmd); err != nil {
		return err
	}

	_, _ = fmt.Fprintln(out, "SynthOrg uninstalled.")
	return nil
}

func stopAndRemoveVolumes(cmd *cobra.Command, info docker.Info, dataDir string) error {
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

	_, _ = fmt.Fprintln(cmd.OutOrStdout(), "Stopping containers...")

	// Use "down -v" if removing volumes (handles both stop and volume removal
	// in a single command), otherwise just "down".
	downArgs := []string{"down"}
	if removeVolumes {
		downArgs = append(downArgs, "-v")
		_, _ = fmt.Fprintln(cmd.OutOrStdout(), "Removing volumes...")
	}

	if err := composeRun(ctx, cmd, info, dataDir, downArgs...); err != nil {
		return fmt.Errorf("stopping containers: %w", err)
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

	if removeData {
		dir := filepath.Clean(dataDir)
		// Safety: refuse to remove root, home, UNC share roots, or drive roots.
		home, homeErr := os.UserHomeDir()
		if homeErr != nil {
			_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: cannot determine home directory: %v\n", homeErr)
		}
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
			return fmt.Errorf("refusing to remove %q — does not look like an app data directory", dir)
		}

		// On Windows the running binary cannot be deleted. If it lives
		// inside the config directory, remove everything else and leave
		// the binary for deferred cleanup in confirmAndRemoveBinary.
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
			_, _ = fmt.Fprintf(cmd.OutOrStdout(), "Removed contents of %s (binary skipped — still running)\n", dir)
		} else {
			if err := os.RemoveAll(dir); err != nil {
				return fmt.Errorf("removing config directory: %w", err)
			}
			_, _ = fmt.Fprintf(cmd.OutOrStdout(), "Removed %s\n", dir)
		}
	}
	return nil
}

func confirmAndRemoveBinary(cmd *cobra.Command) error {
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

	if removeBinary {
		execPath, err := os.Executable()
		if err != nil {
			return fmt.Errorf("finding executable: %w", err)
		}
		// Resolve symlinks so we remove the actual binary.
		if resolved, err := filepath.EvalSymlinks(execPath); err == nil {
			execPath = resolved
		}
		if runtime.GOOS == "windows" {
			_, _ = fmt.Fprintln(cmd.OutOrStdout(), "Cannot delete running binary on Windows.")
			_, _ = fmt.Fprintln(cmd.OutOrStdout(), "To finish cleanup after exit, run:")
			// Use PowerShell Remove-Item -LiteralPath which does not interpret
			// wildcards or cmd.exe metacharacters (%, ^, &, |, <, >).
			escaped := strings.ReplaceAll(execPath, "'", "''")
			_, _ = fmt.Fprintf(cmd.OutOrStdout(), "  powershell -Command \"Remove-Item -LiteralPath '%s'\"\n", escaped)
		} else {
			if err := os.Remove(execPath); err != nil {
				_, _ = fmt.Fprintf(cmd.ErrOrStderr(), "Warning: could not remove binary: %v\n", err)
				_, _ = fmt.Fprintf(cmd.OutOrStdout(), "Manually remove: %s\n", execPath)
			} else {
				_, _ = fmt.Fprintln(cmd.OutOrStdout(), "CLI binary removed.")
			}
		}
	}
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
		// Skip root itself — we only remove contents, not the root directory.
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
