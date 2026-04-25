package cmd

import (
	"bytes"
	"context"
	"errors"
	"strings"
	"testing"

	"github.com/spf13/cobra"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/selfupdate"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
)

// withReleasesBetween installs a stub for the package-level releasesBetween
// var and restores the real GitHub-API-backed implementation on cleanup.
// Tests use it to drive runStableHighlightsWalk down its error and empty
// branches without spinning up a fake server.
func withReleasesBetween(t *testing.T, stub func(ctx context.Context, installed, target string, includeDev bool) ([]selfupdate.Release, error)) {
	t.Helper()
	prev := releasesBetween
	releasesBetween = stub
	t.Cleanup(func() { releasesBetween = prev })
}

// withCommitsBetween is the runDevCommitWalk counterpart of
// withReleasesBetween.
func withCommitsBetween(t *testing.T, stub func(ctx context.Context, base, head string) (selfupdate.CommitRange, error)) {
	t.Helper()
	prev := commitsBetween
	commitsBetween = stub
	t.Cleanup(func() { commitsBetween = prev })
}

// newWalkTestCmd returns a cobra.Command with a captured stdout/stderr
// buffer and a non-prompting GlobalOpts that still carries Hints=always so
// HintError lines render. Used by walk error-branch tests.
func newWalkTestCmd(t *testing.T) (*cobra.Command, *bytes.Buffer) {
	t.Helper()
	cmd := &cobra.Command{}
	var buf bytes.Buffer
	cmd.SetOut(&buf)
	cmd.SetErr(&buf)
	// Yes:true skips bubbletea (the real walk would deadlock without a TTY)
	// while still letting Warn / HintError render to the captured writer.
	cmd.SetContext(SetGlobalOpts(context.Background(), &GlobalOpts{Yes: true, Hints: "always"}))
	return cmd, &buf
}

// requireContains fails the test if any expected substring is missing from
// got. It is a small helper because every walk-error test asserts the same
// shape -- "warn line mentions versions, HintError mentions reason".
func requireContains(t *testing.T, got string, wants ...string) {
	t.Helper()
	for _, w := range wants {
		if !strings.Contains(got, w) {
			t.Errorf("expected output to contain %q\n--- got ---\n%s", w, got)
		}
	}
}

func TestBatchReleases(t *testing.T) {
	tests := []struct {
		name      string
		count     int
		size      int
		wantSizes []int
	}{
		{"three_in_one_batch", 3, 3, []int{3}},
		{"four_split_3_1", 4, 3, []int{3, 1}},
		{"seven_split_3_3_1", 7, 3, []int{3, 3, 1}},
		{"empty", 0, 3, nil},
		{"single", 1, 3, []int{1}},
		{"zero_size", 5, 0, nil},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			rels := make([]selfupdate.Release, tt.count)
			for i := range rels {
				rels[i].TagName = "v0.7." + string(rune('0'+i))
			}
			got := batchReleases(rels, tt.size)
			if len(got) != len(tt.wantSizes) {
				t.Fatalf("got %d batches, want %d (sizes %v)", len(got), len(tt.wantSizes), tt.wantSizes)
			}
			for i, want := range tt.wantSizes {
				if len(got[i]) != want {
					t.Errorf("batch %d size = %d, want %d", i, len(got[i]), want)
				}
			}
		})
	}
}

func TestFormatPublishedDate(t *testing.T) {
	tests := []struct {
		in, want string
	}{
		{"2026-04-25T12:00:00Z", "2026-04-25"},
		{"2026-04-25T23:59:59-05:00", "2026-04-26"}, // UTC normalization
		{"", ""},
		{"not-a-date", "not-a-date"},
	}
	for _, tt := range tests {
		t.Run(tt.in, func(t *testing.T) {
			if got := formatPublishedDate(tt.in); got != tt.want {
				t.Errorf("formatPublishedDate(%q) = %q, want %q", tt.in, got, tt.want)
			}
		})
	}
}

func TestNormalizeVersionRef(t *testing.T) {
	tests := []struct{ in, want string }{
		{"0.7.3-dev.11", "v0.7.3-dev.11"},
		{"v0.7.3-dev.11", "v0.7.3-dev.11"},
		{"0.7.5", "v0.7.5"},
		{"v0.7.5", "v0.7.5"},
		{"", ""},
	}
	for _, tt := range tests {
		t.Run(tt.in, func(t *testing.T) {
			if got := normalizeVersionRef(tt.in); got != tt.want {
				t.Errorf("normalizeVersionRef(%q) = %q, want %q", tt.in, got, tt.want)
			}
		})
	}
}

func TestPluralS(t *testing.T) {
	if got := pluralS(1); got != "" {
		t.Errorf("pluralS(1) = %q, want \"\"", got)
	}
	if got := pluralS(0); got != "s" {
		t.Errorf("pluralS(0) = %q, want \"s\"", got)
	}
	if got := pluralS(5); got != "s" {
		t.Errorf("pluralS(5) = %q, want \"s\"", got)
	}
}

func TestPrintOfflineNotice(t *testing.T) {
	cmd := &cobra.Command{}
	cmd.SetContext(SetGlobalOpts(context.Background(), &GlobalOpts{Hints: "always"}))
	var buf bytes.Buffer
	cmd.SetOut(&buf)

	result := selfupdate.CheckResult{
		CurrentVersion: "v0.7.1",
		LatestVersion:  "v0.7.5",
	}
	printOfflineNotice(cmd, result)
	out := buf.String()
	if !strings.Contains(out, "v0.7.5") {
		t.Errorf("offline notice should contain target version\n--- got ---\n%s", out)
	}
	if !strings.Contains(out, "v0.7.1") {
		t.Errorf("offline notice should contain current version\n--- got ---\n%s", out)
	}
	if !strings.Contains(out, "/releases/tag/v0.7.5") {
		t.Errorf("offline notice should contain release URL\n--- got ---\n%s", out)
	}
}

func TestShouldShowWalk_quietSuppresses(t *testing.T) {
	cmd := &cobra.Command{}
	cmd.SetContext(SetGlobalOpts(context.Background(), &GlobalOpts{Quiet: true}))
	if shouldShowWalk(cmd) {
		t.Error("--quiet should suppress walk")
	}
}

func TestShouldShowWalk_jsonSuppresses(t *testing.T) {
	cmd := &cobra.Command{}
	cmd.SetContext(SetGlobalOpts(context.Background(), &GlobalOpts{JSON: true}))
	if shouldShowWalk(cmd) {
		t.Error("--json should suppress walk")
	}
}

func TestShouldShowWalk_yesSuppresses(t *testing.T) {
	cmd := &cobra.Command{}
	cmd.SetContext(SetGlobalOpts(context.Background(), &GlobalOpts{Yes: true}))
	if shouldShowWalk(cmd) {
		t.Error("--yes should suppress walk")
	}
}

func TestShouldShowWalk_nonTTYSuppresses(t *testing.T) {
	cmd := &cobra.Command{}
	// Set a non-TTY writer (bytes.Buffer is not a *os.File). Even if stdin
	// is a TTY in the test runner, stdout is not, so the walk must not run.
	cmd.SetOut(&bytes.Buffer{})
	cmd.SetContext(SetGlobalOpts(context.Background(), &GlobalOpts{}))
	if shouldShowWalk(cmd) {
		t.Error("non-TTY stdout should suppress walk")
	}
}

func TestPrintWalkSummary_listsAllVersions(t *testing.T) {
	out := ui.NewUIWithOptions(&bytes.Buffer{}, ui.Options{NoColor: true})
	releases := []selfupdate.Release{
		{TagName: "v0.7.2", PublishedAt: "2026-04-22T10:00:00Z", Body: "## [0.7.2]\n### Features\n* x\n---\n"},
		{TagName: "v0.7.3", PublishedAt: "2026-04-25T12:00:00Z", Body: "<!-- HIGHLIGHTS_START -->\n## Highlights\n\n### What's new\n- Bullet\n\n<!-- HIGHLIGHTS_END -->\n## [0.7.3]\n### Features\n* y\n---\n"},
	}
	result := selfupdate.CheckResult{CurrentVersion: "v0.7.1", LatestVersion: "v0.7.3"}

	// Capture writer used by the ui.UI directly so we can inspect output.
	var buf bytes.Buffer
	out2 := ui.NewUIWithOptions(&buf, ui.Options{NoColor: true})
	_ = out
	printWalkSummary(out2, releases, result)
	got := buf.String()
	for _, want := range []string{
		"Walking 2 releases",
		"v0.7.1",
		"v0.7.3",
		"v0.7.2",
		"2026-04-22",
		"2026-04-25",
		"Highlights",
		"commit-based",
	} {
		if !strings.Contains(got, want) {
			t.Errorf("summary missing %q\n--- got ---\n%s", want, got)
		}
	}
}

func TestRunStableHighlightsWalk_warnsOnReleasesBetweenError(t *testing.T) {
	withReleasesBetween(t, func(_ context.Context, _, _ string, _ bool) ([]selfupdate.Release, error) {
		return nil, errors.New("simulated GitHub 503")
	})
	cmd, buf := newWalkTestCmd(t)
	result := selfupdate.CheckResult{CurrentVersion: "v0.7.1", LatestVersion: "v0.7.5"}
	state := config.DefaultState()

	runStableHighlightsWalk(cmd.Context(), cmd, result, state)

	got := buf.String()
	requireContains(t, got,
		"Could not load release list",
		"v0.7.1..v0.7.5",
		"simulated GitHub 503",
		"Showing terse update notice",
		"New version available: v0.7.5",
	)
}

func TestRunStableHighlightsWalk_warnsOnEmptyRange(t *testing.T) {
	withReleasesBetween(t, func(_ context.Context, _, _ string, _ bool) ([]selfupdate.Release, error) {
		return nil, nil
	})
	cmd, buf := newWalkTestCmd(t)
	result := selfupdate.CheckResult{CurrentVersion: "v0.7.4", LatestVersion: "v0.7.5"}
	state := config.DefaultState()

	runStableHighlightsWalk(cmd.Context(), cmd, result, state)

	got := buf.String()
	requireContains(t, got,
		"No releases found strictly between",
		"v0.7.4",
		"v0.7.5",
		"check the GitHub releases page",
		"New version available: v0.7.5",
	)
}

func TestRunDevCommitWalk_warnsOnCompareError(t *testing.T) {
	withCommitsBetween(t, func(_ context.Context, _, _ string) (selfupdate.CommitRange, error) {
		return selfupdate.CommitRange{}, errors.New("404 Not Found")
	})
	cmd, buf := newWalkTestCmd(t)
	// The reproduction case from the user report: installed version stamped
	// without "v" prefix, target with "v". The walk must normalise both to
	// "v0.7.3-dev.11..v0.7.3-dev.19" before passing to commitsBetween.
	result := selfupdate.CheckResult{CurrentVersion: "0.7.3-dev.11", LatestVersion: "v0.7.3-dev.19"}

	runDevCommitWalk(cmd.Context(), cmd, result)

	got := buf.String()
	requireContains(t, got,
		"Could not fetch commit list",
		"v0.7.3-dev.11..v0.7.3-dev.19",
		"404 Not Found",
		"installed dev pre-release tag was pruned",
		"New version available: v0.7.3-dev.19",
	)
}

func TestRunDevCommitWalk_warnsOnEmptyRange(t *testing.T) {
	withCommitsBetween(t, func(_ context.Context, _, _ string) (selfupdate.CommitRange, error) {
		return selfupdate.CommitRange{Commits: nil, TotalCommits: 0}, nil
	})
	cmd, buf := newWalkTestCmd(t)
	result := selfupdate.CheckResult{CurrentVersion: "v0.7.3-dev.18", LatestVersion: "v0.7.3-dev.19"}

	runDevCommitWalk(cmd.Context(), cmd, result)

	got := buf.String()
	requireContains(t, got,
		"GitHub returned 0 commits",
		"v0.7.3-dev.18",
		"v0.7.3-dev.19",
		"New version available: v0.7.3-dev.19",
	)
}

// TestRunDevCommitWalk_normalisesVersionRefs is the regression guard for
// the original user report: a dev-channel installed version stamped without
// the "v" prefix MUST be normalised to "vX.Y.Z-dev.N" before reaching
// commitsBetween, otherwise GitHub's compare API returns 404 for every
// invocation.
func TestRunDevCommitWalk_normalisesVersionRefs(t *testing.T) {
	var seenBase, seenHead string
	withCommitsBetween(t, func(_ context.Context, base, head string) (selfupdate.CommitRange, error) {
		seenBase, seenHead = base, head
		return selfupdate.CommitRange{}, errors.New("stop here")
	})
	cmd, _ := newWalkTestCmd(t)
	result := selfupdate.CheckResult{CurrentVersion: "0.7.3-dev.11", LatestVersion: "0.7.3-dev.19"}

	runDevCommitWalk(cmd.Context(), cmd, result)

	if seenBase != "v0.7.3-dev.11" {
		t.Errorf("base passed to commitsBetween = %q, want %q", seenBase, "v0.7.3-dev.11")
	}
	if seenHead != "v0.7.3-dev.19" {
		t.Errorf("head passed to commitsBetween = %q, want %q", seenHead, "v0.7.3-dev.19")
	}
}

func TestRunChangelogWalk_jsonSuppressesOutput(t *testing.T) {
	cmd := &cobra.Command{}
	cmd.SetContext(SetGlobalOpts(context.Background(), &GlobalOpts{Quiet: false, JSON: true})) // JSON suppresses walk
	var buf bytes.Buffer
	cmd.SetOut(&buf)
	cmd.SetErr(&buf)
	result := selfupdate.CheckResult{CurrentVersion: "v0.7.1", LatestVersion: "v0.7.5"}
	state := config.DefaultState()

	runChangelogWalk(cmd.Context(), cmd, result, state)
	got := buf.String()
	// JSON mode suppresses the walk and any human-readable offline notice.
	// Asserting "no output" -- not just "no panic" -- is what guards against
	// regressions that re-introduce stdout writes in JSON-mode update flows.
	if strings.TrimSpace(got) != "" {
		t.Errorf("expected no output in JSON mode\n--- got ---\n%s", got)
	}
}
