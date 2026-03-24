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

var configGetCmd = &cobra.Command{
	Use:   "get <key>",
	Short: "Get a configuration value",
	Long: `Get a single configuration value.

Supported keys:
  auto_cleanup          Automatically remove old images after update
  channel               Update channel
  image_tag             Current container image tag
  log_level             Log verbosity
  sandbox               Sandbox enabled
  backend_port          Backend API port
  web_port              Web dashboard port
  persistence_backend   Persistence backend
  memory_backend        Memory backend`,
	Args:              cobra.ExactArgs(1),
	RunE:              runConfigGet,
	ValidArgsFunction: completeConfigGetKeys,
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
	configCmd.AddCommand(configGetCmd)
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

// gettableConfigKeys lists all keys supported by `config get`.
// Keep in sync with the Long help text on configGetCmd.
var gettableConfigKeys = []string{
	"auto_cleanup", "backend_port", "channel", "image_tag",
	"log_level", "memory_backend", "persistence_backend",
	"sandbox", "web_port",
}

func completeConfigGetKeys(_ *cobra.Command, _ []string, _ string) ([]string, cobra.ShellCompDirective) {
	return gettableConfigKeys, cobra.ShellCompDirectiveNoFileComp
}

func runConfigGet(cmd *cobra.Command, args []string) error {
	key := args[0]
	dir := resolveDataDir()

	safeDir, err := config.SecurePath(dir)
	if err != nil {
		return fmt.Errorf("invalid data directory: %w", err)
	}

	state, err := config.Load(safeDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	var value string
	switch key {
	case "auto_cleanup":
		value = strconv.FormatBool(state.AutoCleanup)
	case "backend_port":
		value = strconv.Itoa(state.BackendPort)
	case "channel":
		value = state.DisplayChannel()
	case "image_tag":
		value = state.ImageTag
	case "log_level":
		value = state.LogLevel
	case "memory_backend":
		value = state.MemoryBackend
	case "persistence_backend":
		value = state.PersistenceBackend
	case "sandbox":
		value = strconv.FormatBool(state.Sandbox)
	case "web_port":
		value = strconv.Itoa(state.WebPort)
	default:
		return fmt.Errorf("unknown config key %q (supported: %s)", key, strings.Join(gettableConfigKeys, ", "))
	}

	_, _ = fmt.Fprintln(cmd.OutOrStdout(), value)
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
