// Package ui provides a generic option picker built on charm.land/huh/v2.
//
// The picker is intentionally data-driven: callers hand in a slice of
// Option[T] structs describing each choice (label, summary, pros, cons,
// default flag, value) and PickOne returns the chosen value. Adding a
// new choice never requires touching picker.go itself; append a new
// struct literal to the caller's registry (e.g. BusBackends in
// options.go) and the picker renders it automatically.
//
// Non-interactive behaviors:
//   - When --yes / SYNTHORG_YES is set, the picker returns the default
//     option without prompting and is a no-op.
//   - When --quiet is set, same behavior as --yes.
//   - When --plain is set, the picker still works but falls back to an
//     ASCII-only rendering.
//   - When stdin is not a TTY (piped, CI, non-interactive shell), the
//     picker returns the default silently.
//   - When the caller provides an explicit value (e.g. via a CLI flag),
//     callers should skip calling PickOne entirely.

package ui

import (
	"fmt"
	"io"
	"os"
	"strings"

	"charm.land/huh/v2"
	"github.com/mattn/go-isatty"
)

// Option describes a single choice displayed by PickOne.
//
// The generic parameter T is the underlying value type. For most
// registries, T is a string (the value written to config). Using a
// type parameter keeps the picker reusable for future pickers where
// the value is a struct or enum.
type Option[T any] struct {
	// ID is a machine-readable identifier used for matching explicit
	// flag values (e.g. --bus-backend nats). Keep it lowercase ASCII.
	ID string

	// Label is the human-readable title shown in the picker list
	// (e.g. "NATS JetStream"). 1-5 words.
	Label string

	// Summary is a one-line description shown next to the label.
	Summary string

	// Pros is a bullet list of benefits. Rendered under the summary.
	// Keep each bullet short (<80 chars).
	Pros []string

	// Cons is a bullet list of drawbacks. Rendered under Pros.
	// Keep each bullet short (<80 chars).
	Cons []string

	// Default marks this option as the pre-selected default. Exactly
	// one option in a registry should set Default=true. If zero or
	// multiple are marked, PickOne falls back to the first option.
	Default bool

	// Value is the underlying value returned when this option is
	// chosen. For most registries this is a string written to config.
	Value T
}

// PickOneConfig captures the ambient runtime state that affects how
// PickOne renders (or whether it renders at all).
type PickOneConfig struct {
	// Yes mirrors the global --yes / SYNTHORG_YES flag. When true,
	// the picker returns the default without prompting.
	Yes bool

	// Quiet mirrors the global --quiet flag. When true, the picker
	// returns the default without prompting or output.
	Quiet bool

	// Plain mirrors the global --plain flag. When true, the picker
	// renders without Unicode box-drawing characters.
	Plain bool

	// Stdin is the input stream used for TTY detection. Defaults to
	// os.Stdin when zero.
	Stdin io.Reader

	// Stdout is where the picker writes its UI. Defaults to os.Stdout
	// when zero. The picker never writes to stdout in Quiet mode.
	Stdout io.Writer
}

// PickOne renders an interactive single-choice picker and returns the
// selected option's Value.
//
// When the ambient environment is non-interactive (Yes, Quiet, non-TTY
// stdin) the picker is a no-op and returns the default option's value
// immediately. Callers that have an explicit value (e.g. a --foo flag)
// should skip the picker entirely rather than calling with a pre-chosen
// default.
//
// The title is rendered as the form title. The help string is shown
// under the list as muted guidance. Each option's label, summary, pros
// and cons are rendered as the option description.
//
// When cfg.Stdin or cfg.Stdout are set the form uses them instead of
// the default os.Stdin/os.Stdout; tests and wrappers can use this to
// capture output or feed scripted input. When cfg.Plain is true the
// form renders with huh's Base16 theme so output remains legible on
// terminals that do not handle ANSI styling (ASCII-only sessions,
// CI log panes, non-Unicode consoles).
//
// Returns an error if huh fails to render or if options is empty.
func PickOne[T any](
	title string,
	help string,
	options []Option[T],
	cfg PickOneConfig,
) (T, error) {
	var zero T
	if len(options) == 0 {
		return zero, fmt.Errorf("PickOne requires at least one option")
	}

	defaultValue, defaultIdx := pickDefault(options)

	if shouldSkipInteractive(cfg) {
		return defaultValue, nil
	}

	selected := defaultIdx
	selectField := huh.NewSelect[int]().
		Title(title).
		Description(help).
		Options(buildHuhOptions(options)...).
		Value(&selected)

	form := huh.NewForm(huh.NewGroup(selectField))
	if cfg.Plain {
		form = form.WithTheme(huh.ThemeFunc(huh.ThemeBase16))
	}
	if cfg.Stdout != nil {
		form = form.WithOutput(cfg.Stdout)
	}
	if cfg.Stdin != nil {
		form = form.WithInput(cfg.Stdin)
	}
	if err := form.Run(); err != nil {
		return zero, fmt.Errorf("running picker: %w", err)
	}

	if selected < 0 || selected >= len(options) {
		return defaultValue, nil
	}
	return options[selected].Value, nil
}

// FindOption returns the Option with a matching ID from a registry, or
// nil if the ID is not recognized. Callers use this to validate
// explicit flag values (e.g. --bus-backend nats).
func FindOption[T any](options []Option[T], id string) *Option[T] {
	for i := range options {
		if options[i].ID == id {
			return &options[i]
		}
	}
	return nil
}

// OptionIDs returns the IDs of all options in a registry, in order.
// Useful for building error messages like "must be one of: internal,
// nats, ...".
func OptionIDs[T any](options []Option[T]) []string {
	ids := make([]string, 0, len(options))
	for i := range options {
		ids = append(ids, options[i].ID)
	}
	return ids
}

// pickDefault returns the default option's Value and index.
//
// The documented contract in the Option.Default field comment is:
// "Exactly one option in a registry should set Default=true. If zero
// or multiple are marked, PickOne falls back to the first option."
//
// This function enforces that contract. Returning early on the first
// Default=true would silently pick one of several equally-marked
// entries, which hides registry mistakes instead of making them
// deterministic. Count the matches first, then either return the
// unique default or fall back to index 0.
func pickDefault[T any](options []Option[T]) (T, int) {
	defaultCount := 0
	defaultIdx := 0
	for i := range options {
		if options[i].Default {
			defaultCount++
			if defaultCount == 1 {
				defaultIdx = i
			}
		}
	}
	if defaultCount == 1 {
		return options[defaultIdx].Value, defaultIdx
	}
	return options[0].Value, 0
}

// shouldSkipInteractive returns true when the picker should be a
// no-op and return the default immediately.
//
// Skip rules, in order:
//  1. --yes or --quiet is set.
//  2. cfg.Stdin is non-nil and not an *os.File (e.g. bytes.Reader
//     from a test or a pipe wrapper): definitely not a TTY, skip.
//  3. cfg.Stdin (or os.Stdin when unset) is an *os.File but its
//     file descriptor is not a terminal: skip.
//
// Only when cfg.Stdin points at an actual TTY does the picker run
// the interactive form.
func shouldSkipInteractive(cfg PickOneConfig) bool {
	if cfg.Yes || cfg.Quiet {
		return true
	}
	if cfg.Stdin != nil {
		f, ok := cfg.Stdin.(*os.File)
		if !ok {
			return true
		}
		return !isatty.IsTerminal(f.Fd())
	}
	return !isatty.IsTerminal(os.Stdin.Fd())
}

// buildHuhOptions converts the registry into huh.Option values. The
// huh value is the index into options so PickOne can look up the
// T value after the form runs without constraining T to comparable.
func buildHuhOptions[T any](options []Option[T]) []huh.Option[int] {
	huhOpts := make([]huh.Option[int], 0, len(options))
	for i := range options {
		opt := &options[i]
		label := renderOptionLabel(opt)
		huhOpts = append(huhOpts, huh.NewOption(label, i))
	}
	return huhOpts
}

// renderOptionLabel builds the multi-line label shown for each option
// inside the huh select widget: title, summary, pros, cons.
func renderOptionLabel[T any](opt *Option[T]) string {
	var b strings.Builder
	b.WriteString(opt.Label)
	if opt.Default {
		b.WriteString(" (default)")
	}
	if opt.Summary != "" {
		b.WriteString(" -- ")
		b.WriteString(opt.Summary)
	}
	for _, p := range opt.Pros {
		b.WriteString("\n  + ")
		b.WriteString(p)
	}
	for _, c := range opt.Cons {
		b.WriteString("\n  - ")
		b.WriteString(c)
	}
	return b.String()
}
