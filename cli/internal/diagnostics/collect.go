// Package diagnostics collects system information for bug reports.
package diagnostics

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/version"
)

// ContainerDetail summarises a single container's state from compose ps JSON.
type ContainerDetail struct {
	Name   string `json:"Name"`
	State  string `json:"State"`
	Status string `json:"Status"`
	Health string `json:"Health,omitempty"`
}

// Report contains collected diagnostic information.
type Report struct {
	Timestamp      string   `json:"timestamp"`
	OS             string   `json:"os"`
	Arch           string   `json:"arch"`
	CLIVersion     string   `json:"cli_version"`
	CLICommit      string   `json:"cli_commit"`
	DockerVersion  string   `json:"docker_version,omitempty"`
	ComposeVersion string   `json:"compose_version,omitempty"`
	HealthStatus   string   `json:"health_status,omitempty"`
	HealthBody     string   `json:"health_body,omitempty"`
	ContainerPS    string   `json:"container_ps,omitempty"`
	RecentLogs     string   `json:"recent_logs,omitempty"`
	ConfigRedacted string   `json:"config_redacted,omitempty"`
	DiskInfo       string   `json:"disk_info,omitempty"`
	Errors         []string `json:"errors,omitempty"`

	ComposeFileExists bool              `json:"compose_file_exists"`
	ComposeFileValid  bool              `json:"compose_file_valid,omitempty"`
	PortConflicts     []string          `json:"port_conflicts,omitempty"`
	ImageStatus       []string          `json:"image_status,omitempty"`
	ContainerSummary  []ContainerDetail `json:"container_summary,omitempty"`
}

// Collect gathers diagnostics from the system and running containers.
func Collect(ctx context.Context, state config.State) Report {
	r := Report{
		Timestamp:  time.Now().UTC().Format(time.RFC3339),
		OS:         runtime.GOOS,
		Arch:       runtime.GOARCH,
		CLIVersion: version.Version,
		CLICommit:  version.Commit,
	}

	safeDir, pathErr := config.SecurePath(state.DataDir)
	if pathErr != nil {
		r.Errors = append(r.Errors, fmt.Sprintf("path: %v", pathErr))
	}

	// Docker info.
	info, err := docker.Detect(ctx)
	if err != nil {
		r.Errors = append(r.Errors, fmt.Sprintf("docker: %v", err))
	} else {
		r.DockerVersion = info.DockerVersion
		r.ComposeVersion = info.ComposeVersion

		// Version warnings.
		for _, w := range docker.CheckMinVersions(info) {
			r.Errors = append(r.Errors, fmt.Sprintf("version: %s", w))
		}

		if pathErr == nil {
			// Container states.
			if ps, err := docker.ComposeExecOutput(ctx, info, safeDir, "ps", "--format", "json"); err == nil {
				r.ContainerPS = strings.TrimSpace(ps)
			}

			// Recent logs (last 50 lines).
			if logs, err := docker.ComposeExecOutput(ctx, info, safeDir, "logs", "--tail", "50", "--no-color"); err == nil {
				r.RecentLogs = truncate(logs, 4000)
			}
		}
	}

	// Health endpoint.
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort)
	client := &http.Client{Timeout: 5 * time.Second}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, healthURL, nil)
	if err != nil {
		r.HealthStatus = "unreachable"
		r.Errors = append(r.Errors, fmt.Sprintf("health request: %v", err))
	} else if resp, err := client.Do(req); err != nil {
		r.HealthStatus = "unreachable"
		r.Errors = append(r.Errors, fmt.Sprintf("health: %v", err))
	} else {
		defer func() { _ = resp.Body.Close() }()
		body, readErr := io.ReadAll(io.LimitReader(resp.Body, 64*1024))
		if readErr != nil {
			r.Errors = append(r.Errors, fmt.Sprintf("health read: %v", readErr))
		}
		r.HealthStatus = fmt.Sprintf("%d", resp.StatusCode)
		r.HealthBody = truncate(string(body), 1000)
	}

	// Redacted config.
	redacted := state
	if redacted.JWTSecret != "" {
		redacted.JWTSecret = "[REDACTED]"
	}
	if b, err := json.MarshalIndent(redacted, "", "  "); err == nil {
		r.ConfigRedacted = string(b)
	}

	// Compose file check.
	if pathErr == nil {
		exists, valid := checkComposeFile(ctx, info, safeDir)
		r.ComposeFileExists = exists
		r.ComposeFileValid = valid
	}

	// Parse container details from ps output.
	if r.ContainerPS != "" {
		r.ContainerSummary = parseContainerDetails(r.ContainerPS)
	}

	// Port conflicts (only when no containers are running to avoid self-matches).
	if !hasRunningContainers(r.ContainerSummary) {
		r.PortConflicts = checkPorts(ctx, state.BackendPort, state.WebPort)
	}

	// Docker image availability.
	if info.DockerPath != "" {
		r.ImageStatus = checkImages(ctx, state.ImageTag, state.Sandbox)
	}

	// Disk space for data directory (best-effort, skip if path invalid).
	if pathErr == nil {
		r.DiskInfo = diskInfo(ctx, safeDir)
	}

	return r
}

// FormatText returns a human-readable text report.
func (r Report) FormatText() string {
	var b strings.Builder
	b.WriteString("=== SynthOrg Diagnostic Report ===\n\n")
	fmt.Fprintf(&b, "Timestamp: %s\n", r.Timestamp)
	fmt.Fprintf(&b, "OS:        %s/%s\n", r.OS, r.Arch)
	fmt.Fprintf(&b, "CLI:       %s (%s)\n", r.CLIVersion, r.CLICommit)
	fmt.Fprintf(&b, "Docker:    %s\n", r.DockerVersion)
	fmt.Fprintf(&b, "Compose:   %s\n\n", r.ComposeVersion)

	fmt.Fprintf(&b, "--- Health ---\nStatus: %s\n%s\n\n", r.HealthStatus, r.HealthBody)

	b.WriteString("--- Compose File ---\n")
	if r.ComposeFileExists {
		valid := "yes"
		if !r.ComposeFileValid {
			valid = "no"
		}
		fmt.Fprintf(&b, "Exists: yes  Valid: %s\n\n", valid)
	} else {
		b.WriteString("Not found\n\n")
	}

	fmt.Fprintf(&b, "--- Containers ---\n%s\n\n", r.ContainerPS)

	if len(r.ContainerSummary) > 0 {
		b.WriteString("--- Container Summary ---\n")
		for _, c := range r.ContainerSummary {
			line := fmt.Sprintf("  %s: %s", c.Name, c.State)
			if c.Health != "" {
				line += fmt.Sprintf(" (%s)", c.Health)
			}
			fmt.Fprintf(&b, "%s\n", line)
		}
		b.WriteString("\n")
	}

	if len(r.PortConflicts) > 0 {
		b.WriteString("--- Port Conflicts ---\n")
		for _, c := range r.PortConflicts {
			fmt.Fprintf(&b, "  - %s\n", c)
		}
		b.WriteString("\n")
	}

	if len(r.ImageStatus) > 0 {
		b.WriteString("--- Docker Images ---\n")
		for _, s := range r.ImageStatus {
			fmt.Fprintf(&b, "  - %s\n", s)
		}
		b.WriteString("\n")
	}

	fmt.Fprintf(&b, "--- Config (redacted) ---\n%s\n\n", r.ConfigRedacted)
	fmt.Fprintf(&b, "--- Disk ---\n%s\n\n", r.DiskInfo)
	fmt.Fprintf(&b, "--- Recent Logs (may contain sensitive data — review before sharing) ---\n%s\n\n", r.RecentLogs)

	if len(r.Errors) > 0 {
		fmt.Fprintf(&b, "--- Errors ---\n")
		for _, e := range r.Errors {
			fmt.Fprintf(&b, "  - %s\n", e)
		}
	}

	return b.String()
}

func truncate(s string, max int) string {
	if len(s) <= max {
		return s
	}
	return s[:max] + "\n... (truncated)"
}

// checkComposeFile verifies that compose.yml exists and is valid YAML.
func checkComposeFile(ctx context.Context, info docker.Info, dataDir string) (exists, valid bool) {
	composePath := filepath.Join(dataDir, "compose.yml")
	if _, err := os.Stat(composePath); err != nil {
		return false, false
	}
	// compose config --quiet validates the file without printing it.
	if info.DockerPath != "" {
		err := docker.ComposeExec(ctx, info, dataDir, "config", "--quiet")
		return true, err == nil
	}
	return true, false
}

// checkPorts tests whether configured ports are already bound.
func checkPorts(ctx context.Context, backendPort, webPort int) []string {
	dialer := net.Dialer{Timeout: 1 * time.Second}
	var conflicts []string
	for _, p := range []struct {
		name string
		port int
	}{
		{"backend", backendPort},
		{"web", webPort},
	} {
		addr := fmt.Sprintf("127.0.0.1:%d", p.port)
		conn, err := dialer.DialContext(ctx, "tcp", addr)
		if err == nil {
			_ = conn.Close()
			conflicts = append(conflicts, fmt.Sprintf("port %d (%s) is already in use", p.port, p.name))
		}
	}
	return conflicts
}

const imagePrefix = "ghcr.io/aureliolo/synthorg-"

// checkImages reports whether required Docker images exist locally.
func checkImages(ctx context.Context, imageTag string, sandbox bool) []string {
	names := []string{"backend", "web"}
	if sandbox {
		names = append(names, "sandbox")
	}
	var status []string
	for _, name := range names {
		image := imagePrefix + name + ":" + imageTag
		_, err := docker.RunCmd(ctx, "docker", "image", "inspect", image, "--format", "{{.ID}}")
		if err != nil {
			status = append(status, fmt.Sprintf("%s: not found locally", image))
		} else {
			status = append(status, fmt.Sprintf("%s: available", image))
		}
	}
	return status
}

// parseContainerDetails parses NDJSON output from docker compose ps --format json.
func parseContainerDetails(psJSON string) []ContainerDetail {
	var details []ContainerDetail
	for _, line := range strings.Split(psJSON, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var d ContainerDetail
		if err := json.Unmarshal([]byte(line), &d); err != nil {
			continue
		}
		if d.Name != "" {
			details = append(details, d)
		}
	}
	return details
}

// hasRunningContainers returns true if any container is in "running" state.
func hasRunningContainers(details []ContainerDetail) bool {
	for _, d := range details {
		if d.State == "running" {
			return true
		}
	}
	return false
}

func diskInfo(ctx context.Context, dataDir string) string {
	var name string
	var args []string

	// Check the partition containing the data directory rather than root.
	target := dataDir
	if target == "" {
		target = "/"
	}

	switch runtime.GOOS {
	case "windows":
		// Use fsutil on the drive letter of the data dir (or C: as fallback).
		drive := "C:"
		if len(target) >= 2 && target[1] == ':' {
			drive = target[:2]
		}
		name = "fsutil"
		args = []string{"volume", "diskfree", drive}
	default:
		name = "df"
		args = []string{"-h", target}
	}
	cmd := exec.CommandContext(ctx, name, args...)
	var out bytes.Buffer
	cmd.Stdout = &out
	if err := cmd.Run(); err != nil {
		return fmt.Sprintf("unavailable: %v", err)
	}
	return strings.TrimSpace(out.String())
}
