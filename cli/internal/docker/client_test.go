package docker

import (
	"runtime"
	"testing"
)

func TestInstallHint(t *testing.T) {
	hint := installHint()
	if hint == "" {
		t.Error("installHint returned empty string")
	}
	// Should contain a URL
	if len(hint) < 10 {
		t.Errorf("installHint too short: %q", hint)
	}
}

func TestDaemonHint(t *testing.T) {
	hint := daemonHint()
	if hint == "" {
		t.Error("daemonHint returned empty string")
	}
	switch runtime.GOOS {
	case "darwin", "windows":
		if hint != "Start Docker Desktop and try again." {
			t.Errorf("unexpected hint for %s: %q", runtime.GOOS, hint)
		}
	}
}
