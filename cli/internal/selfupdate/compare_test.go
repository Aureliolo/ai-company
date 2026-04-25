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
