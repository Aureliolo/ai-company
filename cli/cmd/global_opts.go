package cmd

import (
	"context"
	"os"

	"github.com/Aureliolo/synthorg/cli/internal/ui"
)

// GlobalOpts holds CLI-wide options resolved from flags, env vars, and config.
type GlobalOpts struct {
	DataDir    string // effective data directory
	SkipVerify bool   // skip image signature verification
	Quiet      bool   // errors only, no spinners/hints/boxes
	Verbose    int    // 0=normal, 1=verbose, 2=trace
	NoColor    bool   // disable ANSI color/styling
	Plain      bool   // ASCII-only output (no Unicode, no spinners)
	JSON       bool   // machine-readable JSON on stdout
	Yes        bool   // auto-accept all interactive prompts
	Hints      string // hint mode: always/auto/never
}

// UIOptions returns ui.Options derived from the global options.
func (g *GlobalOpts) UIOptions() ui.Options {
	return ui.Options{
		Quiet:   g.Quiet || g.JSON, // JSON implies quiet for human output
		Verbose: g.Verbose,
		NoColor: g.NoColor,
		Plain:   g.Plain,
		JSON:    g.JSON,
		Hints:   g.Hints,
	}
}

// ShouldPrompt reports whether the CLI should show interactive prompts.
// Returns false when --yes is active or stdin is not a terminal.
func (g *GlobalOpts) ShouldPrompt() bool {
	if g.Yes {
		return false
	}
	fi, err := os.Stdin.Stat()
	if err != nil {
		return false
	}
	return fi.Mode()&os.ModeCharDevice != 0
}

// globalOptsKey is the context key for GlobalOpts.
type globalOptsKey struct{}

// SetGlobalOpts stores GlobalOpts in a context.
func SetGlobalOpts(ctx context.Context, opts *GlobalOpts) context.Context {
	return context.WithValue(ctx, globalOptsKey{}, opts)
}

// GetGlobalOpts retrieves GlobalOpts from a context.
// Returns a zero-value GlobalOpts if not set (safe default).
func GetGlobalOpts(ctx context.Context) *GlobalOpts {
	if opts, ok := ctx.Value(globalOptsKey{}).(*GlobalOpts); ok {
		return opts
	}
	return &GlobalOpts{Hints: "auto"}
}

// validHintsMode reports whether h is a recognized hints mode.
func validHintsMode(h string) bool {
	return h == "always" || h == "auto" || h == "never"
}
