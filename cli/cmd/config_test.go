package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/config"
)

func TestMaskSecret(t *testing.T) {
	tests := []struct {
		input string
		want  string
	}{
		{"", "(not set)"},
		{"s3cret", "****"},
		{"x", "****"},
	}
	for _, tt := range tests {
		if got := maskSecret(tt.input); got != tt.want {
			t.Errorf("maskSecret(%q) = %q, want %q", tt.input, got, tt.want)
		}
	}
}

func TestConfigShowNotInitialized(t *testing.T) {
	dir := t.TempDir()
	var buf bytes.Buffer

	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "show", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	out := buf.String()
	if !bytes.Contains([]byte(out), []byte("Not initialized")) {
		t.Errorf("expected 'Not initialized' in output, got: %s", out)
	}
}

func TestConfigShowDisplaysFields(t *testing.T) {
	dir := t.TempDir()
	state := config.State{
		DataDir:            dir,
		ImageTag:           "v1.2.3",
		BackendPort:        9000,
		WebPort:            4000,
		Sandbox:            true,
		DockerSock:         "/var/run/docker.sock",
		LogLevel:           "debug",
		JWTSecret:          "super-secret",
		SettingsKey:        "super-settings-key",
		PersistenceBackend: "sqlite",
		MemoryBackend:      "mem0",
	}

	data, err := json.MarshalIndent(state, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "config.json"), data, 0o600); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "show", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	out := buf.String()
	for _, want := range []string{
		"v1.2.3",
		"9000",
		"4000",
		"true",
		"debug",
		"/var/run/docker.sock",
		"****",
		"sqlite",
		"mem0",
	} {
		if !bytes.Contains([]byte(out), []byte(want)) {
			t.Errorf("expected %q in output, got: %s", want, out)
		}
	}

	// Secrets must not appear in output.
	if bytes.Contains([]byte(out), []byte("super-secret")) {
		t.Error("JWT secret leaked in output")
	}
	if bytes.Contains([]byte(out), []byte("super-settings-key")) {
		t.Error("Settings key leaked in output")
	}

	// Settings key label must be present.
	if !bytes.Contains([]byte(out), []byte("Settings key")) {
		t.Error("expected 'Settings key' label in output")
	}
}
