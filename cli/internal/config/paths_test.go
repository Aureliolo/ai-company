package config

import (
	"os"
	"path/filepath"
	"runtime"
	"testing"
)

func TestDataDirDefault(t *testing.T) {
	dir := DataDir()
	if dir == "" {
		t.Fatal("DataDir returned empty string")
	}
	if filepath.Base(dir) != appDirName {
		t.Errorf("DataDir base = %q, want %q", filepath.Base(dir), appDirName)
	}
}

func TestDataDirXDG(t *testing.T) {
	if runtime.GOOS != "linux" {
		t.Skip("XDG test only applies on Linux")
	}
	t.Setenv("XDG_DATA_HOME", "/custom/data")
	got := DataDir()
	want := filepath.Join("/custom/data", appDirName)
	if got != want {
		t.Errorf("DataDir = %q, want %q", got, want)
	}
}

func TestEnsureDir(t *testing.T) {
	tmp := t.TempDir()
	target := filepath.Join(tmp, "nested", "dir")
	if err := EnsureDir(target); err != nil {
		t.Fatalf("EnsureDir: %v", err)
	}
	info, err := os.Stat(target)
	if err != nil {
		t.Fatalf("Stat after EnsureDir: %v", err)
	}
	if !info.IsDir() {
		t.Error("expected directory")
	}
}
