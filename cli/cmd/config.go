package cmd

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
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
  memory_backend        Memory backend (read-only)
  output                Output format
  persistence_backend   Persistence backend (read-only)
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
	Args:              cobra.ExactArgs(2),
	RunE:              runConfigSet,
	ValidArgsFunction: completeConfigSetKeys,
}

var configUnsetCmd = &cobra.Command{
	Use:               "unset <key>",
	Short:             "Reset a configuration key to its default value",
	Args:              cobra.ExactArgs(1),
	RunE:              runConfigUnset,
	ValidArgsFunction: completeConfigUnsetKeys,
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
	printConfigFields(out, state)
	return nil
}

// printConfigFields renders all config fields as key-value pairs.
func printConfigFields(out *ui.UI, state config.State) {
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

func completeConfigSetKeys(_ *cobra.Command, args []string, _ string) ([]string, cobra.ShellCompDirective) {
	if len(args) == 0 {
		return supportedConfigKeys, cobra.ShellCompDirectiveNoFileComp
	}
	return nil, cobra.ShellCompDirectiveNoFileComp
}

func completeConfigUnsetKeys(_ *cobra.Command, _ []string, _ string) ([]string, cobra.ShellCompDirective) {
	return supportedConfigKeys, cobra.ShellCompDirectiveNoFileComp
}

func runConfigGet(cmd *cobra.Command, args []string) error {
	key := args[0]
	if !isKnownGettableKey(key) {
		return fmt.Errorf("unknown config key %q (supported: %s)", key, strings.Join(gettableConfigKeys, ", "))
	}

	safeDir, err := config.SecurePath(GetGlobalOpts(cmd.Context()).DataDir)
	if err != nil {
		return fmt.Errorf("invalid data directory: %w", err)
	}

	state, err := config.Load(safeDir)
	if err != nil {
		return fmt.Errorf("loading config: %w", err)
	}

	_, _ = fmt.Fprintln(cmd.OutOrStdout(), configGetValue(state, key))
	return nil
}

// isKnownGettableKey reports whether key is in the gettableConfigKeys list.
func isKnownGettableKey(key string) bool {
	return slices.Contains(gettableConfigKeys, key)
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

	if key == "image_tag" {
		state.VerifiedDigests = nil // old pins are for the previous tag
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
		return setBool(value, key, &state.AutoApplyCompose)
	case "auto_cleanup":
		return setBool(value, key, &state.AutoCleanup)
	case "auto_pull":
		return setBool(value, key, &state.AutoPull)
	case "auto_restart":
		return setBool(value, key, &state.AutoRestart)
	case "auto_start_after_wipe":
		return setBool(value, key, &state.AutoStartAfterWipe)
	case "auto_update_cli":
		return setBool(value, key, &state.AutoUpdateCLI)
	case "backend_port":
		return setPort(value, "backend_port", state.WebPort, &state.BackendPort)
	case "channel":
		return setEnum(value, key, config.IsValidChannel, config.ChannelNames, &state.Channel)
	case "color":
		return setEnum(value, key, config.IsValidColorMode, config.ColorModeNames, &state.Color)
	case "docker_sock":
		if err := validateDockerSock(value); err != nil {
			return fmt.Errorf("invalid docker_sock: %w", err)
		}
		state.DockerSock = value
	case "hints":
		return setEnum(value, key, config.IsValidHintsMode, config.HintsModeNames, &state.Hints)
	case "image_tag":
		if !config.IsValidImageTag(value) {
			return fmt.Errorf("invalid image_tag %q: must match [a-zA-Z0-9][a-zA-Z0-9._-]*", value)
		}
		state.ImageTag = value
	case "log_level":
		return setEnum(value, key, config.IsValidLogLevel, config.LogLevelNames, &state.LogLevel)
	case "output":
		return setEnum(value, key, config.IsValidOutputMode, config.OutputModeNames, &state.Output)
	case "sandbox":
		return setBool(value, key, &state.Sandbox)
	case "timestamps":
		return setEnum(value, key, config.IsValidTimestampMode, config.TimestampModeNames, &state.Timestamps)
	case "web_port":
		return setPort(value, "web_port", state.BackendPort, &state.WebPort)
	default:
		return fmt.Errorf("unknown config key %q (supported: %s)", key, strings.Join(supportedConfigKeys, ", "))
	}
	return nil
}

// setBool validates and sets a boolean config field.
func setBool(value, key string, target *bool) error {
	if !config.IsValidBool(value) {
		return fmt.Errorf("invalid %s %q: must be one of %s", key, value, config.BoolNames())
	}
	*target = value == "true"
	return nil
}

// setPort validates and sets a port config field, checking for conflicts.
func setPort(value, key string, conflictPort int, target *int) error {
	port, err := strconv.Atoi(value)
	if err != nil || port < 1 || port > 65535 {
		return fmt.Errorf("invalid %s %q: must be 1-65535", key, value)
	}
	otherKey := "web_port"
	if key == "web_port" {
		otherKey = "backend_port"
	}
	if port == conflictPort {
		return fmt.Errorf("%s %d conflicts with %s (%d)", key, port, otherKey, conflictPort)
	}
	*target = port
	return nil
}

// setEnum validates and sets a string config field against a validator.
func setEnum(value, key string, valid func(string) bool, names func() string, target *string) error {
	if !valid(value) {
		return fmt.Errorf("invalid %s %q: must be one of %s", key, value, names())
	}
	*target = value
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
	// Use config.SecurePath directly (not safeStateDir) so that CodeQL
	// can trace the sanitization for go/path-injection.
	safeDir, err := config.SecurePath(state.DataDir)
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

	if err := resetConfigValue(&state, key); err != nil {
		return err
	}
	// Validate port uniqueness after resetting to default.
	if key == "backend_port" && state.BackendPort == state.WebPort {
		return fmt.Errorf("default backend_port %d conflicts with current web_port %d", state.BackendPort, state.WebPort)
	}
	if key == "web_port" && state.WebPort == state.BackendPort {
		return fmt.Errorf("default web_port %d conflicts with current backend_port %d", state.WebPort, state.BackendPort)
	}
	if key == "image_tag" {
		state.VerifiedDigests = nil
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

// resetConfigValue resets a single config key to its default value.
func resetConfigValue(state *config.State, key string) error {
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
	entries := make([]configEntry, 0, len(gettableConfigKeys))

	for _, key := range gettableConfigKeys {
		val := configGetValue(state, key)
		defaultVal := configGetValue(defaults, key)
		source := resolveSource(key, val, defaultVal)
		effectiveVal := val
		switch source {
		case "env":
			if envVal := os.Getenv(envVarForKey(key)); envVal != "" {
				effectiveVal = envVal
			}
		case "default":
			effectiveVal = defaultVal
		}
		entries = append(entries, configEntry{Key: key, Value: effectiveVal, Source: source})
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
	case "memory_backend":
		return state.MemoryBackend
	case "output":
		return state.Output
	case "persistence_backend":
		return state.PersistenceBackend
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
	safeDir, err := config.SecurePath(opts.DataDir)
	if err != nil {
		return fmt.Errorf("invalid data directory: %w", err)
	}
	_, _ = fmt.Fprintln(cmd.OutOrStdout(), config.StatePath(safeDir))
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

	editorBin, editorArgs := resolveEditor()
	// Resolve to absolute path via LookPath to satisfy CodeQL go/command-injection
	// and prevent relative-path confusion. Falls back to the raw name if not found
	// (exec.CommandContext will produce a clear error).
	if resolved, lookErr := exec.LookPath(editorBin); lookErr == nil {
		editorBin = resolved
	}
	editorArgs = append(editorArgs, configPath)
	c := exec.CommandContext(cmd.Context(), editorBin, editorArgs...) //nolint:gosec // editor comes from user's env
	c.Stdin = os.Stdin
	c.Stdout = cmd.OutOrStdout()
	c.Stderr = cmd.ErrOrStderr()
	if err := c.Run(); err != nil {
		return fmt.Errorf("running editor %q: %w", editorBin, err)
	}

	// Validate after edit.
	if _, loadErr := config.Load(safeDir); loadErr != nil {
		errOut.Warn(fmt.Sprintf("Config file has errors: %v", loadErr))
		errOut.HintError("Run 'synthorg config edit' to fix, or 'synthorg init' to regenerate")
	}
	return nil
}

// resolveEditor picks an editor from environment or platform default.
// Returns the binary name and any extra arguments (handles "code --wait" etc.).
func resolveEditor() (string, []string) {
	raw := os.Getenv("VISUAL")
	if raw == "" {
		raw = os.Getenv("EDITOR")
	}
	parts := strings.Fields(raw)
	if len(parts) == 0 {
		if runtime.GOOS == "windows" {
			return "notepad", nil
		}
		return "vi", nil
	}
	return parts[0], parts[1:]
}
