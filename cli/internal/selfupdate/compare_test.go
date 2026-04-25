package selfupdate

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCommitsBetween_normal(t *testing.T) {
	resp := compareResponse{
		TotalCommits: 3,
		Commits: []compareCommitJSON{
			{
				SHA:     "abc1234567890abcdef",
				HTMLURL: "https://github.com/Aureliolo/synthorg/commit/abc1234567890abcdef",
				Commit: compareCommitInner{
					Message: "feat(cli): per-version Highlights walk\n\nLong body that should be ignored.",
					Author:  compareCommitAuthor{Name: "Daisy", Date: "2026-04-25T12:00:00Z"},
				},
			},
			{
				SHA:     "def4567890abcdef1234",
				HTMLURL: "https://github.com/Aureliolo/synthorg/commit/def4567890abcdef1234",
				Commit: compareCommitInner{
					Message: "fix(selfupdate): pagination cap",
					Author:  compareCommitAuthor{Name: "Bob", Date: "2026-04-26T14:00:00Z"},
				},
			},
			{
				SHA:     "ff0000aabbccddeeff",
				HTMLURL: "https://github.com/Aureliolo/synthorg/commit/ff0000aabbccddeeff",
				Commit: compareCommitInner{
					Message: "chore(deps): bump",
					Author:  compareCommitAuthor{Name: "renovate[bot]", Date: "2026-04-27T09:00:00Z"},
				},
			},
		},
	}
	body, _ := json.Marshal(resp)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		want := "/v0.7.3-dev.5...v0.7.3-dev.9"
		if !strings.HasSuffix(r.URL.Path, want) {
			t.Errorf("path = %q, want suffix %q", r.URL.Path, want)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(body)
	}))
	defer srv.Close()

	got, err := commitsBetweenFromURL(context.Background(), srv.URL+"/repos/Aureliolo/synthorg/compare/{base}...{head}", "v0.7.3-dev.5", "v0.7.3-dev.9")
	if err != nil {
		t.Fatalf("CommitsBetween: %v", err)
	}
	if got.TotalCommits != 3 {
		t.Errorf("TotalCommits = %d, want 3", got.TotalCommits)
	}
	if len(got.Commits) != 3 {
		t.Fatalf("len(Commits) = %d, want 3", len(got.Commits))
	}
	c := got.Commits[0]
	if c.SHA != "abc1234567890abcdef" {
		t.Errorf("SHA = %q, want abc1234567890abcdef", c.SHA)
	}
	if c.Subject != "feat(cli): per-version Highlights walk" {
		t.Errorf("Subject = %q, want first line only", c.Subject)
	}
	if c.Author != "Daisy" {
		t.Errorf("Author = %q, want Daisy", c.Author)
	}
	if c.Date != "2026-04-25" {
		t.Errorf("Date = %q, want 2026-04-25 (YYYY-MM-DD)", c.Date)
	}
}

func TestCommitsBetween_emptyRange(t *testing.T) {
	resp := compareResponse{TotalCommits: 0, Commits: nil}
	body, _ := json.Marshal(resp)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(body)
	}))
	defer srv.Close()

	got, err := commitsBetweenFromURL(context.Background(), srv.URL+"/{base}...{head}", "v0.7.3", "v0.7.3")
	if err != nil {
		t.Fatalf("CommitsBetween: %v", err)
	}
	if got.TotalCommits != 0 || len(got.Commits) != 0 {
		t.Errorf("got = %+v, want empty", got)
	}
}

func TestCommitsBetween_rateLimited(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusForbidden)
	}))
	defer srv.Close()
	_, err := commitsBetweenFromURL(context.Background(), srv.URL+"/{base}...{head}", "v0.7.1", "v0.7.5")
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "rate-limited") {
		t.Errorf("error = %v, want rate-limited message", err)
	}
}

func TestCommitsBetween_notFound(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()
	_, err := commitsBetweenFromURL(context.Background(), srv.URL+"/{base}...{head}", "vX", "vY")
	if err == nil {
		t.Fatal("expected error for 404")
	}
}

func TestCommitsBetween_truncated(t *testing.T) {
	// total_commits exceeds len(commits) -- the GitHub compare API caps at 250.
	commits := make([]compareCommitJSON, 250)
	for i := range commits {
		commits[i] = compareCommitJSON{
			SHA: "0000000000000000000000000000000000000000",
			Commit: compareCommitInner{
				Message: "commit subject",
				Author:  compareCommitAuthor{Name: "tester", Date: "2026-04-25T00:00:00Z"},
			},
		}
	}
	resp := compareResponse{TotalCommits: 320, Commits: commits}
	body, _ := json.Marshal(resp)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(body)
	}))
	defer srv.Close()

	got, err := commitsBetweenFromURL(context.Background(), srv.URL+"/{base}...{head}", "v0.6.0", "v0.7.0")
	if err != nil {
		t.Fatalf("CommitsBetween: %v", err)
	}
	if got.TotalCommits != 320 {
		t.Errorf("TotalCommits = %d, want 320", got.TotalCommits)
	}
	if len(got.Commits) != 250 {
		t.Errorf("len(Commits) = %d, want 250 (API cap)", len(got.Commits))
	}
}

func TestCommitsBetween_pathSubstitution(t *testing.T) {
	var seenPath string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seenPath = r.URL.Path
		_, _ = w.Write([]byte(`{"total_commits":0,"commits":[]}`))
	}))
	defer srv.Close()
	urlTpl := srv.URL + "/repos/foo/bar/compare/{base}...{head}"
	_, _ = commitsBetweenFromURL(context.Background(), urlTpl, "v0.1.0", "v0.2.0")
	wantPath := "/repos/foo/bar/compare/v0.1.0...v0.2.0"
	if seenPath != wantPath {
		t.Errorf("seenPath = %q, want %q", seenPath, wantPath)
	}
}

func TestCommitsBetween_pathEscapesMetacharacters(t *testing.T) {
	// Tag values containing URL metacharacters must be percent-escaped so
	// they cannot break out of the path segment (e.g. flip the request to
	// a different endpoint via "?" or split the path with "/").
	tests := []struct {
		name     string
		base     string
		head     string
		wantPath string
	}{
		{
			name:     "question_mark_in_base",
			base:     "v0.1.0?evil=1",
			head:     "v0.2.0",
			wantPath: "/repos/foo/bar/compare/v0.1.0%3Fevil=1...v0.2.0",
		},
		{
			name:     "hash_in_head",
			base:     "v0.1.0",
			head:     "v0.2.0#anchor",
			wantPath: "/repos/foo/bar/compare/v0.1.0...v0.2.0%23anchor",
		},
		{
			name:     "slash_in_tag",
			base:     "v0.1.0/evil",
			head:     "v0.2.0",
			wantPath: "/repos/foo/bar/compare/v0.1.0%2Fevil...v0.2.0",
		},
		{
			name:     "space_in_tag",
			base:     "v0 1",
			head:     "v0.2.0",
			wantPath: "/repos/foo/bar/compare/v0%201...v0.2.0",
		},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// r.RequestURI preserves the percent-encoding as sent on the
			// wire. r.URL.Path silently decodes it, which would defeat the
			// purpose of this test.
			var seenURI string
			srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
				seenURI = r.RequestURI
				_, _ = w.Write([]byte(`{"total_commits":0,"commits":[]}`))
			}))
			defer srv.Close()
			urlTpl := srv.URL + "/repos/foo/bar/compare/{base}...{head}"
			_, _ = commitsBetweenFromURL(context.Background(), urlTpl, tt.base, tt.head)
			if seenURI != tt.wantPath {
				t.Errorf("seenURI = %q, want %q", seenURI, tt.wantPath)
			}
		})
	}
}

// TestCommitsBetween_subjectSkipsLeadingBlankLines guards firstLine against
// messages that begin with one or more blank lines: the subject must resolve
// to the first non-empty line, otherwise commits render with empty subjects.
func TestCommitsBetween_subjectSkipsLeadingBlankLines(t *testing.T) {
	resp := compareResponse{
		TotalCommits: 1,
		Commits: []compareCommitJSON{{
			SHA: "deadbeefcafebabe1234",
			Commit: compareCommitInner{
				Message: "\n\nsubject line\n\nbody",
				Author:  compareCommitAuthor{Name: "x", Date: "2026-04-25T00:00:00Z"},
			},
		}},
	}
	body, _ := json.Marshal(resp)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(body)
	}))
	defer srv.Close()

	got, err := commitsBetweenFromURL(context.Background(), srv.URL+"/{base}...{head}", "a", "b")
	if err != nil {
		t.Fatalf("CommitsBetween: %v", err)
	}
	if want := "subject line"; got.Commits[0].Subject != want {
		t.Errorf("Subject = %q, want %q", got.Commits[0].Subject, want)
	}
}

func TestCommitsBetween_invalidDateGracefulFallback(t *testing.T) {
	resp := compareResponse{
		TotalCommits: 1,
		Commits: []compareCommitJSON{{
			SHA: "deadbeefcafebabe1234",
			Commit: compareCommitInner{
				Message: "subject",
				Author:  compareCommitAuthor{Name: "x", Date: "not-a-date"},
			},
		}},
	}
	body, _ := json.Marshal(resp)
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		_, _ = w.Write(body)
	}))
	defer srv.Close()

	got, err := commitsBetweenFromURL(context.Background(), srv.URL+"/{base}...{head}", "a", "b")
	if err != nil {
		t.Fatalf("CommitsBetween: %v", err)
	}
	if got.Commits[0].Date != "not-a-date" {
		t.Errorf("Date = %q, want raw fallback when unparseable", got.Commits[0].Date)
	}
}
