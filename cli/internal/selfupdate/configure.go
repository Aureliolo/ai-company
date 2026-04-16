package selfupdate

import (
	"net/http"
	"time"
)

// Configure applies the resolved tunables to this package's size limits
// and HTTP timeouts, rebuilding the shared API client with the new
// timeout. Called exactly once from root.go PersistentPreRunE before
// any self-update operation runs. Safe to call more than once.
func Configure(
	maxAPIResp, maxBinary, maxArchiveEntry int64,
	httpTimeoutVal, apiTimeoutVal, tufFetch time.Duration,
) {
	if maxAPIResp > 0 {
		maxAPIResponseBytes = maxAPIResp
	}
	if maxBinary > 0 {
		maxBinaryBytes = maxBinary
	}
	if maxArchiveEntry > 0 {
		maxArchiveEntryBytes = maxArchiveEntry
	}
	if httpTimeoutVal > 0 {
		httpTimeout = httpTimeoutVal
	}
	if apiTimeoutVal > 0 {
		apiTimeout = apiTimeoutVal
		apiClient = &http.Client{
			Timeout:       apiTimeout,
			CheckRedirect: checkRedirectHost,
		}
	}
	if tufFetch > 0 {
		tufFetchTimeout = tufFetch
	}
}
