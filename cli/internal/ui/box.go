package ui

import (
	"fmt"
	"strings"

	"charm.land/lipgloss/v2"
)

// Box draws a bordered box with a title integrated into the top border.
// Title, side and bottom borders are all rendered in the brandBold style
// so the chrome reads as a single semantic unit (consistent with
// BoxError/BoxWarn/BoxSuccess, which swap in err/warn/success styles).
// Content lines are sanitized with stripControlStrict (all control chars
// removed, including ESC) -- pass plain text, not ANSI-styled strings.
//
// In plain mode, uses ASCII borders (+, -, |).
// In quiet mode, suppressed entirely.
//
//	+- Title -----------+
//	| line 1            |
//	| line 2            |
//	+-------------------+
func (u *UI) Box(title string, lines []string) {
	u.boxWithTitleStyle(title, lines, u.brandBold)
}

// BoxError draws a bordered box with a red title (and red border in styled
// mode). Use for top-of-output critical banners where the box itself must
// scream "look here". Content lines are unstyled -- only the chrome turns
// red so longer multi-line bodies stay readable.
func (u *UI) BoxError(title string, lines []string) {
	u.boxWithTitleStyle(title, lines, u.err)
}

// BoxSuccess draws a bordered box with a green title. Pair with BoxError
// at the same call site so the visual weight matches.
func (u *UI) BoxSuccess(title string, lines []string) {
	u.boxWithTitleStyle(title, lines, u.success)
}

// BoxWarn draws a bordered box with an amber title. Use for the
// "degraded but reachable" middle state between BoxSuccess and BoxError.
func (u *UI) BoxWarn(title string, lines []string) {
	u.boxWithTitleStyle(title, lines, u.warn)
}

// boxWithTitleStyle is the shared implementation; titleStyle is applied to
// both the title text and the surrounding border so the box reads as a
// single semantic unit.
func (u *UI) boxWithTitleStyle(title string, lines []string, titleStyle lipgloss.Style) {
	if u.quiet {
		return
	}
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

	u.renderBoxTopStyled(safeTitle, titleW, innerW, titleStyle)
	u.renderBoxContentStyled(sanitized, innerW, titleStyle)
	u.renderBoxBottomStyled(innerW, titleStyle)
}

// renderBoxTop prints the top border with an embedded title.
func (u *UI) renderBoxTop(title string, titleW, innerW int) {
	u.renderBoxTopStyled(title, titleW, innerW, u.brandBold)
}

// renderBoxTopStyled prints the top border with the title rendered using
// the provided style. The corners and dashes use the same style so the
// chrome reads as a coloured frame rather than a single coloured word.
func (u *UI) renderBoxTopStyled(title string, titleW, innerW int, titleStyle lipgloss.Style) {
	dashes := max(innerW-titleW, 1)
	if u.plain {
		top := fmt.Sprintf("  + %s %s+", title, strings.Repeat("-", dashes))
		_, _ = fmt.Fprintln(u.w, top)
		return
	}
	const (
		tl = "\u256d" // rounded top-left ╭
		tr = "\u256e" // rounded top-right ╮
		hz = "\u2500"
	)
	top := fmt.Sprintf("  %s %s %s%s",
		titleStyle.Render(tl),
		titleStyle.Render(title),
		titleStyle.Render(strings.Repeat(hz, dashes)),
		titleStyle.Render(tr))
	_, _ = fmt.Fprintln(u.w, top)
}

// renderBoxContent prints the content lines with muted vertical borders.
// Not used by Box/BoxError/BoxWarn/BoxSuccess (those go through
// renderBoxContentStyled with the title's own style so the whole frame
// is one colour). Kept for any future callers that want muted sides
// against a coloured top.
func (u *UI) renderBoxContent(lines []string, innerW int) {
	u.renderBoxContentStyled(lines, innerW, u.muted)
}

// renderBoxContentStyled prints content lines with vertical borders drawn
// in the supplied style. Used by BoxError/BoxWarn/BoxSuccess so the whole
// frame (top, sides, bottom) reads as a single coloured unit rather than
// a red title on grey chrome.
func (u *UI) renderBoxContentStyled(lines []string, innerW int, borderStyle lipgloss.Style) {
	for _, line := range lines {
		pad := max(innerW-lipgloss.Width(line), 0)
		if u.plain {
			_, _ = fmt.Fprintf(u.w, "  | %s%s |\n", line, strings.Repeat(" ", pad))
		} else {
			const vt = "\u2502"
			_, _ = fmt.Fprintf(u.w, "  %s %s%s %s\n",
				borderStyle.Render(vt), line,
				strings.Repeat(" ", pad), borderStyle.Render(vt))
		}
	}
}

// renderBoxBottom prints the bottom border.
func (u *UI) renderBoxBottom(innerW int) {
	u.renderBoxBottomStyled(innerW, u.muted)
}

// renderBoxBottomStyled prints the bottom border using the supplied style.
func (u *UI) renderBoxBottomStyled(innerW int, style lipgloss.Style) {
	if u.plain {
		_, _ = fmt.Fprintf(u.w, "  +%s+\n", strings.Repeat("-", innerW+2))
		return
	}
	const (
		bl = "\u2570" // rounded bottom-left ╰
		br = "\u256f" // rounded bottom-right ╯
		hz = "\u2500"
	)
	_, _ = fmt.Fprintf(u.w, "  %s%s\n",
		style.Render(bl+strings.Repeat(hz, innerW+2)),
		style.Render(br))
}
