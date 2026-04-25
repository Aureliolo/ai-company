package ui

import (
	"context"
	"fmt"
	"io"
	"os"
	"strings"

	"charm.land/bubbles/v2/viewport"
	tea "charm.land/bubbletea/v2"
	"charm.land/lipgloss/v2"

	"github.com/Aureliolo/synthorg/cli/internal/selfupdate"
)

// CommitWalkOutcome is what RunCommitWalk returns.
type CommitWalkOutcome int

const (
	// CommitWalkDone means the user pressed enter and is happy to proceed.
	CommitWalkDone CommitWalkOutcome = iota
	// CommitWalkQuit means the user pressed q or ctrl+c.
	CommitWalkQuit
)

// CommitWalkInput drives RunCommitWalk -- the dev-channel walk shows a
// single combined commit list (no per-version batching) because dev
// pre-releases have no Highlights blocks.
type CommitWalkInput struct {
	Installed string
	Target    string
	Commits   selfupdate.CommitRange
	Width     int
	Height    int
	Options   Options
	// Output is the writer bubbletea drives. Falls back to os.Stdout when
	// nil so existing call sites that haven't been updated still work.
	Output io.Writer
}

// RunCommitWalk runs the dev-channel commit list view in a single bubbletea
// program and returns the outcome.
func RunCommitWalk(ctx context.Context, in CommitWalkInput) (CommitWalkOutcome, error) {
	m := newCommitWalkModel(in)
	out := in.Output
	if out == nil {
		out = os.Stdout
	}
	p := tea.NewProgram(m, tea.WithContext(ctx), tea.WithOutput(out))
	final, err := p.Run()
	if err != nil {
		return CommitWalkQuit, err
	}
	cm, ok := final.(commitWalkModel)
	if !ok {
		return CommitWalkQuit, fmt.Errorf("commit walk: unexpected final model type %T", final)
	}
	return cm.outcome, nil
}

// commitWalkModel is the bubbletea model for the dev-channel walk.
type commitWalkModel struct {
	installed string
	target    string
	commits   selfupdate.CommitRange
	viewport  viewport.Model
	width     int
	height    int
	opts      Options
	outcome   CommitWalkOutcome
}

// commitWalkFooterText is the keymap line at the bottom of the commit walk.
// Kept as a package constant so viewportHeight can probe its visible width
// without re-rendering.
const commitWalkFooterText = "[j/k] scroll  [g/G] top/bottom  [enter] continue  [q] quit"

// titleVisibleWidth returns the visible width of the rendered title line
// `<prefix><title>  <count>` so the viewportHeight chrome calculation can
// detect when the title wraps on narrow terminals.
func (m commitWalkModel) titleVisibleWidth() int {
	prefix := "── "
	if m.opts.Plain {
		prefix = "-- "
	}
	title := fmt.Sprintf("dev channel: %s -> %s", m.installed, m.target)
	count := fmt.Sprintf("%d commits", m.commits.TotalCommits)
	return lipgloss.Width(prefix) + lipgloss.Width(title) + 2 + lipgloss.Width(count)
}

// viewportHeight reserves chrome for the dev-channel walk layout: the
// title line + viewport trailing newline + footer line. The base budget
// is 3 lines, but on narrow terminals the title or footer can wrap onto
// a second line, so we add 1 chrome line per element that would not fit
// in m.width. This keeps the viewport from overflowing on small windows
// or with long dev-version labels.
func (m commitWalkModel) viewportHeight() int {
	chrome := 3
	if m.width > 0 {
		if m.titleVisibleWidth() > m.width {
			chrome++
		}
		if lipgloss.Width(commitWalkFooterText) > m.width {
			chrome++
		}
	}
	return viewportHeightForChrome(m.height, chrome)
}

// newCommitWalkModel pre-renders the commit list and wires up the viewport.
func newCommitWalkModel(in CommitWalkInput) commitWalkModel {
	w, h := initialDimensions(in.Width, in.Height)
	m := commitWalkModel{
		installed: in.Installed,
		target:    in.Target,
		commits:   in.Commits,
		width:     w,
		height:    h,
		opts:      in.Options,
		outcome:   CommitWalkQuit, // default if program exits unexpectedly
	}
	vp := viewport.New(viewport.WithWidth(w), viewport.WithHeight(m.viewportHeight()))
	vp.SoftWrap = true
	vp.SetContent(RenderCommitList(in.Commits, w, in.Options))
	m.viewport = vp
	return m
}

// Init implements tea.Model.
func (m commitWalkModel) Init() tea.Cmd {
	return tea.RequestWindowSize
}

// Update implements tea.Model.
func (m commitWalkModel) Update(msg tea.Msg) (tea.Model, tea.Cmd) {
	switch msg := msg.(type) {
	case tea.WindowSizeMsg:
		m.width = msg.Width
		m.height = msg.Height
		m.viewport.SetWidth(msg.Width)
		m.viewport.SetHeight(m.viewportHeight())
		// Re-render with the new width so subject truncation tracks resize.
		m.viewport.SetContent(RenderCommitList(m.commits, msg.Width, m.opts))
		return m, nil
	case tea.KeyPressMsg:
		switch msg.String() {
		case "ctrl+c", "q":
			m.outcome = CommitWalkQuit
			return m, tea.Quit
		case "enter":
			m.outcome = CommitWalkDone
			return m, tea.Quit
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
	}
	var cmd tea.Cmd
	m.viewport, cmd = m.viewport.Update(msg)
	return m, cmd
}

// View implements tea.Model.
func (m commitWalkModel) View() tea.View {
	return tea.NewView(m.renderView())
}

func (m commitWalkModel) renderView() string {
	plain := m.opts.NoColor || m.opts.Plain
	muted := lipgloss.NewStyle()
	header := lipgloss.NewStyle()
	if !plain {
		muted = muted.Foreground(colorMuted)
		header = header.Foreground(colorBrand).Bold(true)
	}

	prefix := "── "
	if m.opts.Plain {
		prefix = "-- "
	}

	title := fmt.Sprintf("dev channel: %s -> %s", m.installed, m.target)
	count := fmt.Sprintf("%d commits", m.commits.TotalCommits)
	if m.commits.TotalCommits == 0 {
		count = "0 commits"
	}

	var sb strings.Builder
	sb.WriteString(muted.Render(prefix))
	sb.WriteString(header.Render(title))
	sb.WriteString("  ")
	sb.WriteString(muted.Render(count))
	sb.WriteByte('\n')
	sb.WriteString(m.viewport.View())
	sb.WriteByte('\n')
	sb.WriteString(muted.Render(commitWalkFooterText))
	return sb.String()
}
