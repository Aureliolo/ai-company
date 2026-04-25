// Package ui walk.go contains the bubbletea-based per-version Highlights
// walk used by `synthorg update` to show release context between installed
// and target versions. One Program runs per batch of <=3 versions; the
// caller is responsible for orchestrating multiple batches and threading
// session-level toggle state across them via WalkBatchResult.FinalView.
package ui

import (
	"context"
	"fmt"
	"os"
	"strings"

	"charm.land/bubbles/v2/viewport"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"

	"github.com/Aureliolo/synthorg/cli/internal/selfupdate"
)

// WalkOutcome describes how a batch ended.
type WalkOutcome int

const (
	// WalkOutcomeDone means the user walked through every version in this
	// batch by pressing enter on the last one (and there were no more
	// batches to follow).
	WalkOutcomeDone WalkOutcome = iota
	// WalkOutcomeNextBatch means the user wants the next batch. Only emitted
	// when IsFinalBatch == false.
	WalkOutcomeNextBatch
	// WalkOutcomeQuit means the user pressed `q` or ctrl+c. The walk should
	// stop; the caller continues to the install confirmation prompt.
	WalkOutcomeQuit
)

// changelogView is one of "highlights" or "commits". It is a string (not a
// custom type) so callers can pass the same constants used by config.
type changelogView = string

const (
	viewHighlights changelogView = "highlights"
	viewCommits    changelogView = "commits"
)

// WalkBatchInput drives RunWalkBatch.
type WalkBatchInput struct {
	// Versions is the batch -- typically 1 to 3 entries.
	Versions []selfupdate.Release
	// InitialView is the changelog view to start in. The caller threads
	// this from the config default (state.ChangelogViewOrDefault) and
	// forward across batches via WalkBatchResult.FinalView.
	InitialView changelogView
	// IsFinalBatch suppresses "[n] next batch" messaging when true.
	IsFinalBatch bool
	// Width / Height are the initial terminal dimensions. The Model also
	// listens for tea.WindowSizeMsg so the viewport stays responsive on
	// resize.
	Width, Height int
	// Options carries colour / plain / quiet flags from GlobalOpts.
	Options Options
}

// WalkBatchResult is what RunWalkBatch returns to the orchestrator.
type WalkBatchResult struct {
	Outcome WalkOutcome
	// FinalView is the changelog view active when the batch ended. The
	// orchestrator threads this into the next batch's InitialView so the
	// user's `c` toggle persists across batches.
	FinalView changelogView
}

// RunWalkBatch runs one bubbletea program for a batch of versions and
// returns the outcome. Errors from tea.Program.Run propagate up; the caller
// should treat them as advisory (the walk is informational, not load-bearing).
func RunWalkBatch(ctx context.Context, in WalkBatchInput) (WalkBatchResult, error) {
	if len(in.Versions) == 0 {
		return WalkBatchResult{Outcome: WalkOutcomeDone, FinalView: in.InitialView}, nil
	}

	m := newWalkModel(in)
	progOpts := []tea.ProgramOption{tea.WithContext(ctx), tea.WithOutput(os.Stdout)}
	p := tea.NewProgram(m, progOpts...)
	final, err := p.Run()
	if err != nil {
		return WalkBatchResult{Outcome: WalkOutcomeQuit, FinalView: in.InitialView}, err
	}
	wm, ok := final.(walkModel)
	if !ok {
		return WalkBatchResult{Outcome: WalkOutcomeQuit, FinalView: in.InitialView}, fmt.Errorf("walk: unexpected final model type %T", final)
	}
	return wm.result, nil
}

// walkModel is the bubbletea model. Exported field names are intentionally
// avoided -- this type is package-private state.
type walkModel struct {
	versions     []selfupdate.Release
	idx          int
	view         changelogView
	toggleable   []bool // per-version: false when no Highlights block is present
	contents     []changelogContents
	viewport     viewport.Model
	width        int
	height       int
	opts         Options
	isFinalBatch bool
	flashMsg     string // set when `c` is pressed on a non-toggleable version
	result       WalkBatchResult
}

// changelogContents holds both pre-rendered views for a single version so
// toggling between them is instantaneous (no re-render cost on `c`).
type changelogContents struct {
	highlights string // empty if no Highlights block
	commits    string // never empty (always falls back to commit log)
	header     string // "── v0.7.3 ────────"
}

// newWalkModel constructs the bubbletea model for the supplied batch input.
// Pre-renders both highlights and commits content for every version so the
// viewport can swap between them without re-running the renderer on every
// keypress.
func newWalkModel(in WalkBatchInput) walkModel {
	view := in.InitialView
	if view != viewCommits {
		view = viewHighlights
	}
	contents := make([]changelogContents, len(in.Versions))
	toggleable := make([]bool, len(in.Versions))
	for i, r := range in.Versions {
		hl, ok := selfupdate.ExtractHighlights(r.Body)
		toggleable[i] = ok
		var hlRendered string
		if ok {
			hlRendered = RenderHighlights(hl, in.Options)
		}
		commitsRendered := RenderCommits(selfupdate.ExtractCommits(r.Body), in.Options)
		contents[i] = changelogContents{
			highlights: hlRendered,
			commits:    commitsRendered,
			header:     versionHeader(r, in.Options),
		}
	}

	width, height := initialDimensions(in.Width, in.Height)
	m := walkModel{
		versions:     in.Versions,
		idx:          0,
		view:         view,
		toggleable:   toggleable,
		contents:     contents,
		width:        width,
		height:       height,
		opts:         in.Options,
		isFinalBatch: in.IsFinalBatch,
		result:       WalkBatchResult{Outcome: WalkOutcomeQuit, FinalView: view},
	}
	vp := viewport.New(viewport.WithWidth(width), viewport.WithHeight(m.viewportHeight()))
	vp.SoftWrap = true
	m.viewport = vp
	m.loadCurrentContent()
	return m
}

// initialDimensions provides sane fallback values when the caller does not
// know the terminal size yet (the first WindowSizeMsg will overwrite them).
func initialDimensions(w, h int) (int, int) {
	if w <= 0 {
		w = 80
	}
	if h <= 0 {
		h = 24
	}
	return w, h
}

// viewportHeightForChrome reserves chrome lines for renderView's surrounding
// layout (header + trailing newline + footer, plus any optional fallback /
// flash rows the caller knows about). Falls back to 1 when the terminal is
// too small to render anything meaningful.
func viewportHeightForChrome(termHeight, chrome int) int {
	if termHeight <= chrome+1 {
		return 1
	}
	return termHeight - chrome
}

// viewportHeight returns the viewport height for the current model state.
// Chrome is computed dynamically because renderView's layout depends on
// runtime flags: the version header is always 1 line, the trailing newline
// after the viewport is 1 line, and the footer is 1 line. A non-toggleable
// version adds a fallback-note line; a non-empty flashMsg adds another.
// Static-chrome implementations risk overflowing the terminal on small
// windows when those optional rows appear.
func (m walkModel) viewportHeight() int {
	chrome := 3 // header + viewport trailing newline + footer
	if m.idx < len(m.toggleable) && !m.toggleable[m.idx] {
		chrome++
	}
	if m.flashMsg != "" {
		chrome++
	}
	return viewportHeightForChrome(m.height, chrome)
}

// versionHeader renders the "── v0.7.3 ─────────────── [1/3]" line shown
// above every version's content. The position indicator is added in
// walkModel.View() so it can include the live idx.
func versionHeader(r selfupdate.Release, opts Options) string {
	plain := opts.NoColor || opts.Plain
	style := lipgloss.NewStyle()
	if !plain {
		style = style.Foreground(colorBrand).Bold(true)
	}
	return style.Render(r.TagName)
}

// Init implements tea.Model. We request an initial window size so the
// viewport sizes itself correctly on terminals that did not deliver one
// at startup.
func (m walkModel) Init() tea.Cmd {
	return tea.RequestWindowSize
}

// Update implements tea.Model.
func (m walkModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		return m.handleResize(msg.Width, msg.Height), nil
	case tea.KeyPressMsg:
		return m.handleKey(msg.String())
	}
	// Forward any other message to the viewport so its internal animations
	// (none currently) remain functional.
	var cmd tea.Cmd
	m.viewport, cmd = m.viewport.Update(msg)
	return m, cmd
}

// handleResize updates the model and viewport on terminal resize.
func (m walkModel) handleResize(w, h int) walkModel {
	m.width = w
	m.height = h
	m.viewport.SetWidth(w)
	m.viewport.SetHeight(m.viewportHeight())
	m.loadCurrentContent()
	return m
}

// handleKey processes a key press. Returns the new model + an optional cmd
// (typically tea.Quit when exiting the batch).
func (m walkModel) handleKey(key string) (tea.Model, tea.Cmd) {
	if m.flashMsg != "" {
		m.flashMsg = ""
		// flashMsg lost a line: grow the viewport back so the user gets the
		// space back on the next render.
		m.viewport.SetHeight(m.viewportHeight())
	}
	switch key {
	case "ctrl+c", "q":
		m.result = WalkBatchResult{Outcome: WalkOutcomeQuit, FinalView: m.view}
		return m, tea.Quit
	case "enter":
		return m.advance()
	case "n":
		if m.onLastInBatch() && !m.isFinalBatch {
			m.result = WalkBatchResult{Outcome: WalkOutcomeNextBatch, FinalView: m.view}
			return m, tea.Quit
		}
		return m, nil
	case "c":
		return m.toggleView(), nil
	case "j", "down":
		m.viewport.ScrollDown(1)
		return m, nil
	case "k", "up":
		m.viewport.ScrollUp(1)
		return m, nil
	case "pgdown", " ", "space":
		m.viewport.PageDown()
		return m, nil
	case "pgup":
		m.viewport.PageUp()
		return m, nil
	case "g", "home":
		m.viewport.GotoTop()
		return m, nil
	case "G", "end":
		m.viewport.GotoBottom()
		return m, nil
	}
	return m, nil
}

// advance moves to the next version in the batch, or quits with the
// appropriate outcome when on the last one.
func (m walkModel) advance() (tea.Model, tea.Cmd) {
	if m.onLastInBatch() {
		if m.isFinalBatch {
			m.result = WalkBatchResult{Outcome: WalkOutcomeDone, FinalView: m.view}
		} else {
			m.result = WalkBatchResult{Outcome: WalkOutcomeNextBatch, FinalView: m.view}
		}
		return m, tea.Quit
	}
	m.idx++
	m.viewport.SetYOffset(0)
	m.loadCurrentContent()
	return m, nil
}

// toggleView flips between highlights and commits, or sets a flash message
// when the current version has no Highlights block.
func (m walkModel) toggleView() walkModel {
	if !m.toggleable[m.idx] {
		m.flashMsg = "No AI highlights for this version -- showing commit log."
		// flashMsg gained a line: shrink the viewport so the layout still fits.
		m.viewport.SetHeight(m.viewportHeight())
		return m
	}
	if m.view == viewHighlights {
		m.view = viewCommits
	} else {
		m.view = viewHighlights
	}
	m.loadCurrentContent()
	return m
}

// loadCurrentContent re-points the viewport at the right pre-rendered slice
// and resizes it for the chrome the current state consumes (the optional
// fallback note + flashMsg lines change the chrome budget).
func (m *walkModel) loadCurrentContent() {
	m.viewport.SetHeight(m.viewportHeight())
	if len(m.contents) == 0 {
		m.viewport.SetContent("")
		return
	}
	c := m.contents[m.idx]
	if !m.toggleable[m.idx] {
		// Force commits view when no highlights exist.
		m.viewport.SetContent(c.commits)
		return
	}
	if m.view == viewHighlights {
		m.viewport.SetContent(c.highlights)
	} else {
		m.viewport.SetContent(c.commits)
	}
}

// onLastInBatch reports whether the current version is the last one in this
// batch.
func (m walkModel) onLastInBatch() bool {
	return m.idx == len(m.versions)-1
}

// View implements tea.Model.
func (m walkModel) View() tea.View {
	if len(m.versions) == 0 {
		return tea.NewView("")
	}
	return tea.NewView(m.renderView())
}

// renderView produces the full display string. Layout:
//
//	── v0.7.3 ───────────────────────── [1/3]
//	(optional fallback note for non-toggleable versions)
//	<viewport content>
//	(optional flash message)
//	[c] commits  [j/k] scroll  [enter] next  [q] quit
func (m walkModel) renderView() string {
	plain := m.opts.NoColor || m.opts.Plain
	muted := lipgloss.NewStyle()
	if !plain {
		muted = muted.Foreground(colorMuted)
	}

	header := m.renderHeader()
	footer := m.renderFooter(muted)

	var sb strings.Builder
	sb.WriteString(header)
	sb.WriteByte('\n')
	if !m.toggleable[m.idx] {
		sb.WriteString(RenderFallbackNote(m.opts))
		sb.WriteByte('\n')
	}
	sb.WriteString(m.viewport.View())
	sb.WriteByte('\n')
	if m.flashMsg != "" {
		sb.WriteString(muted.Render(m.flashMsg))
		sb.WriteByte('\n')
	}
	sb.WriteString(footer)
	return sb.String()
}

// renderHeader builds the version-separator line at the top of each version
// view: "── v0.7.3 ───────────────── [1/3]".
func (m walkModel) renderHeader() string {
	c := m.contents[m.idx]
	pos := fmt.Sprintf("[%d/%d]", m.idx+1, len(m.versions))
	prefix := "── "
	if m.opts.Plain {
		prefix = "-- "
	}
	tag := c.header // already styled
	rule := strings.Repeat(separatorRune(m.opts), separatorWidth(m.width, tagPlainWidth(m.versions[m.idx].TagName), len(pos)))
	plain := m.opts.NoColor || m.opts.Plain
	muted := lipgloss.NewStyle()
	if !plain {
		muted = muted.Foreground(colorMuted)
	}
	return muted.Render(prefix) + tag + " " + muted.Render(rule+" "+pos)
}

// separatorRune returns the box-drawing rune used for the version separator,
// or "-" in plain mode.
func separatorRune(opts Options) string {
	if opts.Plain {
		return "-"
	}
	return "─"
}

// separatorWidth returns the number of separator characters that fit between
// the version tag and the position indicator on the header line. Falls back
// to a small fixed width if the terminal is too narrow.
func separatorWidth(termWidth, tagWidth, posWidth int) int {
	const fixedPrefixWidth = 3 // "── "
	const padding = 2          // spaces around the position
	w := termWidth - fixedPrefixWidth - tagWidth - posWidth - padding
	if w < 3 {
		return 3
	}
	return w
}

// tagPlainWidth returns the visible width of a version tag (no styling).
func tagPlainWidth(tag string) int {
	return len(tag)
}

// renderFooter renders the key-binding hint line at the bottom of the view.
// The text adapts to the current version's toggleability and the batch
// position (last item in non-final batch shows `[n] next batch`).
func (m walkModel) renderFooter(muted lipgloss.Style) string {
	parts := []string{}
	switch {
	case !m.toggleable[m.idx]:
		parts = append(parts, "[c] disabled")
	case m.view == viewHighlights:
		parts = append(parts, "[c] commit log")
	default:
		parts = append(parts, "[c] highlights")
	}
	parts = append(parts, "[j/k] scroll", "[g/G] top/bottom")
	switch {
	case m.onLastInBatch() && !m.isFinalBatch:
		parts = append(parts, "[enter/n] next batch")
	case m.onLastInBatch() && m.isFinalBatch:
		parts = append(parts, "[enter] continue")
	default:
		parts = append(parts, "[enter] next")
	}
	parts = append(parts, "[q] quit")
	return muted.Render(strings.Join(parts, "  "))
}
