package cmd

import (
	"context"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
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

// setupClient is the shared HTTP client for setup API requests.
// Per-request timeouts are controlled via context.WithTimeout.
var setupClient = &http.Client{
	CheckRedirect: func(_ *http.Request, _ []*http.Request) error {
		return http.ErrUseLastResponse
	},
}

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

	// Reset the setup_complete flag via the settings API.
	out.Step("Resetting setup flag...")
	if err := resetSetupFlag(ctx, state); err != nil {
		return fmt.Errorf("resetting setup flag: %w", err)
	}
	out.Success("Setup flag reset")

	// Open browser to the setup page.
	setupURL := fmt.Sprintf("http://localhost:%d/setup", state.WebPort)
	out.Step(fmt.Sprintf("Opening %s", setupURL))
	if err := openBrowser(ctx, setupURL); err != nil {
		errOut.Warn(fmt.Sprintf("Could not open browser: %v", err))
		errOut.Hint(fmt.Sprintf("Open %s manually in your browser.", setupURL))
	}

	return nil
}

// resetSetupFlag calls DELETE /api/v1/settings/api/setup_complete to reset
// the first-run flag so the setup wizard re-appears.
func resetSetupFlag(ctx context.Context, state config.State) error {
	apiURL := fmt.Sprintf("http://localhost:%d/api/v1/settings/api/setup_complete", state.BackendPort)

	ctx, cancel := context.WithTimeout(ctx, 10*time.Second)
	defer cancel()

	req, err := http.NewRequestWithContext(ctx, http.MethodDelete, apiURL, nil)
	if err != nil {
		return fmt.Errorf("creating request: %w", err)
	}
	req.Header.Set("Authorization", "Bearer "+buildLocalJWT(state.JWTSecret))

	resp, err := setupClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer func() {
		_, _ = io.Copy(io.Discard, io.LimitReader(resp.Body, 64*1024))
		_ = resp.Body.Close()
	}()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("API returned status %d", resp.StatusCode)
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
