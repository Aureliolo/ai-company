package ui

import (
	"bytes"
	"strings"
	"testing"
)

func TestLogo(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Logo("v1.2.3")
	out := buf.String()
	// Box-drawing banner doesn't spell "SynthOrg" literally — check structure.
	if !strings.Contains(out, "╔") {
		t.Error("Logo output missing expected box-drawing content")
	}
	if !strings.Contains(out, "v1.2.3") {
		t.Error("Logo output missing version string")
	}
}

func TestSuccess(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Success("all good")
	out := buf.String()
	if !strings.Contains(out, IconSuccess) {
		t.Errorf("Success output missing icon %q: %s", IconSuccess, out)
	}
	if !strings.Contains(out, "all good") {
		t.Errorf("Success output missing message: %s", out)
	}
}

func TestStep(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Step("doing work")
	out := buf.String()
	if !strings.Contains(out, IconInProgress) {
		t.Errorf("Step output missing icon %q: %s", IconInProgress, out)
	}
	if !strings.Contains(out, "doing work") {
		t.Errorf("Step output missing message: %s", out)
	}
}

func TestWarn(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Warn("careful")
	out := buf.String()
	if !strings.Contains(out, IconWarning) {
		t.Errorf("Warn output missing icon %q: %s", IconWarning, out)
	}
	if !strings.Contains(out, "careful") {
		t.Errorf("Warn output missing message: %s", out)
	}
}

func TestError(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Error("bad thing")
	out := buf.String()
	if !strings.Contains(out, IconError) {
		t.Errorf("Error output missing icon %q: %s", IconError, out)
	}
	if !strings.Contains(out, "bad thing") {
		t.Errorf("Error output missing message: %s", out)
	}
}

func TestKeyValue(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.KeyValue("Data dir", "/tmp/test")
	out := buf.String()
	if !strings.Contains(out, "Data dir:") {
		t.Errorf("KeyValue output missing key: %s", out)
	}
	if !strings.Contains(out, "/tmp/test") {
		t.Errorf("KeyValue output missing value: %s", out)
	}
}

func TestHint(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Hint("try this")
	out := buf.String()
	if !strings.Contains(out, IconHint) {
		t.Errorf("Hint output missing icon %q: %s", IconHint, out)
	}
	if !strings.Contains(out, "try this") {
		t.Errorf("Hint output missing message: %s", out)
	}
}
