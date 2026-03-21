package ui

import (
	"fmt"
	"strings"

	"github.com/charmbracelet/lipgloss"
)

// Box draws a bordered box with a title integrated into the top border.
// Content lines are sanitized with stripControlStrict (all control chars
// removed, including ESC) -- pass plain text, not ANSI-styled strings.
//
//	+- Title -----------+
//	| line 1            |
//	| line 2            |
//	+-------------------+
func (u *UI) Box(title string, lines []string) {
	if len(lines) == 0 {
		return
	}

	safeTitle := stripControlStrict(title)
	titleW := lipgloss.Width(safeTitle)

	sanitized := make([]string, len(lines))
	for i, line := range lines {
		sanitized[i] = stripControlStrict(line)
	}

	maxContentW := 0
	for _, line := range sanitized {
		if w := lipgloss.Width(line); w > maxContentW {
			maxContentW = w
		}
	}

	innerW := max(maxContentW, titleW+2, 18)

	u.renderBoxTop(safeTitle, titleW, innerW)
	u.renderBoxContent(sanitized, innerW)
	u.renderBoxBottom(innerW)
}

// renderBoxTop prints the top border with an embedded title.
func (u *UI) renderBoxTop(title string, titleW, innerW int) {
	const (
		tl = "\u250c"
		tr = "\u2510"
		hz = "\u2500"
	)
	dashes := max(innerW-titleW, 1)
	top := fmt.Sprintf("  %s %s %s%s",
		u.muted.Render(tl),
		u.brandBold.Render(title),
		u.muted.Render(strings.Repeat(hz, dashes)),
		u.muted.Render(tr))
	_, _ = fmt.Fprintln(u.w, top)
}

// renderBoxContent prints the content lines with vertical borders.
func (u *UI) renderBoxContent(lines []string, innerW int) {
	const vt = "\u2502"
	for _, line := range lines {
		pad := max(innerW-lipgloss.Width(line), 0)
		_, _ = fmt.Fprintf(u.w, "  %s %s%s %s\n",
			u.muted.Render(vt), line,
			strings.Repeat(" ", pad), u.muted.Render(vt))
	}
}

// renderBoxBottom prints the bottom border.
func (u *UI) renderBoxBottom(innerW int) {
	const (
		bl = "\u2514"
		br = "\u2518"
		hz = "\u2500"
	)
	_, _ = fmt.Fprintf(u.w, "  %s%s\n",
		u.muted.Render(bl+strings.Repeat(hz, innerW+2)),
		u.muted.Render(br))
}
