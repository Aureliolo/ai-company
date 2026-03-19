package cmd

import (
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/config"
)

func TestTargetImageTag(t *testing.T) {
	tests := []struct {
		name    string
		version string
		want    string
	}{
		{name: "with v prefix", version: "v0.2.7", want: "0.2.7"},
		{name: "without prefix", version: "0.2.6", want: "0.2.6"},
		{name: "dev build", version: "dev", want: "latest"},
		{name: "empty string", version: "", want: "latest"},
		{name: "invalid chars fall back to latest", version: "v1.0.0\n", want: "latest"},
		{name: "shell injection falls back to latest", version: "v1.0.0;rm -rf", want: "latest"},
		{name: "valid semver with pre-release", version: "v1.0.0-rc.1", want: "1.0.0-rc.1"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := targetImageTag(tt.version)
			if got != tt.want {
				t.Errorf("targetImageTag(%q) = %q, want %q", tt.version, got, tt.want)
			}
		})
	}
}

func TestLineDiff(t *testing.T) {
	tests := []struct {
		name         string
		old          string
		updated      string
		wantContains []string
		wantAbsent   []string
		wantEmpty    bool
	}{
		{
			name:      "identical input",
			old:       "line1\nline2\nline3",
			updated:   "line1\nline2\nline3",
			wantEmpty: true,
		},
		{
			name:         "added lines",
			old:          "line1\nline2",
			updated:      "line1\nline2\nline3",
			wantContains: []string{"+ line3"},
			wantAbsent:   []string{"- "},
		},
		{
			name:         "removed lines",
			old:          "line1\nline2\nline3",
			updated:      "line1\nline2",
			wantContains: []string{"- line3"},
			wantAbsent:   []string{"+ "},
		},
		{
			name:         "changed lines",
			old:          "aaa\nbbb",
			updated:      "aaa\nccc",
			wantContains: []string{"- bbb", "+ ccc"},
		},
		{
			name:      "trailing newline identical",
			old:       "line1\nline2\n",
			updated:   "line1\nline2\n",
			wantEmpty: true,
		},
		{
			name:         "trailing newline added",
			old:          "line1\nline2",
			updated:      "line1\nline2\n",
			wantContains: []string{"+ "},
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := lineDiff(tt.old, tt.updated)
			if tt.wantEmpty && got != "" {
				t.Errorf("expected empty diff, got %q", got)
			}
			for _, s := range tt.wantContains {
				if !strings.Contains(got, s) {
					t.Errorf("diff should contain %q, got %q", s, got)
				}
			}
			for _, s := range tt.wantAbsent {
				if strings.Contains(got, s) {
					t.Errorf("diff should not contain %q, got %q", s, got)
				}
			}
		})
	}
}

func FuzzLineDiff(f *testing.F) {
	f.Add("line1\nline2", "line1\nline3")
	f.Add("", "new content")
	f.Add("a\nb\nc", "a\nb\nc")
	f.Add("", "")
	f.Fuzz(func(t *testing.T, old, updated string) {
		// Should not panic on any input.
		_ = lineDiff(old, updated)
	})
}

func TestRedactSecret(t *testing.T) {
	tests := []struct {
		name string
		line string
		want string
	}{
		{
			name: "jwt secret redacted",
			line: `      SYNTHORG_JWT_SECRET: "supersecret123"`,
			want: `      SYNTHORG_JWT_SECRET: [REDACTED]`,
		},
		{
			name: "non-secret line unchanged",
			line: `      SYNTHORG_LOG_DIR: "/data/logs"`,
			want: `      SYNTHORG_LOG_DIR: "/data/logs"`,
		},
		{
			name: "case insensitive match",
			line: `      synthorg_jwt_secret: "abc"`,
			want: `      synthorg_jwt_secret: [REDACTED]`,
		},
		{
			name: "token key redacted",
			line: `      AUTH_TOKEN: "mytoken"`,
			want: `      AUTH_TOKEN: [REDACTED]`,
		},
		{
			name: "password key redacted",
			line: `      DB_PASSWORD: "hunter2"`,
			want: `      DB_PASSWORD: [REDACTED]`,
		},
		{
			name: "api key redacted",
			line: `      EXTERNAL_API_KEY: "key123"`,
			want: `      EXTERNAL_API_KEY: [REDACTED]`,
		},
		{
			name: "credentials key redacted",
			line: `      SERVICE_CREDENTIALS: "creds"`,
			want: `      SERVICE_CREDENTIALS: [REDACTED]`,
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := redactSecret(tt.line)
			if got != tt.want {
				t.Errorf("redactSecret(%q) = %q, want %q", tt.line, got, tt.want)
			}
		})
	}
}

func TestErrReexec_Identity(t *testing.T) {
	// Verify sentinel identity via errors.Is.
	if !errors.Is(errReexec, errReexec) {
		t.Fatal("errors.Is(errReexec, errReexec) should be true")
	}
	other := errors.New("other error")
	if errors.Is(other, errReexec) {
		t.Fatal("errors.Is(other, errReexec) should be false")
	}
	// Verify sentinel survives wrapping via %w.
	wrapped := fmt.Errorf("context: %w", errReexec)
	if !errors.Is(wrapped, errReexec) {
		t.Fatal("errors.Is(wrapped, errReexec) should be true")
	}
}

func TestLoadAndGenerate_NoCompose(t *testing.T) {
	dir := t.TempDir()
	composePath := filepath.Join(dir, "compose.yml")
	existing, fresh, err := loadAndGenerate(composePath, config.State{})
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if existing != nil || fresh != nil {
		t.Fatal("expected nil results when compose.yml does not exist")
	}
}

func TestLoadAndGenerate_PermissionError(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("permission-based test not reliable on Windows")
	}
	dir := t.TempDir()
	composePath := filepath.Join(dir, "compose.yml")
	if err := os.WriteFile(composePath, []byte("test"), 0o000); err != nil {
		t.Fatalf("setup: %v", err)
	}
	t.Cleanup(func() { _ = os.Chmod(composePath, 0o600) })

	_, _, err := loadAndGenerate(composePath, config.State{})
	if err == nil {
		t.Fatal("expected error for permission-denied compose.yml")
	}
	if !strings.Contains(err.Error(), "reading existing compose") {
		t.Errorf("error should mention reading compose, got: %v", err)
	}
}
