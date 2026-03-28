package cmd

import (
	"bytes"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
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

func TestConfigSetLogLevel(t *testing.T) {
	tests := []struct {
		name  string
		value string
		want  string
	}{
		{"set to debug", "debug", "debug"},
		{"set to info", "info", "info"},
		{"set to warn", "warn", "warn"},
		{"set to error", "error", "error"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			dir := t.TempDir()
			state := config.DefaultState()
			state.DataDir = dir
			if err := config.Save(state); err != nil {
				t.Fatal(err)
			}

			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "set", "log_level", tt.value, "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			loaded, err := config.Load(dir)
			if err != nil {
				t.Fatalf("Load after set: %v", err)
			}
			if loaded.LogLevel != tt.want {
				t.Errorf("LogLevel = %q, want %q", loaded.LogLevel, tt.want)
			}
		})
	}
}

func TestConfigSetRejectsInvalidLogLevel(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}
	orig := state.LogLevel

	for _, value := range []string{"verbose", "trace", "INFO", "Debug", ""} {
		var buf bytes.Buffer
		rootCmd.SetOut(&buf)
		rootCmd.SetErr(&buf)
		rootCmd.SetArgs([]string{"config", "set", "log_level", value, "--data-dir", dir})
		err := rootCmd.Execute()
		if err == nil {
			t.Errorf("expected error for log_level=%q", value)
		}
		loaded, loadErr := config.Load(dir)
		if loadErr != nil {
			t.Fatalf("Load after rejected %q: %v", value, loadErr)
		}
		if loaded.LogLevel != orig {
			t.Errorf("rejected %q mutated LogLevel: got %q, want %q", value, loaded.LogLevel, orig)
		}
	}
}

func FuzzConfigSetLogLevel(f *testing.F) {
	f.Add("debug")
	f.Add("info")
	f.Add("warn")
	f.Add("error")
	f.Add("verbose")
	f.Add("trace")
	f.Add("")
	f.Add("INFO")

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
		rootCmd.SetArgs([]string{"config", "set", "log_level", value, "--data-dir", dir})
		err := rootCmd.Execute()

		allowed := value == "debug" || value == "info" || value == "warn" || value == "error"
		if allowed && err != nil {
			t.Fatalf("unexpected error for %q: %v", value, err)
		}
		if !allowed && err == nil {
			t.Fatalf("expected error for %q", value)
		}
	})
}

func TestConfigGet(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	state.Channel = "dev"
	state.ImageTag = "0.5.0-dev.9"
	state.LogLevel = "debug"
	state.AutoCleanup = true
	state.Sandbox = true
	state.BackendPort = 9000
	state.WebPort = 4000
	state.PersistenceBackend = "sqlite"
	state.MemoryBackend = "mem0"
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	tests := []struct {
		key  string
		want string
	}{
		{"channel", "dev"},
		{"image_tag", "0.5.0-dev.9"},
		{"log_level", "debug"},
		{"auto_cleanup", "true"},
		{"sandbox", "true"},
		{"backend_port", "9000"},
		{"web_port", "4000"},
		{"persistence_backend", "sqlite"},
		{"memory_backend", "mem0"},
	}

	for _, tt := range tests {
		t.Run(tt.key, func(t *testing.T) {
			// Reset rootCmd output after each subtest to prevent
			// cross-contamination of shared Cobra state.
			t.Cleanup(func() {
				rootCmd.SetOut(nil)
				rootCmd.SetErr(nil)
				rootCmd.SetArgs(nil)
			})
			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "get", tt.key, "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			got := strings.TrimSpace(buf.String())
			if got != tt.want {
				t.Errorf("config get %s = %q, want %q", tt.key, got, tt.want)
			}
		})
	}
}

func TestConfigGetUnknownKey(t *testing.T) {
	t.Cleanup(func() {
		rootCmd.SetOut(nil)
		rootCmd.SetErr(nil)
		rootCmd.SetArgs(nil)
	})
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "get", "unknown_key", "--data-dir", dir})
	err := rootCmd.Execute()
	if err == nil {
		t.Fatal("expected error for unknown key")
	}
}

func TestConfigGetRejectsSecretKeys(t *testing.T) {
	t.Cleanup(func() {
		rootCmd.SetOut(nil)
		rootCmd.SetErr(nil)
		rootCmd.SetArgs(nil)
	})
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	for _, key := range []string{"jwt_secret", "settings_key"} {
		t.Run(key, func(t *testing.T) {
			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "get", key, "--data-dir", dir})
			err := rootCmd.Execute()
			if err == nil {
				t.Fatalf("expected error for secret key %q", key)
			}
		})
	}
}

func TestConfigGetDefaultChannel(t *testing.T) {
	t.Cleanup(func() {
		rootCmd.SetOut(nil)
		rootCmd.SetErr(nil)
		rootCmd.SetArgs(nil)
	})
	// Seed a config file that omits "channel" so Load's unmarshal-onto-
	// DefaultState fallback supplies the default "stable" value.
	dir := t.TempDir()
	raw, err := json.Marshal(map[string]any{
		"data_dir":            dir,
		"backend_port":        3001,
		"web_port":            3000,
		"log_level":           "info",
		"persistence_backend": "sqlite",
		"memory_backend":      "mem0",
	})
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "config.json"), raw, 0o600); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "get", "channel", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	got := strings.TrimSpace(buf.String())
	if got != "stable" {
		t.Errorf("config get channel = %q, want stable", got)
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

func TestConfigSetBackendPort(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "backend_port", "9000", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	loaded, err := config.Load(dir)
	if err != nil {
		t.Fatalf("Load after set: %v", err)
	}
	if loaded.BackendPort != 9000 {
		t.Errorf("BackendPort = %d, want 9000", loaded.BackendPort)
	}
}

func TestConfigSetBackendPortRejectsInvalid(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	for _, value := range []string{"0", "-1", "65536", "abc", ""} {
		var buf bytes.Buffer
		rootCmd.SetOut(&buf)
		rootCmd.SetErr(&buf)
		rootCmd.SetArgs([]string{"config", "set", "backend_port", value, "--data-dir", dir})
		if err := rootCmd.Execute(); err == nil {
			t.Errorf("expected error for backend_port=%q", value)
		}
	}
}

func TestConfigSetPortUniqueness(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	// Default: backend=3001, web=3000
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	// Try setting backend_port to same as web_port.
	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "backend_port", "3000", "--data-dir", dir})
	if err := rootCmd.Execute(); err == nil {
		t.Fatal("expected error when backend_port == web_port")
	}

	// Try setting web_port to same as backend_port.
	buf.Reset()
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "web_port", "3001", "--data-dir", dir})
	if err := rootCmd.Execute(); err == nil {
		t.Fatal("expected error when web_port == backend_port")
	}
}

func TestConfigSetWebPort(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "web_port", "4000", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	loaded, err := config.Load(dir)
	if err != nil {
		t.Fatalf("Load after set: %v", err)
	}
	if loaded.WebPort != 4000 {
		t.Errorf("WebPort = %d, want 4000", loaded.WebPort)
	}
}

func TestConfigSetSandbox(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	state.Sandbox = false
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "sandbox", "true", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	loaded, err := config.Load(dir)
	if err != nil {
		t.Fatalf("Load after set: %v", err)
	}
	if !loaded.Sandbox {
		t.Error("Sandbox should be true after set")
	}
}

func TestConfigSetImageTag(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "set", "image_tag", "v1.2.3", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	loaded, err := config.Load(dir)
	if err != nil {
		t.Fatalf("Load after set: %v", err)
	}
	if loaded.ImageTag != "v1.2.3" {
		t.Errorf("ImageTag = %q, want v1.2.3", loaded.ImageTag)
	}
}

func TestConfigSetColor(t *testing.T) {
	for _, value := range []string{"always", "auto", "never"} {
		t.Run(value, func(t *testing.T) {
			dir := t.TempDir()
			state := config.DefaultState()
			state.DataDir = dir
			if err := config.Save(state); err != nil {
				t.Fatal(err)
			}

			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "set", "color", value, "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			loaded, err := config.Load(dir)
			if err != nil {
				t.Fatalf("Load after set: %v", err)
			}
			if loaded.Color != value {
				t.Errorf("Color = %q, want %q", loaded.Color, value)
			}
		})
	}
}

func TestConfigSetColorRejectsInvalid(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	for _, value := range []string{"Always", "NEVER", "none", ""} {
		var buf bytes.Buffer
		rootCmd.SetOut(&buf)
		rootCmd.SetErr(&buf)
		rootCmd.SetArgs([]string{"config", "set", "color", value, "--data-dir", dir})
		if err := rootCmd.Execute(); err == nil {
			t.Errorf("expected error for color=%q", value)
		}
	}
}

func TestConfigSetOutput(t *testing.T) {
	for _, value := range []string{"text", "json"} {
		t.Run(value, func(t *testing.T) {
			dir := t.TempDir()
			state := config.DefaultState()
			state.DataDir = dir
			if err := config.Save(state); err != nil {
				t.Fatal(err)
			}

			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "set", "output", value, "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			loaded, err := config.Load(dir)
			if err != nil {
				t.Fatalf("Load after set: %v", err)
			}
			if loaded.Output != value {
				t.Errorf("Output = %q, want %q", loaded.Output, value)
			}
		})
	}
}

func TestConfigSetTimestamps(t *testing.T) {
	for _, value := range []string{"relative", "iso8601"} {
		t.Run(value, func(t *testing.T) {
			dir := t.TempDir()
			state := config.DefaultState()
			state.DataDir = dir
			if err := config.Save(state); err != nil {
				t.Fatal(err)
			}

			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "set", "timestamps", value, "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			loaded, err := config.Load(dir)
			if err != nil {
				t.Fatalf("Load after set: %v", err)
			}
			if loaded.Timestamps != value {
				t.Errorf("Timestamps = %q, want %q", loaded.Timestamps, value)
			}
		})
	}
}

func TestConfigSetHints(t *testing.T) {
	for _, value := range []string{"always", "auto", "never"} {
		t.Run(value, func(t *testing.T) {
			dir := t.TempDir()
			state := config.DefaultState()
			state.DataDir = dir
			if err := config.Save(state); err != nil {
				t.Fatal(err)
			}

			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "set", "hints", value, "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}

			loaded, err := config.Load(dir)
			if err != nil {
				t.Fatalf("Load after set: %v", err)
			}
			if loaded.Hints != value {
				t.Errorf("Hints = %q, want %q", loaded.Hints, value)
			}
		})
	}
}

func TestConfigSetAutoBehaviorKeys(t *testing.T) {
	tests := []struct {
		key   string
		field func(config.State) bool
	}{
		{"auto_update_cli", func(s config.State) bool { return s.AutoUpdateCLI }},
		{"auto_pull", func(s config.State) bool { return s.AutoPull }},
		{"auto_restart", func(s config.State) bool { return s.AutoRestart }},
		{"auto_apply_compose", func(s config.State) bool { return s.AutoApplyCompose }},
		{"auto_start_after_wipe", func(s config.State) bool { return s.AutoStartAfterWipe }},
	}

	for _, tt := range tests {
		t.Run(tt.key, func(t *testing.T) {
			dir := t.TempDir()
			state := config.DefaultState()
			state.DataDir = dir
			if err := config.Save(state); err != nil {
				t.Fatal(err)
			}

			// Set to true.
			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "set", tt.key, "true", "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("set true: %v", err)
			}

			loaded, err := config.Load(dir)
			if err != nil {
				t.Fatalf("Load after set true: %v", err)
			}
			if !tt.field(loaded) {
				t.Errorf("%s should be true", tt.key)
			}

			// Set to false.
			buf.Reset()
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "set", tt.key, "false", "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("set false: %v", err)
			}

			loaded, err = config.Load(dir)
			if err != nil {
				t.Fatalf("Load after set false: %v", err)
			}
			if tt.field(loaded) {
				t.Errorf("%s should be false", tt.key)
			}
		})
	}
}

func TestConfigUnsetChannel(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	state.Channel = "dev"
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "unset", "channel", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	loaded, err := config.Load(dir)
	if err != nil {
		t.Fatalf("Load after unset: %v", err)
	}
	if loaded.Channel != "stable" {
		t.Errorf("Channel = %q, want stable (default)", loaded.Channel)
	}
}

func TestConfigUnsetBackendPort(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	state.BackendPort = 9000
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "unset", "backend_port", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	loaded, err := config.Load(dir)
	if err != nil {
		t.Fatalf("Load after unset: %v", err)
	}
	if loaded.BackendPort != 3001 {
		t.Errorf("BackendPort = %d, want 3001 (default)", loaded.BackendPort)
	}
}

func TestConfigUnsetRejectsUnknownKey(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "unset", "unknown_key", "--data-dir", dir})
	if err := rootCmd.Execute(); err == nil {
		t.Fatal("expected error for unknown key")
	}
}

func TestConfigListShowsAllKeys(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "list", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	out := buf.String()
	for _, key := range []string{"backend_port", "web_port", "channel", "log_level", "color", "hints"} {
		if !strings.Contains(out, key) {
			t.Errorf("expected %q in config list output", key)
		}
	}
}

func TestConfigListSourceDefault(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "list", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	out := buf.String()
	if !strings.Contains(out, "default") {
		t.Error("expected 'default' source in config list output for default values")
	}
}

func TestConfigPathPrintsPath(t *testing.T) {
	dir := t.TempDir()

	var buf bytes.Buffer
	rootCmd.SetOut(&buf)
	rootCmd.SetErr(&buf)
	rootCmd.SetArgs([]string{"config", "path", "--data-dir", dir})
	if err := rootCmd.Execute(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	got := strings.TrimSpace(buf.String())
	want := config.StatePath(dir)
	if got != want {
		t.Errorf("config path = %q, want %q", got, want)
	}
}

func TestConfigGetNewKeys(t *testing.T) {
	dir := t.TempDir()
	state := config.DefaultState()
	state.DataDir = dir
	state.Color = "never"
	state.Output = "json"
	state.Timestamps = "iso8601"
	state.Hints = "always"
	state.AutoUpdateCLI = true
	state.AutoPull = true
	state.AutoRestart = true
	state.AutoApplyCompose = true
	state.AutoStartAfterWipe = true
	if err := config.Save(state); err != nil {
		t.Fatal(err)
	}

	tests := []struct {
		key  string
		want string
	}{
		{"color", "never"},
		{"output", "json"},
		{"timestamps", "iso8601"},
		{"hints", "always"},
		{"auto_update_cli", "true"},
		{"auto_pull", "true"},
		{"auto_restart", "true"},
		{"auto_apply_compose", "true"},
		{"auto_start_after_wipe", "true"},
		{"docker_sock", ""},
	}

	for _, tt := range tests {
		t.Run(tt.key, func(t *testing.T) {
			t.Cleanup(func() {
				rootCmd.SetOut(nil)
				rootCmd.SetErr(nil)
				rootCmd.SetArgs(nil)
			})
			var buf bytes.Buffer
			rootCmd.SetOut(&buf)
			rootCmd.SetErr(&buf)
			rootCmd.SetArgs([]string{"config", "get", tt.key, "--data-dir", dir})
			if err := rootCmd.Execute(); err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			got := strings.TrimSpace(buf.String())
			if got != tt.want {
				t.Errorf("config get %s = %q, want %q", tt.key, got, tt.want)
			}
		})
	}
}

func FuzzConfigSetBackendPort(f *testing.F) {
	f.Add("3001")
	f.Add("9000")
	f.Add("0")
	f.Add("65536")
	f.Add("abc")
	f.Add("")
	f.Add("-1")

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
		rootCmd.SetArgs([]string{"config", "set", "backend_port", value, "--data-dir", dir})
		err := rootCmd.Execute()

		port, parseErr := strconv.Atoi(value)
		valid := parseErr == nil && port >= 1 && port <= 65535 && port != 3000 // 3000 is default web_port
		if valid && err != nil {
			t.Fatalf("unexpected error for %q: %v", value, err)
		}
		if !valid && err == nil {
			t.Fatalf("expected error for %q", value)
		}
	})
}

func FuzzConfigSetColor(f *testing.F) {
	f.Add("always")
	f.Add("auto")
	f.Add("never")
	f.Add("")
	f.Add("Always")
	f.Add("NEVER")

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
		rootCmd.SetArgs([]string{"config", "set", "color", value, "--data-dir", dir})
		err := rootCmd.Execute()

		valid := value == "always" || value == "auto" || value == "never"
		if valid && err != nil {
			t.Fatalf("unexpected error for %q: %v", value, err)
		}
		if !valid && err == nil {
			t.Fatalf("expected error for %q", value)
		}
	})
}
