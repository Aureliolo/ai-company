package cmd

import (
	"os"
	"strings"
)

// Environment variable names for SynthOrg CLI configuration.
// Precedence: CLI flag > env var > config file > default.
const (
	EnvDataDir       = "SYNTHORG_DATA_DIR"
	EnvLogLevel      = "SYNTHORG_LOG_LEVEL"
	EnvBackendPort   = "SYNTHORG_BACKEND_PORT"
	EnvWebPort       = "SYNTHORG_WEB_PORT"
	EnvChannel       = "SYNTHORG_CHANNEL"
	EnvImageTag      = "SYNTHORG_IMAGE_TAG"
	EnvNoVerify      = "SYNTHORG_NO_VERIFY"
	EnvSkipVerify    = "SYNTHORG_SKIP_VERIFY" // backward-compat alias for EnvNoVerify
	EnvAutoUpdateCLI = "SYNTHORG_AUTO_UPDATE_CLI"
	EnvAutoPull      = "SYNTHORG_AUTO_PULL"
	EnvAutoRestart   = "SYNTHORG_AUTO_RESTART"
	EnvTelemetry     = "SYNTHORG_TELEMETRY"
	EnvQuiet         = "SYNTHORG_QUIET"
	EnvYes           = "SYNTHORG_YES" // suppresses ALL interactive confirmation prompts
)

// envBool returns true if the named env var is set to a truthy value
// ("1", "true", "yes", case-insensitive). All other values -- including
// "false", "0", "no", and empty string -- are treated as false.
// There is no way to explicitly negate a flag via env var; absence = off.
func envBool(name string) bool {
	v := strings.TrimSpace(os.Getenv(name))
	if v == "" {
		return false
	}
	switch strings.ToLower(v) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// noColorFromEnv checks the standard environment signals for disabling color:
// NO_COLOR (any non-empty value), CLICOLOR=0, TERM=dumb.
func noColorFromEnv() bool {
	if os.Getenv("NO_COLOR") != "" {
		return true
	}
	if os.Getenv("CLICOLOR") == "0" {
		return true
	}
	if os.Getenv("TERM") == "dumb" {
		return true
	}
	return false
}
