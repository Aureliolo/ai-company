package ui

import (
	"strings"
	"testing"

	"github.com/Aureliolo/synthorg/cli/internal/selfupdate"
)

func sampleRange() selfupdate.CommitRange {
	return selfupdate.CommitRange{
		TotalCommits: 3,
		Commits: []selfupdate.Commit{
			{
				SHA:     "abc1234567890abcdef0123456789abcdef01234",
				Subject: "feat(cli): per-version Highlights walk",
				Author:  "Daisy",
				Date:    "2026-04-25",
				URL:     "https://github.com/x/y/commit/abc1234",
			},
			{
				SHA:     "def4567890abcdef1234567890abcdef12345678",
				Subject: "fix(selfupdate): pagination cap",
				Author:  "Bob",
				Date:    "2026-04-26",
			},
			{
				SHA:     "ff0000aabbccddeeff00112233445566778899aa",
				Subject: "chore(deps): bump",
				Author:  "renovate[bot]",
				Date:    "2026-04-27",
			},
		},
	}
}

func TestRenderCommitList_basic(t *testing.T) {
	r := sampleRange()
	got := RenderCommitList(r, 100, Options{NoColor: true})
	for _, want := range []string{
		"abc1234",
		"def4567",
		"ff0000a",
		"feat(cli): per-version Highlights walk",
		"fix(selfupdate): pagination cap",
		"chore(deps): bump",
		"Daisy",
		"renovate[bot]",
		"2026-04-25",
		"2026-04-27",
	} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q\n--- got ---\n%s", want, got)
		}
	}
	// Full SHAs should not appear (only short prefix).
	if strings.Contains(got, "abc1234567890") {
		t.Errorf("full SHA leaked, want sha7\n--- got ---\n%s", got)
	}
}

func TestRenderCommitList_truncationFooter(t *testing.T) {
	r := sampleRange()
	r.TotalCommits = 320
	// Pad commits to mirror the API cap exactly (250).
	for len(r.Commits) < 250 {
		r.Commits = append(r.Commits, selfupdate.Commit{
			SHA:     "0000000000000000000000000000000000000000",
			Subject: "padding",
			Author:  "tester",
			Date:    "2026-04-25",
		})
	}
	got := RenderCommitList(r, 100, Options{NoColor: true})
	if !strings.Contains(got, "250") || !strings.Contains(got, "320") {
		t.Errorf("truncation footer should mention 250 of 320\n--- got ---\n%s", got)
	}
}

func TestRenderCommitList_noTruncationFooterWhenInRange(t *testing.T) {
	r := sampleRange() // 3 commits total, 3 returned
	got := RenderCommitList(r, 100, Options{NoColor: true})
	if strings.Contains(got, " of ") {
		t.Errorf("no truncation footer expected when len(Commits) == TotalCommits\n--- got ---\n%s", got)
	}
}

func TestRenderCommitList_emptyRange(t *testing.T) {
	r := selfupdate.CommitRange{TotalCommits: 0}
	got := RenderCommitList(r, 100, Options{NoColor: true})
	if !strings.Contains(got, "no commits") {
		t.Errorf("empty range should say 'no commits', got %q", got)
	}
}

func TestRenderCommitList_longSubjectTruncation(t *testing.T) {
	r := selfupdate.CommitRange{
		TotalCommits: 1,
		Commits: []selfupdate.Commit{{
			SHA:     "deadbeefcafebabe1234567890abcdef12345678",
			Subject: strings.Repeat("very long subject line ", 20),
			Author:  "tester",
			Date:    "2026-04-25",
		}},
	}
	width := 60
	got := RenderCommitList(r, width, Options{NoColor: true})
	for line := range strings.SplitSeq(got, "\n") {
		if l := len(line); l > width+5 { // small slack for ANSI-stripped width fudge factor
			t.Errorf("line exceeds width %d: len=%d %q", width, l, line)
		}
	}
}

func TestRenderCommitList_plainMode(t *testing.T) {
	r := sampleRange()
	got := RenderCommitList(r, 100, Options{Plain: true})
	if hasANSI(got) {
		t.Errorf("Plain mode should not emit ANSI codes\n--- got ---\n%s", got)
	}
	if strings.Contains(got, "…") {
		t.Errorf("Plain mode should use ASCII '...' not Unicode ellipsis\n--- got ---\n%s", got)
	}
}

func TestRenderCommitList_colorMode(t *testing.T) {
	r := sampleRange()
	got := RenderCommitList(r, 100, Options{})
	if !hasANSI(got) {
		t.Errorf("color mode should emit ANSI codes\n--- got ---\n%s", got)
	}
}

func TestRenderCommitList_stripsEmbeddedANSIFromCommitFields(t *testing.T) {
	r := selfupdate.CommitRange{
		TotalCommits: 1,
		Commits: []selfupdate.Commit{{
			SHA:     "abc1234567890abcdef0123456789abcdef01234",
			Subject: "\x1b[31mfake-warning\x1b[0m: actual subject",
			Author:  "\x1b[32mevil-author\x1b[0m",
			Date:    "2026-04-25",
		}},
	}
	got := RenderCommitList(r, 120, Options{NoColor: true})
	if strings.Contains(got, "\x1b[31m") || strings.Contains(got, "\x1b[32m") || strings.Contains(got, "\x1b[0m") {
		t.Errorf("RenderCommitList leaked attacker-controlled ANSI escape\n--- got ---\n%q", got)
	}
	for _, want := range []string{"fake-warning", "actual subject", "evil-author", "2026-04-25"} {
		if !strings.Contains(got, want) {
			t.Errorf("text should be preserved (%q)\n--- got ---\n%s", want, got)
		}
	}
}
