package cmd

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/diagnostics"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

var doctorCmd = &cobra.Command{
	Use:   "doctor",
	Short: "Run diagnostics and generate a bug report",
	Long:  "Collects system info, container states, health, and logs. Saves a diagnostic file and prints a pre-filled GitHub issue URL.",
	RunE:  runDoctor,
}

func init() {
	rootCmd.AddCommand(doctorCmd)
}

func runDoctor(cmd *cobra.Command, _ []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()
	out := ui.NewUI(cmd.OutOrStdout())

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	out.Step("Collecting diagnostics...")
	report := diagnostics.Collect(ctx, state)

	// Save full plain-text report to file (for bug report attachment).
	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	filename := fmt.Sprintf("synthorg-diagnostic-%s.txt", time.Now().Format("20060102-150405"))
	savePath := filepath.Join(safeDir, filename)
	text := report.FormatText()
	if err := os.WriteFile(savePath, []byte(text), 0o600); err != nil {
		out.Warn(fmt.Sprintf("Could not save diagnostic file: %v", err))
	} else {
		out.Success(fmt.Sprintf("Saved to: %s", savePath))
	}
	_, _ = fmt.Fprintln(out.Writer())

	// Render styled output to terminal.
	renderDoctorEnvironment(out, report)
	renderDoctorHealth(out, report)
	renderDoctorContainers(out, report)
	renderDoctorImages(out, report)
	renderDoctorInfra(out, report)
	renderDoctorConfig(out, state)
	renderDoctorDisk(out, report)
	renderDoctorErrors(out, report)

	_, _ = fmt.Fprintln(out.Writer())
	out.Section("Links")
	out.Link("Dashboard", fmt.Sprintf("http://localhost:%d", state.WebPort))
	out.Link("API docs", fmt.Sprintf("http://localhost:%d/docs/api", state.BackendPort))

	_, _ = fmt.Fprintln(out.Writer())
	out.Hint("Run 'synthorg doctor report' to file a bug report")
	out.Hint("Run 'synthorg logs' to view container logs")

	return nil
}

func renderDoctorEnvironment(out *ui.UI, r diagnostics.Report) {
	out.Section("Environment")
	out.KeyValue("OS", fmt.Sprintf("%s/%s", r.OS, r.Arch))
	out.KeyValue("CLI", fmt.Sprintf("%s (%s)", r.CLIVersion, r.CLICommit))
	out.KeyValue("Docker", r.DockerVersion)
	out.KeyValue("Compose", r.ComposeVersion)
	_, _ = fmt.Fprintln(out.Writer())
}

func renderDoctorHealth(out *ui.UI, r diagnostics.Report) {
	if r.HealthStatus == "" {
		return
	}
	switch r.HealthStatus {
	case "200":
		out.Success(fmt.Sprintf("Backend healthy (HTTP %s)", r.HealthStatus))
	case "unreachable":
		out.Error("Backend unreachable")
	default:
		out.Error(fmt.Sprintf("Backend unhealthy (HTTP %s)", r.HealthStatus))
	}
}

func renderDoctorContainers(out *ui.UI, r diagnostics.Report) {
	if len(r.ContainerSummary) == 0 {
		out.Warn("No containers detected")
		return
	}
	_, _ = fmt.Fprintln(out.Writer())
	out.Section("Containers")
	for _, c := range r.ContainerSummary {
		switch {
		case c.Health == "healthy":
			out.Success(fmt.Sprintf("%-24s healthy", c.Name))
		case c.Health == "unhealthy", c.State == "exited":
			status := c.Health
			if status == "" {
				status = c.State
			}
			out.Error(fmt.Sprintf("%-24s %s", c.Name, status))
		case c.Health != "":
			out.Warn(fmt.Sprintf("%-24s %s (%s)", c.Name, c.State, c.Health))
		default:
			out.Step(fmt.Sprintf("%-24s %s", c.Name, c.State))
		}
	}
}

func renderDoctorImages(out *ui.UI, r diagnostics.Report) {
	if len(r.ImageStatus) == 0 {
		return
	}
	_, _ = fmt.Fprintln(out.Writer())
	out.Section("Images")
	for _, img := range r.ImageStatus {
		if strings.HasSuffix(img, ": available") {
			out.Success(img)
		} else {
			out.Error(img)
		}
	}
}

func renderDoctorInfra(out *ui.UI, r diagnostics.Report) {
	_, _ = fmt.Fprintln(out.Writer())
	if r.ComposeFileExists {
		valid := "not checked"
		if r.ComposeFileValid != nil {
			if *r.ComposeFileValid {
				valid = "valid"
			} else {
				valid = "invalid"
			}
		}
		if valid == "valid" {
			out.Success(fmt.Sprintf("Compose file: exists, %s", valid))
		} else {
			out.Warn(fmt.Sprintf("Compose file: exists, %s", valid))
		}
	} else {
		out.Error("Compose file: not found")
	}
	for _, conflict := range r.PortConflicts {
		out.Error(fmt.Sprintf("Port conflict: %s", conflict))
	}
}

func renderDoctorConfig(out *ui.UI, state config.State) {
	_, _ = fmt.Fprintln(out.Writer())
	out.Section("Config")
	out.KeyValue("Data dir", state.DataDir)
	out.KeyValue("Image tag", state.ImageTag)
	out.KeyValue("Backend port", fmt.Sprintf("%d", state.BackendPort))
	out.KeyValue("Web port", fmt.Sprintf("%d", state.WebPort))
	out.KeyValue("Sandbox", fmt.Sprintf("%v", state.Sandbox))
	out.KeyValue("Persistence", state.PersistenceBackend)
	out.KeyValue("Memory", state.MemoryBackend)
	out.KeyValue("Log level", state.LogLevel)
	out.KeyValue("JWT secret", maskSecret(state.JWTSecret))
	out.KeyValue("Settings key", maskSecret(state.SettingsKey))
}

func renderDoctorDisk(out *ui.UI, r diagnostics.Report) {
	if r.DiskInfo == "" {
		return
	}
	_, _ = fmt.Fprintln(out.Writer())
	out.Section("Disk")
	// DiskInfo is a single line like "Total: 930.6 GiB  Used: 596.8 GiB  Free: 333.7 GiB  (64% used)"
	_, _ = fmt.Fprintf(out.Writer(), "  %s\n", r.DiskInfo)
}

func renderDoctorErrors(out *ui.UI, r diagnostics.Report) {
	if len(r.Errors) == 0 {
		return
	}
	_, _ = fmt.Fprintln(out.Writer())
	out.Section("Errors")
	for _, e := range r.Errors {
		out.Error(e)
	}
}
