package cmd

import (
	"errors"
	"strings"
	"testing"
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
	if !errors.Is(errReexec, errReexec) {
		t.Fatal("errors.Is(errReexec, errReexec) should be true")
	}
	other := errors.New("other error")
	if errors.Is(other, errReexec) {
		t.Fatal("errors.Is(other, errReexec) should be false")
	}
}
