package ui

import (
	"strings"
	"testing"
)

// hasANSI reports whether s contains ANSI escape sequences.
func hasANSI(s string) bool {
	return strings.Contains(s, "\x1b[")
}

func TestRenderHighlights_basic(t *testing.T) {
	body := strings.TrimSpace(`
### What you'll notice

- Update walks every release between installed and target.
- Press c to toggle between highlights and commit-based view.

### What's new

- Per-version Highlights view in synthorg update.

### Under the hood

- Bubbletea-based viewport for in-block scrolling.
`)
	opts := Options{NoColor: true}
	got := RenderHighlights(body, opts)

	for _, want := range []string{
		"What you'll notice",
		"What's new",
		"Under the hood",
		"Update walks every release between installed and target.",
		"Press c to toggle between highlights",
		"Bubbletea-based viewport",
	} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q\n--- got ---\n%s", want, got)
		}
	}
	// Bullets should be converted away from raw "- ".
	if strings.Contains(got, "\n- ") {
		t.Errorf("raw `- ` bullets should be replaced\n--- got ---\n%s", got)
	}
	// Section headers should be stripped of `### ` prefix.
	if strings.Contains(got, "### ") {
		t.Errorf("`### ` heading prefix should be stripped\n--- got ---\n%s", got)
	}
	// NoColor mode means no ANSI escape codes.
	if hasANSI(got) {
		t.Errorf("NoColor=true output should not contain ANSI codes")
	}
}

func TestRenderHighlights_colorMode(t *testing.T) {
	body := "### What's new\n\n- Bullet."
	opts := Options{}
	got := RenderHighlights(body, opts)
	if !hasANSI(got) {
		t.Errorf("color mode should emit ANSI escape codes\n--- got ---\n%s", got)
	}
	if !strings.Contains(got, "What's new") {
		t.Errorf("output should contain heading text")
	}
}

func TestRenderHighlights_plainMode(t *testing.T) {
	body := "### What's new\n\n- A bullet point."
	opts := Options{Plain: true}
	got := RenderHighlights(body, opts)
	if hasANSI(got) {
		t.Errorf("Plain mode should not emit ANSI codes")
	}
	// Plain mode uses ASCII bullet character or just text indent.
	if !strings.Contains(got, "A bullet point") {
		t.Errorf("plain output missing bullet text\n--- got ---\n%s", got)
	}
}

func TestRenderHighlights_stripsMarkdownLinks(t *testing.T) {
	body := "### What's new\n\n- See [the docs](https://example.com/docs) for details."
	opts := Options{NoColor: true}
	got := RenderHighlights(body, opts)
	if strings.Contains(got, "](https://") {
		t.Errorf("Markdown link syntax should be stripped or rewritten\n--- got ---\n%s", got)
	}
	if !strings.Contains(got, "the docs") {
		t.Errorf("link label should be preserved\n--- got ---\n%s", got)
	}
}

func TestRenderCommits_basic(t *testing.T) {
	body := strings.TrimSpace(`
## [0.7.3](https://github.com/Aureliolo/synthorg/compare/v0.7.2...v0.7.3) (2026-04-25)


### Features

* **cli:** per-version Highlights walk ([#1564](https://github.com/Aureliolo/synthorg/issues/1564)) ([abc1234](https://github.com/Aureliolo/synthorg/commit/abc1234abc1234abc1234abc1234abc1234abc12))
* **selfupdate:** harden pagination cap ([#1573](https://github.com/Aureliolo/synthorg/issues/1573)) ([fed9876](https://github.com/Aureliolo/synthorg/commit/fed9876fed9876fed9876fed9876fed9876fed98))


### Bug Fixes

* **web:** repair locale fallback ([#1577](https://github.com/Aureliolo/synthorg/issues/1577)) ([cba8765](https://github.com/Aureliolo/synthorg/commit/cba8765cba8765cba8765cba8765cba8765cba87))
`)
	opts := Options{NoColor: true}
	got := RenderCommits(body, opts)

	for _, want := range []string{
		"Features",
		"Bug Fixes",
		"per-version Highlights walk",
		"harden pagination cap",
		"repair locale fallback",
		"#1564",
		"#1573",
	} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q\n--- got ---\n%s", want, got)
		}
	}
	for _, omit := range []string{
		"## [0.7.3]", // version heading should be stripped
		"abc1234abc1234",
		"fed9876fed9876",
		"cba8765cba8765",
		"](https://github.com/Aureliolo/synthorg/commit/",
		"### Features", // raw markdown heading prefix stripped
	} {
		if strings.Contains(got, omit) {
			t.Errorf("output should not contain %q\n--- got ---\n%s", omit, got)
		}
	}
}

func TestRenderCommits_stripsBoldEmphasis(t *testing.T) {
	body := "### Features\n\n* **cli:** add toggle ([#1500](https://github.com/x/y/issues/1500)) ([abc1234](https://github.com/x/y/commit/abc1234abcdef0123456789abcdef0123456789ab))"
	opts := Options{NoColor: true}
	got := RenderCommits(body, opts)
	// Conventional-commit scope **cli:** should render readably -- either keep
	// it bold (color mode only) or strip the asterisks (NoColor / Plain).
	if strings.Contains(got, "**cli:**") {
		t.Errorf("raw markdown bold (`**...**`) should be stripped\n--- got ---\n%s", got)
	}
	if !strings.Contains(got, "cli") {
		t.Errorf("scope text should be preserved\n--- got ---\n%s", got)
	}
}

func TestRenderCommits_emptyBody(t *testing.T) {
	got := RenderCommits("", Options{NoColor: true})
	if strings.TrimSpace(got) != "" {
		t.Errorf("empty body should render empty, got %q", got)
	}
}

func TestRenderCommits_noPRReference(t *testing.T) {
	body := "### Maintenance\n\n* internal-only refactor without PR reference"
	opts := Options{NoColor: true}
	got := RenderCommits(body, opts)
	if !strings.Contains(got, "internal-only refactor without PR reference") {
		t.Errorf("missing bullet text\n--- got ---\n%s", got)
	}
}

func TestRenderFallbackNote_textPresent(t *testing.T) {
	for _, opts := range []Options{
		{},
		{NoColor: true},
		{Plain: true},
	} {
		got := RenderFallbackNote(opts)
		if !strings.Contains(got, "No AI highlights") {
			t.Errorf("opts %+v: fallback should mention 'No AI highlights', got %q", opts, got)
		}
	}
}

func TestRenderFallbackNote_plainNoANSI(t *testing.T) {
	got := RenderFallbackNote(Options{Plain: true})
	if hasANSI(got) {
		t.Errorf("Plain mode should not emit ANSI codes, got %q", got)
	}
}
