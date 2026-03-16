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
	"github.com/mattn/go-runewidth"
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

// Writer returns the underlying writer for direct output.
func (u *UI) Writer() io.Writer { return u.w }

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

// Section prints a bold section header.
func (u *UI) Section(title string) {
	_, _ = fmt.Fprintln(u.w, u.brandBold.Render(stripControl(title)))
}

// Link prints a labeled URL in muted color.
func (u *UI) Link(label, url string) {
	_, _ = fmt.Fprintf(u.w, "  %s %s\n", u.label.Render(stripControl(label)+":"), u.muted.Render(stripControl(url)))
}

// Table prints rows as a fixed-width table with a header.
// All values are sanitized to prevent terminal control injection.
func (u *UI) Table(headers []string, rows [][]string) {
	if len(headers) == 0 {
		return
	}
	// Sanitize all inputs.
	sanHeaders := make([]string, len(headers))
	for i, h := range headers {
		sanHeaders[i] = stripControl(h)
	}
	sanRows := make([][]string, len(rows))
	for i, row := range rows {
		sanRow := make([]string, len(row))
		for j, cell := range row {
			sanRow[j] = stripControl(cell)
		}
		sanRows[i] = sanRow
	}
	widths := make([]int, len(sanHeaders))
	for i, h := range sanHeaders {
		widths[i] = runewidth.StringWidth(h)
	}
	for _, row := range sanRows {
		for i := range widths {
			if i < len(row) {
				if w := runewidth.StringWidth(row[i]); w > widths[i] {
					widths[i] = w
				}
			}
		}
	}
	printRow := func(cells []string) {
		var b strings.Builder
		b.WriteString("  ")
		for i, w := range widths {
			cell := ""
			if i < len(cells) {
				cell = cells[i]
			}
			if i > 0 {
				b.WriteString("  ")
			}
			b.WriteString(cell)
			pad := w - runewidth.StringWidth(cell)
			if pad > 0 {
				b.WriteString(strings.Repeat(" ", pad))
			}
		}
		_, _ = fmt.Fprintln(u.w, b.String())
	}
	printRow(sanHeaders)
	sep := make([]string, len(sanHeaders))
	for i, w := range widths {
		sep[i] = strings.Repeat("─", w)
	}
	printRow(sep)
	for _, row := range sanRows {
		printRow(row)
	}
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
