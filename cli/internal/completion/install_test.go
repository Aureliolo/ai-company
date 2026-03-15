package completion

import (
	"context"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/spf13/cobra"
)

func testRootCmd() *cobra.Command {
	return &cobra.Command{Use: "synthorg"}
}

func TestDetectShellFromEnv(t *testing.T) {
	// On Windows, unknown shells fall back to PowerShell.
	unknownShellResult := Unknown
	if runtime.GOOS == "windows" {
		unknownShellResult = PowerShell
	}

	tests := []struct {
		env  string
		want ShellType
	}{
		{"/bin/bash", Bash},
		{"/usr/bin/zsh", Zsh},
		{"/usr/bin/fish", Fish},
		{"/usr/bin/pwsh", PowerShell},
		{"/bin/sh", unknownShellResult},
	}
	for _, tt := range tests {
		t.Run(tt.env, func(t *testing.T) {
			t.Setenv("SHELL", tt.env)
			if got := DetectShell(); got != tt.want {
				t.Errorf("DetectShell() with SHELL=%q = %v, want %v", tt.env, got, tt.want)
			}
		})
	}
}

func TestShellTypeString(t *testing.T) {
	tests := []struct {
		shell ShellType
		want  string
	}{
		{Bash, "bash"},
		{Zsh, "zsh"},
		{Fish, "fish"},
		{PowerShell, "powershell"},
		{Unknown, "unknown"},
	}
	for _, tt := range tests {
		if got := tt.shell.String(); got != tt.want {
			t.Errorf("ShellType(%d).String() = %q, want %q", tt.shell, got, tt.want)
		}
	}
}

func TestFileContains(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "test.txt")
	if err := os.WriteFile(path, []byte("hello world"), 0o644); err != nil {
		t.Fatal(err)
	}

	found, err := fileContains(path, "hello")
	if err != nil {
		t.Fatal(err)
	}
	if !found {
		t.Error("expected to find 'hello'")
	}

	found, err = fileContains(path, "missing")
	if err != nil {
		t.Fatal(err)
	}
	if found {
		t.Error("should not find 'missing'")
	}
}

func TestFileContainsNotExist(t *testing.T) {
	found, err := fileContains("/nonexistent/path/file.txt", "anything")
	if err != nil {
		t.Fatal(err)
	}
	if found {
		t.Error("nonexistent file should return false")
	}
}

func TestInstallBashIdempotent(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home) // Windows

	root := testRootCmd()

	// First install.
	res, err := Install(context.Background(), root, Bash)
	if err != nil {
		t.Fatalf("first install: %v", err)
	}
	if res.AlreadyInstalled {
		t.Error("first install should not be marked as already installed")
	}

	// Read the file to verify content.
	data, err := os.ReadFile(filepath.Join(home, ".bashrc"))
	if err != nil {
		t.Fatal(err)
	}
	if got := string(data); !strings.Contains(got, marker) || !strings.Contains(got, "synthorg completion bash") {
		t.Errorf("unexpected .bashrc content: %s", got)
	}

	// Second install should be idempotent.
	res, err = Install(context.Background(), root, Bash)
	if err != nil {
		t.Fatalf("second install: %v", err)
	}
	if !res.AlreadyInstalled {
		t.Error("second install should be marked as already installed")
	}
}

func TestInstallZshCreatesFiles(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)

	root := testRootCmd()

	res, err := Install(context.Background(), root, Zsh)
	if err != nil {
		t.Fatalf("install: %v", err)
	}

	// Completion file should exist.
	compFile := filepath.Join(home, ".zsh", "completion", "_synthorg")
	if _, err := os.Stat(compFile); err != nil {
		t.Errorf("completion file not created: %v", err)
	}

	// .zshrc should have fpath line.
	zshrc := filepath.Join(home, ".zshrc")
	data, err := os.ReadFile(zshrc)
	if err != nil {
		t.Fatalf("reading .zshrc: %v", err)
	}
	if !strings.Contains(string(data), "fpath=") {
		t.Error(".zshrc should contain fpath line")
	}

	// Second install should be idempotent.
	res, err = Install(context.Background(), root, Zsh)
	if err != nil {
		t.Fatalf("second install: %v", err)
	}
	if !res.AlreadyInstalled {
		t.Error("second install should be marked as already installed")
	}
}

func TestInstallFishCreatesFile(t *testing.T) {
	home := t.TempDir()
	t.Setenv("HOME", home)
	t.Setenv("USERPROFILE", home)

	root := testRootCmd()

	res, err := Install(context.Background(), root, Fish)
	if err != nil {
		t.Fatalf("install: %v", err)
	}

	compFile := filepath.Join(home, ".config", "fish", "completions", "synthorg.fish")
	if _, err := os.Stat(compFile); err != nil {
		t.Errorf("completion file not created: %v", err)
	}

	// Second install should be idempotent.
	res, err = Install(context.Background(), root, Fish)
	if err != nil {
		t.Fatalf("second install: %v", err)
	}
	if !res.AlreadyInstalled {
		t.Error("second install should be marked as already installed")
	}
}

func TestInstallUnknownShell(t *testing.T) {
	root := testRootCmd()
	_, err := Install(context.Background(), root, Unknown)
	if err == nil {
		t.Error("expected error for unknown shell")
	}
}
