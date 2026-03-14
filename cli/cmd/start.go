package cmd

import (
	"context"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/health"
	"github.com/spf13/cobra"
)

var startCmd = &cobra.Command{
	Use:   "start",
	Short: "Pull images and start the SynthOrg stack",
	RunE:  runStart,
}

func init() {
	rootCmd.AddCommand(startCmd)
}

func runStart(cmd *cobra.Command, args []string) error {
	ctx := cmd.Context()
	dir := resolveDataDir()

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	composePath := filepath.Join(state.DataDir, "compose.yml")
	if _, err := os.Stat(composePath); os.IsNotExist(err) {
		return fmt.Errorf("compose.yml not found in %s — run 'synthorg init' first", state.DataDir)
	}

	info, err := docker.Detect(ctx)
	if err != nil {
		return err
	}
	fmt.Fprintf(cmd.OutOrStdout(), "Docker %s, Compose %s\n", info.DockerVersion, info.ComposeVersion)

	// Pull latest images.
	fmt.Fprintln(cmd.OutOrStdout(), "Pulling images...")
	if err := composeRun(ctx, info, state.DataDir, "pull"); err != nil {
		return fmt.Errorf("pulling images: %w", err)
	}

	// Start containers.
	fmt.Fprintln(cmd.OutOrStdout(), "Starting containers...")
	if err := composeRun(ctx, info, state.DataDir, "up", "-d"); err != nil {
		return fmt.Errorf("starting containers: %w", err)
	}

	// Wait for health.
	fmt.Fprintln(cmd.OutOrStdout(), "Waiting for backend to become healthy...")
	healthURL := fmt.Sprintf("http://localhost:%d/api/v1/health", state.BackendPort)
	if err := health.WaitForHealthy(ctx, healthURL, 90*time.Second, 2*time.Second, 5*time.Second); err != nil {
		fmt.Fprintf(cmd.ErrOrStderr(), "Warning: health check did not pass: %v\n", err)
		fmt.Fprintln(cmd.ErrOrStderr(), "Containers are running. Run 'synthorg doctor' for diagnostics.")
	} else {
		fmt.Fprintln(cmd.OutOrStdout(), "SynthOrg is running!")
		fmt.Fprintf(cmd.OutOrStdout(), "  API:       http://localhost:%d/api/v1/health\n", state.BackendPort)
		fmt.Fprintf(cmd.OutOrStdout(), "  Dashboard: http://localhost:%d\n", state.WebPort)
	}

	return nil
}

func composeRun(ctx context.Context, info docker.Info, dir string, args ...string) error {
	parts := strings.Fields(info.ComposePath)
	parts = append(parts, args...)

	c := exec.CommandContext(ctx, parts[0], parts[1:]...)
	c.Dir = dir
	c.Stdout = os.Stdout
	c.Stderr = os.Stderr
	return c.Run()
}
