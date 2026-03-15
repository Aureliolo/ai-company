// Package ui provides styled CLI output using lipgloss. It defines a
// writer-bound UI type with methods for rendering status lines (success, error,
// warning, step, hint), key-value pairs, and the SynthOrg Unicode logo with
// consistent colors and icons.
package ui

import (
	"fmt"
	"io"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Color palette for CLI styling.
var (
	colorBrand   = lipgloss.Color("99")  // purple
	colorSuccess = lipgloss.Color("42")  // green
	colorWarn    = lipgloss.Color("214") // orange
	colorError   = lipgloss.Color("196") // red
	colorMuted   = lipgloss.Color("245") // gray
	colorLabel   = lipgloss.Color("43")  // cyan
)

// IconSuccess indicates a completed operation.
const IconSuccess = "✓"

// IconInProgress indicates an ongoing operation.
const IconInProgress = "●"

// IconWarning indicates a potential issue.
const IconWarning = "!"

// IconError indicates a failed operation.
const IconError = "✗"

// IconHint indicates a suggestion or next step.
const IconHint = "→"

// UI provides styled CLI output bound to a specific writer.
// Binding to a writer (rather than defaulting to os.Stdout) enables
// testability and correct stderr/stdout separation in Cobra commands.
type UI struct {
	w         io.Writer
	brand     lipgloss.Style
	brandBold lipgloss.Style
	success   lipgloss.Style
	warn      lipgloss.Style
	err       lipgloss.Style
	muted     lipgloss.Style
	label     lipgloss.Style
}

// NewUI creates a UI bound to the given writer.
// The renderer auto-detects whether the writer is a terminal and adjusts
// color output accordingly (no ANSI codes when piped or redirected).
func NewUI(w io.Writer) *UI {
	r := lipgloss.NewRenderer(w)
	return &UI{
		w:         w,
		brand:     r.NewStyle().Foreground(colorBrand),
		brandBold: r.NewStyle().Foreground(colorBrand).Bold(true),
		success:   r.NewStyle().Foreground(colorSuccess),
		warn:      r.NewStyle().Foreground(colorWarn),
		err:       r.NewStyle().Foreground(colorError),
		muted:     r.NewStyle().Foreground(colorMuted),
		label:     r.NewStyle().Foreground(colorLabel),
	}
}

// Logo renders the SynthOrg Unicode logo in brand color with a version tag.
func (u *UI) Logo(version string) {
	art := u.brandBold.Render(logo)
	ver := u.muted.Render(stripControl(version))
	_, _ = fmt.Fprintf(u.w, "%s  %s\n", art, ver)
}

// printLine prints a styled icon followed by a sanitized message.
func (u *UI) printLine(style lipgloss.Style, icon, msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", style.Render(icon), stripControl(msg))
}

// Step prints an in-progress status line.
func (u *UI) Step(msg string) {
	u.printLine(u.brand, IconInProgress, msg)
}

// Success prints a success status line.
func (u *UI) Success(msg string) {
	u.printLine(u.success, IconSuccess, msg)
}

// Warn prints a warning status line.
func (u *UI) Warn(msg string) {
	u.printLine(u.warn, IconWarning, msg)
}

// Error prints an error status line.
func (u *UI) Error(msg string) {
	u.printLine(u.err, IconError, msg)
}

// KeyValue prints a labeled key-value pair.
func (u *UI) KeyValue(key, value string) {
	_, _ = fmt.Fprintf(u.w, "  %s %s\n", u.label.Render(stripControl(key)+":"), stripControl(value))
}

// Hint prints a hint/suggestion line in muted color.
func (u *UI) Hint(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.muted.Render(IconHint), u.muted.Render(stripControl(msg)))
}

// stripControl removes ASCII control characters (except tab and newline)
// to prevent terminal escape sequence injection in displayed values.
func stripControl(s string) string {
	return strings.Map(func(r rune) rune {
		if r < 0x20 && r != '\t' && r != '\n' {
			return -1
		}
		return r
	}, s)
}
