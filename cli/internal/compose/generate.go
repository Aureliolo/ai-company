// Package compose generates Docker Compose YAML from an embedded template.
package compose

import (
	"bytes"
	_ "embed"
	"text/template"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/version"
)

//go:embed compose.yml.tmpl
var composeTmpl string

// Params are the template parameters for compose generation.
type Params struct {
	CLIVersion  string
	ImageTag    string
	BackendPort int
	WebPort     int
	LogLevel    string
	JWTSecret   string
	Sandbox     bool
	DockerSock  string
}

// ParamsFromState creates Params from a persisted State.
func ParamsFromState(s config.State) Params {
	return Params{
		CLIVersion:  version.Version,
		ImageTag:    s.ImageTag,
		BackendPort: s.BackendPort,
		WebPort:     s.WebPort,
		LogLevel:    s.LogLevel,
		JWTSecret:   s.JWTSecret,
		Sandbox:     s.Sandbox,
		DockerSock:  s.DockerSock,
	}
}

// Generate renders the compose template with the given parameters.
func Generate(p Params) ([]byte, error) {
	tmpl, err := template.New("compose").Parse(composeTmpl)
	if err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	if err := tmpl.Execute(&buf, p); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}
