package config

import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

const stateFileName = "config.json"

// State is the persisted CLI configuration written by `synthorg init`.
type State struct {
	DataDir            string            `json:"data_dir"`
	ImageTag           string            `json:"image_tag"`
	Channel            string            `json:"channel"`
	BackendPort        int               `json:"backend_port"`
	WebPort            int               `json:"web_port"`
	Sandbox            bool              `json:"sandbox"`
	DockerSock         string            `json:"docker_sock,omitempty"`
	LogLevel           string            `json:"log_level"`
	JWTSecret          string            `json:"jwt_secret,omitempty"`
	SettingsKey        string            `json:"settings_key,omitempty"`
	PersistenceBackend string            `json:"persistence_backend"`
	MemoryBackend      string            `json:"memory_backend"`
	AutoCleanup        bool              `json:"auto_cleanup"`
	VerifiedDigests    map[string]string `json:"verified_digests,omitempty"`

	// Display preferences (empty = use default).
	Color      string `json:"color,omitempty"`      // always/auto/never
	Output     string `json:"output,omitempty"`     // text/json
	Timestamps string `json:"timestamps,omitempty"` // relative/iso8601
	Hints      string `json:"hints,omitempty"`      // always/auto/never

	// Auto-behavior keys (false = prompt interactively).
	AutoUpdateCLI      bool `json:"auto_update_cli"`
	AutoPull           bool `json:"auto_pull"`
	AutoRestart        bool `json:"auto_restart"`
	AutoApplyCompose   bool `json:"auto_apply_compose"`
	AutoStartAfterWipe bool `json:"auto_start_after_wipe"`

	// Telemetry (opt-in anonymous product telemetry, default false).
	TelemetryOptIn bool `json:"telemetry_opt_in"`
}

// DefaultState returns a State with sensible defaults for the interactive init
// wizard. Note: Load applies a more conservative fallback (sandbox disabled)
// when no config file exists.
func DefaultState() State {
	return State{
		DataDir:            DataDir(),
		ImageTag:           "latest",
		Channel:            "stable",
		BackendPort:        3001,
		WebPort:            3000,
		Sandbox:            true,
		LogLevel:           "info",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
	}
}

// DisplayChannel returns the channel for display, defaulting to "stable" when empty.
func (s State) DisplayChannel() string {
	if s.Channel == "" {
		return "stable"
	}
	return s.Channel
}

// StatePath returns the path to the config file inside the data directory.
func StatePath(dataDir string) string {
	return filepath.Join(dataDir, stateFileName)
}

// Load reads State from disk. Returns a default state with the given dataDir
// if the file does not exist (so --data-dir is respected on bootstrap).
func Load(dataDir string) (State, error) {
	safeDir, err := SecurePath(dataDir)
	if err != nil {
		return State{}, err
	}
	path := StatePath(safeDir)
	data, err := os.ReadFile(path) //nolint:gosec // path validated by SecurePath
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			defaults := DefaultState()
			defaults.DataDir = safeDir
			// Conservative fallback: sandbox requires explicit user confirmation
			// via `synthorg init`, so disable it when no config file exists.
			defaults.Sandbox = false
			return defaults, nil
		}
		return State{}, fmt.Errorf("reading config %s: %w", path, err)
	}
	// Unmarshal onto defaults so missing fields retain default values.
	s := DefaultState()
	if err := json.Unmarshal(data, &s); err != nil {
		return State{}, fmt.Errorf("parsing config %s: %w", path, err)
	}
	if err := s.validate(); err != nil {
		return State{}, fmt.Errorf("config %s: %w", path, err)
	}
	// Canonicalize and validate DataDir.
	if s.DataDir != "" {
		safeLoaded, err := SecurePath(s.DataDir)
		if err != nil {
			return State{}, fmt.Errorf("data_dir: %w", err)
		}
		s.DataDir = safeLoaded
	} else {
		// Config file omitted data_dir; fall back to the directory we loaded from.
		s.DataDir = safeDir
	}
	return s, nil
}

var validPersistenceBackends = map[string]bool{"sqlite": true}
var validMemoryBackends = map[string]bool{"mem0": true}
var validChannels = map[string]bool{"stable": true, "dev": true}
var validLogLevels = map[string]bool{"debug": true, "info": true, "warn": true, "error": true}
var validColorModes = map[string]bool{"always": true, "auto": true, "never": true}
var validOutputModes = map[string]bool{"text": true, "json": true}
var validTimestampModes = map[string]bool{"relative": true, "iso8601": true}
var validHintsModes = map[string]bool{"always": true, "auto": true, "never": true}

// IsValidChannel reports whether name is a known update channel.
func IsValidChannel(name string) bool {
	return validChannels[name]
}

// ChannelNames returns the allowed channel names.
func ChannelNames() string { return sortedKeys(validChannels) }

// IsValidLogLevel reports whether name is a known log level.
func IsValidLogLevel(name string) bool {
	return validLogLevels[name]
}

// LogLevelNames returns the allowed log level names.
func LogLevelNames() string { return sortedKeys(validLogLevels) }

// sortedKeys returns a comma-separated sorted list of map keys.
func sortedKeys(m map[string]bool) string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return strings.Join(keys, ", ")
}

// IsValidBool reports whether value is a strict boolean string ("true" or "false").
func IsValidBool(value string) bool {
	return value == "true" || value == "false"
}

// BoolNames returns the allowed boolean values.
func BoolNames() string { return "true, false" }

// IsValidPersistenceBackend reports whether name is a known persistence backend.
func IsValidPersistenceBackend(name string) bool {
	return validPersistenceBackends[name]
}

// IsValidMemoryBackend reports whether name is a known memory backend.
func IsValidMemoryBackend(name string) bool {
	return validMemoryBackends[name]
}

// PersistenceBackendNames returns the allowed persistence backend names.
func PersistenceBackendNames() string { return sortedKeys(validPersistenceBackends) }

// MemoryBackendNames returns the allowed memory backend names.
func MemoryBackendNames() string { return sortedKeys(validMemoryBackends) }

// IsValidColorMode reports whether name is a known color mode.
func IsValidColorMode(name string) bool { return validColorModes[name] }

// ColorModeNames returns the allowed color mode names.
func ColorModeNames() string { return sortedKeys(validColorModes) }

// IsValidOutputMode reports whether name is a known output mode.
func IsValidOutputMode(name string) bool { return validOutputModes[name] }

// OutputModeNames returns the allowed output mode names.
func OutputModeNames() string { return sortedKeys(validOutputModes) }

// IsValidTimestampMode reports whether name is a known timestamp mode.
func IsValidTimestampMode(name string) bool { return validTimestampModes[name] }

// TimestampModeNames returns the allowed timestamp mode names.
func TimestampModeNames() string { return sortedKeys(validTimestampModes) }

// IsValidHintsMode reports whether name is a known hints mode.
func IsValidHintsMode(name string) bool { return validHintsModes[name] }

// HintsModeNames returns the allowed hints mode names.
func HintsModeNames() string { return sortedKeys(validHintsModes) }

// validate checks that loaded config values are within safe ranges.
func (s State) validate() error {
	if s.BackendPort < 1 || s.BackendPort > 65535 {
		return fmt.Errorf("invalid backend_port %d: must be 1-65535", s.BackendPort)
	}
	if s.WebPort < 1 || s.WebPort > 65535 {
		return fmt.Errorf("invalid web_port %d: must be 1-65535", s.WebPort)
	}
	if !IsValidPersistenceBackend(s.PersistenceBackend) {
		return fmt.Errorf("invalid persistence_backend %q: must be one of %s", s.PersistenceBackend, sortedKeys(validPersistenceBackends))
	}
	if !IsValidMemoryBackend(s.MemoryBackend) {
		return fmt.Errorf("invalid memory_backend %q: must be one of %s", s.MemoryBackend, sortedKeys(validMemoryBackends))
	}
	if s.Channel != "" && !IsValidChannel(s.Channel) {
		return fmt.Errorf("invalid channel %q: must be one of %s", s.Channel, sortedKeys(validChannels))
	}
	if s.LogLevel != "" && !IsValidLogLevel(s.LogLevel) {
		return fmt.Errorf("invalid log_level %q: must be one of %s", s.LogLevel, sortedKeys(validLogLevels))
	}
	if s.ImageTag != "" && !IsValidImageTag(s.ImageTag) {
		return fmt.Errorf("invalid image_tag %q: must match [a-zA-Z0-9][a-zA-Z0-9._-]*", s.ImageTag)
	}
	if s.Color != "" && !IsValidColorMode(s.Color) {
		return fmt.Errorf("invalid color %q: must be one of %s", s.Color, ColorModeNames())
	}
	if s.Output != "" && !IsValidOutputMode(s.Output) {
		return fmt.Errorf("invalid output %q: must be one of %s", s.Output, OutputModeNames())
	}
	if s.Timestamps != "" && !IsValidTimestampMode(s.Timestamps) {
		return fmt.Errorf("invalid timestamps %q: must be one of %s", s.Timestamps, TimestampModeNames())
	}
	if s.Hints != "" && !IsValidHintsMode(s.Hints) {
		return fmt.Errorf("invalid hints %q: must be one of %s", s.Hints, HintsModeNames())
	}
	for name, digest := range s.VerifiedDigests {
		if !isValidDigestFormat(digest) {
			return fmt.Errorf("invalid verified_digests[%q]: %q is not a valid sha256 digest", name, digest)
		}
	}
	return nil
}

// IsValidImageTag checks that tag matches [a-zA-Z0-9][a-zA-Z0-9._-]*
// and is at most 128 characters long (Docker tag length limit).
func IsValidImageTag(tag string) bool {
	if len(tag) == 0 || len(tag) > 128 {
		return false
	}
	first := tag[0]
	if !isAlphaNum(first) {
		return false
	}
	for i := 1; i < len(tag); i++ {
		c := tag[i]
		if !isAlphaNum(c) && c != '.' && c != '_' && c != '-' {
			return false
		}
	}
	return true
}

func isAlphaNum(c byte) bool {
	return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')
}

// isValidDigestFormat checks if d matches sha256:<64-hex-chars>.
// Avoids importing the verify package to prevent circular dependencies.
func isValidDigestFormat(d string) bool {
	if len(d) != 71 || d[:7] != "sha256:" {
		return false
	}
	for _, c := range d[7:] {
		if (c < '0' || c > '9') && (c < 'a' || c > 'f') {
			return false
		}
	}
	return true
}

// Save writes State to disk as indented JSON.
// DataDir is normalized to the SecurePath-cleaned form before persisting.
func Save(s State) error {
	safeDir, err := SecurePath(s.DataDir)
	if err != nil {
		return fmt.Errorf("securing data dir: %w", err)
	}
	s.DataDir = safeDir // persist the canonical path
	if err := os.MkdirAll(safeDir, 0o700); err != nil {
		return fmt.Errorf("creating config directory: %w", err)
	}
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return fmt.Errorf("marshaling config: %w", err)
	}
	return os.WriteFile(StatePath(safeDir), data, 0o600) //nolint:gosec // path validated by SecurePath
}
