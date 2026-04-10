package ui

import (
	"bytes"
	"testing"
)

// pickerTestOptions is the fixture used by all picker tests.
// It mirrors the shape of BusBackends so regressions in the generic
// helper surface cleanly without depending on the real registry.
var pickerTestOptions = []Option[string]{
	{
		ID:      "alpha",
		Label:   "Alpha",
		Summary: "default option",
		Pros:    []string{"zero setup", "fast"},
		Cons:    []string{"single process"},
		Default: true,
		Value:   "alpha",
	},
	{
		ID:      "beta",
		Label:   "Beta",
		Summary: "opt-in option",
		Pros:    []string{"distributed", "durable"},
		Cons:    []string{"extra container"},
		Default: false,
		Value:   "beta",
	},
}

func TestPickOneReturnsDefaultWhenYes(t *testing.T) {
	t.Parallel()
	cfg := PickOneConfig{Yes: true}
	got, err := PickOne("Test", "help", pickerTestOptions, cfg)
	if err != nil {
		t.Fatalf("PickOne returned error: %v", err)
	}
	if got != "alpha" {
		t.Errorf("expected default %q, got %q", "alpha", got)
	}
}

func TestPickOneReturnsDefaultWhenQuiet(t *testing.T) {
	t.Parallel()
	cfg := PickOneConfig{Quiet: true}
	got, err := PickOne("Test", "help", pickerTestOptions, cfg)
	if err != nil {
		t.Fatalf("PickOne returned error: %v", err)
	}
	if got != "alpha" {
		t.Errorf("expected default %q, got %q", "alpha", got)
	}
}

func TestPickOneReturnsDefaultWhenNonTTYStdin(t *testing.T) {
	t.Parallel()
	cfg := PickOneConfig{Stdin: bytes.NewReader(nil)}
	got, err := PickOne("Test", "help", pickerTestOptions, cfg)
	if err != nil {
		t.Fatalf("PickOne returned error: %v", err)
	}
	if got != "alpha" {
		t.Errorf("expected default %q, got %q", "alpha", got)
	}
}

func TestPickOneErrorsOnEmptyOptions(t *testing.T) {
	t.Parallel()
	cfg := PickOneConfig{Yes: true}
	_, err := PickOne[string]("Test", "help", nil, cfg)
	if err == nil {
		t.Fatal("expected error for empty options, got nil")
	}
}

func TestPickDefaultFallsBackToFirstWhenNoneMarked(t *testing.T) {
	t.Parallel()
	opts := []Option[string]{
		{ID: "a", Label: "A", Value: "a"},
		{ID: "b", Label: "B", Value: "b"},
	}
	cfg := PickOneConfig{Yes: true}
	got, err := PickOne("Test", "help", opts, cfg)
	if err != nil {
		t.Fatalf("PickOne returned error: %v", err)
	}
	if got != "a" {
		t.Errorf("expected first option %q, got %q", "a", got)
	}
}

func TestPickDefaultFallsBackToFirstWhenMultipleMarked(t *testing.T) {
	// Documented behavior: "If zero or multiple are marked, PickOne
	// falls back to the first option." A registry that accidentally
	// marks two options as Default=true must not silently pick
	// whichever one scanning encounters first -- that would hide
	// registry mistakes.
	t.Parallel()
	opts := []Option[string]{
		{ID: "a", Label: "A", Value: "a"},
		{ID: "b", Label: "B", Value: "b", Default: true},
		{ID: "c", Label: "C", Value: "c", Default: true},
	}
	cfg := PickOneConfig{Yes: true}
	got, err := PickOne("Test", "help", opts, cfg)
	if err != nil {
		t.Fatalf("PickOne returned error: %v", err)
	}
	if got != "a" {
		t.Errorf("expected first option %q, got %q", "a", got)
	}
}

func TestPickDefaultHonoursUniqueDefault(t *testing.T) {
	t.Parallel()
	opts := []Option[string]{
		{ID: "a", Label: "A", Value: "a"},
		{ID: "b", Label: "B", Value: "b", Default: true},
		{ID: "c", Label: "C", Value: "c"},
	}
	cfg := PickOneConfig{Yes: true}
	got, err := PickOne("Test", "help", opts, cfg)
	if err != nil {
		t.Fatalf("PickOne returned error: %v", err)
	}
	if got != "b" {
		t.Errorf("expected unique default %q, got %q", "b", got)
	}
}

func TestFindOptionByID(t *testing.T) {
	t.Parallel()
	got := FindOption(pickerTestOptions, "beta")
	if got == nil {
		t.Fatal("FindOption returned nil for valid ID")
	}
	if got.Value != "beta" {
		t.Errorf("expected value %q, got %q", "beta", got.Value)
	}
}

func TestFindOptionUnknownID(t *testing.T) {
	t.Parallel()
	got := FindOption(pickerTestOptions, "nonexistent")
	if got != nil {
		t.Errorf("expected nil for unknown ID, got %+v", got)
	}
}

func TestOptionIDsOrderPreserved(t *testing.T) {
	t.Parallel()
	ids := OptionIDs(pickerTestOptions)
	if len(ids) != 2 {
		t.Fatalf("expected 2 IDs, got %d", len(ids))
	}
	if ids[0] != "alpha" || ids[1] != "beta" {
		t.Errorf("expected [alpha beta], got %v", ids)
	}
}

func TestBusBackendsRegistryShape(t *testing.T) {
	t.Parallel()
	// Regression guard: the BusBackends registry should contain at least
	// internal and nats, exactly one default, and every entry should
	// have non-empty Pros + Cons (neutral framing invariant).
	if len(BusBackends) < 2 {
		t.Fatalf("expected at least 2 bus backends, got %d", len(BusBackends))
	}

	defaults := 0
	for i := range BusBackends {
		opt := &BusBackends[i]
		if opt.Default {
			defaults++
		}
		if opt.ID == "" {
			t.Errorf("backend at index %d has empty ID", i)
		}
		if opt.Label == "" {
			t.Errorf("backend %q has empty Label", opt.ID)
		}
		if len(opt.Pros) < 2 {
			t.Errorf("backend %q has %d pros; expected >= 2 for neutral framing", opt.ID, len(opt.Pros))
		}
		if len(opt.Cons) < 2 {
			t.Errorf("backend %q has %d cons; expected >= 2 for neutral framing", opt.ID, len(opt.Cons))
		}
	}
	if defaults != 1 {
		t.Errorf("expected exactly 1 default bus backend, got %d", defaults)
	}

	if FindOption(BusBackends, "internal") == nil {
		t.Error("expected 'internal' bus backend in registry")
	}
	if FindOption(BusBackends, "nats") == nil {
		t.Error("expected 'nats' bus backend in registry")
	}
}
