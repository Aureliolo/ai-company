package diagnostics

import (
	"testing"
)

func TestTruncate(t *testing.T) {
	tests := []struct {
		name  string
		input string
		max   int
		want  string
	}{
		{"short", "hello", 10, "hello"},
		{"exact", "hello", 5, "hello"},
		{"truncated", "hello world", 5, "hello\n... (truncated)"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := truncate(tt.input, tt.max)
			if got != tt.want {
				t.Errorf("truncate(%q, %d) = %q, want %q", tt.input, tt.max, got, tt.want)
			}
		})
	}
}

func TestReportFormatText(t *testing.T) {
	r := Report{
		Timestamp:  "2026-03-14T00:00:00Z",
		OS:         "linux",
		Arch:       "amd64",
		CLIVersion: "dev",
		CLICommit:  "none",
	}
	text := r.FormatText()
	if text == "" {
		t.Fatal("FormatText returned empty string")
	}
	if len(text) < 50 {
		t.Errorf("FormatText suspiciously short: %d chars", len(text))
	}
}
