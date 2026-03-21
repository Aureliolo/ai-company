package cmd

import (
	"context"
	"errors"
	"fmt"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

var setupCmd = &cobra.Command{
	Use:   "setup",
	Short: "Re-open the first-run setup wizard",
	Long: `Reset the setup_complete flag and open the setup wizard in the browser.

This is useful when you want to re-configure providers, company settings,
or add agents through the guided setup flow. Requires the SynthOrg stack
to be running ('synthorg start').`,
	RunE: runSetup,
}

func init() {
	rootCmd.AddCommand(setupCmd)
}

func runSetup(cmd *cobra.Command, _ []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	composePath := filepath.Join(safeDir, "compose.yml")
	if _, err := os.Stat(composePath); errors.Is(err, os.ErrNotExist) {
		return fmt.Errorf("compose.yml not found in %s -- run 'synthorg init' first", safeDir)
	}

	out := ui.NewUI(cmd.OutOrStdout())
	errOut := ui.NewUI(cmd.ErrOrStderr())

	// Verify Docker is available and containers are running.
	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}

	psOut, err := docker.ComposeExecOutput(ctx, info, safeDir, "ps", "--format", "json")
	if err != nil || psOut == "" || psOut == "[]" || psOut == "[]\n" {
		return fmt.Errorf("no containers running -- run 'synthorg start' first")
	}

	// Reset the setup_complete flag via docker exec into the backend container.
	sp := out.StartSpinner("Resetting setup flag...")
	if err := resetSetupFlag(ctx, info, safeDir); err != nil {
		sp.Error(fmt.Sprintf("Failed to reset setup flag: %v", err))
		return fmt.Errorf("resetting setup flag: %w", err)
	}
	sp.Success("Setup flag reset")

	// Open browser to the setup page.
	setupURL := fmt.Sprintf("http://localhost:%d/setup", state.WebPort)
	out.Hint(fmt.Sprintf("Opening %s", setupURL))
	if err := openBrowser(ctx, setupURL); err != nil {
		errOut.Warn(fmt.Sprintf("Could not open browser: %v", err))
		errOut.Hint(fmt.Sprintf("Open %s manually in your browser.", setupURL))
	}

	return nil
}

// resetSetupFlag deletes the setup_complete setting directly inside the
// backend container via docker compose exec. This avoids the need for API
// authentication -- the CLI manages the Docker stack locally and can exec
// into containers it controls.
func resetSetupFlag(ctx context.Context, info docker.Info, dataDir string) error {
	// Python one-liner that deletes the setup_complete row from the settings
	// table in the SQLite database. Uses the SYNTHORG_DB_PATH environment
	// variable (set in compose.yml) with a safe fallback.
	pyScript := strings.Join([]string{
		"import sqlite3, os",
		"c = sqlite3.connect(os.environ.get('SYNTHORG_DB_PATH', '/data/synthorg.db'))",
		"c.execute(\"DELETE FROM settings WHERE namespace='api' AND key='setup_complete'\")",
		"c.commit()",
		"print('ok')",
	}, "; ")

	out, err := docker.ComposeExecOutput(ctx, info, dataDir, "exec", "-T", "backend", "python", "-c", pyScript)
	if err != nil {
		return fmt.Errorf("docker exec failed: %w", err)
	}
	if !strings.Contains(strings.TrimSpace(out), "ok") {
		return fmt.Errorf("unexpected output from backend: %s", strings.TrimSpace(out))
	}
	return nil
}

// openBrowser opens a URL in the default browser. Only localhost HTTP(S)
// URLs are permitted to prevent arbitrary command execution.
func openBrowser(ctx context.Context, rawURL string) error {
	parsed, err := url.Parse(rawURL)
	if err != nil {
		return fmt.Errorf("invalid URL %q: %w", rawURL, err)
	}
	if parsed.Scheme != "http" && parsed.Scheme != "https" {
		return fmt.Errorf("refusing to open URL with scheme %q -- only http and https are allowed", parsed.Scheme)
	}
	host := parsed.Hostname()
	if host != "localhost" && host != "127.0.0.1" {
		return fmt.Errorf("refusing to open URL with host %q -- only localhost and 127.0.0.1 are allowed", host)
	}

	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.CommandContext(ctx, "rundll32", "url.dll,FileProtocolHandler", rawURL)
	case "darwin":
		cmd = exec.CommandContext(ctx, "open", rawURL)
	default:
		cmd = exec.CommandContext(ctx, "xdg-open", rawURL)
	}
	if err := cmd.Start(); err != nil {
		return fmt.Errorf("starting browser: %w", err)
	}
	go func() { _ = cmd.Wait() }() // reap child, prevent zombie
	return nil
}
