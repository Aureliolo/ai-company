package verify

import "time"

// Configure applies the resolved tunables to this package's registry and
// timeout variables. Called exactly once from root.go PersistentPreRunE
// before any command handler consumes these values.
//
// Assignments are unconditional: every parameter overwrites the
// corresponding package variable. This makes Configure deterministic
// across repeated calls (e.g. in tests) -- passing empty strings / zero
// durations resets the package to those values rather than leaking the
// previous override. Callers that want defaults should pass the values
// from config.DefaultTunables(); callers that want a clean reset (tests)
// can do the same. Not thread-safe against concurrent reads.
func Configure(
	registryHost, imageRepoPrefix,
	dhiReg, postgresTag, natsTag string,
	tufFetch, attestationHTTP time.Duration,
) {
	RegistryHost = registryHost
	ImageRepoPrefix = imageRepoPrefix
	dhiRegistry = dhiReg
	postgresImageTag = postgresTag
	natsImageTag = natsTag
	TUFFetchTimeout = tufFetch
	attestationHTTPTimeout = attestationHTTP
}

// DHIRegistry returns the configured DHI registry hostname. Exposed so
// other packages (e.g. compose template generation) can reference the
// same value without re-declaring a constant.
func DHIRegistry() string { return dhiRegistry }

// PostgresImageTag returns the configured Postgres DHI image tag.
func PostgresImageTag() string { return postgresImageTag }

// NATSImageTag returns the configured NATS DHI image tag.
func NATSImageTag() string { return natsImageTag }
