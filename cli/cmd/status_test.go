package cmd

import (
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/ui"
)

func TestImageTag(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"ghcr.io/aureliolo/synthorg-backend:0.2.9", "0.2.9"},
		{"ghcr.io/aureliolo/synthorg-web:latest", "latest"},
		{"nocolon", "nocolon"},
		{"", ""},
		{"registry:5000/image:v1.0", "v1.0"},
		{"registry:5000/image", "registry:5000/image"},
	}
	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			if got := imageTag(tt.input); got != tt.want {
				t.Errorf("imageTag(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestHealthIcon(t *testing.T) {
	tests := []struct {
		state  string
		health string
		want   string
	}{
		{"running", "healthy", ui.IconSuccess},
		{"running", "unhealthy", ui.IconError},
		{"running", "", ui.IconInProgress},
		{"restarting", "", ui.IconWarning},
		{"exited", "", ui.IconError},
		{"", "", ui.IconError},
	}
	for _, tt := range tests {
		name := tt.state + "/" + tt.health
		if name == "/" {
			name = "empty/empty"
		}
		t.Run(name, func(t *testing.T) {
			if got := healthIcon(tt.state, tt.health); got != tt.want {
				t.Errorf("healthIcon(%q, %q) = %q, want %q", tt.state, tt.health, got, tt.want)
			}
		})
	}
}

func TestParseContainerJSON(t *testing.T) {
	input := `{"Name":"a","Service":"backend","State":"running","Health":"healthy","Image":"img:1.0"}
{"Name":"b","Service":"web","State":"running","Health":"","Image":"img:1.0"}
invalid json line
`
	containers, failures := parseContainerJSON(input)
	if len(containers) != 2 {
		t.Fatalf("expected 2 containers, got %d", len(containers))
	}
	if failures != 1 {
		t.Errorf("expected 1 failure, got %d", failures)
	}
	if containers[0].Service != "backend" {
		t.Errorf("first container service = %q", containers[0].Service)
	}
}

func TestParseContainerJSON_Array(t *testing.T) {
	input := `[{"Name":"a","Service":"backend","State":"running","Health":"healthy","Image":"img:1.0"},{"Name":"b","Service":"web","State":"running","Health":"","Image":"img:1.0"}]`
	containers, failures := parseContainerJSON(input)
	if len(containers) != 2 {
		t.Fatalf("expected 2 containers, got %d", len(containers))
	}
	if failures != 0 {
		t.Errorf("expected 0 failures, got %d", failures)
	}
	if containers[0].Service != "backend" {
		t.Errorf("first container service = %q", containers[0].Service)
	}
}

func TestFormatUptime(t *testing.T) {
	tests := []struct {
		seconds float64
		want    string
	}{
		{0, "0s"},
		{45, "45s"},
		{90, "1m 30s"},
		{3600, "1h 0m"},
		{12991, "3h 36m"},
		{86400, "24h 0m"},
		{-90, "-1m 30s"},
	}
	for _, tt := range tests {
		t.Run(tt.want, func(t *testing.T) {
			if got := formatUptime(tt.seconds); got != tt.want {
				t.Errorf("formatUptime(%v) = %q, want %q", tt.seconds, got, tt.want)
			}
		})
	}
}
