// Package compose generates Docker Compose YAML from an embedded template.
package compose

import (
	"bytes"
	_ "embed"
	"fmt"
	"net/url"
	"regexp"
	"strings"
	"text/template"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/verify"
	"github.com/Aureliolo/synthorg/cli/internal/version"
)

//go:embed compose.yml.tmpl
var composeTmpl string

// imageTagPattern validates image tags to prevent YAML injection.
var imageTagPattern = regexp.MustCompile(`^[a-zA-Z0-9][a-zA-Z0-9._-]*$`)

// Digest validation uses verify.IsValidDigest to avoid duplicating the pattern.

// allowedLogLevels restricts log level values to a known safe set.
var allowedLogLevels = map[string]bool{
	"debug": true,
	"info":  true,
	"warn":  true,
	"error": true,
}

// Params are the template parameters for compose generation.
type Params struct {
	CLIVersion         string
	ImageTag           string
	BackendPort        int
	WebPort            int
	NatsClientPort     int
	LogLevel           string
	JWTSecret          string
	SettingsKey        string
	Sandbox            bool
	DockerSock         string
	DockerSockGID      int // host GID owning DockerSock; -1 skips group_add
	PersistenceBackend string
	MemoryBackend      string
	BusBackend         string
	TelemetryOptIn     bool
	PostgresPort       int
	PostgresPassword   string
	DigestPins         map[string]string // image name suffix → digest (e.g. "backend" → "sha256:abc...")
}

// ParamsFromState creates Params from a persisted State.
func ParamsFromState(s config.State) Params {
	busBackend := s.BusBackend
	if busBackend == "" {
		busBackend = "internal"
	}
	natsPort := s.NatsClientPort
	if natsPort == 0 {
		natsPort = 3003
	}
	return Params{
		CLIVersion:         version.Version,
		ImageTag:           s.ImageTag,
		BackendPort:        s.BackendPort,
		WebPort:            s.WebPort,
		NatsClientPort:     natsPort,
		LogLevel:           s.LogLevel,
		JWTSecret:          s.JWTSecret,
		SettingsKey:        s.SettingsKey,
		Sandbox:            s.Sandbox,
		DockerSock:         s.DockerSock,
		DockerSockGID:      s.DockerSockGID,
		PersistenceBackend: s.PersistenceBackend,
		MemoryBackend:      s.MemoryBackend,
		BusBackend:         busBackend,
		TelemetryOptIn:     s.TelemetryOptIn,
		PostgresPort:       s.PostgresPort,
		PostgresPassword:   s.PostgresPassword,
	}
}

// PostgresEnabled reports whether the Postgres persistence backend is active.
func (p Params) PostgresEnabled() bool {
	return p.PersistenceBackend == "postgres"
}

// DistributedEnabled reports whether the distributed runtime profile is
// active (currently: bus_backend is anything other than "internal").
func (p Params) DistributedEnabled() bool {
	return p.BusBackend != "" && p.BusBackend != "internal"
}

// Generate renders the compose template with the given parameters.
// It validates all string parameters before rendering to prevent YAML injection.
func Generate(p Params) ([]byte, error) {
	if err := validateParams(p); err != nil {
		return nil, fmt.Errorf("validating params: %w", err)
	}

	funcMap := template.FuncMap{
		"yamlStr":            yamlStr,
		"digestPin":          digestPin(p.DigestPins),
		"sandboxImageRef":    sandboxImageRef(p.DigestPins),
		"distributedEnabled": p.DistributedEnabled,
		"postgresEnabled":    p.PostgresEnabled,
		"pgDSN":              func() string { return pgDSN(p) },
	}

	tmpl, err := template.New("compose").Funcs(funcMap).Parse(composeTmpl)
	if err != nil {
		return nil, fmt.Errorf("parsing template: %w", err)
	}
	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, p); err != nil {
		return nil, fmt.Errorf("executing template: %w", err)
	}
	return buf.Bytes(), nil
}

// validateParams checks all template parameters for safe values.
func validateParams(p Params) error {
	if !imageTagPattern.MatchString(p.ImageTag) {
		return fmt.Errorf("invalid image tag %q: must match %s", p.ImageTag, imageTagPattern.String())
	}
	if p.LogLevel != "" && !allowedLogLevels[p.LogLevel] {
		return fmt.Errorf("invalid log level %q: must be one of debug, info, warn, error", p.LogLevel)
	}
	if p.BackendPort < 1 || p.BackendPort > 65535 {
		return fmt.Errorf("invalid backend port %d: must be 1-65535", p.BackendPort)
	}
	if p.WebPort < 1 || p.WebPort > 65535 {
		return fmt.Errorf("invalid web port %d: must be 1-65535", p.WebPort)
	}
	if p.BackendPort == p.WebPort {
		return fmt.Errorf("backend and web ports must be different (both set to %d)", p.BackendPort)
	}
	if p.Sandbox {
		if p.DockerSock == "" {
			return fmt.Errorf("docker socket path must be set when sandbox is enabled")
		}
		if strings.ContainsAny(p.DockerSock, "\"'`$\n\r{}[]") {
			return fmt.Errorf("docker socket path %q contains unsafe characters", p.DockerSock)
		}
		if p.DockerSockGID < -1 || p.DockerSockGID > 4294967295 {
			return fmt.Errorf("invalid docker socket gid %d: must be -1 to 4294967295", p.DockerSockGID)
		}
	}
	if !config.IsValidPersistenceBackend(p.PersistenceBackend) {
		return fmt.Errorf("invalid persistence backend %q: must be one of %s", p.PersistenceBackend, config.PersistenceBackendNames())
	}
	if !config.IsValidMemoryBackend(p.MemoryBackend) {
		return fmt.Errorf("invalid memory backend %q: must be one of %s", p.MemoryBackend, config.MemoryBackendNames())
	}
	if p.BusBackend != "" && !config.IsValidBusBackend(p.BusBackend) {
		return fmt.Errorf("invalid bus backend %q: must be one of %s", p.BusBackend, config.BusBackendNames())
	}
	if p.DistributedEnabled() {
		if p.NatsClientPort < 1 || p.NatsClientPort > 65535 {
			return fmt.Errorf("invalid nats client port %d: must be 1-65535", p.NatsClientPort)
		}
		if p.NatsClientPort == p.BackendPort || p.NatsClientPort == p.WebPort {
			return fmt.Errorf("nats client port %d collides with another service port", p.NatsClientPort)
		}
	}
	if p.PostgresEnabled() {
		if p.PostgresPort < 1 || p.PostgresPort > 65535 {
			return fmt.Errorf("invalid postgres port %d: must be 1-65535", p.PostgresPort)
		}
		if p.PostgresPort == p.BackendPort || p.PostgresPort == p.WebPort {
			return fmt.Errorf("postgres port %d collides with another service port", p.PostgresPort)
		}
		if p.DistributedEnabled() && p.PostgresPort == p.NatsClientPort {
			return fmt.Errorf("postgres port %d collides with nats client port %d", p.PostgresPort, p.NatsClientPort)
		}
		if strings.TrimSpace(p.PostgresPassword) == "" {
			return fmt.Errorf("postgres password is required when persistence backend is postgres")
		}
		if len(p.PostgresPassword) < 32 {
			return fmt.Errorf("postgres password must be >= 32 characters, got %d", len(p.PostgresPassword))
		}
	}
	// Cross-validate secrets: if one is set, both must be set.
	// Both-empty is valid for development/testing (template omits env vars).
	hasJWT := strings.TrimSpace(p.JWTSecret) != ""
	hasKey := strings.TrimSpace(p.SettingsKey) != ""
	if hasJWT && !hasKey {
		return fmt.Errorf("SYNTHORG_SETTINGS_KEY is required when JWT secret is set")
	}
	if hasKey && !hasJWT {
		return fmt.Errorf("JWT secret is required when SYNTHORG_SETTINGS_KEY is set")
	}
	for name, d := range p.DigestPins {
		if !verify.IsValidDigest(d) {
			return fmt.Errorf("invalid digest pin for %q: %q is not a valid sha256 digest", name, d)
		}
	}
	return nil
}

// pgDSN builds a properly percent-encoded PostgreSQL connection string.
// Uses url.UserPassword for userinfo encoding per RFC 3986 section 3.2.1.
func pgDSN(p Params) string {
	if !p.PostgresEnabled() || p.PostgresPassword == "" {
		return ""
	}
	u := &url.URL{
		Scheme: "postgresql",
		User:   url.UserPassword("synthorg", p.PostgresPassword),
		Host:   "postgres:5432",
		Path:   "/synthorg",
	}
	return u.String()
}

// digestPin returns a template function that resolves an image name to either
// a digest-pinned reference (repo@digest) or a tag-based reference (repo:tag).
func digestPin(pins map[string]string) func(name, repo, tag string) string {
	return func(name, repo, tag string) string {
		if d, ok := pins[name]; ok && d != "" {
			return repo + "@" + d
		}
		return repo + ":" + tag
	}
}

// sandboxImageRef returns a template function that resolves the sandbox image
// to its digest-pinned or tag-based reference. Wired into the backend's
// SYNTHORG_SANDBOX_IMAGE env var so the backend and CLI stay version-locked
// when the backend spawns ephemeral sandbox containers via aiodocker.
func sandboxImageRef(pins map[string]string) func(tag string) string {
	return func(tag string) string {
		return verify.FormatImageRef("sandbox", tag, pins["sandbox"])
	}
}

// yamlStr safely quotes a string value for YAML, escaping special characters.
// Also escapes $ to prevent Docker Compose variable interpolation.
func yamlStr(s string) string {
	// If the string contains YAML-special or Compose-interpolation characters,
	// double-quote and escape.
	if strings.ContainsAny(s, "\x00$:#{}[]|>&*!%@`\"'\\\n\r\t") {
		escaped := strings.ReplaceAll(s, "\x00", "") // YAML cannot represent null bytes
		escaped = strings.ReplaceAll(escaped, `\`, `\\`)
		escaped = strings.ReplaceAll(escaped, `"`, `\"`)
		escaped = strings.ReplaceAll(escaped, "\n", `\n`)
		escaped = strings.ReplaceAll(escaped, "\r", `\r`)
		escaped = strings.ReplaceAll(escaped, "\t", `\t`)
		// Escape $ to prevent Docker Compose variable interpolation.
		escaped = strings.ReplaceAll(escaped, "$", "$$")
		return `"` + escaped + `"`
	}
	return `"` + s + `"`
}
