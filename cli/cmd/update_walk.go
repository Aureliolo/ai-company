package cmd

import (
	"context"
	"fmt"
	"io"
	"os"
	"strings"
	"time"

	"github.com/mattn/go-isatty"
	"github.com/spf13/cobra"
	"golang.org/x/term"

	"github.com/Aureliolo/synthorg/cli/internal/config"
	"github.com/Aureliolo/synthorg/cli/internal/selfupdate"
	"github.com/Aureliolo/synthorg/cli/internal/ui"
	"github.com/Aureliolo/synthorg/cli/internal/version"
)

// walkBatchSize is the number of versions shown per bubbletea program in the
// stable-channel per-release walk. Picked so a typical 80x24 terminal can
// fit one block plus the key footer without forcing scroll.
const walkBatchSize = 3

// runChangelogWalk renders the per-release Highlights walk (stable channel)
// or the combined commit-list view (dev channel) before the install confirm
// prompt in updateCLI. The walk is informational and never blocks the
// update; any failure falls back to a terse "Update available" notice.
//
// Gating: walk is skipped entirely in non-interactive contexts (--yes,
// --quiet, --json, non-TTY stdin or stdout). The single-line fallback is
// printed in those cases so the user still sees the version jump.
func runChangelogWalk(ctx context.Context, cmd *cobra.Command, result selfupdate.CheckResult, state config.State) {
	if !shouldShowWalk(cmd) {
		printOfflineNotice(cmd, result)
		return
	}

	if state.Channel == "dev" {
		runDevCommitWalk(ctx, cmd, result)
		return
	}

	runStableHighlightsWalk(ctx, cmd, result, state)
}

// runStableHighlightsWalk fetches every release in (installed, target] and
// renders them oldest-to-newest in batches of walkBatchSize using the
// per-release Highlights walk Model.
func runStableHighlightsWalk(ctx context.Context, cmd *cobra.Command, result selfupdate.CheckResult, state config.State) {
	opts := GetGlobalOpts(ctx)
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())

	releases, err := selfupdate.ReleasesBetween(ctx, result.CurrentVersion, result.LatestVersion, false)
	if err != nil {
		printOfflineNotice(cmd, result)
		return
	}
	if len(releases) == 0 {
		// Nothing strictly between installed and target. Fall through to
		// the existing one-line notice so the user still sees the jump.
		printOfflineNotice(cmd, result)
		return
	}

	printWalkSummary(out, releases, result)
	if !confirmStartWalk(opts) {
		return
	}

	width, height := terminalSize(cmd)
	view := state.ChangelogViewOrDefault()
	batches := batchReleases(releases, walkBatchSize)
	for batchIdx, batch := range batches {
		isFinal := batchIdx == len(batches)-1
		batchResult, err := ui.RunWalkBatch(ctx, ui.WalkBatchInput{
			Versions:     batch,
			InitialView:  view,
			IsFinalBatch: isFinal,
			Width:        width,
			Height:       height,
			Options:      opts.UIOptions(),
			Output:       cmd.OutOrStdout(),
		})
		if err != nil {
			out.Warn(fmt.Sprintf("walk batch %d: %v", batchIdx, err))
			return
		}
		if batchResult.Outcome == ui.WalkOutcomeQuit {
			return
		}
		view = batchResult.FinalView
		if !isFinal {
			out.Blank()
		}
	}
}

// runDevCommitWalk fetches all commits between the installed and target dev
// (or stable) tag via the GitHub compare API and renders them in a single
// scrollable bubbletea program. Dev pre-releases have no Highlights blocks,
// so a per-release walk is uninformative -- a flat commit list is what the
// user actually wants to see.
func runDevCommitWalk(ctx context.Context, cmd *cobra.Command, result selfupdate.CheckResult) {
	opts := GetGlobalOpts(ctx)
	commitRange, err := selfupdate.CommitsBetween(ctx, result.CurrentVersion, result.LatestVersion)
	if err != nil {
		printOfflineNotice(cmd, result)
		return
	}
	width, height := terminalSize(cmd)
	if _, err := ui.RunCommitWalk(ctx, ui.CommitWalkInput{
		Installed: result.CurrentVersion,
		Target:    result.LatestVersion,
		Commits:   commitRange,
		Width:     width,
		Height:    height,
		Options:   opts.UIOptions(),
		Output:    cmd.OutOrStdout(),
	}); err != nil {
		out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())
		out.Warn(fmt.Sprintf("commit walk: %v", err))
	}
}

// shouldShowWalk reports whether the walk UI should run for this invocation.
// Bubbletea requires both stdin and stdout to be a TTY; --yes / --quiet /
// --json all suppress the walk.
func shouldShowWalk(cmd *cobra.Command) bool {
	opts := GetGlobalOpts(cmd.Context())
	if opts.Quiet || opts.JSON || opts.Yes {
		return false
	}
	if !opts.ShouldPrompt() {
		return false
	}
	return writerIsTTY(cmd.OutOrStdout())
}

// writerIsTTY reports whether w is a terminal file descriptor.
func writerIsTTY(w io.Writer) bool {
	f, ok := w.(*os.File)
	if !ok {
		return false
	}
	return isatty.IsTerminal(f.Fd()) || isatty.IsCygwinTerminal(f.Fd())
}

// terminalSize returns the (width, height) of the terminal attached to
// cmd's output. Falls back to (80, 24) when the size cannot be determined.
func terminalSize(cmd *cobra.Command) (int, int) {
	if f, ok := cmd.OutOrStdout().(*os.File); ok {
		if w, h, err := term.GetSize(int(f.Fd())); err == nil && w > 0 && h > 0 {
			return w, h
		}
	}
	return 80, 24
}

// printWalkSummary prints a one-line summary above the walk so the user
// sees what they are about to walk through. The bubbletea Model handles
// the per-version layout; this is plain UI output.
func printWalkSummary(out *ui.UI, releases []selfupdate.Release, result selfupdate.CheckResult) {
	out.Section(fmt.Sprintf("Walking %d release%s: %s -> %s",
		len(releases), pluralS(len(releases)),
		result.CurrentVersion, result.LatestVersion,
	))
	for _, r := range releases {
		_, hasHighlights := selfupdate.ExtractHighlights(r.Body)
		marker := "commit-based"
		if hasHighlights {
			marker = "Highlights"
		}
		out.KeyValue(r.TagName, fmt.Sprintf("%s   %s", formatPublishedDate(r.PublishedAt), marker))
	}
	out.Blank()
}

// confirmStartWalk asks the user (interactively) to start the walk. Returns
// false to abort; non-interactive paths (Yes, no TTY) never reach this code.
func confirmStartWalk(opts *GlobalOpts) bool {
	// In non-prompting modes (Yes, no TTY) shouldShowWalk would have already
	// returned false before reaching here. Belt-and-braces: skip the prompt
	// if for some reason we got here without a TTY.
	if !opts.ShouldPrompt() {
		return false
	}
	// We could prompt here, but the issue's UX explicitly opens the walk
	// directly after the summary table. Returning true preserves that flow.
	// Users can still abort via `q` once inside the bubbletea program.
	return true
}

// pluralS returns "s" when n != 1, "" otherwise.
func pluralS(n int) string {
	if n == 1 {
		return ""
	}
	return "s"
}

// formatPublishedDate parses a GitHub `published_at` ISO 8601 string and
// returns "YYYY-MM-DD". Falls back to the raw input when unparseable.
func formatPublishedDate(raw string) string {
	if raw == "" {
		return ""
	}
	if t, err := time.Parse(time.RFC3339, raw); err == nil {
		return t.UTC().Format("2006-01-02")
	}
	return raw
}

// batchReleases splits a slice of releases into chunks of at most size
// elements. The final batch may be smaller. Returns nil for an empty input.
func batchReleases(releases []selfupdate.Release, size int) [][]selfupdate.Release {
	if size <= 0 {
		return nil
	}
	if len(releases) == 0 {
		return nil
	}
	batches := make([][]selfupdate.Release, 0, (len(releases)+size-1)/size)
	for i := 0; i < len(releases); i += size {
		end := min(i+size, len(releases))
		batches = append(batches, releases[i:end])
	}
	return batches
}

// printOfflineNotice prints the terse "Update available" line + a release
// notes URL hint for non-interactive contexts and offline / rate-limited
// fallbacks. Existing call sites (the original updateCLI Step output) are
// replaced by this so we never print the version-jump twice.
func printOfflineNotice(cmd *cobra.Command, result selfupdate.CheckResult) {
	opts := GetGlobalOpts(cmd.Context())
	out := ui.NewUIWithOptions(cmd.OutOrStdout(), opts.UIOptions())
	out.Step(fmt.Sprintf("New version available: %s (current: %s)",
		result.LatestVersion, result.CurrentVersion))
	out.HintNextStep(fmt.Sprintf("Release notes: %s/releases/tag/v%s",
		version.RepoURL, strings.TrimPrefix(result.LatestVersion, "v")))
}
