package cmd

import (
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

func TestLineDiff_NoDifference(t *testing.T) {
	text := "line1\nline2\nline3"
	got := lineDiff(text, text)
	if got != "" {
		t.Errorf("lineDiff with identical input should be empty, got %q", got)
	}
}

func TestLineDiff_AddedLines(t *testing.T) {
	old := "line1\nline2"
	new := "line1\nline2\nline3"
	got := lineDiff(old, new)
	if !strings.Contains(got, "+ line3") {
		t.Errorf("lineDiff should show added line3, got %q", got)
	}
	// No removed lines.
	if strings.Contains(got, "- ") {
		t.Errorf("lineDiff should have no removed lines, got %q", got)
	}
}

func TestLineDiff_RemovedLines(t *testing.T) {
	old := "line1\nline2\nline3"
	new := "line1\nline2"
	got := lineDiff(old, new)
	if !strings.Contains(got, "- line3") {
		t.Errorf("lineDiff should show removed line3, got %q", got)
	}
	if strings.Contains(got, "+ ") {
		t.Errorf("lineDiff should have no added lines, got %q", got)
	}
}

func TestLineDiff_ChangedLines(t *testing.T) {
	old := "aaa\nbbb"
	new := "aaa\nccc"
	got := lineDiff(old, new)
	if !strings.Contains(got, "- bbb") {
		t.Errorf("lineDiff should show removed bbb, got %q", got)
	}
	if !strings.Contains(got, "+ ccc") {
		t.Errorf("lineDiff should show added ccc, got %q", got)
	}
}

func TestErrReexec_IsSentinel(t *testing.T) {
	if errReexec == nil {
		t.Fatal("errReexec should not be nil")
	}
	if errReexec.Error() == "" {
		t.Fatal("errReexec should have a message")
	}
}
