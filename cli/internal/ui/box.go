package ui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Box draws a bordered box with a title integrated into the top border.
// Lines may contain pre-rendered ANSI escape codes; visual width is
// measured via lipgloss.Width for correct padding.
//
//	+- Title -----------+
//	| line 1            |
//	| line 2            |
//	+-------------------+
func (u *UI) Box(title string, lines []string) {
	if len(lines) == 0 {
		return
	}

	// Sanitize lines: strip C0 control characters but preserve ANSI escape
	// codes (needed for pre-rendered styled content like colored icons).
	// Measure visual width via lipgloss.Width which handles ANSI correctly.
	sanitized := make([]string, len(lines))
	for i, line := range lines {
		sanitized[i] = stripControl(line)
	}

	titleW := lipgloss.Width(title)
	maxContentW := 0
	for _, line := range sanitized {
		if w := lipgloss.Width(line); w > maxContentW {
			maxContentW = w
		}
	}

	// Inner width = content area (between left padding and right padding).
	// Minimum: title + 2 (space after title + at least 1 dash before corner).
	innerW := max(maxContentW, titleW+2, 18)

	// Box-drawing characters.
	const (
		tl = "\u250c" // top-left corner
		tr = "\u2510" // top-right corner
		bl = "\u2514" // bottom-left corner
		br = "\u2518" // bottom-right corner
		hz = "\u2500" // horizontal line
		vt = "\u2502" // vertical line
	)

	// Top border: "  +- Title --...--+"
	dashesAfterTitle := max(innerW-titleW-1, 1) // -1 for the space after title
	top := fmt.Sprintf("  %s %s %s%s",
		u.muted.Render(tl),
		u.brandBold.Render(stripControl(title)),
		u.muted.Render(strings.Repeat(hz, dashesAfterTitle)),
		u.muted.Render(tr))
	_, _ = fmt.Fprintln(u.w, top)

	// Content lines: "  | content        |"
	for _, line := range sanitized {
		contentW := lipgloss.Width(line)
		pad := max(innerW-contentW, 0)
		_, _ = fmt.Fprintf(u.w, "  %s %s%s %s\n",
			u.muted.Render(vt),
			line,
			strings.Repeat(" ", pad),
			u.muted.Render(vt))
	}

	// Bottom border: "  +---...---+"
	_, _ = fmt.Fprintf(u.w, "  %s%s\n",
		u.muted.Render(bl+strings.Repeat(hz, innerW+2)),
		u.muted.Render(br))
}
