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
		case strings.Contains(base, "pwsh"):
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

	switch shell {
	case Bash:
		return installBash(rootCmd, res)
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

func installBash(_ *cobra.Command, res Result) (Result, error) {
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
		return res, nil
	}

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

	// Ensure fpath is configured in .zshrc.
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
		return res, nil
	}

	if err := os.MkdirAll(compDir, 0o755); err != nil {
		return res, fmt.Errorf("creating completion directory: %w", err)
	}

	var buf bytes.Buffer
	if err := rootCmd.GenFishCompletion(&buf, true); err != nil {
		return res, fmt.Errorf("generating fish completion: %w", err)
	}
	return res, os.WriteFile(compFile, buf.Bytes(), 0o644)
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
	// Try pwsh (PowerShell Core) first, then powershell (Windows PowerShell).
	for _, shell := range []string{"pwsh", "powershell"} {
		out, err := exec.CommandContext(ctx, shell, "-NoProfile", "-Command", "echo $PROFILE").Output()
		if err == nil {
			p := strings.TrimSpace(string(out))
			if p == "" || len(p) > 2048 {
				continue
			}
			p = filepath.Clean(p)
			if !filepath.IsAbs(p) {
				continue
			}
			return p, nil
		}
	}

	// Fallback: construct the default path.
	home, err := os.UserHomeDir()
	if err != nil {
		return "", fmt.Errorf("cannot determine home directory: %w", err)
	}
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
	if _, err := f.WriteString(content); err != nil {
		_ = f.Close()
		return fmt.Errorf("writing to %s: %w", path, err)
	}
	return f.Close()
}
