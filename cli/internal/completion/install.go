// Package completion provides shell completion installation helpers.
package completion

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/spf13/cobra"
)

// ShellType identifies a supported shell.
type ShellType int

const (
	Unknown ShellType = iota
	Bash
	Zsh
	Fish
	PowerShell
)

// String returns the shell name.
func (s ShellType) String() string {
	switch s {
	case Bash:
		return "bash"
	case Zsh:
		return "zsh"
	case Fish:
		return "fish"
	case PowerShell:
		return "powershell"
	default:
		return "unknown"
	}
}

const marker = "# synthorg shell completion"

// DetectShell returns the user's current shell.
// On Unix it reads $SHELL; on Windows it defaults to PowerShell.
func DetectShell() ShellType {
	shell := os.Getenv("SHELL")
	if shell != "" {
		base := filepath.Base(shell)
		switch {
		case strings.Contains(base, "bash"):
			return Bash
		case strings.Contains(base, "zsh"):
			return Zsh
		case strings.Contains(base, "fish"):
			return Fish
		case strings.Contains(base, "pwsh") || strings.Contains(base, "powershell"):
			return PowerShell
		}
	}
	if runtime.GOOS == "windows" {
		return PowerShell
	}
	return Unknown
}

// Result describes what the install operation did.
type Result struct {
	Shell            ShellType
	ProfilePath      string
	AlreadyInstalled bool
}

// Install generates and installs shell completions for the given root command.
func Install(ctx context.Context, rootCmd *cobra.Command, shell ShellType) (Result, error) {
	res := Result{Shell: shell}

	if rootCmd == nil && (shell == Zsh || shell == Fish) {
		return res, fmt.Errorf("root command is required for %s completion generation", shell)
	}

	switch shell {
	case Bash:
		return installBash(res)
	case Zsh:
		return installZsh(rootCmd, res)
	case Fish:
		return installFish(rootCmd, res)
	case PowerShell:
		return installPowerShell(ctx, res)
	default:
		return res, fmt.Errorf("unsupported shell: %s", shell)
	}
}

func installBash(res Result) (Result, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return res, fmt.Errorf("cannot determine home directory: %w", err)
	}
	profile := filepath.Join(home, ".bashrc")
	res.ProfilePath = profile

	installed, err := fileContains(profile, marker)
	if err != nil {
		return res, err
	}
	if installed {
		res.AlreadyInstalled = true
		return res, nil
	}

	snippet := "\n" + marker + "\n" + `eval "$(synthorg completion bash)"` + "\n"
	return res, appendToFile(profile, snippet)
}

func installZsh(rootCmd *cobra.Command, res Result) (Result, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return res, fmt.Errorf("cannot determine home directory: %w", err)
	}

	// Write completion function file.
	compDir := filepath.Join(home, ".zsh", "completion")
	compFile := filepath.Join(compDir, "_synthorg")
	res.ProfilePath = compFile

	if _, err := os.Stat(compFile); err == nil {
		res.AlreadyInstalled = true
	}

	// Always regenerate the completion file so updated commands are picked up.
	if err := os.MkdirAll(compDir, 0o755); err != nil {
		return res, fmt.Errorf("creating completion directory: %w", err)
	}
	var buf bytes.Buffer
	if err := rootCmd.GenZshCompletion(&buf); err != nil {
		return res, fmt.Errorf("generating zsh completion: %w", err)
	}
	if err := os.WriteFile(compFile, buf.Bytes(), 0o644); err != nil {
		return res, fmt.Errorf("writing completion file: %w", err)
	}

	// Ensure fpath is configured in .zshrc (idempotent).
	zshrc := filepath.Join(home, ".zshrc")
	fpathLine := "fpath=(~/.zsh/completion $fpath)"
	installed, err := fileContains(zshrc, fpathLine)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return res, err
	}
	if !installed {
		snippet := "\n" + marker + "\n" + fpathLine + "\nautoload -Uz compinit && compinit\n"
		if err := appendToFile(zshrc, snippet); err != nil {
			return res, err
		}
	}

	return res, nil
}

func installFish(rootCmd *cobra.Command, res Result) (Result, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return res, fmt.Errorf("cannot determine home directory: %w", err)
	}

	compDir := filepath.Join(home, ".config", "fish", "completions")
	compFile := filepath.Join(compDir, "synthorg.fish")
	res.ProfilePath = compFile

	if _, err := os.Stat(compFile); err == nil {
		res.AlreadyInstalled = true
	}

	// Always regenerate the completion file so updated commands are picked up.
	if err := os.MkdirAll(compDir, 0o755); err != nil {
		return res, fmt.Errorf("creating completion directory: %w", err)
	}
	var buf bytes.Buffer
	if err := rootCmd.GenFishCompletion(&buf, true); err != nil {
		return res, fmt.Errorf("generating fish completion: %w", err)
	}
	if err := os.WriteFile(compFile, buf.Bytes(), 0o644); err != nil {
		return res, fmt.Errorf("writing completion file: %w", err)
	}
	return res, nil
}

func installPowerShell(ctx context.Context, res Result) (Result, error) {
	profile, err := powershellProfilePath(ctx)
	if err != nil {
		return res, err
	}
	res.ProfilePath = profile

	installed, err := fileContains(profile, marker)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return res, err
	}
	if installed {
		res.AlreadyInstalled = true
		return res, nil
	}

	snippet := "\n" + marker + "\nsynthorg completion powershell | Out-String | Invoke-Expression\n"
	return res, appendToFile(profile, snippet)
}

// powershellProfilePath resolves the PowerShell profile path.
func powershellProfilePath(ctx context.Context) (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("cannot determine home directory: %w", err)
	}

	// Resolve home through symlinks for reliable containment check.
	resolvedHome, err := filepath.EvalSymlinks(home)
	if err != nil {
		resolvedHome = home
	}

	// Try pwsh (PowerShell Core) first, then powershell (Windows PowerShell).
	for _, shell := range []string{"pwsh", "powershell"} {
		probeCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
		out, err := exec.CommandContext(probeCtx, shell, "-NoProfile", "-Command", "echo $PROFILE").Output()
		cancel()
		if err != nil {
			continue
		}
		p := strings.TrimSpace(string(out))
		if p == "" || len(p) > 2048 {
			continue
		}
		p = filepath.Clean(p)
		if !filepath.IsAbs(p) {
			continue
		}
		// Resolve symlinks and verify path is inside user's home directory.
		resolvedP, err := filepath.EvalSymlinks(filepath.Dir(p))
		if err != nil {
			// Parent dir may not exist yet -- fall back to lexical check.
			resolvedP = filepath.Clean(filepath.Dir(p))
		}
		resolvedP = filepath.Join(resolvedP, filepath.Base(p))
		rel, relErr := filepath.Rel(resolvedHome, resolvedP)
		if relErr != nil || strings.HasPrefix(rel, "..") {
			continue
		}
		return resolvedP, nil
	}

	// Fallback: construct the default path (home already resolved above).
	if runtime.GOOS == "windows" {
		return filepath.Join(home, "Documents", "PowerShell", "Microsoft.PowerShell_profile.ps1"), nil
	}
	return filepath.Join(home, ".config", "powershell", "Microsoft.PowerShell_profile.ps1"), nil
}

// fileContains checks whether a file contains the given substring.
// Returns (false, nil) if the file does not exist.
func fileContains(path, sub string) (bool, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return false, nil
		}
		return false, fmt.Errorf("reading %s: %w", path, err)
	}
	return strings.Contains(string(data), sub), nil
}

// Uninstall removes shell completion snippets and generated files.
func Uninstall(ctx context.Context, shell ShellType) error {
	switch shell {
	case Bash:
		return uninstallBash()
	case Zsh:
		return uninstallZsh()
	case Fish:
		return uninstallFish()
	case PowerShell:
		return uninstallPowerShell(ctx)
	default:
		return fmt.Errorf("unsupported shell: %s", shell)
	}
}

func uninstallBash() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("cannot determine home directory: %w", err)
	}
	return removeMarkerBlock(filepath.Join(home, ".bashrc"))
}

func uninstallZsh() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("cannot determine home directory: %w", err)
	}
	// Remove completion function file.
	compFile := filepath.Join(home, ".zsh", "completion", "_synthorg")
	if err := os.Remove(compFile); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("removing completion file: %w", err)
	}
	// Remove fpath snippet from .zshrc.
	return removeMarkerBlock(filepath.Join(home, ".zshrc"))
}

func uninstallFish() error {
	home, err := os.UserHomeDir()
	if err != nil {
		return fmt.Errorf("cannot determine home directory: %w", err)
	}
	compFile := filepath.Join(home, ".config", "fish", "completions", "synthorg.fish")
	if err := os.Remove(compFile); err != nil && !errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("removing completion file: %w", err)
	}
	return nil
}

func uninstallPowerShell(ctx context.Context) error {
	profile, err := powershellProfilePath(ctx)
	if err != nil {
		return err
	}
	return removeMarkerBlock(profile)
}

// maxSnippetLines caps how many non-empty lines after the marker are
// treated as part of the snippet, preventing unbounded deletion if a
// user's content follows without a blank-line separator.
const maxSnippetLines = 5

// removeMarkerBlock removes the first marker block from a shell profile.
// A block starts at the marker line and includes up to maxSnippetLines
// contiguous non-empty lines after it, plus the terminating empty line.
// Only the first occurrence is removed to avoid greedy deletion.
// The original file permissions are preserved.
// If the file does not exist or has no marker, this is a no-op.
func removeMarkerBlock(path string) error {
	info, err := os.Stat(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return nil
		}
		return fmt.Errorf("stat %s: %w", path, err)
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("reading %s: %w", path, err)
	}
	content := string(data)
	if !strings.Contains(content, marker) {
		return nil
	}

	var result []string
	lines := strings.Split(content, "\n")
	inBlock := false
	found := false
	blockLines := 0
	for _, line := range lines {
		if !found && strings.TrimSpace(line) == marker {
			inBlock = true
			found = true
			blockLines = 0
			continue
		}
		if inBlock {
			if strings.TrimSpace(line) != "" && blockLines < maxSnippetLines {
				blockLines++
				continue
			}
			// Empty line or cap reached -- end the block.
			inBlock = false
			if strings.TrimSpace(line) == "" {
				// Consume the terminating empty line.
				continue
			}
			// Cap reached on a non-empty line -- keep it.
		}
		result = append(result, line)
	}

	cleaned := strings.Join(result, "\n")
	return os.WriteFile(path, []byte(cleaned), info.Mode())
}

// appendToFile appends content to a file, creating it if needed.
func appendToFile(path, content string) error {
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return fmt.Errorf("creating directory %s: %w", dir, err)
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return fmt.Errorf("opening %s: %w", path, err)
	}
	_, writeErr := f.WriteString(content)
	closeErr := f.Close()
	if writeErr != nil {
		return fmt.Errorf("writing to %s: %w", path, writeErr)
	}
	if closeErr != nil {
		return fmt.Errorf("closing %s: %w", path, closeErr)
	}
	return nil
}
