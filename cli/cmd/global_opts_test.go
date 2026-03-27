package cmd

import (
	"context"
	"testing"
)

func TestGetGlobalOptsDefault(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	opts := GetGlobalOpts(ctx)

	if opts == nil {
		t.Fatal("GetGlobalOpts should never return nil")
	}
	if opts.Hints != "auto" {
		t.Errorf("Hints = %q, want %q", opts.Hints, "auto")
	}
	if opts.Quiet || opts.JSON || opts.Plain || opts.NoColor || opts.Yes {
		t.Error("default opts should have all bool fields false")
	}
}

func TestSetGetGlobalOpts(t *testing.T) {
	t.Parallel()
	ctx := context.Background()
	want := &GlobalOpts{
		DataDir:    "/tmp/test",
		SkipVerify: true,
		Quiet:      true,
		Verbose:    2,
		NoColor:    true,
		Plain:      true,
		JSON:       false,
		Yes:        true,
		Hints:      "never",
	}
	ctx = SetGlobalOpts(ctx, want)
	got := GetGlobalOpts(ctx)

	if got != want {
		t.Errorf("GetGlobalOpts returned different pointer: got %p, want %p", got, want)
	}
	if got.DataDir != "/tmp/test" {
		t.Errorf("DataDir = %q, want %q", got.DataDir, "/tmp/test")
	}
	if got.Verbose != 2 {
		t.Errorf("Verbose = %d, want 2", got.Verbose)
	}
	if got.Hints != "never" {
		t.Errorf("Hints = %q, want %q", got.Hints, "never")
	}
}

func TestUIOptionsQuietImpliedByJSON(t *testing.T) {
	t.Parallel()
	opts := &GlobalOpts{JSON: true, Hints: "auto"}
	uiOpts := opts.UIOptions()

	if !uiOpts.Quiet {
		t.Error("UIOptions().Quiet should be true when JSON is true")
	}
	if !uiOpts.JSON {
		t.Error("UIOptions().JSON should be true")
	}
}

func TestUIOptionsPlain(t *testing.T) {
	t.Parallel()
	opts := &GlobalOpts{Plain: true, Hints: "always"}
	uiOpts := opts.UIOptions()

	if !uiOpts.Plain {
		t.Error("UIOptions().Plain should be true")
	}
	if uiOpts.Hints != "always" {
		t.Errorf("UIOptions().Hints = %q, want %q", uiOpts.Hints, "always")
	}
}

func TestShouldPromptWithYes(t *testing.T) {
	t.Parallel()
	opts := &GlobalOpts{Yes: true}
	if opts.ShouldPrompt() {
		t.Error("ShouldPrompt() should return false when Yes is true")
	}
}

func TestShouldPromptDefault(t *testing.T) {
	t.Parallel()
	opts := &GlobalOpts{}
	// In CI/test environments, stdin is a pipe (non-TTY), so ShouldPrompt
	// must return false. If this test ever runs with a real TTY stdin
	// (e.g. manual `go test`), the result would be true -- both are valid.
	got := opts.ShouldPrompt()
	if got {
		t.Log("ShouldPrompt() returned true -- stdin appears to be a TTY (expected in interactive test runs)")
	}
}
