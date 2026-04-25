package ui

import (
	"regexp"
	"strings"

	"charm.land/lipgloss/v2"
)

// changelogStyle is a small palette built from the package-level color
// constants. Captured per-call so the same renderer respects opts.NoColor /
// opts.Plain consistently.
type changelogStyle struct {
	highlightHeader lipgloss.Style // ### What's new (sky blue, bold)
	commitHeader    lipgloss.Style // ### Features (indigo, bold)
	muted           lipgloss.Style // dim attribution / fallback note
	bullet          string         // "•" or "-"
	indent          string         // "  "
}

func newChangelogStyle(opts Options) changelogStyle {
	plain := opts.NoColor || opts.Plain
	bullet := "•"
	if opts.Plain {
		bullet = "-"
	}

	highlightHeader := lipgloss.NewStyle()
	commitHeader := lipgloss.NewStyle()
	muted := lipgloss.NewStyle()
	if !plain {
		highlightHeader = highlightHeader.Foreground(colorLabel).Bold(true)
		commitHeader = commitHeader.Foreground(colorBrand).Bold(true)
		muted = muted.Foreground(colorMuted)
	}
	return changelogStyle{
		highlightHeader: highlightHeader,
		commitHeader:    commitHeader,
		muted:           muted,
		bullet:          bullet,
		indent:          "  ",
	}
}

// markdownLinkRe matches `[label](url)` and is used to flatten links to plain
// text. Captures the label.
var markdownLinkRe = regexp.MustCompile(`\[([^\]]+)\]\(([^)]+)\)`)

// commitHashLinkRe matches the trailing commit-hash link Release Please emits:
// "([abc1234](https://github.com/.../commit/abc1234...))". Stripped from
// commit-based output to reduce noise in the walk.
var commitHashLinkRe = regexp.MustCompile(`\s*\(\[[0-9a-f]{7,40}\]\([^)]+\)\)`)

// boldEmphasisRe matches `**text**` and captures the inner text. Used to
// strip Markdown bold from commit subjects in NoColor / Plain mode.
var boldEmphasisRe = regexp.MustCompile(`\*\*([^*]+)\*\*`)

// RenderHighlights formats the styled-block content of a release Highlights
// section. body is expected to be the output of selfupdate.ExtractHighlights,
// already stripped of markers / "## Highlights" / attribution.
func RenderHighlights(body string, opts Options) string {
	st := newChangelogStyle(opts)
	body = strings.ReplaceAll(body, "\r\n", "\n")
	lines := strings.Split(body, "\n")
	var out strings.Builder
	for _, line := range lines {
		out.WriteString(formatHighlightLine(line, st))
		out.WriteByte('\n')
	}
	return strings.TrimRight(out.String(), "\n")
}

// formatHighlightLine handles a single line in the highlights body. Returns
// the styled line (no trailing newline).
func formatHighlightLine(line string, st changelogStyle) string {
	trimmed := strings.TrimSpace(line)
	if trimmed == "" {
		return ""
	}
	if rest, ok := strings.CutPrefix(trimmed, "### "); ok {
		return st.highlightHeader.Render(strings.TrimSpace(rest))
	}
	if rest, ok := bulletPayload(trimmed); ok {
		return st.indent + st.bullet + " " + flattenInline(rest)
	}
	// Anything else: attribution blockquote (`> _...`) or stray text.
	if rest, ok := strings.CutPrefix(trimmed, ">"); ok {
		blockquote := strings.TrimSpace(strings.Trim(rest, "_"))
		return st.muted.Render(st.indent + blockquote)
	}
	return st.indent + flattenInline(trimmed)
}

// RenderCommits formats the commit-based changelog of a release. body is
// expected to be the output of selfupdate.ExtractCommits.
func RenderCommits(body string, opts Options) string {
	st := newChangelogStyle(opts)
	body = strings.ReplaceAll(body, "\r\n", "\n")
	lines := strings.Split(body, "\n")
	var out strings.Builder
	for _, line := range lines {
		rendered, keep := formatCommitLine(line, st)
		if !keep {
			continue
		}
		out.WriteString(rendered)
		out.WriteByte('\n')
	}
	return strings.TrimRight(out.String(), "\n")
}

// formatCommitLine returns the styled line and a keep flag. Lines like the
// release-please version heading ("## [0.7.3]...") are dropped because the
// walk renders its own version separator above the block.
func formatCommitLine(line string, st changelogStyle) (string, bool) {
	trimmed := strings.TrimSpace(line)
	if trimmed == "" {
		return "", false
	}
	// Drop release-please version heading.
	if strings.HasPrefix(trimmed, "## [") || strings.HasPrefix(trimmed, "## ") {
		return "", false
	}
	if rest, ok := strings.CutPrefix(trimmed, "### "); ok {
		return st.commitHeader.Render(strings.TrimSpace(rest)), true
	}
	if rest, ok := bulletPayload(trimmed); ok {
		return st.indent + st.bullet + " " + flattenCommitInline(rest), true
	}
	return st.indent + flattenCommitInline(trimmed), true
}

// bulletPayload reports whether line starts with a Markdown bullet ("- " or
// "* ") and returns the payload after the bullet marker.
func bulletPayload(line string) (string, bool) {
	if rest, ok := strings.CutPrefix(line, "- "); ok {
		return rest, true
	}
	if rest, ok := strings.CutPrefix(line, "* "); ok {
		return rest, true
	}
	return "", false
}

// flattenInline rewrites Markdown links `[label](url)` to "label" and strips
// `**bold**` markers. Used for highlight bullets where we want a clean
// single-line read.
func flattenInline(s string) string {
	s = markdownLinkRe.ReplaceAllString(s, "$1")
	s = boldEmphasisRe.ReplaceAllString(s, "$1")
	return s
}

// flattenCommitInline rewrites a release-please commit line. Specifically:
//   - Drops the trailing `([sha7](url))` commit-hash link (noise in the walk).
//   - Rewrites issue/PR links `[#1234](url)` to "#1234".
//   - Drops the leading `**scope:**` Markdown bold markers (we keep the scope
//     text but render it readably without asterisks; lipgloss can't apply
//     mid-line bold here without parsing the full Markdown stream).
func flattenCommitInline(s string) string {
	s = commitHashLinkRe.ReplaceAllString(s, "")
	s = markdownLinkRe.ReplaceAllString(s, "$1")
	s = boldEmphasisRe.ReplaceAllString(s, "$1")
	return strings.TrimSpace(s)
}

// RenderFallbackNote returns the dimmed status line shown for versions that
// have no Highlights block (pre-#1555 releases or No-Highlights opt-out).
func RenderFallbackNote(opts Options) string {
	st := newChangelogStyle(opts)
	const text = "No AI highlights -- showing commit log"
	return st.muted.Render(text)
}
