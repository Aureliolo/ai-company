// Package ui provides styled CLI output using lipgloss. It defines a
// writer-bound UI type with methods for rendering status lines (success, error,
// warning, step, hint), key-value pairs, boxes, inline spinners, and the
// SynthOrg Unicode logo with consistent colors and icons.
package ui

import (
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/charmbracelet/lipgloss"
	"github.com/mattn/go-isatty"
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
const IconSuccess = "\u2713"

// IconInProgress indicates an ongoing operation.
const IconInProgress = "\u25cf"

// IconWarning indicates a potential issue.
const IconWarning = "!"

// IconError indicates a failed operation.
const IconError = "\u2717"

// IconHint indicates a suggestion or next step.
const IconHint = "\u2192"

// UI provides styled CLI output bound to a specific writer.
// Binding to a writer (rather than defaulting to os.Stdout) enables
// testability and correct stderr/stdout separation in Cobra commands.
type UI struct {
	w         io.Writer
	isTTY     bool
	brand     lipgloss.Style
	brandBold lipgloss.Style
	success   lipgloss.Style
	warn      lipgloss.Style
	err       lipgloss.Style
	muted     lipgloss.Style
	label     lipgloss.Style
	bold      lipgloss.Style
}

// NewUI creates a UI bound to the given writer.
// The renderer auto-detects whether the writer is a terminal and adjusts
// color output accordingly (no ANSI codes when piped or redirected).
func NewUI(w io.Writer) *UI {
	r := lipgloss.NewRenderer(w)
	return &UI{
		w:         w,
		isTTY:     writerIsTTY(w),
		brand:     r.NewStyle().Foreground(colorBrand),
		brandBold: r.NewStyle().Foreground(colorBrand).Bold(true),
		success:   r.NewStyle().Foreground(colorSuccess),
		warn:      r.NewStyle().Foreground(colorWarn),
		err:       r.NewStyle().Foreground(colorError),
		muted:     r.NewStyle().Foreground(colorMuted),
		label:     r.NewStyle().Foreground(colorLabel),
		bold:      r.NewStyle().Bold(true),
	}
}

// Writer returns the underlying writer for direct output.
func (u *UI) Writer() io.Writer { return u.w }

// IsTTY reports whether the underlying writer is a terminal.
func (u *UI) IsTTY() bool { return u.isTTY }

// Logo renders the SynthOrg Unicode logo in brand color with a version tag.
func (u *UI) Logo(version string) {
	art := u.brandBold.Render(logo)
	ver := u.muted.Render(stripControl(version))
	_, _ = fmt.Fprintf(u.w, "%s  %s\n\n", art, ver)
}

// printLine prints a styled icon followed by a styled message.
func (u *UI) printLine(style lipgloss.Style, icon, msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", style.Render(icon), style.Render(stripControl(msg)))
}

// Step prints an in-progress status line (brand purple).
func (u *UI) Step(msg string) {
	_, _ = fmt.Fprintf(u.w, "%s %s\n", u.brand.Render(IconInProgress), u.bold.Render(stripControl(msg)))
}

// Success prints a success status line (green).
func (u *UI) Success(msg string) {
	u.printLine(u.success, IconSuccess, msg)
}

// Warn prints a warning status line (orange).
func (u *UI) Warn(msg string) {
	u.printLine(u.warn, IconWarning, msg)
}

// Error prints an error status line (red).
func (u *UI) Error(msg string) {
	u.printLine(u.err, IconError, msg)
}

// KeyValue prints a labeled key-value pair with indentation.
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

// Blank prints an empty line for visual separation.
func (u *UI) Blank() {
	_, _ = fmt.Fprintln(u.w)
}

// Plain prints an undecorated message (e.g. for passthrough output).
func (u *UI) Plain(msg string) {
	_, _ = fmt.Fprintln(u.w, stripControl(msg))
}

// Divider prints a horizontal rule for visual separation.
func (u *UI) Divider() {
	_, _ = fmt.Fprintln(u.w, u.muted.Render(strings.Repeat("\u2500", 40)))
}

// InlineKV prints compact inline key-value pairs on a single line.
// Pairs are given as alternating key, value strings.
// Example: InlineKV("Docker", "29.2.1 "+IconSuccess, "Compose", "5.1.0 "+IconSuccess)
func (u *UI) InlineKV(pairs ...string) {
	if len(pairs)%2 != 0 {
		pairs = pairs[:len(pairs)-1] // drop unpaired trailing key
	}
	var b strings.Builder
	b.WriteString("  ")
	for i := 0; i+1 < len(pairs); i += 2 {
		if i > 0 {
			b.WriteString("   ")
		}
		b.WriteString(u.label.Render(stripControl(pairs[i])))
		b.WriteString(" ")
		b.WriteString(stripControl(pairs[i+1]))
	}
	_, _ = fmt.Fprintln(u.w, b.String())
}

// SuccessIcon returns a styled green checkmark for embedding in strings.
func (u *UI) SuccessIcon() string { return u.success.Render(IconSuccess) }

// ErrorIcon returns a styled red cross for embedding in strings.
func (u *UI) ErrorIcon() string { return u.err.Render(IconError) }

// WarnIcon returns a styled orange exclamation for embedding in strings.
func (u *UI) WarnIcon() string { return u.warn.Render(IconWarning) }

// writerIsTTY reports whether w is a terminal file descriptor.
func writerIsTTY(w io.Writer) bool {
	f, ok := w.(*os.File)
	if !ok {
		return false
	}
	return isatty.IsTerminal(f.Fd()) || isatty.IsCygwinTerminal(f.Fd())
}

// Table prints rows as a fixed-width table with a header.
// All values are sanitized to prevent terminal control injection.
func (u *UI) Table(headers []string, rows [][]string) {
	if len(headers) == 0 {
		return
	}
	sanHeaders, sanRows := sanitizeTable(headers, rows)
	widths := calcColumnWidths(sanHeaders, sanRows)
	u.printTableRow(widths, sanHeaders)
	sep := make([]string, len(sanHeaders))
	for i, w := range widths {
		sep[i] = strings.Repeat("\u2500", w)
	}
	u.printTableRow(widths, sep)
	for _, row := range sanRows {
		u.printTableRow(widths, row)
	}
}

// sanitizeTable strips control chars and collapses whitespace in all cells.
func sanitizeTable(headers []string, rows [][]string) ([]string, [][]string) {
	sanitize := func(s string) string {
		s = stripControl(s)
		s = strings.ReplaceAll(s, "\n", " ")
		s = strings.ReplaceAll(s, "\t", " ")
		return s
	}
	sh := make([]string, len(headers))
	for i, h := range headers {
		sh[i] = sanitize(h)
	}
	sr := make([][]string, len(rows))
	for i, row := range rows {
		r := make([]string, len(row))
		for j, cell := range row {
			r[j] = sanitize(cell)
		}
		sr[i] = r
	}
	return sh, sr
}

// calcColumnWidths computes the maximum visual width per column.
func calcColumnWidths(headers []string, rows [][]string) []int {
	widths := make([]int, len(headers))
	for i, h := range headers {
		widths[i] = runewidth.StringWidth(h)
	}
	for _, row := range rows {
		for i := range widths {
			if i < len(row) {
				if w := runewidth.StringWidth(row[i]); w > widths[i] {
					widths[i] = w
				}
			}
		}
	}
	return widths
}

// printTableRow prints a single table row with aligned columns.
func (u *UI) printTableRow(widths []int, cells []string) {
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

// stripControl removes ASCII control characters (except tab and newline),
// DEL, and C1 control bytes (0x80-0x9F) to prevent terminal escape
// sequence injection in displayed values.
func stripControl(s string) string {
	return strings.Map(func(r rune) rune {
		if (r < 0x20 && r != '\t' && r != '\n') || r == 0x7F || (r >= 0x80 && r <= 0x9F) {
			return -1
		}
		return r
	}, s)
}

// stripControlStrict removes all ASCII control characters (< 0x20) including
// tab, newline, and ESC, plus DEL (0x7F) and C1 control bytes (0x80-0x9F).
// Use for single-line contexts (box content, spinner messages) where embedded
// newlines or tabs would corrupt layout.
func stripControlStrict(s string) string {
	return strings.Map(func(r rune) rune {
		if r < 0x20 || r == 0x7F || (r >= 0x80 && r <= 0x9F) {
			return -1
		}
		return r
	}, s)
}
