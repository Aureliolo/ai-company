package cmd

import (
	"fmt"
	"net/url"
	"os"
	"path/filepath"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/diagnostics"
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

func runDoctor(cmd *cobra.Command, args []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()
	out := cmd.OutOrStdout()

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	fmt.Fprintln(out, "Collecting diagnostics...")
	report := diagnostics.Collect(ctx, state)
	text := report.FormatText()

	// Save to file.
	filename := fmt.Sprintf("synthorg-diagnostic-%s.txt", time.Now().Format("20060102-150405"))
	savePath := filepath.Join(state.DataDir, filename)
	if err := os.WriteFile(savePath, []byte(text), 0o600); err != nil {
		fmt.Fprintf(cmd.ErrOrStderr(), "Warning: could not save diagnostic file: %v\n", err)
	} else {
		fmt.Fprintf(out, "Saved to: %s\n\n", savePath)
	}

	fmt.Fprintln(out, text)

	// Generate GitHub issue URL.
	issueTitle := fmt.Sprintf("[CLI] Bug report — %s/%s, CLI %s", report.OS, report.Arch, report.CLIVersion)
	issueBody := fmt.Sprintf("## Diagnostic Report\n\n```\n%s\n```\n\n## Steps to Reproduce\n\n1. \n\n## Expected Behavior\n\n\n## Actual Behavior\n\n", text)

	// URL-encode and truncate if needed (GitHub URL limit ~8000 chars).
	encodedBody := url.QueryEscape(issueBody)
	if len(encodedBody) > 6000 {
		encodedBody = url.QueryEscape("## Diagnostic Report\n\nSee attached diagnostic file.\n\n## Steps to Reproduce\n\n1. \n")
	}

	issueURL := fmt.Sprintf(
		"https://github.com/Aureliolo/synthorg/issues/new?title=%s&labels=type%%3Abug&body=%s",
		url.QueryEscape(issueTitle),
		encodedBody,
	)

	fmt.Fprintf(out, "File a bug report:\n  %s\n", issueURL)

	return nil
}
