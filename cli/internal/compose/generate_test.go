package compose

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/config"
)

func TestGenerateDefault(t *testing.T) {
	t.Parallel()
	p := Params{
		CLIVersion:         "dev",
		ImageTag:           "latest",
		BackendPort:        8000,
		WebPort:            3000,
		LogLevel:           "info",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
	}
	out, err := Generate(p)
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	yaml := string(out)

	// Verify key elements.
	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-backend:latest")
	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-web:latest")
	assertContains(t, yaml, `"8000:8000"`)
	assertContains(t, yaml, `"3000:8080"`)
	assertContains(t, yaml, "no-new-privileges:true")
	assertContains(t, yaml, "cap_drop:")
	assertContains(t, yaml, "read_only: true")
	assertContains(t, yaml, "service_healthy")
	assertContains(t, yaml, "'ok'") // healthcheck checks for 'ok'
	assertContains(t, yaml, "synthorg-data:")

	// No sandbox by default.
	if strings.Contains(yaml, "sandbox") {
		t.Error("default output should not contain sandbox service")
	}

	// No secrets by default.
	if strings.Contains(yaml, "JWT_SECRET") {
		t.Error("default output should not contain JWT_SECRET")
	}
	if strings.Contains(yaml, "SETTINGS_KEY") {
		t.Error("default output should not contain SETTINGS_KEY")
	}

	compareGolden(t, "compose_default.yml", out)
}

func TestGenerateCustomPorts(t *testing.T) {
	t.Parallel()
	p := Params{
		CLIVersion:         "dev",
		ImageTag:           "v0.2.0",
		BackendPort:        9000,
		WebPort:            4000,
		LogLevel:           "debug",
		JWTSecret:          "test-secret-value",
		SettingsKey:        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
	}
	out, err := Generate(p)
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	yaml := string(out)

	assertContains(t, yaml, `"9000:8000"`)
	assertContains(t, yaml, `"4000:8080"`)
	assertContains(t, yaml, "synthorg-backend:v0.2.0")
	assertContains(t, yaml, "SYNTHORG_JWT_SECRET")
	assertContains(t, yaml, "test-secret-value")
	assertContains(t, yaml, "SYNTHORG_SETTINGS_KEY")
	assertContains(t, yaml, "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=")

	compareGolden(t, "compose_custom_ports.yml", out)
}

func TestGenerateWithSandbox(t *testing.T) {
	t.Parallel()
	p := Params{
		CLIVersion:         "dev",
		ImageTag:           "latest",
		BackendPort:        8000,
		WebPort:            3000,
		LogLevel:           "info",
		Sandbox:            true,
		DockerSock:         "/var/run/docker.sock",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
	}
	out, err := Generate(p)
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	yaml := string(out)

	assertContains(t, yaml, "synthorg-sandbox:latest")
	assertContains(t, yaml, "/var/run/docker.sock:/var/run/docker.sock:ro")
	assertContains(t, yaml, "no-new-privileges:true")

	// Sandbox healthcheck override (faster than Dockerfile's 30s interval).
	assertContains(t, yaml, `test: ["CMD", "true"]`)
	assertContains(t, yaml, "interval: 10s")
	assertContains(t, yaml, "start_period: 5s")
}

func TestGenerateWithDigestPins(t *testing.T) {
	t.Parallel()
	p := Params{
		CLIVersion:         "dev",
		ImageTag:           "0.3.0",
		BackendPort:        8000,
		WebPort:            3000,
		LogLevel:           "info",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
		DigestPins: map[string]string{
			"backend": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
			"web":     "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
		},
	}
	out, err := Generate(p)
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	yaml := string(out)

	// Digest-pinned images should use @digest syntax.
	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-backend@sha256:aaaa")
	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-web@sha256:bbbb")

	// Should NOT contain tag-based references for pinned images.
	if strings.Contains(yaml, "synthorg-backend:0.3.0") {
		t.Error("digest-pinned backend should not use tag")
	}
	if strings.Contains(yaml, "synthorg-web:0.3.0") {
		t.Error("digest-pinned web should not use tag")
	}

	compareGolden(t, "compose_digest_pins.yml", out)
}

func TestGenerateWithDigestPinsAndSandbox(t *testing.T) {
	t.Parallel()
	p := Params{
		CLIVersion:         "dev",
		ImageTag:           "0.3.0",
		BackendPort:        8000,
		WebPort:            3000,
		LogLevel:           "info",
		Sandbox:            true,
		DockerSock:         "/var/run/docker.sock",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
		DigestPins: map[string]string{
			"backend": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
			"web":     "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
			"sandbox": "sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
		},
	}
	out, err := Generate(p)
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	yaml := string(out)

	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-backend@sha256:aaaa")
	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-web@sha256:bbbb")
	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-sandbox@sha256:cccc")
}

func TestGenerateNilDigestPinsFallsBackToTag(t *testing.T) {
	t.Parallel()
	p := Params{
		CLIVersion:         "dev",
		ImageTag:           "0.3.0",
		BackendPort:        8000,
		WebPort:            3000,
		LogLevel:           "info",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
		DigestPins:         nil,
	}
	out, err := Generate(p)
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	yaml := string(out)

	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-backend:0.3.0")
	assertContains(t, yaml, "ghcr.io/aureliolo/synthorg-web:0.3.0")
}

func TestGenerateHardeningPresent(t *testing.T) {
	t.Parallel()
	p := Params{
		CLIVersion:         "dev",
		ImageTag:           "latest",
		BackendPort:        8000,
		WebPort:            3000,
		LogLevel:           "info",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
	}
	out, err := Generate(p)
	if err != nil {
		t.Fatalf("Generate: %v", err)
	}
	yaml := string(out)

	// CIS hardening elements must be present.
	hardening := []string{
		"no-new-privileges:true",
		"cap_drop:",
		"- ALL",
		"read_only: true",
		"tmpfs:",
		"restart: unless-stopped",
	}
	for _, h := range hardening {
		assertContains(t, yaml, h)
	}
}

func TestParamsFromState(t *testing.T) {
	t.Parallel()
	s := config.State{
		DataDir:            "/tmp/test",
		ImageTag:           "v1.0.0",
		BackendPort:        9000,
		WebPort:            4000,
		LogLevel:           "debug",
		JWTSecret:          "secret",
		SettingsKey:        "settings-key",
		Sandbox:            true,
		DockerSock:         "/var/run/docker.sock",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
	}
	p := ParamsFromState(s)

	if p.ImageTag != "v1.0.0" {
		t.Errorf("ImageTag = %q, want v1.0.0", p.ImageTag)
	}
	if p.BackendPort != 9000 {
		t.Errorf("BackendPort = %d, want 9000", p.BackendPort)
	}
	if p.WebPort != 4000 {
		t.Errorf("WebPort = %d, want 4000", p.WebPort)
	}
	if !p.Sandbox {
		t.Error("Sandbox should be true")
	}
	if p.DockerSock != "/var/run/docker.sock" {
		t.Errorf("DockerSock = %q", p.DockerSock)
	}
	if p.PersistenceBackend != "sqlite" {
		t.Errorf("PersistenceBackend = %q, want sqlite", p.PersistenceBackend)
	}
	if p.MemoryBackend != "mem0" {
		t.Errorf("MemoryBackend = %q, want mem0", p.MemoryBackend)
	}
	if p.JWTSecret != "secret" {
		t.Errorf("JWTSecret = %q, want secret", p.JWTSecret)
	}
	if p.SettingsKey != "settings-key" {
		t.Errorf("SettingsKey = %q, want settings-key", p.SettingsKey)
	}
}

func assertContains(t *testing.T, s, substr string) {
	t.Helper()
	if !strings.Contains(s, substr) {
		t.Errorf("output missing %q", substr)
	}
}

func compareGolden(t *testing.T, name string, actual []byte) {
	t.Helper()
	golden := filepath.Join("..", "..", "testdata", name)

	if os.Getenv("UPDATE_GOLDEN") == "1" {
		if err := os.MkdirAll(filepath.Dir(golden), 0o755); err != nil {
			t.Fatalf("create testdata dir: %v", err)
		}
		if err := os.WriteFile(golden, actual, 0o644); err != nil {
			t.Fatalf("update golden: %v", err)
		}
		return
	}

	expected, err := os.ReadFile(golden)
	if err != nil {
		t.Fatalf("golden file %s missing: %v\nRun with UPDATE_GOLDEN=1 to create", golden, err)
	}

	if string(expected) != string(actual) {
		t.Errorf("output differs from golden file %s\nRun with UPDATE_GOLDEN=1 to update", name)
	}
}
