package verify

import "time"

// Configure applies the resolved tunables to this package's registry and
// timeout variables. Called exactly once from root.go PersistentPreRunE
// before any command handler consumes these values. Safe to call more
// than once (e.g. in tests) but not thread-safe against concurrent reads.
func Configure(
	registryHost, imageRepoPrefix,
	dhiReg, postgresTag, natsTag string,
	tufFetch, attestationHTTP time.Duration,
) {
	if registryHost != "" {
		RegistryHost = registryHost
	}
	if imageRepoPrefix != "" {
		ImageRepoPrefix = imageRepoPrefix
	}
	if dhiReg != "" {
		dhiRegistry = dhiReg
	}
	if postgresTag != "" {
		postgresImageTag = postgresTag
	}
	if natsTag != "" {
		natsImageTag = natsTag
	}
	if tufFetch > 0 {
		TUFFetchTimeout = tufFetch
	}
	if attestationHTTP > 0 {
		attestationHTTPTimeout = attestationHTTP
	}
}

// DHIRegistry returns the configured DHI registry hostname. Exposed so
// other packages (e.g. compose template generation) can reference the
// same value without re-declaring a constant.
func DHIRegistry() string { return dhiRegistry }

// PostgresImageTag returns the configured Postgres DHI image tag.
func PostgresImageTag() string { return postgresImageTag }

// NATSImageTag returns the configured NATS DHI image tag.
func NATSImageTag() string { return natsImageTag }
