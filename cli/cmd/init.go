package cmd

import (
	"crypto/rand"
	"encoding/base64"
	"fmt"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/compose"
	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/Aureliolo/synthorg/cli/internal/version"
	"github.com/charmbracelet/huh"
	"github.com/spf13/cobra"
)

var (
	initBackendPort int
	initWebPort     int
	initSandbox     string
	initImageTag    string
	initChannel     string
	initLogLevel    string
)

var initCmd = &cobra.Command{
	Use:   "init",
	Short: "Interactive setup wizard for SynthOrg",
	Long: `Creates a data directory, generates a Docker Compose file, and optionally pulls images.

When all required flags are provided, the interactive wizard is skipped
(useful for CI/automation).`,
	Example: `  synthorg init                                         # interactive setup wizard
  synthorg init --backend-port 3001 --web-port 3000 --sandbox true  # non-interactive`,
	RunE: runInit,
}

func init() {
	initCmd.Flags().IntVar(&initBackendPort, "backend-port", 0, "backend API port (1-65535)")
	initCmd.Flags().IntVar(&initWebPort, "web-port", 0, "web dashboard port (1-65535)")
	initCmd.Flags().StringVar(&initSandbox, "sandbox", "", "enable agent sandbox (\"true\" or \"false\")")
	initCmd.Flags().StringVar(&initImageTag, "image-tag", "", "container image tag")
	initCmd.Flags().StringVar(&initChannel, "channel", "", "update channel (\"stable\" or \"dev\")")
	initCmd.Flags().StringVar(&initLogLevel, "log-level", "", "log level (\"debug\", \"info\", \"warn\", \"error\")")
	initCmd.GroupID = "core"
	rootCmd.AddCommand(initCmd)
}

// initAllFlagsSet returns true when all required init flags are provided,
// enabling fully non-interactive setup. The --image-tag and --channel flags
// are optional (default to CLI version and "stable" respectively).
// Telemetry opt-in is intentionally interactive-only; non-interactive
// init defaults to telemetry disabled (opt-in via "config set" or env var).
func initAllFlagsSet() bool {
	return initBackendPort > 0 && initWebPort > 0 && initSandbox != "" &&
		initLogLevel != ""
}

func runInit(cmd *cobra.Command, _ []string) error {
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	if err := validateInitFlags(); err != nil {
		return err
	}
	var answers setupAnswers
	switch {
	case initAllFlagsSet():
		// Non-interactive: all required flags provided.
		answers = buildAnswersFromFlags(opts.DataDir)
	case isInteractive():
		out.Logo(version.Version)
		var err error
		answers, err = runSetupFormWithOverrides(opts.DataDir)
		if err != nil {
			return err
		}
	default:
		return fmt.Errorf("synthorg init requires an interactive terminal (or provide all flags: --backend-port, --web-port, --sandbox, --log-level)")
	}

	state, err := buildState(answers)
	if err != nil {
		return err
	}

	// Handle re-init over existing config (secrets change, needs confirmation).
	if existing := config.StatePath(state.DataDir); fileExists(existing) {
		proceed, err := handleReinit(cmd, &state, opts)
		if err != nil {
			return err
		}
		if !proceed {
			return nil
		}
	}

	safeDir, err := writeInitFiles(state)
	if err != nil {
		return err
	}

	printInitSuccess(out, safeDir)
	hintAfterInit(out, state)
	return nil
}

// hintAfterInit emits contextual guidance after a successful init.
func hintAfterInit(out *ui.UI, state config.State) {
	if state.Channel == "dev" {
		out.HintTip("Dev channel receives frequent pre-release updates. Run 'synthorg config set channel stable' to switch.")
	}
	out.HintGuidance("Customize settings later with 'synthorg config set <key> <value>'. Run 'synthorg config list' to see all options.")
}

// handleReinit loads the existing config, confirms overwrite (interactive or
// --yes), and preserves the settings key in state. Returns false if declined.
func handleReinit(cmd *cobra.Command, state *config.State, opts *GlobalOpts) (bool, error) {
	oldState, loadErr := config.Load(state.DataDir)
	if loadErr != nil {
		return false, fmt.Errorf("existing config at %s is unreadable: %w (delete it manually to force a fresh init)",
			config.StatePath(state.DataDir), loadErr)
	}
	if opts.Yes {
		if oldState.SettingsKey != "" {
			state.SettingsKey = oldState.SettingsKey
		}
		return true, nil
	}
	if !isInteractive() {
		return false, fmt.Errorf("existing config found at %s; pass --yes to overwrite",
			config.StatePath(state.DataDir))
	}
	kept, err := confirmReinit(cmd, oldState, opts)
	if err != nil {
		return false, err
	}
	if kept == nil {
		return false, nil
	}
	if *kept != "" {
		state.SettingsKey = *kept
	}
	return true, nil
}

// confirmReinit prompts the user to confirm overwriting existing config.
// Returns a pointer to the existing settings key to preserve, or nil if the
// user declined. An empty string means no key existed to preserve.
func confirmReinit(cmd *cobra.Command, oldState config.State, opts *GlobalOpts) (*string, error) {
	errOut := ui.NewUIWithOptions(cmd.ErrOrStderr(), opts.UIOptions())
	errOut.Warn("Existing config at " + config.StatePath(oldState.DataDir) + " will be overwritten.")
	errOut.Warn("A new JWT secret will be generated -- running containers will need a restart.")
	if oldState.SettingsKey == "" {
		errOut.Warn("A new settings encryption key will also be generated.")
	}
	var proceed bool
	form := huh.NewForm(huh.NewGroup(
		huh.NewConfirm().Title("Overwrite existing configuration?").Value(&proceed),
	))
	if err := form.Run(); err != nil {
		return nil, err
	}
	if !proceed {
		return nil, nil
	}
	key := oldState.SettingsKey
	return &key, nil
}

func printInitSuccess(out *ui.UI, dataDir string) {
	out.Blank()
	out.Success("SynthOrg initialized")
	out.KeyValue("Data dir", dataDir)
	out.KeyValue("Compose file", filepath.Join(dataDir, "compose.yml"))
	out.KeyValue("Config", config.StatePath(dataDir))
	out.Warn("Keep compose.yml and config.json private -- they contain your secrets.")
	out.HintNextStep("Run 'synthorg start' to launch.")
}

// setupAnswers holds raw form input before validation.
type setupAnswers struct {
	dir                string
	backendPortStr     string
	webPortStr         string
	sandbox            bool
	dockerSock         string
	logLevel           string
	persistenceBackend string
	memoryBackend      string
	channel            string // optional override (empty = default "stable")
	imageTag           string // optional override (empty = use CLI version)
	telemetryOptIn     bool
}

// validateInitFlags checks that provided CLI flag values are valid before
// the interactive/non-interactive branch. Only validates flags that were set.
func validateInitFlags() error {
	if initBackendPort != 0 && (initBackendPort < 1 || initBackendPort > 65535) {
		return fmt.Errorf("invalid --backend-port %d: must be 1-65535", initBackendPort)
	}
	if initWebPort != 0 && (initWebPort < 1 || initWebPort > 65535) {
		return fmt.Errorf("invalid --web-port %d: must be 1-65535", initWebPort)
	}
	if initBackendPort != 0 && initWebPort != 0 && initBackendPort == initWebPort {
		return fmt.Errorf("--backend-port and --web-port must differ, both are %d", initBackendPort)
	}
	if initSandbox != "" && !config.IsValidBool(initSandbox) {
		return fmt.Errorf("invalid --sandbox %q: must be \"true\" or \"false\"", initSandbox)
	}
	if initLogLevel != "" && !config.IsValidLogLevel(initLogLevel) {
		return fmt.Errorf("invalid --log-level %q: must be one of %s", initLogLevel, config.LogLevelNames())
	}
	if initImageTag != "" && !config.IsValidImageTag(initImageTag) {
		return fmt.Errorf("invalid --image-tag %q: must match [a-zA-Z0-9][a-zA-Z0-9._-]*", initImageTag)
	}
	if initChannel != "" && !config.IsValidChannel(initChannel) {
		return fmt.Errorf("invalid --channel %q: must be one of %s", initChannel, config.ChannelNames())
	}
	return nil
}

// applyFlagOverrides pre-fills the setup answers with any CLI flag values that were set.
func applyFlagOverrides(a *setupAnswers) {
	if initBackendPort > 0 {
		a.backendPortStr = strconv.Itoa(initBackendPort)
	}
	if initWebPort > 0 {
		a.webPortStr = strconv.Itoa(initWebPort)
	}
	if initSandbox != "" {
		a.sandbox = initSandbox == "true"
	}
	if initLogLevel != "" {
		a.logLevel = initLogLevel
	}
	if initChannel != "" {
		a.channel = initChannel
	}
	if initImageTag != "" {
		a.imageTag = initImageTag
	}
}

// buildAnswersFromFlags constructs setupAnswers from CLI flags for non-interactive mode.
func buildAnswersFromFlags(dataDir string) setupAnswers {
	defaults := config.DefaultState()
	a := setupAnswers{
		dir:                dataDir,
		backendPortStr:     strconv.Itoa(initBackendPort),
		webPortStr:         strconv.Itoa(initWebPort),
		sandbox:            initSandbox == "true",
		dockerSock:         defaultDockerSock(),
		logLevel:           initLogLevel,
		persistenceBackend: defaults.PersistenceBackend,
		memoryBackend:      defaults.MemoryBackend,
		channel:            initChannel,
		imageTag:           initImageTag,
	}
	return a
}

// runSetupFormWithOverrides runs the interactive form with any CLI flag values
// pre-filled as defaults.
func runSetupFormWithOverrides(resolvedDataDir string) (setupAnswers, error) {
	defaults := config.DefaultState()
	dir := defaults.DataDir
	if resolvedDataDir != "" {
		dir = resolvedDataDir
	}
	a := setupAnswers{
		dir:                dir,
		backendPortStr:     fmt.Sprintf("%d", defaults.BackendPort),
		webPortStr:         fmt.Sprintf("%d", defaults.WebPort),
		sandbox:            defaults.Sandbox,
		dockerSock:         defaultDockerSock(),
		logLevel:           defaults.LogLevel,
		persistenceBackend: defaults.PersistenceBackend,
		memoryBackend:      defaults.MemoryBackend,
	}

	applyFlagOverrides(&a)

	form := huh.NewForm(
		huh.NewGroup(
			huh.NewInput().Title("Data directory").
				Description("Where SynthOrg stores its data").Value(&a.dir),
			huh.NewInput().Title("Backend API port").
				Description("Port for the REST/WebSocket API").Value(&a.backendPortStr),
			huh.NewInput().Title("Web dashboard port").
				Description("Port for the web UI").Value(&a.webPortStr),
			huh.NewConfirm().Title("Enable agent code sandbox?").
				Description("Mounts Docker socket for sandboxed code execution").Value(&a.sandbox),
		),
		huh.NewGroup(
			huh.NewInput().Title("Docker socket path").Value(&a.dockerSock),
		).WithHideFunc(func() bool { return !a.sandbox }),
		huh.NewGroup(
			huh.NewNote().Title("Backends").
				Description(fmt.Sprintf(
					"Persistence: %s · Memory: %s\n(More options coming soon)",
					a.persistenceBackend, a.memoryBackend,
				)),
		),
		huh.NewGroup(
			huh.NewConfirm().Title("Help improve SynthOrg?").
				Description(
					"Send anonymous usage data (agent count, feature usage, error rates).\n"+
						"We NEVER collect API keys, chat content, or personal data.\n"+
						"You can change this later: synthorg config set telemetry_opt_in false",
				).Value(&a.telemetryOptIn),
		),
	)

	if err := form.Run(); err != nil {
		return a, err
	}
	return a, nil
}

func buildState(a setupAnswers) (config.State, error) {
	dir := strings.TrimSpace(a.dir)
	if !filepath.IsAbs(dir) {
		return config.State{}, fmt.Errorf("data directory must be an absolute path, got %q", dir)
	}

	backendPort, err := parsePort(a.backendPortStr, "backend")
	if err != nil {
		return config.State{}, err
	}
	webPort, err := parsePort(a.webPortStr, "web")
	if err != nil {
		return config.State{}, err
	}

	dockerSock := strings.TrimSpace(a.dockerSock)
	if a.sandbox {
		if err := validateDockerSock(dockerSock); err != nil {
			return config.State{}, err
		}
	}

	jwtSecret, settingsKey, err := generateInitSecrets()
	if err != nil {
		return config.State{}, err
	}

	imageTag := resolveImageTag(a.imageTag)
	channel := "stable"
	if a.channel != "" {
		channel = a.channel
	}

	return config.State{
		DataDir:            dir,
		ImageTag:           imageTag,
		Channel:            channel,
		BackendPort:        backendPort,
		WebPort:            webPort,
		Sandbox:            a.sandbox,
		DockerSock:         dockerSock,
		LogLevel:           a.logLevel,
		JWTSecret:          jwtSecret,
		SettingsKey:        settingsKey,
		PersistenceBackend: a.persistenceBackend,
		MemoryBackend:      a.memoryBackend,
		TelemetryOptIn:     a.telemetryOptIn,
	}, nil
}

// writeInitFiles creates the data directory, generates compose.yml, and saves
// config. Returns the sanitized data directory path.
func writeInitFiles(state config.State) (string, error) {
	safeDir, err := config.SecurePath(state.DataDir)
	if err != nil {
		return "", err
	}
	state.DataDir = safeDir // normalize before persisting
	if err := os.MkdirAll(safeDir, 0o700); err != nil {
		return "", fmt.Errorf("creating data directory: %w", err)
	}

	params := compose.ParamsFromState(state)
	composeYAML, err := compose.Generate(params)
	if err != nil {
		return "", fmt.Errorf("generating compose file: %w", err)
	}

	composePath := filepath.Join(safeDir, "compose.yml")
	if err := os.WriteFile(composePath, composeYAML, 0o600); err != nil {
		return "", fmt.Errorf("writing compose file: %w", err)
	}

	if err := config.Save(state); err != nil {
		return "", fmt.Errorf("saving config: %w", err)
	}
	return safeDir, nil
}

// resolveImageTag returns the image tag to use: the override if set,
// the CLI version, or "latest" for dev builds.
func resolveImageTag(override string) string {
	if override != "" {
		return override
	}
	if v := version.Version; v != "" && v != "dev" {
		return v
	}
	return "latest"
}

// generateInitSecrets creates the JWT and settings encryption secrets.
// The settings key is 32 bytes (44-char URL-safe base64), matching the format
// required by Python cryptography.fernet.Fernet. Do NOT change byte counts.
func generateInitSecrets() (jwtSecret, settingsKey string, err error) {
	jwtSecret, err = generateSecret(48)
	if err != nil {
		return "", "", fmt.Errorf("generating JWT secret: %w", err)
	}
	settingsKey, err = generateSecret(32)
	if err != nil {
		return "", "", fmt.Errorf("generating settings encryption key: %w", err)
	}
	return jwtSecret, settingsKey, nil
}

func validateDockerSock(path string) error {
	if !filepath.IsAbs(path) && !strings.HasPrefix(path, "//") {
		return fmt.Errorf("docker socket must be an absolute path, got %q", path)
	}
	if strings.ContainsAny(path, "\"'`$\n\r{}[]") {
		return fmt.Errorf("docker socket path %q contains unsafe characters", path)
	}
	return nil
}

func defaultDockerSock() string {
	if runtime.GOOS == "windows" {
		return "//./pipe/docker_engine"
	}
	return "/var/run/docker.sock"
}

func generateSecret(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	return base64.URLEncoding.EncodeToString(b), nil
}

// fileExists reports whether the given path exists on disk.
// The path must be absolute; relative paths are treated as non-existent.
func fileExists(path string) bool {
	safe, err := config.SecurePath(path)
	if err != nil {
		return false
	}
	_, err = os.Stat(safe)
	return err == nil
}

func parsePort(s, name string) (int, error) {
	s = strings.TrimSpace(s)
	n, err := strconv.Atoi(s)
	if err != nil || n < 1 || n > 65535 {
		return 0, fmt.Errorf("invalid %s port: %q (must be 1-65535)", name, s)
	}
	return n, nil
}
