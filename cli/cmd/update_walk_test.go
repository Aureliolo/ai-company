package cmd

import (
	"bytes"
	"context"
	"strings"
	"testing"

	"github.com/spf13/cobra"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/selfupdate"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
)

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

func TestRunChangelogWalk_quietPrintsOfflineNotice(t *testing.T) {
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
