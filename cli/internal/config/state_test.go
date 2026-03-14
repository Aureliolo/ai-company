package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDefaultState(t *testing.T) {
	s := DefaultState()
	if s.BackendPort != 8000 {
		t.Errorf("BackendPort = %d, want 8000", s.BackendPort)
	}
	if s.WebPort != 3000 {
		t.Errorf("WebPort = %d, want 3000", s.WebPort)
	}
	if s.ImageTag != "latest" {
		t.Errorf("ImageTag = %q, want latest", s.ImageTag)
	}
	if s.LogLevel != "info" {
		t.Errorf("LogLevel = %q, want info", s.LogLevel)
	}
}

func TestSaveAndLoad(t *testing.T) {
	tmp := t.TempDir()
	s := State{
		DataDir:     tmp,
		ImageTag:    "v0.1.5",
		BackendPort: 9000,
		WebPort:     3001,
		LogLevel:    "debug",
		JWTSecret:   "test-secret",
	}

	if err := Save(s); err != nil {
		t.Fatalf("Save: %v", err)
	}

	loaded, err := Load(tmp)
	if err != nil {
		t.Fatalf("Load: %v", err)
	}

	if loaded.BackendPort != s.BackendPort {
		t.Errorf("BackendPort = %d, want %d", loaded.BackendPort, s.BackendPort)
	}
	if loaded.ImageTag != s.ImageTag {
		t.Errorf("ImageTag = %q, want %q", loaded.ImageTag, s.ImageTag)
	}
	if loaded.JWTSecret != s.JWTSecret {
		t.Errorf("JWTSecret = %q, want %q", loaded.JWTSecret, s.JWTSecret)
	}
}

func TestLoadMissing(t *testing.T) {
	tmp := t.TempDir()
	s, err := Load(tmp)
	if err != nil {
		t.Fatalf("Load missing file: %v", err)
	}
	// Should return defaults
	if s.BackendPort != 8000 {
		t.Errorf("expected default BackendPort 8000, got %d", s.BackendPort)
	}
}

func TestLoadInvalid(t *testing.T) {
	tmp := t.TempDir()
	if err := os.WriteFile(filepath.Join(tmp, stateFileName), []byte("{invalid"), 0o600); err != nil {
		t.Fatal(err)
	}
	_, err := Load(tmp)
	if err == nil {
		t.Fatal("expected error for invalid JSON")
	}
}
