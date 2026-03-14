// Package config handles CLI configuration, data directory resolution, and
// persisted state.
package config

import (
	"os"
	"path/filepath"
	"runtime"
)

const appDirName = "synthorg"

// DataDir returns the default data directory for the current platform:
//   - Linux:   $XDG_DATA_HOME/synthorg or ~/.local/share/synthorg
//   - macOS:   ~/Library/Application Support/synthorg
//   - Windows: %LOCALAPPDATA%\synthorg
func DataDir() string {
	switch runtime.GOOS {
	case "darwin":
		home, _ := os.UserHomeDir()
		return filepath.Join(home, "Library", "Application Support", appDirName)
	case "windows":
		if dir := os.Getenv("LOCALAPPDATA"); dir != "" {
			return filepath.Join(dir, appDirName)
		}
		home, _ := os.UserHomeDir()
		return filepath.Join(home, "AppData", "Local", appDirName)
	default: // linux and others
		if dir := os.Getenv("XDG_DATA_HOME"); dir != "" {
			return filepath.Join(dir, appDirName)
		}
		home, _ := os.UserHomeDir()
		return filepath.Join(home, ".local", "share", appDirName)
	}
}

// EnsureDir creates the directory (and parents) if it does not exist.
func EnsureDir(path string) error {
	return os.MkdirAll(path, 0o700)
}
