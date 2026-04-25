package selfupdate

import (
	"context"
	"strings"
	"time"
)

// Commit is the projected, UI-friendly view of a GitHub compare commit
// returned by CommitsBetween.
type Commit struct {
	SHA     string // full 40-char SHA
	Subject string // first line of the commit message
	Author  string // author name
	Date    string // YYYY-MM-DD (best-effort; raw value when unparseable)
	URL     string // html_url to the commit on github.com
}

// CommitRange is the result of a comparison between two refs. TotalCommits
// may exceed len(Commits) when the range is larger than the compare API's
// 250-commit cap; the caller can render a "showing 250 of N" footer.
type CommitRange struct {
	Commits      []Commit
	TotalCommits int
}

// compareResponse mirrors the subset of the GitHub compare endpoint payload
// we need. Kept package-private; CommitRange is the exported surface.
type compareResponse struct {
	TotalCommits int                 `json:"total_commits"`
	Commits      []compareCommitJSON `json:"commits"`
}

type compareCommitJSON struct {
	SHA     string             `json:"sha"`
	HTMLURL string             `json:"html_url"`
	Commit  compareCommitInner `json:"commit"`
}

type compareCommitInner struct {
	Message string              `json:"message"`
	Author  compareCommitAuthor `json:"author"`
}

type compareCommitAuthor struct {
	Name string `json:"name"`
	Date string `json:"date"` // RFC 3339
}

// CommitsBetween fetches the commits in (base, head]. base and head may be
// tags, branches, or SHAs. Uses GitHub's compare endpoint, which returns up
// to 250 commits in a single response; for larger ranges TotalCommits >
// len(Commits) and the UI surfaces a truncation note.
func CommitsBetween(ctx context.Context, base, head string) (CommitRange, error) {
	return commitsBetweenFromURL(ctx, compareBaseURL(), base, head)
}

// compareBaseURL returns the compare-endpoint template. Kept as a function
// so tests can inject an httptest URL via commitsBetweenFromURL.
func compareBaseURL() string {
	return "https://api.github.com/repos/" + repoSlug + "/compare/{base}...{head}"
}

// commitsBetweenFromURL is the testable core of CommitsBetween. urlTpl must
// contain "{base}" and "{head}" placeholders. base/head are tag/ref values
// substituted into the template before issuing the request.
func commitsBetweenFromURL(ctx context.Context, urlTpl, base, head string) (CommitRange, error) {
	u := strings.ReplaceAll(urlTpl, "{base}", base)
	u = strings.ReplaceAll(u, "{head}", head)

	resp, err := fetchJSON[compareResponse](ctx, u)
	if err != nil {
		return CommitRange{}, err
	}
	commits := make([]Commit, len(resp.Commits))
	for i, c := range resp.Commits {
		commits[i] = Commit{
			SHA:     c.SHA,
			Subject: firstLine(c.Commit.Message),
			Author:  c.Commit.Author.Name,
			Date:    formatCommitDate(c.Commit.Author.Date),
			URL:     c.HTMLURL,
		}
	}
	return CommitRange{Commits: commits, TotalCommits: resp.TotalCommits}, nil
}

// firstLine returns the first non-empty line of a commit message (the
// subject). Returns the input verbatim if no newline is present.
func firstLine(msg string) string {
	if line, _, ok := strings.Cut(msg, "\n"); ok {
		return strings.TrimSpace(line)
	}
	return strings.TrimSpace(msg)
}

// formatCommitDate parses an RFC 3339 timestamp from the GitHub compare API
// and returns YYYY-MM-DD. On parse failure, returns the raw input so the UI
// can still display something meaningful.
func formatCommitDate(raw string) string {
	if raw == "" {
		return ""
	}
	if t, err := time.Parse(time.RFC3339, raw); err == nil {
		return t.UTC().Format("2006-01-02")
	}
	return raw
}
