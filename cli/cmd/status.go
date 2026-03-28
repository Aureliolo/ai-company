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

var (
	statusWatch    bool
	statusInterval string
	statusWide     bool
	statusNoTrunc  bool
	statusServices string
	statusCheck    bool
)

var statusCmd = &cobra.Command{
	Use:   "status",
	Short: "Show container states, health, and versions",
	Example: `  synthorg status              # show current status
  synthorg status --watch      # continuously poll
  synthorg status --wide       # show extra columns
  synthorg status --check      # exit code only (for scripts)`,
	RunE: runStatus,
}

func init() {
	statusCmd.Flags().BoolVarP(&statusWatch, "watch", "w", false, "continuously poll status")
	statusCmd.Flags().StringVar(&statusInterval, "interval", "2s", "watch polling interval (e.g. 2s, 5s)")
	statusCmd.Flags().BoolVar(&statusWide, "wide", false, "show extra columns (ports)")
	statusCmd.Flags().BoolVar(&statusNoTrunc, "no-trunc", false, "show full image names")
	statusCmd.Flags().StringVar(&statusServices, "services", "", "filter by service names (comma-separated)")
	statusCmd.Flags().BoolVar(&statusCheck, "check", false, "exit code only: 0=healthy, 3=unhealthy, 4=unreachable")
	statusCmd.GroupID = "core"
	rootCmd.AddCommand(statusCmd)
}

func runStatus(cmd *cobra.Command, _ []string) error {
	ctx := cmd.Context()
	opts := GetGlobalOpts(ctx)

	state, err := config.Load(opts.DataDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	// --check: silent exit code mode (validates response body, not just HTTP status).
	if statusCheck {
		body, statusCode, fetchErr := fetchHealth(ctx, state.BackendPort)
		if fetchErr != nil {
			return NewExitError(ExitUnreachable, fetchErr)
		}
		if statusCode < 200 || statusCode >= 300 {
			return NewExitError(ExitUnhealthy, nil)
		}
		var envelope struct {
			Data healthResponse `json:"data"`
		}
		if json.Unmarshal(body, &envelope) != nil || envelope.Data.Status != "ok" {
			return NewExitError(ExitUnhealthy, nil)
		}
		return nil // exit 0
	}

	// Parse --interval early (even without --watch, catch invalid values).
	interval, parseErr := time.ParseDuration(statusInterval)
	if parseErr != nil {
		return fmt.Errorf("invalid --interval %q: %w", statusInterval, parseErr)
	}

	if statusWatch {
		if interval <= 0 {
			return fmt.Errorf("invalid --interval %q: must be > 0", statusInterval)
		}
		return runStatusWatch(cmd, state, opts, interval)
	}

	return runStatusOnce(cmd, state, opts)
}

func runStatusWatch(cmd *cobra.Command, state config.State, opts *GlobalOpts, interval time.Duration) error {
	ctx := cmd.Context()
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		// Clear screen (best-effort: ANSI escape for TTY, separator for non-TTY).
		if isInteractive() && !opts.Plain {
			_, _ = fmt.Fprint(cmd.OutOrStdout(), "\033[H\033[2J")
		} else {
			_, _ = fmt.Fprintln(cmd.OutOrStdout(), "---")
		}
		if err := runStatusOnce(cmd, state, opts); err != nil {
			return err
		}

		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
		}
	}
}

func runStatusOnce(cmd *cobra.Command, state config.State, opts *GlobalOpts) error {
	ctx := cmd.Context()
	jsonOut := opts.JSON
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())
	printVersionInfo(out, state)

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if _, err := os.Stat(composePath); errors.Is(err, os.ErrNotExist) {
		out.Warn("Not initialized -- run 'synthorg init' first.")
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
	out.KeyValue("Channel", state.DisplayChannel())
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
func renderContainerTable(out *ui.UI, containers []containerInfo, wide, noTrunc bool) {
	headers := []string{"SERVICE", "STATE", "HEALTH", "IMAGE", "STATUS"}
	if wide {
		headers = append(headers, "PORTS")
	}
	rows := make([][]string, 0, len(containers))
	for _, c := range containers {
		icon := healthIcon(c.State, c.Health)
		healthLabel := c.Health
		if healthLabel == "" {
			healthLabel = "-"
		}
		imageDisplay := imageTag(c.Image)
		if noTrunc {
			imageDisplay = c.Image
		}
		row := []string{
			c.Service, icon + " " + c.State, healthLabel,
			imageDisplay, c.Status,
		}
		if wide {
			row = append(row, c.Ports)
		}
		rows = append(rows, row)
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

	if statusServices != "" {
		containers = filterByServices(out, containers, statusServices)
	}

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
		if statusServices != "" {
			out.Warn("No containers match requested services")
		} else {
			out.Warn("No containers running")
		}
		return
	}
	_, _ = fmt.Fprintln(w, "Containers:")
	renderContainerTable(out, containers, statusWide, statusNoTrunc)
	out.HintTip("Run 'synthorg logs' to view container logs")
	_, _ = fmt.Fprintln(w)
}

// filterByServices filters containers to only those matching the comma-separated
// service names, warning about invalid names.
func filterByServices(out *ui.UI, containers []containerInfo, services string) []containerInfo {
	filter := make(map[string]bool)
	for _, s := range strings.Split(services, ",") {
		s = strings.TrimSpace(s)
		if s == "" {
			continue
		}
		if !serviceNamePattern.MatchString(s) {
			out.Warn(fmt.Sprintf("invalid service name %q in --services: must be alphanumeric, hyphens, or underscores", s))
			continue
		}
		filter[s] = true
	}
	filtered := containers[:0]
	for _, c := range containers {
		if filter[c.Service] {
			filtered = append(filtered, c)
		}
	}
	return filtered
}

func printResourceUsage(ctx context.Context, out *ui.UI, info docker.Info, dataDir string) {
	psOut, err := docker.ComposeExecOutput(ctx, info, dataDir, "ps", "-q")
	if err != nil || strings.TrimSpace(psOut) == "" {
		return
	}
	ids := strings.Fields(strings.TrimSpace(psOut))
	statsArgs := append([]string{"stats", "--no-stream", "--format",
		"table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}", "--"}, ids...)
	statsOut, err := docker.RunCmd(ctx, info.DockerPath, statsArgs...)
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
	if seconds < 0 {
		return "-" + formatUptime(-seconds)
	}
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
	out.Blank()
	out.Box("Links", []string{
		fmt.Sprintf("  %-12s http://localhost:%d", "Dashboard", state.WebPort),
		fmt.Sprintf("  %-12s http://localhost:%d/api", "API docs", state.BackendPort),
		fmt.Sprintf("  %-12s http://localhost:%d/api/v1/health", "Health", state.BackendPort),
	})
}
