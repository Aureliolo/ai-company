// Package verify provides container image signature and SLSA provenance
// verification using sigstore-go and go-containerregistry.
package verify

import (
	"fmt"
	"net/http"
	"time"

	"github.com/sigstore/sigstore-go/pkg/root"
	"github.com/sigstore/sigstore-go/pkg/tuf"
	"github.com/sigstore/sigstore-go/pkg/verify"
	"github.com/theupdateframework/go-tuf/v2/metadata/fetcher"
)

const (
	// ExpectedIssuer is the OIDC issuer for GitHub Actions keyless signing.
	ExpectedIssuer = "https://token.actions.githubusercontent.com"

	// ExpectedSANRegex matches the docker.yml workflow identity from the
	// SynthOrg repo on version tags or the main branch. Only accepts
	// signatures from the docker workflow — not from arbitrary workflows
	// or feature branches.
	ExpectedSANRegex = `^https://github\.com/Aureliolo/synthorg/\.github/workflows/docker\.yml@refs/(tags/v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.\-]+)?(\+[0-9A-Za-z.\-]+)?|heads/main)$`

	// RegistryHost is the container registry hosting SynthOrg images.
	RegistryHost = "ghcr.io"

	// ImageRepoPrefix is the repository prefix for all SynthOrg images.
	ImageRepoPrefix = "aureliolo/synthorg-"

	// TUFFetchTimeout bounds the TUF metadata fetch for the trusted root.
	TUFFetchTimeout = 30 * time.Second
)

// ImageNames returns the canonical set of SynthOrg service image suffixes.
// Returns a new slice each call to prevent callers from mutating the list.
func ImageNames() []string { return []string{"backend", "web", "sandbox"} }

// BuildVerifier creates a Sigstore verifier using the public good trusted
// root. The verifier requires SCTs, transparency log entries, and integrated
// timestamps (sigstore-go v1.1+ requirements).
func BuildVerifier() (*verify.Verifier, error) {
	opts := tuf.DefaultOptions()
	f := fetcher.NewDefaultFetcher()
	f.SetHTTPClient(&http.Client{Timeout: TUFFetchTimeout})
	opts = opts.WithFetcher(f)

	trustedRoot, err := root.FetchTrustedRootWithOptions(opts)
	if err != nil {
		return nil, fmt.Errorf("fetching sigstore trusted root: %w", err)
	}

	sev, err := verify.NewVerifier(trustedRoot,
		verify.WithSignedCertificateTimestamps(1),
		verify.WithTransparencyLog(1),
		verify.WithIntegratedTimestamps(1),
	)
	if err != nil {
		return nil, fmt.Errorf("creating sigstore verifier: %w", err)
	}
	return sev, nil
}

// BuildIdentityPolicy creates a certificate identity policy for verifying
// container image signatures from the SynthOrg repository's CI workflows.
func BuildIdentityPolicy() (verify.CertificateIdentity, error) {
	certID, err := verify.NewShortCertificateIdentity(
		ExpectedIssuer, "",
		"", ExpectedSANRegex,
	)
	if err != nil {
		return verify.CertificateIdentity{}, fmt.Errorf("creating certificate identity: %w", err)
	}
	return certID, nil
}
