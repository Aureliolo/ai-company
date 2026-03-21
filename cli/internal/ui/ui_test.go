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
	// Box-drawing banner doesn't spell "SynthOrg" literally -- check structure.
	if !strings.Contains(out, "╔") {
		t.Error("Logo output missing expected box-drawing content")
	}
	if !strings.Contains(out, "v1.2.3") {
		t.Error("Logo output missing version string")
	}
	// Verify version string is positioned after the logo art.
	if trimmed := strings.TrimRight(out, "\n"); !strings.HasSuffix(trimmed, "v1.2.3") {
		t.Errorf("version string should appear at the end of logo output, got %q", trimmed)
	}
}

func TestOutputMethods(t *testing.T) {
	cases := []struct {
		name string
		call func(*UI)
		want []string
	}{
		{"Success", func(u *UI) { u.Success("all good") }, []string{IconSuccess, "all good"}},
		{"Step", func(u *UI) { u.Step("doing work") }, []string{IconInProgress, "doing work"}},
		{"Warn", func(u *UI) { u.Warn("careful") }, []string{IconWarning, "careful"}},
		{"Error", func(u *UI) { u.Error("bad thing") }, []string{IconError, "bad thing"}},
		{"KeyValue", func(u *UI) { u.KeyValue("Data dir", "/tmp/test") }, []string{"Data dir:", "/tmp/test"}},
		{"Hint", func(u *UI) { u.Hint("try this") }, []string{IconHint, "try this"}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			var buf bytes.Buffer
			u := NewUI(&buf)
			tc.call(u)
			out := buf.String()
			for _, s := range tc.want {
				if !strings.Contains(out, s) {
					t.Errorf("output missing %q: %s", s, out)
				}
			}
			if !strings.HasSuffix(out, "\n") {
				t.Errorf("output not newline-terminated: %q", out)
			}
		})
	}
}

func TestLink(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Link("Dashboard", "http://localhost:3000")
	out := buf.String()
	if !strings.Contains(out, "Dashboard:") {
		t.Error("Link missing label")
	}
	if !strings.Contains(out, "http://localhost:3000") {
		t.Error("Link missing URL")
	}
}

func TestTable(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Table(
		[]string{"NAME", "VALUE"},
		[][]string{{"foo", "bar"}, {"longer", "x"}},
	)
	out := buf.String()
	if !strings.Contains(out, "NAME") {
		t.Error("Table missing header")
	}
	if !strings.Contains(out, "foo") || !strings.Contains(out, "bar") {
		t.Error("Table missing row data")
	}
	if !strings.Contains(out, "───") {
		t.Error("Table missing separator")
	}
}

func TestTableEmpty(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Table(nil, nil)
	if buf.Len() != 0 {
		t.Error("Table with nil headers should produce no output")
	}
}

func TestWriter(t *testing.T) {
	var buf bytes.Buffer
	u := NewUI(&buf)
	if u.Writer() != &buf {
		t.Error("Writer() should return the underlying writer")
	}
}
