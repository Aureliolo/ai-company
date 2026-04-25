package selfupdate

import (
	"context"
	"fmt"
	"net/url"
	"sort"
	"strconv"
	"strings"
)

const (
	// releasesPerPage is the page size used by listReleases. GitHub allows
	// up to 100 entries per page on the releases listing endpoint.
	releasesPerPage = 100

	// maxReleasePages bounds how far back the walk will read. 5 pages * 100
	// entries = up to 500 releases, which covers years of history at the
	// current cadence. Beyond that, the early-stop "older than installed"
	// check means real-world walks finish in 1-2 pages.
	maxReleasePages = 5
)

// ReleasesBetween returns the releases in (installed, target], ordered
// oldest-to-newest. Drafts are excluded; pre-releases are excluded unless
// includeDev is true. Returns an empty slice (no error) when no releases
// fall in the range.
func ReleasesBetween(ctx context.Context, installed, target string, includeDev bool) ([]Release, error) {
	return releasesBetweenFromURL(ctx, releasesBaseURL(), installed, target, includeDev)
}

// releasesBaseURL returns the GitHub API endpoint for listing releases. Kept
// as a function so tests can inject an httptest URL via releasesBetweenFromURL.
func releasesBaseURL() string {
	return "https://api.github.com/repos/" + repoSlug + "/releases"
}

// releasesBetweenFromURL is the testable core of ReleasesBetween. baseURL is
// the endpoint to paginate against (without per_page / page query params --
// listReleases adds those).
func releasesBetweenFromURL(ctx context.Context, baseURL, installed, target string, includeDev bool) ([]Release, error) {
	all, err := listReleases(ctx, baseURL, installed)
	if err != nil {
		return nil, err
	}

	filtered := make([]Release, 0, len(all))
	for _, r := range all {
		if r.Draft {
			continue
		}
		if !includeDev && isDevTag(r.TagName) {
			continue
		}
		// Strictly above installed.
		cmpInst, err := compareWithDev(r.TagName, installed)
		if err != nil {
			continue // malformed tag -- skip silently
		}
		if cmpInst <= 0 {
			continue
		}
		// At or below target.
		cmpTar, err := compareWithDev(r.TagName, target)
		if err != nil {
			continue
		}
		if cmpTar > 0 {
			continue
		}
		filtered = append(filtered, Release{
			TagName:     r.TagName,
			Body:        r.Body,
			PublishedAt: r.PublishedAt,
			Assets:      r.Assets,
		})
	}

	sort.SliceStable(filtered, func(i, j int) bool {
		c, _ := compareWithDev(filtered[i].TagName, filtered[j].TagName)
		return c < 0
	})

	return filtered, nil
}

// listReleases paginates the releases endpoint with per_page=releasesPerPage
// up to maxReleasePages. Stops early when:
//   - a page returns < releasesPerPage entries (last page)
//   - every entry on a page sorts at or below installed (no point reading
//     deeper history)
//
// Returns the union of all fetched pages (unsorted; caller filters + sorts).
func listReleases(ctx context.Context, baseURL, installed string) ([]devRelease, error) {
	var combined []devRelease
	for page := 1; page <= maxReleasePages; page++ {
		pageURL, err := buildPageURL(baseURL, page)
		if err != nil {
			return nil, fmt.Errorf("building page URL: %w", err)
		}
		entries, err := fetchJSON[[]devRelease](ctx, pageURL)
		if err != nil {
			return nil, err
		}
		if len(entries) == 0 {
			break
		}
		combined = append(combined, entries...)
		if len(entries) < releasesPerPage {
			break
		}
		if installed != "" && allAtOrBelow(entries, installed) {
			break
		}
	}
	return combined, nil
}

// buildPageURL appends per_page + page query params to baseURL. Returns the
// formatted URL or an error if baseURL is malformed.
func buildPageURL(baseURL string, page int) (string, error) {
	parsed, err := url.Parse(baseURL)
	if err != nil {
		return "", err
	}
	q := parsed.Query()
	q.Set("per_page", strconv.Itoa(releasesPerPage))
	q.Set("page", strconv.Itoa(page))
	parsed.RawQuery = q.Encode()
	return parsed.String(), nil
}

// allAtOrBelow reports whether every release in entries sorts at or below
// installed. Used as an early-stop signal: if the entire current page is
// older than what the user already has, deeper pages cannot contain anything
// new.
func allAtOrBelow(entries []devRelease, installed string) bool {
	for _, r := range entries {
		cmp, err := compareWithDev(r.TagName, installed)
		if err != nil {
			// Malformed tag: be conservative and keep paginating.
			return false
		}
		if cmp > 0 {
			return false
		}
	}
	return true
}

// isDevTag reports whether a tag carries the "-dev.N" pre-release suffix.
func isDevTag(tag string) bool {
	return strings.Contains(tag, "-dev.")
}
