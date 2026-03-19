package cmd

import (
	"errors"
	"fmt"
	"os"
	"strconv"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "Manage SynthOrg configuration",
	Long: `Display or manage the SynthOrg CLI configuration.

Running 'synthorg config' without a subcommand shows the current configuration
(equivalent to 'synthorg config show').`,
	Args: cobra.NoArgs,
	RunE: runConfigShow,
}

var configShowCmd = &cobra.Command{
	Use:   "show",
	Short: "Display current configuration",
	Args:  cobra.NoArgs,
	RunE:  runConfigShow,
}

func init() {
	configCmd.AddCommand(configShowCmd)
	rootCmd.AddCommand(configCmd)
}

func runConfigShow(cmd *cobra.Command, _ []string) error {
	dir := resolveDataDir()
	out := ui.NewUI(cmd.OutOrStdout())

	safeDir, err := config.SecurePath(dir)
	if err != nil {
		return fmt.Errorf("invalid data directory: %w", err)
	}

	statePath := config.StatePath(safeDir)
	if _, err := os.Stat(statePath); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			out.Warn("Not initialized — no config found at " + statePath)
			out.Hint("Run 'synthorg init' to set up")
			return nil
		}
		return fmt.Errorf("checking config file: %w", err)
	}

	state, err := config.Load(safeDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	out.KeyValue("Config file", statePath)
	out.KeyValue("Data directory", state.DataDir)
	out.KeyValue("Image tag", state.ImageTag)
	out.KeyValue("Backend port", strconv.Itoa(state.BackendPort))
	out.KeyValue("Web port", strconv.Itoa(state.WebPort))
	out.KeyValue("Log level", state.LogLevel)
	out.KeyValue("Sandbox", strconv.FormatBool(state.Sandbox))
	if state.Sandbox && state.DockerSock != "" {
		out.KeyValue("Docker socket", state.DockerSock)
	}
	out.KeyValue("Persistence backend", state.PersistenceBackend)
	out.KeyValue("Memory backend", state.MemoryBackend)
	out.KeyValue("JWT secret", maskSecret(state.JWTSecret))
	out.KeyValue("Settings key", maskSecret(state.SettingsKey))

	return nil
}

func maskSecret(s string) string {
	if s == "" {
		return "(not set)"
	}
	return "****"
}
