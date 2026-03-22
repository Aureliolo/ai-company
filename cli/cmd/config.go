package cmd

import (
	"errors"
	"fmt"
	"os"
	"strconv"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

// supportedConfigKeys is the single source of truth for `config set` key names.
var supportedConfigKeys = []string{"auto_cleanup", "channel", "log_level"}

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

var configSetCmd = &cobra.Command{
	Use:   "set <key> <value>",
	Short: "Set a configuration value",
	Long: `Set a configuration value.

Supported keys:
  auto_cleanup  Automatically remove old images after update: "true" or "false"
  channel       Update channel: "stable" or "dev"
  log_level     Log verbosity: "debug", "info", "warn", "error"`,
	Args: cobra.ExactArgs(2),
	RunE: runConfigSet,
}

func init() {
	configCmd.AddCommand(configShowCmd)
	configCmd.AddCommand(configSetCmd)
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
			out.Warn("Not initialized -- no config found at " + statePath)
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
	out.KeyValue("Channel", state.DisplayChannel())
	out.KeyValue("Backend port", strconv.Itoa(state.BackendPort))
	out.KeyValue("Web port", strconv.Itoa(state.WebPort))
	out.KeyValue("Log level", state.LogLevel)
	out.KeyValue("Sandbox", strconv.FormatBool(state.Sandbox))
	if state.Sandbox && state.DockerSock != "" {
		out.KeyValue("Docker socket", state.DockerSock)
	}
	out.KeyValue("Persistence backend", state.PersistenceBackend)
	out.KeyValue("Memory backend", state.MemoryBackend)
	out.KeyValue("Auto cleanup", strconv.FormatBool(state.AutoCleanup))
	out.KeyValue("JWT secret", maskSecret(state.JWTSecret))
	out.KeyValue("Settings key", maskSecret(state.SettingsKey))

	return nil
}

func runConfigSet(cmd *cobra.Command, args []string) error {
	key, value := args[0], args[1]
	dir := resolveDataDir()
	out := ui.NewUI(cmd.OutOrStdout())

	state, err := config.Load(dir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	switch key {
	case "auto_cleanup":
		if !config.IsValidBool(value) {
			return fmt.Errorf("invalid auto_cleanup %q: must be one of %s", value, config.BoolNames())
		}
		state.AutoCleanup = value == "true"
	case "channel":
		if !config.IsValidChannel(value) {
			return fmt.Errorf("invalid channel %q: must be one of %s", value, config.ChannelNames())
		}
		state.Channel = value
	case "log_level":
		if !config.IsValidLogLevel(value) {
			return fmt.Errorf("invalid log_level %q: must be one of %s", value, config.LogLevelNames())
		}
		state.LogLevel = value
	default:
		return fmt.Errorf("unknown config key %q (supported: %s)", key, strings.Join(supportedConfigKeys, ", "))
	}

	if err := config.Save(state); err != nil {
		return fmt.Errorf("saving config: %w", err)
	}
	out.Success(fmt.Sprintf("Set %s = %s", key, value))
	return nil
}

func maskSecret(s string) string {
	if s == "" {
		return "(not set)"
	}
	return "****"
}
