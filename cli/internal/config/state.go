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
	BackendPort        int               `json:"backend_port"`
	WebPort            int               `json:"web_port"`
	Sandbox            bool              `json:"sandbox"`
	DockerSock         string            `json:"docker_sock,omitempty"`
	LogLevel           string            `json:"log_level"`
	JWTSecret          string            `json:"jwt_secret,omitempty"`
	PersistenceBackend string            `json:"persistence_backend"`
	MemoryBackend      string            `json:"memory_backend"`
	VerifiedDigests    map[string]string `json:"verified_digests,omitempty"`
}

// DefaultState returns a State with sensible defaults for the interactive init
// wizard. Note: Load applies a more conservative fallback (sandbox disabled)
// when no config file exists.
func DefaultState() State {
	return State{
		DataDir:            DataDir(),
		ImageTag:           "latest",
		BackendPort:        8000,
		WebPort:            3000,
		Sandbox:            true,
		LogLevel:           "info",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
	}
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

// sortedKeys returns a comma-separated sorted list of map keys.
func sortedKeys(m map[string]bool) string {
	keys := make([]string, 0, len(m))
	for k := range m {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	return strings.Join(keys, ", ")
}

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
	for name, digest := range s.VerifiedDigests {
		if !isValidDigestFormat(digest) {
			return fmt.Errorf("invalid verified_digests[%q]: %q is not a valid sha256 digest", name, digest)
		}
	}
	return nil
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
		return err
	}
	s.DataDir = safeDir // persist the canonical path
	if err := os.MkdirAll(safeDir, 0o700); err != nil {
		return err
	}
	data, err := json.MarshalIndent(s, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(StatePath(safeDir), data, 0o600) //nolint:gosec // path validated by SecurePath
}
