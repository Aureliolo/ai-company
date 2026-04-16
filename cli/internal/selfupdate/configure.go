package selfupdate

import (
	"net/http"
	"time"
)

// Configure applies the resolved tunables to this package's size limits
// and HTTP timeouts, rebuilding the shared API client with the new
// timeout. Called exactly once from root.go PersistentPreRunE before
// any self-update operation runs.
//
// Assignments are unconditional so Configure is deterministic across
// repeated calls (tests reset by passing defaults from
// config.DefaultTunables()); guard-clause "preserve prior value" logic
// would otherwise leak overrides between test cases.
func Configure(
	maxAPIResp, maxBinary, maxArchiveEntry int64,
	httpTimeoutVal, apiTimeoutVal, tufFetch time.Duration,
) {
	maxAPIResponseBytes = maxAPIResp
	maxBinaryBytes = maxBinary
	maxArchiveEntryBytes = maxArchiveEntry
	httpTimeout = httpTimeoutVal
	apiTimeout = apiTimeoutVal
	apiClient = &http.Client{
		Timeout:       apiTimeout,
		CheckRedirect: checkRedirectHost,
	}
	tufFetchTimeout = tufFetch
}
