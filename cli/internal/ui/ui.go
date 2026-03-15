// Package ui provides styled CLI output using lipgloss.
package ui

import (
	"fmt"
	"io"

	"github.com/charmbracelet/lipgloss"
)

// Status icons for CLI output.
const (
	IconSuccess    = "✓"
	IconInProgress = "●"
	IconWarning    = "!"
	IconError      = "✗"
	IconHint       = "→"
)

// UI provides styled CLI output bound to a specific writer.
type UI struct {
	w       io.Writer
	brand   lipgloss.Style
	success lipgloss.Style
	warn    lipgloss.Style
	err     lipgloss.Style
	muted   lipgloss.Style
	label   lipgloss.Style
}

// NewUI creates a UI bound to the given writer.
// The renderer auto-detects terminal capabilities from the writer.
func NewUI(w io.Writer) *UI {
	r := lipgloss.NewRenderer(w)
	return &UI{
		w:       w,
		brand:   r.NewStyle().Foreground(lipgloss.Color("99")),
		success: r.NewStyle().Foreground(lipgloss.Color("42")),
		warn:    r.NewStyle().Foreground(lipgloss.Color("214")),
		err:     r.NewStyle().Foreground(lipgloss.Color("196")),
		muted:   r.NewStyle().Foreground(lipgloss.Color("245")),
		label:   r.NewStyle().Foreground(lipgloss.Color("43")),
	}
}

// Logo renders the SynthOrg ASCII art logo in brand color with a version tag.
func (u *UI) Logo(version string) {
	art := u.brand.Bold(true).Render(logo)
	ver := u.muted.Render(version)
	_, _ = fmt.Fprintf(u.w, "%s  %s\n", art, ver)
}

// Step prints an in-progress status line.
func (u *UI) Step(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.brand.Render(IconInProgress), msg)
}

// Success prints a success status line.
func (u *UI) Success(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.success.Render(IconSuccess), msg)
}

// Warn prints a warning status line.
func (u *UI) Warn(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.warn.Render(IconWarning), msg)
}

// Error prints an error status line.
func (u *UI) Error(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.err.Render(IconError), msg)
}

// KeyValue prints a labeled key-value pair.
func (u *UI) KeyValue(key, value string) {
	_, _ = fmt.Fprintf(u.w, "  %s %s\n", u.label.Render(key+":"), value)
}

// Hint prints a hint/suggestion line in muted color.
func (u *UI) Hint(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.muted.Render(IconHint), u.muted.Render(msg))
}
