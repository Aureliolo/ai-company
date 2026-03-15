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
	w io.Writer
	r *lipgloss.Renderer
}

// NewUI creates a UI bound to the given writer.
// The renderer auto-detects terminal capabilities from the writer.
func NewUI(w io.Writer) *UI {
	return &UI{
		w: w,
		r: lipgloss.NewRenderer(w),
	}
}

func (u *UI) brandStyle() lipgloss.Style {
	return u.r.NewStyle().Foreground(lipgloss.Color("99"))
}

func (u *UI) successStyle() lipgloss.Style {
	return u.r.NewStyle().Foreground(lipgloss.Color("42"))
}

func (u *UI) warnStyle() lipgloss.Style {
	return u.r.NewStyle().Foreground(lipgloss.Color("214"))
}

func (u *UI) errorStyle() lipgloss.Style {
	return u.r.NewStyle().Foreground(lipgloss.Color("196"))
}

func (u *UI) mutedStyle() lipgloss.Style {
	return u.r.NewStyle().Foreground(lipgloss.Color("245"))
}

func (u *UI) labelStyle() lipgloss.Style {
	return u.r.NewStyle().Foreground(lipgloss.Color("43"))
}

// Logo renders the SynthOrg ASCII art logo in brand color with a version tag.
func (u *UI) Logo(version string) {
	art := u.brandStyle().Bold(true).Render(logo)
	ver := u.mutedStyle().Render(version)
	_, _ = fmt.Fprintf(u.w, "%s  %s\n", art, ver)
}

// Step prints an in-progress status line.
func (u *UI) Step(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.brandStyle().Render(IconInProgress), msg)
}

// Success prints a success status line.
func (u *UI) Success(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.successStyle().Render(IconSuccess), msg)
}

// Warn prints a warning status line.
func (u *UI) Warn(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.warnStyle().Render(IconWarning), msg)
}

// Error prints an error status line.
func (u *UI) Error(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.errorStyle().Render(IconError), msg)
}

// KeyValue prints a labeled key-value pair.
func (u *UI) KeyValue(key, value string) {
	_, _ = fmt.Fprintf(u.w, "  %s %s\n", u.labelStyle().Render(key+":"), value)
}

// Hint prints a hint/suggestion line in muted color.
func (u *UI) Hint(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.mutedStyle().Render(IconHint), u.mutedStyle().Render(msg))
}
