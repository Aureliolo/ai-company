package cmd

import (
	"context"
	"errors"
	"fmt"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"time"

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
		return fmt.Errorf("not initialized -- run 'synthorg init' first")
	}

	out := ui.NewUI(cmd.OutOrStdout())

	// Verify Docker is available and containers are running.
	info, err := docker.Detect(ctx)
	if err != nil {
		return fmt.Errorf("docker not available: %w", err)
	}

	psOut, err := docker.ComposeExecOutput(ctx, info, safeDir, "ps", "--format", "json")
	if err != nil || psOut == "" {
		return fmt.Errorf("no containers running -- run 'synthorg start' first")
	}

	// Reset the setup_complete flag via the settings API.
	out.Step("Resetting setup flag...")
	if err := resetSetupFlag(ctx, state); err != nil {
		out.Warn(fmt.Sprintf("Could not reset setup flag: %v", err))
		out.Hint("You can manually delete the api.setup_complete setting.")
	} else {
		out.Success("Setup flag reset")
	}

	// Open browser to the setup page.
	setupURL := fmt.Sprintf("http://localhost:%d/setup", state.WebPort)
	out.Step(fmt.Sprintf("Opening %s", setupURL))
	if err := openBrowser(ctx, setupURL); err != nil {
		out.Warn(fmt.Sprintf("Could not open browser: %v", err))
		out.Hint(fmt.Sprintf("Open %s manually in your browser.", setupURL))
	}

	return nil
}

// resetSetupFlag calls DELETE /api/v1/settings/api/setup_complete to reset
// the first-run flag so the setup wizard re-appears.
func resetSetupFlag(ctx context.Context, state config.State) error {
	url := fmt.Sprintf("http://localhost:%d/api/v1/settings/api/setup_complete", state.BackendPort)

	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, url, nil)
	if err != nil {
		return fmt.Errorf("creating request: %w", err)
	}

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("API returned status %d", resp.StatusCode)
	}
	return nil
}

// openBrowser opens a URL in the default browser.
func openBrowser(ctx context.Context, url string) error {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.CommandContext(ctx, "rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.CommandContext(ctx, "open", url)
	default:
		cmd = exec.CommandContext(ctx, "xdg-open", url)
	}
	return cmd.Start()
}
