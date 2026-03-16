package cmd

import "testing"

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
