package selfupdate

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync/atomic"
	"testing"
)

// makeReleases builds devRelease fixtures for tests. tag prefix "v" is
// expected; pre-releases are flagged when the tag contains "-dev.".
func makeReleases(tags ...string) []devRelease {
	releases := make([]devRelease, 0, len(tags))
	for _, tag := range tags {
		releases = append(releases, devRelease{
			TagName:     tag,
			Body:        "body for " + tag,
			PublishedAt: "2026-04-20T00:00:00Z",
			Assets: []Asset{
				{Name: assetName(), BrowserDownloadURL: expectedURLPrefix + tag + "/" + assetName()},
				{Name: "checksums.txt", BrowserDownloadURL: expectedURLPrefix + tag + "/checksums.txt"},
			},
			Prerelease: strings.Contains(tag, "-dev."),
		})
	}
	return releases
}

// fixtureServer returns a httptest server that serves JSON-encoded releases
// for any path. Optionally, a pageHandler can be provided to override
// per-request responses (for pagination tests).
func fixtureServer(t *testing.T, releases []devRelease) *httptest.Server {
	t.Helper()
	body, err := json.Marshal(releases)
	if err != nil {
		t.Fatalf("marshalling fixtures: %v", err)
	}
	return httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(body)
	}))
}

func TestReleasesBetween(t *testing.T) {
	tests := []struct {
		name       string
		releases   []devRelease
		installed  string
		target     string
		includeDev bool
		wantTags   []string // expected order
	}{
		{
			name:      "simple_range",
			releases:  makeReleases("v0.7.5", "v0.7.4", "v0.7.3", "v0.7.2", "v0.7.1", "v0.7.0"),
			installed: "v0.7.1",
			target:    "v0.7.5",
			wantTags:  []string{"v0.7.2", "v0.7.3", "v0.7.4", "v0.7.5"},
		},
		{
			name:       "dev_off_excludes_pre_releases",
			releases:   makeReleases("v0.7.4", "v0.7.3-dev.2", "v0.7.2", "v0.7.1"),
			installed:  "v0.7.1",
			target:     "v0.7.4",
			includeDev: false,
			wantTags:   []string{"v0.7.2", "v0.7.4"},
		},
		{
			name:       "dev_on_includes_pre_releases",
			releases:   makeReleases("v0.7.4", "v0.7.3-dev.2", "v0.7.2", "v0.7.1"),
			installed:  "v0.7.1",
			target:     "v0.7.4",
			includeDev: true,
			wantTags:   []string{"v0.7.2", "v0.7.3-dev.2", "v0.7.4"},
		},
		{
			name:      "empty_range",
			releases:  makeReleases("v0.7.5", "v0.7.4"),
			installed: "v0.7.5",
			target:    "v0.7.5",
			wantTags:  []string{},
		},
		{
			name:      "out_of_order_api_response",
			releases:  makeReleases("v0.7.3", "v0.7.5", "v0.7.2", "v0.7.4", "v0.7.1"),
			installed: "v0.7.1",
			target:    "v0.7.5",
			wantTags:  []string{"v0.7.2", "v0.7.3", "v0.7.4", "v0.7.5"},
		},
		{
			name:      "target_below_installed_returns_empty",
			releases:  makeReleases("v0.7.3", "v0.7.2", "v0.7.1"),
			installed: "v0.7.5",
			target:    "v0.7.3",
			wantTags:  []string{},
		},
		{
			name: "draft_is_filtered",
			releases: append(makeReleases("v0.7.3", "v0.7.1"),
				devRelease{TagName: "v0.7.2", Draft: true, Assets: []Asset{}, PublishedAt: "2026-04-20"}),
			installed: "v0.7.1",
			target:    "v0.7.3",
			wantTags:  []string{"v0.7.3"},
		},
		{
			name:      "preserves_body_and_published",
			releases:  makeReleases("v0.7.2"),
			installed: "v0.7.1",
			target:    "v0.7.2",
			wantTags:  []string{"v0.7.2"},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			srv := fixtureServer(t, tt.releases)
			defer srv.Close()

			got, err := releasesBetweenFromURL(context.Background(), srv.URL, tt.installed, tt.target, tt.includeDev)
			if err != nil {
				t.Fatalf("ReleasesBetween: %v", err)
			}
			gotTags := make([]string, len(got))
			for i, r := range got {
				gotTags[i] = r.TagName
			}
			if len(gotTags) != len(tt.wantTags) {
				t.Fatalf("tags = %v, want %v", gotTags, tt.wantTags)
			}
			for i := range gotTags {
				if gotTags[i] != tt.wantTags[i] {
					t.Fatalf("tags = %v, want %v", gotTags, tt.wantTags)
				}
			}
			// Confirm Body + PublishedAt round-trip.
			if tt.name == "preserves_body_and_published" && len(got) > 0 {
				if got[0].Body != "body for v0.7.2" {
					t.Errorf("Body = %q, want %q", got[0].Body, "body for v0.7.2")
				}
				if got[0].PublishedAt != "2026-04-20T00:00:00Z" {
					t.Errorf("PublishedAt = %q, want 2026-04-20T00:00:00Z", got[0].PublishedAt)
				}
			}
		})
	}
}

func TestReleasesBetween_pagination(t *testing.T) {
	// Page 1: 100 entries (full page); Page 2: 30 entries (signals last page).
	page1 := make([]devRelease, releasesPerPage)
	for i := range page1 {
		page1[i] = devRelease{
			TagName: fmt.Sprintf("v0.8.%d", releasesPerPage-i), // 100, 99, ..., 1
			Assets: []Asset{
				{Name: assetName(), BrowserDownloadURL: expectedURLPrefix + "tag/" + assetName()},
				{Name: "checksums.txt", BrowserDownloadURL: expectedURLPrefix + "tag/checksums.txt"},
			},
		}
	}
	page2 := make([]devRelease, 30)
	for i := range page2 {
		page2[i] = devRelease{
			TagName: fmt.Sprintf("v0.7.%d", 30-i), // 30, 29, ..., 1
			Assets: []Asset{
				{Name: assetName(), BrowserDownloadURL: expectedURLPrefix + "tag/" + assetName()},
				{Name: "checksums.txt", BrowserDownloadURL: expectedURLPrefix + "tag/checksums.txt"},
			},
		}
	}

	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		page := r.URL.Query().Get("page")
		w.Header().Set("Content-Type", "application/json")
		var body []byte
		switch page {
		case "1":
			body, _ = json.Marshal(page1)
		case "2":
			body, _ = json.Marshal(page2)
		default:
			body, _ = json.Marshal([]devRelease{}) // empty -- should not be reached
		}
		calls.Add(1)
		_, _ = w.Write(body)
	}))
	defer srv.Close()

	got, err := releasesBetweenFromURL(context.Background(), srv.URL, "v0.7.20", "v0.8.50", false)
	if err != nil {
		t.Fatalf("ReleasesBetween: %v", err)
	}
	// Expect tags strictly above v0.7.20 and at-or-below v0.8.50:
	// v0.7.21 ... v0.7.30 (10 entries) + v0.8.1 ... v0.8.50 (50 entries) = 60.
	if len(got) != 60 {
		t.Errorf("len(got) = %d, want 60", len(got))
	}
	if got[0].TagName != "v0.7.21" {
		t.Errorf("first = %q, want v0.7.21", got[0].TagName)
	}
	if got[len(got)-1].TagName != "v0.8.50" {
		t.Errorf("last = %q, want v0.8.50", got[len(got)-1].TagName)
	}
	if calls.Load() != 2 {
		t.Errorf("calls = %d, want 2 (page 1 then page 2 stops)", calls.Load())
	}
}

func TestReleasesBetween_rateLimited(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		w.WriteHeader(http.StatusForbidden)
	}))
	defer srv.Close()

	_, err := releasesBetweenFromURL(context.Background(), srv.URL, "v0.7.1", "v0.7.5", false)
	if err == nil {
		t.Fatal("expected rate-limited error")
	}
	if !strings.Contains(err.Error(), "rate-limited") {
		t.Errorf("error %v should mention rate-limited", err)
	}
}

func TestReleasesBetween_invalidInstalledRejected(t *testing.T) {
	srv := fixtureServer(t, makeReleases("v0.7.5"))
	defer srv.Close()
	_, err := releasesBetweenFromURL(context.Background(), srv.URL, "v0.7.NaN", "v0.7.5", false)
	if err == nil {
		t.Fatal("expected error for malformed installed version")
	}
	if !strings.Contains(err.Error(), "invalid installed version") {
		t.Errorf("error should mention invalid installed version, got: %v", err)
	}
}

func TestReleasesBetween_invalidTargetRejected(t *testing.T) {
	srv := fixtureServer(t, makeReleases("v0.7.5"))
	defer srv.Close()
	_, err := releasesBetweenFromURL(context.Background(), srv.URL, "v0.7.1", "v0.7.NaN", false)
	if err == nil {
		t.Fatal("expected error for malformed target version")
	}
	if !strings.Contains(err.Error(), "invalid target version") {
		t.Errorf("error should mention invalid target version, got: %v", err)
	}
}

func TestReleasesBetween_emptyAPI(t *testing.T) {
	srv := fixtureServer(t, []devRelease{})
	defer srv.Close()
	got, err := releasesBetweenFromURL(context.Background(), srv.URL, "v0.7.1", "v0.7.5", false)
	if err != nil {
		t.Fatalf("ReleasesBetween: %v", err)
	}
	if len(got) != 0 {
		t.Errorf("len(got) = %d, want 0", len(got))
	}
}

func TestReleasesBetween_paginationCap(t *testing.T) {
	// Always return a full page so the loop must hit maxReleasePages.
	full := make([]devRelease, releasesPerPage)
	for i := range full {
		// Use very high version numbers so the "older than installed" early
		// stop never triggers and we exercise the page cap.
		full[i] = devRelease{
			TagName: fmt.Sprintf("v9.9.%d", i+1),
			Assets: []Asset{
				{Name: assetName(), BrowserDownloadURL: expectedURLPrefix + "tag/" + assetName()},
				{Name: "checksums.txt", BrowserDownloadURL: expectedURLPrefix + "tag/checksums.txt"},
			},
		}
	}
	body, _ := json.Marshal(full)
	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		calls.Add(1)
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(body)
	}))
	defer srv.Close()

	_, err := releasesBetweenFromURL(context.Background(), srv.URL, "v0.0.0", "v99.99.99", false)
	if err != nil {
		t.Fatalf("ReleasesBetween: %v", err)
	}
	if got := calls.Load(); got != int32(maxReleasePages) {
		t.Errorf("calls = %d, want %d (page cap)", got, maxReleasePages)
	}
}
