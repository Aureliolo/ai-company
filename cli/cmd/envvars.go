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
)

// envBool returns true if the named env var is set to a truthy value.
func envBool(name string) bool {
	v := os.Getenv(name)
	if v == "" {
		return false
	}
	switch strings.ToLower(v) {
	case "1", "true", "yes":
		return true
	}
	return false
}

// envString returns the value of the named env var, or empty string if unset.
func envString(name string) string {
	return os.Getenv(name)
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
