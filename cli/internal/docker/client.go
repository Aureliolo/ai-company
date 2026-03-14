// Package docker provides Docker and Compose detection and execution helpers.
package docker

import (
	"bytes"
	"context"
	"fmt"
	"os/exec"
	"runtime"
	"strings"
)

// Info holds detected Docker environment details.
type Info struct {
	DockerPath     string
	DockerVersion  string
	ComposePath    string // "docker compose" or "docker-compose"
	ComposeVersion string
	ComposeV2      bool // true if using Compose V2 plugin
}

// Detect checks for Docker and Compose availability and returns diagnostic
// Info. Returns an error only if Docker itself is not found or the daemon is
// not running.
func Detect(ctx context.Context) (Info, error) {
	var info Info

	// 1. Check Docker binary.
	dockerPath, err := exec.LookPath("docker")
	if err != nil {
		return info, fmt.Errorf("docker not found on PATH: %w\n\n%s", err, installHint())
	}
	info.DockerPath = dockerPath

	// 2. Verify daemon is running.
	ver, err := runCmd(ctx, "docker", "info", "--format", "{{.ServerVersion}}")
	if err != nil {
		return info, fmt.Errorf("docker daemon is not running: %w\n\n%s", err, daemonHint())
	}
	info.DockerVersion = strings.TrimSpace(ver)

	// 3. Try Compose V2 plugin first, then fall back to standalone.
	if cver, err := runCmd(ctx, "docker", "compose", "version", "--short"); err == nil {
		info.ComposePath = "docker compose"
		info.ComposeVersion = strings.TrimSpace(cver)
		info.ComposeV2 = true
	} else if cver, err := runCmd(ctx, "docker-compose", "version", "--short"); err == nil {
		info.ComposePath = "docker-compose"
		info.ComposeVersion = strings.TrimSpace(cver)
	} else {
		return info, fmt.Errorf("docker compose not found (tried V2 plugin and standalone)\n\n%s", installHint())
	}

	return info, nil
}

// ComposeExec runs `docker compose` (or `docker-compose`) with the given
// arguments, forwarding stdout/stderr to the provided writers.
func ComposeExec(ctx context.Context, info Info, dir string, args ...string) error {
	parts := strings.Fields(info.ComposePath)
	parts = append(parts, args...)

	cmd := exec.CommandContext(ctx, parts[0], parts[1:]...)
	cmd.Dir = dir
	cmd.Stdout = nil // caller should capture if needed
	cmd.Stderr = nil
	return cmd.Run()
}

// ComposeExecOutput runs a compose command and returns combined output.
func ComposeExecOutput(ctx context.Context, info Info, dir string, args ...string) (string, error) {
	parts := strings.Fields(info.ComposePath)
	parts = append(parts, args...)

	cmd := exec.CommandContext(ctx, parts[0], parts[1:]...)
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	return string(out), err
}

func runCmd(ctx context.Context, name string, args ...string) (string, error) {
	cmd := exec.CommandContext(ctx, name, args...)
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	if err := cmd.Run(); err != nil {
		return "", fmt.Errorf("%w: %s", err, stderr.String())
	}
	return stdout.String(), nil
}

func installHint() string {
	switch runtime.GOOS {
	case "darwin":
		return "Install Docker Desktop: https://docs.docker.com/desktop/install/mac-install/"
	case "windows":
		return "Install Docker Desktop: https://docs.docker.com/desktop/install/windows-install/"
	default:
		return "Install Docker Engine: https://docs.docker.com/engine/install/"
	}
}

func daemonHint() string {
	switch runtime.GOOS {
	case "darwin", "windows":
		return "Start Docker Desktop and try again."
	default:
		return "Start the Docker daemon: sudo systemctl start docker"
	}
}
