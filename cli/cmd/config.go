package cmd

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/compose"
	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/spf13/cobra"
)

// supportedConfigKeys is the single source of truth for `config set` key names.
var supportedConfigKeys = []string{
	"auto_apply_compose", "auto_cleanup", "auto_pull", "auto_restart",
	"auto_start_after_wipe", "auto_update_cli",
	"backend_port", "channel", "color", "docker_sock",
	"hints", "image_tag", "log_level", "output",
	"sandbox", "timestamps", "web_port",
}

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
  auto_apply_compose    Auto-apply compose changes
  auto_cleanup          Automatically remove old images after update
  auto_pull             Auto-accept container image pulls
  auto_restart          Auto-restart containers after update
  auto_start_after_wipe Auto-start containers after wipe
  auto_update_cli       Auto-accept CLI self-updates
  backend_port          Backend API port
  channel               Update channel
  color                 Color output mode
  docker_sock           Docker socket path
  hints                 Hint display mode
  image_tag             Current container image tag
  log_level             Log verbosity
  memory_backend        Memory backend
  output                Output format
  persistence_backend   Persistence backend
  sandbox               Sandbox enabled
  timestamps            Timestamp display mode
  web_port              Web dashboard port`,
	Args:              cobra.ExactArgs(1),
	RunE:              runConfigGet,
	ValidArgsFunction: completeConfigGetKeys,
}

var configSetCmd = &cobra.Command{
	Use:   "set <key> <value>",
	Short: "Set a configuration value",
	Long: `Set a configuration value.

Supported keys:
  auto_apply_compose     Auto-apply compose changes: "true" or "false"
  auto_cleanup           Automatically remove old images after update: "true" or "false"
  auto_pull              Auto-accept container image pulls: "true" or "false"
  auto_restart           Auto-restart containers after update: "true" or "false"
  auto_start_after_wipe  Auto-start containers after wipe: "true" or "false"
  auto_update_cli        Auto-accept CLI self-updates: "true" or "false"
  backend_port           Backend API port: 1-65535
  channel                Update channel: "stable" or "dev"
  color                  Color output: "always", "auto", "never"
  docker_sock            Docker socket path (absolute)
  hints                  Hint display: "always", "auto", "never"
  image_tag              Container image tag
  log_level              Log verbosity: "debug", "info", "warn", "error"
  output                 Output format: "text" or "json"
  sandbox                Enable sandbox: "true" or "false"
  timestamps             Timestamp format: "relative" or "iso8601"
  web_port               Web dashboard port: 1-65535

Keys that affect Docker compose (backend_port, web_port, sandbox, docker_sock,
image_tag, log_level) trigger automatic compose.yml regeneration.`,
	Args: cobra.ExactArgs(2),
	RunE: runConfigSet,
}

var configUnsetCmd = &cobra.Command{
	Use:   "unset <key>",
	Short: "Reset a configuration key to its default value",
	Args:  cobra.ExactArgs(1),
	RunE:  runConfigUnset,
}

var configListCmd = &cobra.Command{
	Use:   "list",
	Short: "Show all config keys with resolved value and source",
	Args:  cobra.NoArgs,
	RunE:  runConfigList,
}

var configPathCmd = &cobra.Command{
	Use:   "path",
	Short: "Print the config file path",
	Args:  cobra.NoArgs,
	RunE:  runConfigPath,
}

var configEditCmd = &cobra.Command{
	Use:   "edit",
	Short: "Open config file in your editor",
	Args:  cobra.NoArgs,
	RunE:  runConfigEdit,
}

func init() {
	configCmd.AddCommand(configShowCmd)
	configCmd.AddCommand(configGetCmd)
	configCmd.AddCommand(configSetCmd)
	configCmd.AddCommand(configUnsetCmd)
	configCmd.AddCommand(configListCmd)
	configCmd.AddCommand(configPathCmd)
	configCmd.AddCommand(configEditCmd)
	rootCmd.AddCommand(configCmd)
}

func runConfigShow(cmd *cobra.Command, _ []string) error {
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	safeDir, err := config.SecurePath(opts.DataDir)
	if err != nil {
		return fmt.Errorf("invalid data directory: %w", err)
	}

	statePath := config.StatePath(safeDir)
	if _, err := os.Stat(statePath); err != nil {
		if errors.Is(err, os.ErrNotExist) {
			out.Warn("Not initialized -- no config found at " + statePath)
			out.HintNextStep("Run 'synthorg init' to set up")
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
	out.KeyValue("Color", displayOrDefault(state.Color, "auto"))
	out.KeyValue("Output", displayOrDefault(state.Output, "text"))
	out.KeyValue("Timestamps", displayOrDefault(state.Timestamps, "relative"))
	out.KeyValue("Hints", displayOrDefault(state.Hints, "auto"))
	out.KeyValue("Auto update CLI", strconv.FormatBool(state.AutoUpdateCLI))
	out.KeyValue("Auto pull", strconv.FormatBool(state.AutoPull))
	out.KeyValue("Auto restart", strconv.FormatBool(state.AutoRestart))
	out.KeyValue("Auto apply compose", strconv.FormatBool(state.AutoApplyCompose))
	out.KeyValue("Auto start after wipe", strconv.FormatBool(state.AutoStartAfterWipe))
	out.KeyValue("JWT secret", maskSecret(state.JWTSecret))
	out.KeyValue("Settings key", maskSecret(state.SettingsKey))

	return nil
}

// displayOrDefault returns the value if non-empty, otherwise the fallback label.
func displayOrDefault(value, fallback string) string {
	if value == "" {
		return fallback + " (default)"
	}
	return value
}

// gettableConfigKeys lists all keys supported by `config get`.
// Keep in sync with the Long help text on configGetCmd.
var gettableConfigKeys = []string{
	"auto_apply_compose", "auto_cleanup", "auto_pull", "auto_restart",
	"auto_start_after_wipe", "auto_update_cli",
	"backend_port", "channel", "color", "docker_sock",
	"hints", "image_tag", "log_level", "memory_backend",
	"output", "persistence_backend", "sandbox", "timestamps", "web_port",
}

func completeConfigGetKeys(_ *cobra.Command, _ []string, _ string) ([]string, cobra.ShellCompDirective) {
	return gettableConfigKeys, cobra.ShellCompDirectiveNoFileComp
}

func runConfigGet(cmd *cobra.Command, args []string) error {
	key := args[0]

	safeDir, err := config.SecurePath(GetGlobalOpts(cmd.Context()).DataDir)
	if err != nil {
		return fmt.Errorf("invalid data directory: %w", err)
	}

	state, err := config.Load(safeDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	var value string
	switch key {
	case "auto_apply_compose":
		value = strconv.FormatBool(state.AutoApplyCompose)
	case "auto_cleanup":
		value = strconv.FormatBool(state.AutoCleanup)
	case "auto_pull":
		value = strconv.FormatBool(state.AutoPull)
	case "auto_restart":
		value = strconv.FormatBool(state.AutoRestart)
	case "auto_start_after_wipe":
		value = strconv.FormatBool(state.AutoStartAfterWipe)
	case "auto_update_cli":
		value = strconv.FormatBool(state.AutoUpdateCLI)
	case "backend_port":
		value = strconv.Itoa(state.BackendPort)
	case "channel":
		value = state.DisplayChannel()
	case "color":
		value = state.Color
	case "docker_sock":
		value = state.DockerSock
	case "hints":
		value = state.Hints
	case "image_tag":
		value = state.ImageTag
	case "log_level":
		value = state.LogLevel
	case "memory_backend":
		value = state.MemoryBackend
	case "output":
		value = state.Output
	case "persistence_backend":
		value = state.PersistenceBackend
	case "sandbox":
		value = strconv.FormatBool(state.Sandbox)
	case "timestamps":
		value = state.Timestamps
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
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	state, err := config.Load(opts.DataDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	if err := applyConfigValue(&state, key, value); err != nil {
		return err
	}

	if composeAffectingKeys[key] {
		if err := regenerateCompose(state); err != nil {
			return err
		}
	}

	if err := config.Save(state); err != nil {
		return fmt.Errorf("saving config: %w", err)
	}
	msg := fmt.Sprintf("Set %s = %s", key, value)
	if composeAffectingKeys[key] {
		msg += " (compose regenerated)"
	}
	out.Success(msg)
	return nil
}

// applyConfigValue validates and applies a single key=value to state.
func applyConfigValue(state *config.State, key, value string) error {
	switch key {
	case "auto_apply_compose":
		if !config.IsValidBool(value) {
			return fmt.Errorf("invalid auto_apply_compose %q: must be one of %s", value, config.BoolNames())
		}
		state.AutoApplyCompose = value == "true"
	case "auto_cleanup":
		if !config.IsValidBool(value) {
			return fmt.Errorf("invalid auto_cleanup %q: must be one of %s", value, config.BoolNames())
		}
		state.AutoCleanup = value == "true"
	case "auto_pull":
		if !config.IsValidBool(value) {
			return fmt.Errorf("invalid auto_pull %q: must be one of %s", value, config.BoolNames())
		}
		state.AutoPull = value == "true"
	case "auto_restart":
		if !config.IsValidBool(value) {
			return fmt.Errorf("invalid auto_restart %q: must be one of %s", value, config.BoolNames())
		}
		state.AutoRestart = value == "true"
	case "auto_start_after_wipe":
		if !config.IsValidBool(value) {
			return fmt.Errorf("invalid auto_start_after_wipe %q: must be one of %s", value, config.BoolNames())
		}
		state.AutoStartAfterWipe = value == "true"
	case "auto_update_cli":
		if !config.IsValidBool(value) {
			return fmt.Errorf("invalid auto_update_cli %q: must be one of %s", value, config.BoolNames())
		}
		state.AutoUpdateCLI = value == "true"
	case "backend_port":
		port, err := strconv.Atoi(value)
		if err != nil || port < 1 || port > 65535 {
			return fmt.Errorf("invalid backend_port %q: must be 1-65535", value)
		}
		if port == state.WebPort {
			return fmt.Errorf("backend_port %d conflicts with web_port", port)
		}
		state.BackendPort = port
	case "channel":
		if !config.IsValidChannel(value) {
			return fmt.Errorf("invalid channel %q: must be one of %s", value, config.ChannelNames())
		}
		state.Channel = value
	case "color":
		if !config.IsValidColorMode(value) {
			return fmt.Errorf("invalid color %q: must be one of %s", value, config.ColorModeNames())
		}
		state.Color = value
	case "docker_sock":
		if err := validateDockerSock(value); err != nil {
			return fmt.Errorf("invalid docker_sock: %w", err)
		}
		state.DockerSock = value
	case "hints":
		if !config.IsValidHintsMode(value) {
			return fmt.Errorf("invalid hints %q: must be one of %s", value, config.HintsModeNames())
		}
		state.Hints = value
	case "image_tag":
		if !config.IsValidImageTag(value) {
			return fmt.Errorf("invalid image_tag %q: must match [a-zA-Z0-9][a-zA-Z0-9._-]*", value)
		}
		state.ImageTag = value
	case "log_level":
		if !config.IsValidLogLevel(value) {
			return fmt.Errorf("invalid log_level %q: must be one of %s", value, config.LogLevelNames())
		}
		state.LogLevel = value
	case "output":
		if !config.IsValidOutputMode(value) {
			return fmt.Errorf("invalid output %q: must be one of %s", value, config.OutputModeNames())
		}
		state.Output = value
	case "sandbox":
		if !config.IsValidBool(value) {
			return fmt.Errorf("invalid sandbox %q: must be one of %s", value, config.BoolNames())
		}
		state.Sandbox = value == "true"
	case "timestamps":
		if !config.IsValidTimestampMode(value) {
			return fmt.Errorf("invalid timestamps %q: must be one of %s", value, config.TimestampModeNames())
		}
		state.Timestamps = value
	case "web_port":
		port, err := strconv.Atoi(value)
		if err != nil || port < 1 || port > 65535 {
			return fmt.Errorf("invalid web_port %q: must be 1-65535", value)
		}
		if port == state.BackendPort {
			return fmt.Errorf("web_port %d conflicts with backend_port", port)
		}
		state.WebPort = port
	default:
		return fmt.Errorf("unknown config key %q (supported: %s)", key, strings.Join(supportedConfigKeys, ", "))
	}
	return nil
}

func maskSecret(s string) string {
	if s == "" {
		return "(not set)"
	}
	return "****"
}

// composeAffectingKeys lists config keys that require compose.yml regeneration.
var composeAffectingKeys = map[string]bool{
	"backend_port": true, "web_port": true, "sandbox": true,
	"docker_sock": true, "image_tag": true, "log_level": true,
}

// regenerateCompose regenerates compose.yml from the current state.
// Called after config set/unset for compose-affecting keys.
func regenerateCompose(state config.State) error {
	safeDir, err := safeStateDir(state)
	if err != nil {
		return err
	}
	composePath := filepath.Join(safeDir, "compose.yml")

	// Only regenerate if compose.yml already exists (init creates it).
	if _, statErr := os.Stat(composePath); errors.Is(statErr, os.ErrNotExist) {
		return nil
	}

	params := compose.ParamsFromState(state)
	params.DigestPins = state.VerifiedDigests
	generated, err := compose.Generate(params)
	if err != nil {
		return fmt.Errorf("regenerating compose: %w", err)
	}
	return atomicWriteFile(composePath, generated, safeDir)
}

func runConfigUnset(cmd *cobra.Command, args []string) error {
	key := args[0]
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	state, err := config.Load(opts.DataDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	defaults := config.DefaultState()
	switch key {
	case "auto_apply_compose":
		state.AutoApplyCompose = defaults.AutoApplyCompose
	case "auto_cleanup":
		state.AutoCleanup = defaults.AutoCleanup
	case "auto_pull":
		state.AutoPull = defaults.AutoPull
	case "auto_restart":
		state.AutoRestart = defaults.AutoRestart
	case "auto_start_after_wipe":
		state.AutoStartAfterWipe = defaults.AutoStartAfterWipe
	case "auto_update_cli":
		state.AutoUpdateCLI = defaults.AutoUpdateCLI
	case "backend_port":
		state.BackendPort = defaults.BackendPort
	case "channel":
		state.Channel = defaults.Channel
	case "color":
		state.Color = ""
	case "docker_sock":
		state.DockerSock = ""
	case "hints":
		state.Hints = ""
	case "image_tag":
		state.ImageTag = defaults.ImageTag
	case "log_level":
		state.LogLevel = defaults.LogLevel
	case "output":
		state.Output = ""
	case "sandbox":
		state.Sandbox = defaults.Sandbox
	case "timestamps":
		state.Timestamps = ""
	case "web_port":
		state.WebPort = defaults.WebPort
	default:
		return fmt.Errorf("unknown config key %q (supported: %s)", key, strings.Join(supportedConfigKeys, ", "))
	}

	if composeAffectingKeys[key] {
		if err := regenerateCompose(state); err != nil {
			return err
		}
	}

	if err := config.Save(state); err != nil {
		return fmt.Errorf("saving config: %w", err)
	}
	out.Success(fmt.Sprintf("Reset %s to default", key))
	return nil
}

// configEntry represents a config key with its resolved value and source.
type configEntry struct {
	Key    string `json:"key"`
	Value  string `json:"value"`
	Source string `json:"source"`
}

// envVarForKey maps config key names to their SYNTHORG_* env var constants.
func envVarForKey(key string) string {
	switch key {
	case "backend_port":
		return EnvBackendPort
	case "web_port":
		return EnvWebPort
	case "channel":
		return EnvChannel
	case "image_tag":
		return EnvImageTag
	case "log_level":
		return EnvLogLevel
	case "auto_update_cli":
		return EnvAutoUpdateCLI
	case "auto_pull":
		return EnvAutoPull
	case "auto_restart":
		return EnvAutoRestart
	default:
		return ""
	}
}

func runConfigList(cmd *cobra.Command, _ []string) error {
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	state, err := config.Load(opts.DataDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	defaults := config.DefaultState()
	entries := make([]configEntry, 0, len(supportedConfigKeys))

	for _, key := range supportedConfigKeys {
		val := configGetValue(state, key)
		source := resolveSource(key, val, configGetValue(defaults, key))
		entries = append(entries, configEntry{Key: key, Value: val, Source: source})
	}

	if opts.JSON {
		enc := json.NewEncoder(cmd.OutOrStdout())
		enc.SetIndent("", "  ")
		return enc.Encode(entries)
	}

	for _, e := range entries {
		out.KeyValue(fmt.Sprintf("%-22s [%s]", e.Key, e.Source), e.Value)
	}
	return nil
}

// configGetValue returns the string representation of a config key's value.
func configGetValue(state config.State, key string) string {
	switch key {
	case "auto_apply_compose":
		return strconv.FormatBool(state.AutoApplyCompose)
	case "auto_cleanup":
		return strconv.FormatBool(state.AutoCleanup)
	case "auto_pull":
		return strconv.FormatBool(state.AutoPull)
	case "auto_restart":
		return strconv.FormatBool(state.AutoRestart)
	case "auto_start_after_wipe":
		return strconv.FormatBool(state.AutoStartAfterWipe)
	case "auto_update_cli":
		return strconv.FormatBool(state.AutoUpdateCLI)
	case "backend_port":
		return strconv.Itoa(state.BackendPort)
	case "channel":
		return state.DisplayChannel()
	case "color":
		return state.Color
	case "docker_sock":
		return state.DockerSock
	case "hints":
		return state.Hints
	case "image_tag":
		return state.ImageTag
	case "log_level":
		return state.LogLevel
	case "output":
		return state.Output
	case "sandbox":
		return strconv.FormatBool(state.Sandbox)
	case "timestamps":
		return state.Timestamps
	case "web_port":
		return strconv.Itoa(state.WebPort)
	default:
		return ""
	}
}

// resolveSource determines where a config value came from.
func resolveSource(key, currentVal, defaultVal string) string {
	if envVar := envVarForKey(key); envVar != "" {
		if os.Getenv(envVar) != "" {
			return "env"
		}
	}
	if currentVal != defaultVal {
		return "config"
	}
	return "default"
}

func runConfigPath(cmd *cobra.Command, _ []string) error {
	opts := GetGlobalOpts(cmd.Context())
	_, _ = fmt.Fprintln(cmd.OutOrStdout(), config.StatePath(opts.DataDir))
	return nil
}

func runConfigEdit(cmd *cobra.Command, _ []string) error {
	opts := GetGlobalOpts(cmd.Context())
	errOut := ui.NewUIWithOptions(cmd.ErrOrStderr(), opts.UIOptions())

	safeDir, err := config.SecurePath(opts.DataDir)
	if err != nil {
		return fmt.Errorf("invalid data directory: %w", err)
	}

	configPath := config.StatePath(safeDir)
	if _, statErr := os.Stat(configPath); errors.Is(statErr, os.ErrNotExist) {
		return fmt.Errorf("config file not found at %s -- run 'synthorg init' first", configPath)
	}

	editor := resolveEditor()
	c := exec.CommandContext(cmd.Context(), editor, configPath) //nolint:gosec // editor comes from user's env
	c.Stdin = os.Stdin
	c.Stdout = cmd.OutOrStdout()
	c.Stderr = cmd.ErrOrStderr()
	if err := c.Run(); err != nil {
		return fmt.Errorf("running editor %q: %w", editor, err)
	}

	// Validate after edit.
	if _, loadErr := config.Load(safeDir); loadErr != nil {
		errOut.Warn(fmt.Sprintf("Config file has errors: %v", loadErr))
		errOut.HintError("Run 'synthorg config edit' to fix, or 'synthorg init' to regenerate")
	}
	return nil
}

// resolveEditor picks an editor from environment or platform default.
func resolveEditor() string {
	if e := os.Getenv("VISUAL"); e != "" {
		return e
	}
	if e := os.Getenv("EDITOR"); e != "" {
		return e
	}
	if runtime.GOOS == "windows" {
		return "notepad"
	}
	return "vi"
}
