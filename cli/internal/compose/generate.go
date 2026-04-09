// Package compose generates Docker Compose YAML from an embedded template.
package compose

import (
	"bytes"
	_ "embed"
	"fmt"
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
	LogLevel           string
	JWTSecret          string
	SettingsKey        string
	Sandbox            bool
	DockerSock         string
	PersistenceBackend string
	MemoryBackend      string
	TelemetryOptIn     bool
	DigestPins         map[string]string // image name suffix → digest (e.g. "backend" → "sha256:abc...")
}

// ParamsFromState creates Params from a persisted State.
func ParamsFromState(s config.State) Params {
	return Params{
		CLIVersion:         version.Version,
		ImageTag:           s.ImageTag,
		BackendPort:        s.BackendPort,
		WebPort:            s.WebPort,
		LogLevel:           s.LogLevel,
		JWTSecret:          s.JWTSecret,
		SettingsKey:        s.SettingsKey,
		Sandbox:            s.Sandbox,
		DockerSock:         s.DockerSock,
		PersistenceBackend: s.PersistenceBackend,
		MemoryBackend:      s.MemoryBackend,
		TelemetryOptIn:     s.TelemetryOptIn,
	}
}

// Generate renders the compose template with the given parameters.
// It validates all string parameters before rendering to prevent YAML injection.
func Generate(p Params) ([]byte, error) {
	if err := validateParams(p); err != nil {
		return nil, fmt.Errorf("validating params: %w", err)
	}

	funcMap := template.FuncMap{
		"yamlStr":   yamlStr,
		"digestPin": digestPin(p.DigestPins),
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
	}
	if !config.IsValidPersistenceBackend(p.PersistenceBackend) {
		return fmt.Errorf("invalid persistence backend %q: must be one of %s", p.PersistenceBackend, config.PersistenceBackendNames())
	}
	if !config.IsValidMemoryBackend(p.MemoryBackend) {
		return fmt.Errorf("invalid memory backend %q: must be one of %s", p.MemoryBackend, config.MemoryBackendNames())
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
