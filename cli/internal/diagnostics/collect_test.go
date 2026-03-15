package diagnostics

import (
	"context"
	"net"
	"strings"
	"testing"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
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
		{"empty", "", 5, ""},
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

	// Check key sections are present.
	for _, section := range []string{"Diagnostic Report", "Timestamp:", "OS:", "CLI:", "Health", "Containers", "Config"} {
		if !strings.Contains(text, section) {
			t.Errorf("FormatText missing section %q", section)
		}
	}
}

func TestReportFormatTextWithErrors(t *testing.T) {
	r := Report{
		Timestamp:  "2026-03-14T00:00:00Z",
		OS:         "linux",
		Arch:       "amd64",
		CLIVersion: "dev",
		CLICommit:  "none",
		Errors:     []string{"docker not found", "health unreachable"},
	}
	text := r.FormatText()
	if !strings.Contains(text, "Errors") {
		t.Error("FormatText should include Errors section")
	}
	if !strings.Contains(text, "docker not found") {
		t.Error("FormatText should include error details")
	}
}

func TestCollectDoesNotPanic(t *testing.T) {
	// Collect should never panic even with a bad state.
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	state := config.State{
		DataDir:     t.TempDir(),
		BackendPort: 99999, // unreachable port
	}
	report := Collect(ctx, state)

	if report.OS == "" {
		t.Error("OS should be set")
	}
	if report.CLIVersion == "" {
		t.Error("CLIVersion should be set")
	}
	if report.Timestamp == "" {
		t.Error("Timestamp should be set")
	}
}

func TestDiskInfo(t *testing.T) {
	info := diskInfo(context.Background(), t.TempDir())
	// Should return something (even "unavailable: ...")
	if info == "" {
		t.Error("diskInfo returned empty")
	}
}

func TestParseContainerDetails(t *testing.T) {
	tests := []struct {
		name  string
		input string
		want  int
	}{
		{
			"single",
			`{"Name":"synthorg-backend-1","State":"running","Status":"Up 5 minutes","Health":"healthy"}`,
			1,
		},
		{
			"multiple_ndjson",
			"{\"Name\":\"backend\",\"State\":\"running\",\"Status\":\"Up\"}\n{\"Name\":\"web\",\"State\":\"exited\",\"Status\":\"Exited (1)\"}",
			2,
		},
		{"empty", "", 0},
		{"invalid_json", "not json at all", 0},
		{"blank_lines", "\n\n\n", 0},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := parseContainerDetails(tt.input)
			if len(got) != tt.want {
				t.Errorf("parseContainerDetails: got %d details, want %d", len(got), tt.want)
			}
		})
	}
}

func TestParseContainerDetailsFields(t *testing.T) {
	input := `{"Name":"synthorg-backend-1","State":"running","Status":"Up 5 minutes","Health":"healthy"}`
	details := parseContainerDetails(input)
	if len(details) != 1 {
		t.Fatalf("expected 1 detail, got %d", len(details))
	}
	d := details[0]
	if d.Name != "synthorg-backend-1" {
		t.Errorf("Name = %q, want %q", d.Name, "synthorg-backend-1")
	}
	if d.State != "running" {
		t.Errorf("State = %q, want %q", d.State, "running")
	}
	if d.Health != "healthy" {
		t.Errorf("Health = %q, want %q", d.Health, "healthy")
	}
}

func TestHasRunningContainers(t *testing.T) {
	tests := []struct {
		name    string
		details []ContainerDetail
		want    bool
	}{
		{"empty", nil, false},
		{"running", []ContainerDetail{{State: "running"}}, true},
		{"exited", []ContainerDetail{{State: "exited"}}, false},
		{"mixed", []ContainerDetail{{State: "exited"}, {State: "running"}}, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := hasRunningContainers(tt.details); got != tt.want {
				t.Errorf("hasRunningContainers = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestCheckPortsDetectsConflict(t *testing.T) {
	ctx := context.Background()
	// Start a listener to occupy a port.
	var lc net.ListenConfig
	ln, err := lc.Listen(ctx, "tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer func() { _ = ln.Close() }()
	port := ln.Addr().(*net.TCPAddr).Port

	conflicts := checkPorts(ctx, port, 0)
	if len(conflicts) == 0 {
		t.Error("expected port conflict for occupied port")
	}

	found := false
	for _, c := range conflicts {
		if strings.Contains(c, "backend") {
			found = true
		}
	}
	if !found {
		t.Error("expected conflict to mention 'backend'")
	}
}

func TestCheckPortsNoConflict(t *testing.T) {
	// Use port 0 which should never be bound.
	conflicts := checkPorts(context.Background(), 0, 0)
	if len(conflicts) != 0 {
		t.Errorf("expected no conflicts, got %v", conflicts)
	}
}

func TestFormatTextNewSections(t *testing.T) {
	r := Report{
		Timestamp:         "2026-03-15T00:00:00Z",
		OS:                "linux",
		Arch:              "amd64",
		CLIVersion:        "dev",
		CLICommit:         "none",
		ComposeFileExists: true,
		ComposeFileValid:  ptrBool(true),
		PortConflicts:     []string{"port 8000 (backend) is already in use"},
		ImageStatus:       []string{"ghcr.io/aureliolo/synthorg-backend:latest: available"},
		ContainerSummary: []ContainerDetail{
			{Name: "backend", State: "running", Health: "healthy"},
		},
	}
	text := r.FormatText()
	for _, want := range []string{
		"Compose File",
		"Exists: yes  Valid: yes",
		"Container Summary",
		"backend: running (healthy)",
		"Port Conflicts",
		"port 8000",
		"Docker Images",
		"synthorg-backend",
	} {
		if !strings.Contains(text, want) {
			t.Errorf("FormatText missing %q", want)
		}
	}
}

func ptrBool(v bool) *bool { return &v }
