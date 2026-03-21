package ui

import (
	"bytes"
	"strings"
	"testing"
)

func TestLogo(t *testing.T) {
	t.Parallel()
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
	t.Parallel()
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
	t.Parallel()
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
	t.Parallel()
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
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Table(nil, nil)
	if buf.Len() != 0 {
		t.Error("Table with nil headers should produce no output")
	}
}

func TestWriter(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	if u.Writer() != &buf {
		t.Error("Writer() should return the underlying writer")
	}
}

func TestBlank(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Blank()
	if buf.String() != "\n" {
		t.Errorf("Blank should produce single newline, got %q", buf.String())
	}
}

func TestPlain(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Plain("hello world")
	if !strings.Contains(buf.String(), "hello world") {
		t.Error("Plain missing message")
	}
}

func TestDivider(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Divider()
	out := buf.String()
	if !strings.Contains(out, "\u2500") {
		t.Error("Divider missing horizontal line character")
	}
}

func TestInlineKV(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.InlineKV("Docker", "29.2.1", "Compose", "5.1.0")
	out := buf.String()
	if !strings.Contains(out, "Docker") || !strings.Contains(out, "29.2.1") {
		t.Error("InlineKV missing first pair")
	}
	if !strings.Contains(out, "Compose") || !strings.Contains(out, "5.1.0") {
		t.Error("InlineKV missing second pair")
	}
}

func TestIconAccessors(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	if !strings.Contains(u.SuccessIcon(), IconSuccess) {
		t.Error("SuccessIcon missing checkmark")
	}
	if !strings.Contains(u.ErrorIcon(), IconError) {
		t.Error("ErrorIcon missing cross")
	}
	if !strings.Contains(u.WarnIcon(), IconWarning) {
		t.Error("WarnIcon missing exclamation")
	}
}

func TestIsTTY(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	// A bytes.Buffer is not a TTY.
	if u.IsTTY() {
		t.Error("bytes.Buffer should not be detected as TTY")
	}
}

func TestBox(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Box("Test Box", []string{"line one", "line two"})
	out := buf.String()
	if !strings.Contains(out, "Test Box") {
		t.Error("Box missing title")
	}
	if !strings.Contains(out, "line one") {
		t.Error("Box missing first line")
	}
	if !strings.Contains(out, "line two") {
		t.Error("Box missing second line")
	}
	// Check box-drawing characters.
	if !strings.Contains(out, "\u250c") { // top-left corner
		t.Error("Box missing top-left corner")
	}
	if !strings.Contains(out, "\u2514") { // bottom-left corner
		t.Error("Box missing bottom-left corner")
	}
	if !strings.Contains(out, "\u2502") { // vertical line
		t.Error("Box missing vertical line")
	}
}

func TestBoxEmpty(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	u.Box("Empty", nil)
	if buf.Len() != 0 {
		t.Error("Box with no lines should produce no output")
	}
}

func TestSpinnerNonTTY(t *testing.T) {
	t.Parallel()
	// On a non-TTY writer (bytes.Buffer), the spinner should print a
	// static step line immediately and Stop/Success should work without
	// animation.
	var buf bytes.Buffer
	u := NewUI(&buf)
	s := u.StartSpinner("loading...")
	s.Success("done!")
	out := buf.String()
	if !strings.Contains(out, "loading...") {
		t.Error("Spinner should print step message on non-TTY")
	}
	if !strings.Contains(out, "done!") {
		t.Error("Spinner.Success should print final message")
	}
}

func TestSpinnerDoubleStop(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	s := u.StartSpinner("work")
	s.Stop()
	s.Stop() // should not panic
}

func TestStripControl(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"plain text", "hello", "hello"},
		{"bell char", "hello\x07world", "helloworld"},
		{"backspace", "hello\x08world", "helloworld"},
		{"carriage return", "hello\rworld", "helloworld"},
		{"ESC byte", "hello\x1b[2Jworld", "hello[2Jworld"},
		{"null byte", "hello\x00world", "helloworld"},
		{"preserves tab", "hello\tworld", "hello\tworld"},
		{"preserves newline", "hello\nworld", "hello\nworld"},
		{"multiple controls", "\x01\x02\x03ok", "ok"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := stripControl(tt.input)
			if got != tt.want {
				t.Errorf("stripControl(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestStripControlStrict(t *testing.T) {
	t.Parallel()

	tests := []struct {
		name  string
		input string
		want  string
	}{
		{"plain text", "hello", "hello"},
		{"strips tab", "hello\tworld", "helloworld"},
		{"strips newline", "hello\nworld", "helloworld"},
		{"strips ESC", "hello\x1b[32mworld", "hello[32mworld"},
		{"strips all controls", "\x00\x01\t\n\x1bok", "ok"},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			got := stripControlStrict(tt.input)
			if got != tt.want {
				t.Errorf("stripControlStrict(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

// TestSpinnerConcurrentStop exercises the Spinner's concurrency safety by
// calling Stop from multiple goroutines concurrently. The sync.Once in
// waitAndClear should prevent any panics from double-closing the done channel.
// Note: full TTY spinner animation testing requires a pseudo-terminal which
// is not available in unit tests; CI uses the race detector to catch races.
func TestSpinnerConcurrentStop(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	s := u.StartSpinner("concurrent work")

	done := make(chan struct{})
	for range 5 {
		go func() {
			s.Stop()
			done <- struct{}{}
		}()
	}
	for range 5 {
		<-done
	}
}

func TestLiveBoxNonTTY(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	lb := u.NewLiveBox("Pull Images", []string{"backend", "web", "sandbox"})

	// Non-TTY: NewLiveBox prints a step line with the title.
	out := buf.String()
	if !strings.Contains(out, "Pull Images") {
		t.Error("NewLiveBox should print title on non-TTY")
	}

	// Updating lines should print status lines.
	lb.UpdateLine(0, IconSuccess)
	out = buf.String()
	if !strings.Contains(out, "backend") {
		t.Error("UpdateLine should print label on non-TTY")
	}

	lb.UpdateLine(1, IconError)
	out = buf.String()
	if !strings.Contains(out, "web") {
		t.Error("UpdateLine error should print label on non-TTY")
	}

	lb.UpdateLine(2, IconSuccess)
	lb.Finish()
}

func TestLiveBoxFinishIdempotent(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	lb := u.NewLiveBox("Test", []string{"a"})
	lb.UpdateLine(0, IconSuccess)
	lb.Finish()
	lb.Finish() // should not panic
}

func TestLiveBoxOutOfBounds(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	lb := u.NewLiveBox("Test", []string{"a"})
	lb.UpdateLine(-1, IconSuccess) // should not panic
	lb.UpdateLine(5, IconSuccess)  // should not panic
	lb.UpdateLine(0, IconSuccess)
	lb.Finish()
}

func TestLiveBoxBuildLines(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	lb := u.NewLiveBox("Test", []string{"svc1", "svc2"})

	lb.mu.Lock()
	// Before any updates, all lines should show spinner frame.
	lines := lb.buildLines(0)
	lb.mu.Unlock()

	if len(lines) != 2 {
		t.Fatalf("expected 2 lines, got %d", len(lines))
	}
	if !strings.Contains(lines[0], "svc1") {
		t.Error("line 0 missing label svc1")
	}
	if !strings.Contains(lines[0], spinnerFrames[0]) {
		t.Error("line 0 should contain spinner frame")
	}

	// After marking finished, line should show status.
	lb.UpdateLine(0, IconSuccess)
	lb.mu.Lock()
	lines = lb.buildLines(0)
	lb.mu.Unlock()
	if !strings.Contains(lines[0], IconSuccess) {
		t.Error("finished line should show success icon")
	}
	if !strings.Contains(lines[1], spinnerFrames[0]) {
		t.Error("unfinished line should still show spinner")
	}

	lb.UpdateLine(1, IconSuccess)
	lb.Finish()
}

func TestInlineKVOddArgs(t *testing.T) {
	t.Parallel()
	var buf bytes.Buffer
	u := NewUI(&buf)
	// Odd number of args: last key should be dropped silently.
	u.InlineKV("Docker", "29.2.1", "Orphan")
	out := buf.String()
	if !strings.Contains(out, "Docker") || !strings.Contains(out, "29.2.1") {
		t.Error("InlineKV should render complete pairs")
	}
	if strings.Contains(out, "Orphan") {
		t.Error("InlineKV should drop unpaired trailing key")
	}
}
