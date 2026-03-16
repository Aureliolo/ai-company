package cmd

import (
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/diagnostics"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/Aureliolo/synthorg/cli/internal/version"
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
	text := report.FormatText()

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	filename := fmt.Sprintf("synthorg-diagnostic-%s.txt", time.Now().Format("20060102-150405"))
	savePath := filepath.Join(safeDir, filename)
	if err := os.WriteFile(savePath, []byte(text), 0o600); err != nil {
		errOut := ui.NewUI(cmd.ErrOrStderr())
		errOut.Warn(fmt.Sprintf("Could not save diagnostic file: %v", err))
	} else {
		out.Success(fmt.Sprintf("Saved to: %s", savePath))
	}

	_, _ = fmt.Fprintln(out.Writer())
	_, _ = fmt.Fprintln(out.Writer(), text)

	issueURL := buildIssueURL(report)

	out.Hint("To file a bug report:")
	out.KeyValue("1. Attach", savePath)
	out.Link("2. Open", issueURL)

	_, _ = fmt.Fprintln(out.Writer())
	out.Link("Dashboard", fmt.Sprintf("http://localhost:%d", state.WebPort))
	out.Link("API docs", fmt.Sprintf("http://localhost:%d/api", state.BackendPort))

	return nil
}

func buildIssueURL(report diagnostics.Report) string {
	issueTitle := fmt.Sprintf("[CLI] Bug report — %s/%s, CLI %s",
		report.OS, report.Arch, report.CLIVersion)
	issueBody := fmt.Sprintf(
		"## Environment\n\nOS: %s/%s\nCLI: %s (%s)\nDocker: %s\nCompose: %s\nHealth: %s\n\n"+
			"> Attach the diagnostic file from `synthorg doctor`\n\n"+
			"## Steps to Reproduce\n\n1. \n\n## Expected Behavior\n\n\n## Actual Behavior\n\n",
		report.OS, report.Arch, report.CLIVersion, report.CLICommit,
		report.DockerVersion, report.ComposeVersion, report.HealthStatus,
	)

	encodedBody := url.QueryEscape(issueBody)
	if len(encodedBody) > 3500 {
		issueBody = fmt.Sprintf(
			"## Environment\n\nOS: %s/%s\nCLI: %s\nDocker: %s\nHealth: %s\n\n"+
				"> Attach the diagnostic file from `synthorg doctor`\n",
			report.OS, report.Arch, report.CLIVersion,
			report.DockerVersion, report.HealthStatus,
		)
		encodedBody = url.QueryEscape(issueBody)
	}

	return fmt.Sprintf(
		"%s/issues/new?title=%s&labels=type%%3Abug&body=%s",
		version.RepoURL,
		url.QueryEscape(issueTitle),
		encodedBody,
	)
}
