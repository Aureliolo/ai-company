package cmd

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/Aureliolo/synthorg/cli/internal/version"
	"github.com/spf13/cobra"
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show container states, health, and versions",
	RunE:  runStatus,
}

func init() {
	statusCmd.Flags().Bool("json", false, "Output raw JSON")
	rootCmd.AddCommand(statusCmd)
}

func runStatus(cmd *cobra.Command, _ []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()
	jsonOut, _ := cmd.Flags().GetBool("json")

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	out := ui.NewUI(cmd.OutOrStdout())
	printVersionInfo(out, state)

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if _, err := os.Stat(composePath); errors.Is(err, os.ErrNotExist) {
		out.Warn("Not initialized — run 'synthorg init' first.")
		return nil
	}

	info, err := docker.Detect(ctx)
	if err != nil {
		out.Warn(fmt.Sprintf("Docker not available: %v", err))
		return nil
	}
	out.KeyValue("Docker", info.DockerVersion)
	out.KeyValue("Compose", info.ComposeVersion)
	_, _ = fmt.Fprintln(out.Writer())

	printContainerStates(ctx, out, info, safeDir, jsonOut)
	printResourceUsage(ctx, out, info, safeDir)
	printHealthStatus(ctx, out, state, jsonOut)
	printLinks(out, state)

	return nil
}

func printVersionInfo(out *ui.UI, state config.State) {
	out.KeyValue("CLI version", fmt.Sprintf("%s (%s)", version.Version, version.Commit))
	out.KeyValue("Data dir", state.DataDir)
	out.KeyValue("Image tag", state.ImageTag)
	_, _ = fmt.Fprintln(out.Writer())
}

// containerInfo holds parsed container state from docker compose ps.
type containerInfo struct {
	Name    string `json:"Name"`
	Service string `json:"Service"`
	State   string `json:"State"`
	Health  string `json:"Health"`
	Status  string `json:"Status"`
	Ports   string `json:"Ports"`
	Image   string `json:"Image"`
}

// imageTag extracts the tag from an image string like "ghcr.io/foo/bar:v1.0".
// Handles registry ports correctly (e.g. "registry:5000/image" has no tag).
func imageTag(image string) string {
	i := strings.LastIndex(image, ":")
	if i < 0 || i < strings.LastIndex(image, "/") {
		return image
	}
	return image[i+1:]
}

// healthIcon returns a status icon for a container's health/state.
func healthIcon(state, health string) string {
	if health == "healthy" {
		return ui.IconSuccess
	}
	if health == "unhealthy" {
		return ui.IconError
	}
	if state == "running" {
		return ui.IconInProgress
	}
	if state == "restarting" {
		return ui.IconWarning
	}
	return ui.IconError
}

// parseContainerJSON parses docker compose ps output.
// Handles both JSON array (Compose v2.21+) and NDJSON (older versions).
func parseContainerJSON(psOut string) ([]containerInfo, int) {
	trimmed := strings.TrimSpace(psOut)
	// Try JSON array first (Compose v2.21+).
	if strings.HasPrefix(trimmed, "[") {
		var containers []containerInfo
		if json.Unmarshal([]byte(trimmed), &containers) == nil {
			return containers, 0
		}
	}
	// Fall back to NDJSON (one object per line).
	var containers []containerInfo
	var failures int
	for _, line := range strings.Split(trimmed, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var c containerInfo
		if json.Unmarshal([]byte(line), &c) == nil {
			containers = append(containers, c)
		} else {
			failures++
		}
	}
	return containers, failures
}

// renderContainerTable formats containers as a table.
func renderContainerTable(out *ui.UI, containers []containerInfo) {
	headers := []string{"SERVICE", "STATE", "HEALTH", "IMAGE", "STATUS"}
	rows := make([][]string, 0, len(containers))
	for _, c := range containers {
		icon := healthIcon(c.State, c.Health)
		healthLabel := c.Health
		if healthLabel == "" {
			healthLabel = "-"
		}
		rows = append(rows, []string{
			c.Service, icon + " " + c.State, healthLabel,
			imageTag(c.Image), c.Status,
		})
	}
	out.Table(headers, rows)
}

func printContainerStates(ctx context.Context, out *ui.UI, info docker.Info, dataDir string, jsonOut bool) {
	psOut, err := docker.ComposeExecOutput(ctx, info, dataDir, "ps", "--format", "json")
	if err != nil {
		out.Warn(fmt.Sprintf("Could not get container states: %v", err))
		return
	}
	w := out.Writer()
	containers, failures := parseContainerJSON(psOut)
	if jsonOut {
		b, err := json.MarshalIndent(containers, "", "  ")
		if err != nil {
			out.Warn(fmt.Sprintf("Could not marshal container JSON: %v", err))
			return
		}
		_, _ = fmt.Fprintln(w, string(b))
		return
	}
	if failures > 0 {
		out.Warn(fmt.Sprintf("%d container lines could not be parsed", failures))
	}
	if len(containers) == 0 {
		out.Warn("No containers running")
		return
	}
	_, _ = fmt.Fprintln(w, "Containers:")
	renderContainerTable(out, containers)
	_, _ = fmt.Fprintln(w)
}

func printResourceUsage(ctx context.Context, out *ui.UI, info docker.Info, dataDir string) {
	psOut, err := docker.ComposeExecOutput(ctx, info, dataDir, "ps", "-q")
	if err != nil || strings.TrimSpace(psOut) == "" {
		return
	}
	ids := strings.Fields(strings.TrimSpace(psOut))
	statsArgs := append([]string{"stats", "--no-stream", "--format",
		"table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"}, ids...)
	statsOut, err := docker.RunCmd(ctx, "docker", statsArgs...)
	if err != nil {
		out.Warn(fmt.Sprintf("Could not get resource usage: %v", err))
		return
	}
	w := out.Writer()
	_, _ = fmt.Fprintln(w, "Resource usage:")
	_, _ = fmt.Fprintln(w, statsOut)
}

// healthResponse holds the parsed health check JSON.
type healthResponse struct {
	Status      string  `json:"status"`
	Version     string  `json:"version"`
	Persistence any     `json:"persistence"`
	MessageBus  any     `json:"message_bus"`
	Uptime      float64 `json:"uptime_seconds"`
}

func printHealthStatus(ctx context.Context, out *ui.UI, state config.State, jsonOut bool) {
	body, statusCode, err := fetchHealth(ctx, state.BackendPort)
	if err != nil {
		out.Error(err.Error())
		return
	}
	if jsonOut {
		w := out.Writer()
		_, _ = fmt.Fprintln(w, "Health check:")
		_, _ = fmt.Fprintf(w, "  %s\n", string(body))
		return
	}
	renderHealthSummary(out, body, statusCode)
}

func fetchHealth(ctx context.Context, port int) ([]byte, int, error) {
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", port)
	client := &http.Client{Timeout: 5 * time.Second}
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, healthURL, nil)
	if err != nil {
		return nil, 0, fmt.Errorf("health check error: %w", err)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("backend unreachable: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 64*1024))
	if err != nil {
		return nil, 0, fmt.Errorf("health check read error: %w", err)
	}
	return body, resp.StatusCode, nil
}

func renderHealthSummary(out *ui.UI, body []byte, statusCode int) {
	var envelope struct {
		Data healthResponse `json:"data"`
	}
	if json.Unmarshal(body, &envelope) != nil || envelope.Data.Status == "" {
		out.Warn(fmt.Sprintf("Health: unparseable response (HTTP %d)", statusCode))
		return
	}
	hr := envelope.Data
	if statusCode >= 200 && statusCode < 300 && hr.Status == "ok" {
		out.Success(fmt.Sprintf("Backend healthy (v%s, uptime %s)", hr.Version, formatUptime(hr.Uptime)))
		persistLabel := "not configured"
		if hr.Persistence != nil {
			persistLabel = fmt.Sprintf("%v", hr.Persistence)
		}
		out.KeyValue("Persistence", persistLabel)
	} else {
		out.Error(fmt.Sprintf("Backend unhealthy (HTTP %d)", statusCode))
	}
}

// formatUptime converts seconds to a human-readable duration like "3h 36m".
func formatUptime(seconds float64) string {
	d := time.Duration(seconds) * time.Second
	h := int(d.Hours())
	m := int(d.Minutes()) % 60
	if h > 0 {
		return fmt.Sprintf("%dh %dm", h, m)
	}
	if m > 0 {
		return fmt.Sprintf("%dm %ds", m, int(d.Seconds())%60)
	}
	return fmt.Sprintf("%ds", int(d.Seconds()))
}

func printLinks(out *ui.UI, state config.State) {
	_, _ = fmt.Fprintln(out.Writer())
	out.Link("Dashboard", fmt.Sprintf("http://localhost:%d", state.WebPort))
	out.Link("API docs", fmt.Sprintf("http://localhost:%d/api", state.BackendPort))
	out.Link("Health", fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort))
}
