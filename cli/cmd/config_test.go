package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
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

	// Both secret labels must be present with masked values.
	if !bytes.Contains([]byte(out), []byte("Settings key")) {
		t.Error("expected 'Settings key' label in output")
	}
	if !bytes.Contains([]byte(out), []byte("JWT secret")) {
		t.Error("expected 'JWT secret' label in output")
	}
	// Count "****" occurrences -- must appear at least twice (JWT + Settings key).
	maskCount := bytes.Count([]byte(out), []byte("****"))
	if maskCount < 2 {
		t.Errorf("expected at least 2 masked secrets (****), got %d", maskCount)
	}
}

func TestConfigSetChannel(t *testing.T) {
	dir := t.TempDir()
	// Create initial config.
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "channel", "dev", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	// Verify the channel was persisted.
	loaded, err := config.Load(dir)
	if err != nil {
		t.Fatalf("Load after set: %v", err)
	}
	if loaded.Channel != "dev" {
		t.Errorf("Channel = %q, want dev", loaded.Channel)
	}
}

func TestConfigSetRejectsInvalidChannel(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "channel", "nightly", "--data-dir", dir})
	err := rootCmd.Execute()
	if err == nil {
		t.Fatal("expected error for invalid channel")
	}
}

func TestConfigSetAutoCleanup(t *testing.T) {
	tests := []struct {
		name     string
		initial  bool
		setValue string
		want     bool
	}{
		{"set to true", false, "true", true},
		{"set to false", true, "false", false},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			dir := t.TempDir()
			state := config.DefaultState()
			state.DataDir = dir
			state.AutoCleanup = tt.initial
			if err := config.Save(state); err != nil {
				t.Fatal(err)
			}

			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "set", "auto_cleanup", tt.setValue, "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			loaded, err := config.Load(dir)
			if err != nil {
				t.Fatalf("Load after set: %v", err)
			}
			if loaded.AutoCleanup != tt.want {
				t.Errorf("AutoCleanup = %v, want %v", loaded.AutoCleanup, tt.want)
			}
		})
	}
}

func FuzzConfigSetAutoCleanup(f *testing.F) {
	f.Add("true")
	f.Add("false")
	f.Add("TRUE")
	f.Add("1")
	f.Add("yes")
	f.Add("")

	f.Fuzz(func(t *testing.T, value string) {
		dir := t.TempDir()
		state := config.DefaultState()
		state.DataDir = dir
		if err := config.Save(state); err != nil {
			t.Fatalf("Save: %v", err)
		}

		var buf bytes.Buffer
		rootCmd.SetOut(&buf)
		rootCmd.SetErr(&buf)
		rootCmd.SetArgs([]string{"config", "set", "auto_cleanup", value, "--data-dir", dir})
		err := rootCmd.Execute()

		allowed := value == "true" || value == "false"
		if allowed && err != nil {
			t.Fatalf("unexpected error for %q: %v", value, err)
		}
		if !allowed && err == nil {
			t.Fatalf("expected error for %q", value)
		}
	})
}

func TestConfigSetRejectsInvalidAutoCleanup(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	for _, value := range []string{"yes", "1", "YES", "True"} {
		var buf bytes.Buffer
		rootCmd.SetOut(&buf)
		rootCmd.SetErr(&buf)
		rootCmd.SetArgs([]string{"config", "set", "auto_cleanup", value, "--data-dir", dir})
		err := rootCmd.Execute()
		if err == nil {
			t.Errorf("expected error for auto_cleanup=%q", value)
		}
	}
}

func TestConfigShowAutoCleanup(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
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
	found := false
	for _, line := range strings.Split(out, "\n") {
		if strings.Contains(line, "Auto cleanup") {
			found = true
			if !strings.Contains(line, "false") {
				t.Errorf("Auto cleanup line should contain 'false', got: %s", line)
			}
			break
		}
	}
	if !found {
		t.Error("expected 'Auto cleanup' label in output")
	}
}

func TestConfigSetRejectsUnknownKey(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "unknown_key", "value", "--data-dir", dir})
	err := rootCmd.Execute()
	if err == nil {
		t.Fatal("expected error for unknown key")
	}
}
