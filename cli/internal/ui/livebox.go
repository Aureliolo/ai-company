package ui

import (
	"fmt"
	"sync"
	"time"

	"github.com/charmbracelet/lipgloss"
)

// liveBoxLine holds the current state of a single line in a LiveBox.
type liveBoxLine struct {
	label    string // left-aligned label (e.g. service name)
	status   string // right-aligned status icon/text (set on finish)
	finished bool
}

// LiveBox renders a bordered box whose content lines update in place.
// Each line shows an animated spinner until marked finished. On non-TTY
// writers, each finish prints a plain status line instead.
type LiveBox struct {
	ui         *UI
	title      string
	lines      []liveBoxLine
	labelW     int // max label width for alignment
	innerW     int
	mu         sync.Mutex
	done       chan struct{}
	closeOnce  sync.Once
	finishOnce sync.Once
	wg         sync.WaitGroup
	started    bool
}

// NewLiveBox creates a live-updating box and renders it immediately.
// Labels are the left-aligned text for each line. The box animates
// spinners on unfinished lines until all lines are finished or
// Finish is called.
func (u *UI) NewLiveBox(title string, labels []string) *LiveBox {
	lines := make([]liveBoxLine, len(labels))
	for i, l := range labels {
		lines[i] = liveBoxLine{label: stripControlStrict(l)}
	}

	// Compute max label width for alignment.
	maxLabelW := 0
	for _, line := range lines {
		w := lipgloss.Width(line.label)
		if w > maxLabelW {
			maxLabelW = w
		}
	}

	// Compute inner width from the widest possible line content.
	// Format: "  <label>  <status>" -- status is at most a few chars.
	maxContentW := 0
	for _, line := range lines {
		w := lipgloss.Width(fmt.Sprintf("  %-*s %s", maxLabelW, line.label, IconSuccess))
		if w > maxContentW {
			maxContentW = w
		}
	}
	titleW := lipgloss.Width(stripControlStrict(title))
	innerW := max(maxContentW, titleW+2, 18)

	lb := &LiveBox{
		ui:     u,
		title:  stripControlStrict(title),
		lines:  lines,
		labelW: maxLabelW,
		innerW: innerW,
		done:   make(chan struct{}),
	}

	if !u.isTTY {
		// Non-TTY: print the title as a step, updates come as plain lines.
		u.Step(lb.title)
		return lb
	}

	// Render initial box frame. The goroutine has not started yet,
	// so these writes cannot race with the animation loop.
	u.renderBoxTop(lb.title, titleW, innerW)
	contentLines := lb.buildLines(0)
	u.renderBoxContent(contentLines, innerW)
	u.renderBoxBottom(innerW)

	// Start animation goroutine.
	lb.started = true
	lb.wg.Go(lb.run)

	return lb
}

// UpdateLine marks a line as finished with the given status icon/text.
// Thread-safe -- can be called from multiple goroutines.
func (lb *LiveBox) UpdateLine(index int, status string) {
	lb.mu.Lock()
	defer lb.mu.Unlock()

	if index < 0 || index >= len(lb.lines) {
		return
	}
	lb.lines[index].status = stripControlStrict(status)
	lb.lines[index].finished = true

	if !lb.ui.isTTY {
		// Non-TTY: print a status line immediately.
		// Compare the stored (already-stripped) value, not the raw input.
		if lb.lines[index].status == IconError {
			lb.ui.Error(lb.lines[index].label)
		} else {
			lb.ui.Success(lb.lines[index].label)
		}
	}
}

// Finish stops the animation and leaves the final box state on screen.
// Safe to call multiple times and concurrently with the animation goroutine.
func (lb *LiveBox) Finish() {
	if !lb.started {
		return
	}
	lb.finishOnce.Do(func() {
		lb.closeDone()
		lb.wg.Wait()

		// Always redraw to ensure the final state is rendered. The last
		// UpdateLine calls may have landed between ticker ticks, so run()
		// could have exited via <-lb.done without drawing the finished icons.
		lb.mu.Lock()
		contentLines := lb.buildLines(-1) // no spinner frame
		lb.mu.Unlock()

		lb.redraw(contentLines)
	})
}

// closeDone signals the animation goroutine to stop.
// Safe to call from both Finish and the auto-close path in run.
func (lb *LiveBox) closeDone() {
	lb.closeOnce.Do(func() { close(lb.done) })
}

// run drives the spinner animation until Finish is called or all lines complete.
func (lb *LiveBox) run() {
	ticker := time.NewTicker(spinnerInterval)
	defer ticker.Stop()

	frame := 0
	for {
		select {
		case <-lb.done:
			return
		case <-ticker.C:
			lb.mu.Lock()
			allDone := lb.allFinished()
			contentLines := lb.buildLines(frame)
			lb.mu.Unlock()

			lb.redraw(contentLines)
			frame = (frame + 1) % len(spinnerFrames)

			if allDone {
				lb.closeDone()
				return
			}
		}
	}
}

// buildLines generates the current display strings for all lines.
// Must be called with lb.mu held.
func (lb *LiveBox) buildLines(frame int) []string {
	result := make([]string, len(lb.lines))
	for i, line := range lb.lines {
		switch {
		case line.finished:
			result[i] = fmt.Sprintf("  %-*s %s", lb.labelW, line.label, line.status)
		case frame >= 0:
			result[i] = fmt.Sprintf("  %-*s %s", lb.labelW, line.label, spinnerFrames[frame])
		default:
			result[i] = fmt.Sprintf("  %-*s ...", lb.labelW, line.label)
		}
	}
	return result
}

// allFinished reports whether every line has been marked finished.
// Must be called with lb.mu held.
func (lb *LiveBox) allFinished() bool {
	for _, line := range lb.lines {
		if !line.finished {
			return false
		}
	}
	return true
}

// redraw moves the cursor up over the content + bottom border and redraws them.
// No-op on non-TTY writers to avoid emitting raw ANSI escape sequences.
func (lb *LiveBox) redraw(contentLines []string) {
	if !lb.ui.isTTY {
		return
	}
	moveUp := len(lb.lines) + 1 // content lines + bottom border
	_, _ = fmt.Fprintf(lb.ui.w, "\033[%dA", moveUp)

	lb.ui.renderBoxContent(contentLines, lb.innerW)
	lb.ui.renderBoxBottom(lb.innerW)
}
