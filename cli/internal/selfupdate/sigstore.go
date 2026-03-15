package selfupdate

import (
	"crypto/sha256"
	"fmt"
	"net/http"
	"time"

	protobundle "github.com/sigstore/protobuf-specs/gen/pb-go/bundle/v1"
	"github.com/sigstore/sigstore-go/pkg/bundle"
	"github.com/sigstore/sigstore-go/pkg/root"
	"github.com/sigstore/sigstore-go/pkg/tuf"
	"github.com/sigstore/sigstore-go/pkg/verify"
	"github.com/theupdateframework/go-tuf/v2/metadata/fetcher"
)

const (
	// expectedIssuer is the OIDC issuer for GitHub Actions keyless signing.
	expectedIssuer = "https://token.actions.githubusercontent.com"
	// expectedSANRegex matches the CLI release workflow identity for this repo.
	// Only accepts signatures from the cli.yml workflow on semver tag pushes.
	expectedSANRegex = `^https://github\.com/Aureliolo/synthorg/\.github/workflows/cli\.yml@refs/tags/v[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.\-]+)?(\+[0-9A-Za-z.\-]+)?$`
	// tufFetchTimeout bounds the TUF metadata fetch for the trusted root.
	tufFetchTimeout = 30 * time.Second
)

// verifySigstoreBundle verifies the Sigstore bundle for checksums.txt.
// It checks that:
// 1. The bundle signature is valid over the artifact digest
// 2. The signing certificate chains to Sigstore's trusted root
// 3. The signer identity matches the expected GitHub Actions workflow
// 4. The artifact digest matches the actual checksums data
func verifySigstoreBundle(checksumData, bundleData []byte) error {
	b, err := loadBundleFromJSON(bundleData)
	if err != nil {
		return fmt.Errorf("parsing sigstore bundle: %w", err)
	}

	// Use Sigstore's public good trusted root with a bounded HTTP timeout.
	opts := tuf.DefaultOptions()
	f := fetcher.NewDefaultFetcher()
	f.SetHTTPClient(&http.Client{Timeout: tufFetchTimeout})
	opts = opts.WithFetcher(f)
	trustedRoot, err := root.FetchTrustedRootWithOptions(opts)
	if err != nil {
		return fmt.Errorf("fetching sigstore trusted root: %w", err)
	}

	// Build verifier requiring SCTs, transparency log entries, and
	// integrated timestamps (required by sigstore-go v1.1+).
	sev, err := verify.NewVerifier(trustedRoot,
		verify.WithSignedCertificateTimestamps(1),
		verify.WithTransparencyLog(1),
		verify.WithIntegratedTimestamps(1),
	)
	if err != nil {
		return fmt.Errorf("creating sigstore verifier: %w", err)
	}

	// Build identity policy — must match GitHub Actions OIDC from our repo.
	certID, err := verify.NewShortCertificateIdentity(
		expectedIssuer, "",
		"", expectedSANRegex,
	)
	if err != nil {
		return fmt.Errorf("creating certificate identity: %w", err)
	}

	// Compute the artifact digest for verification.
	digest := sha256.Sum256(checksumData)

	// Verify the bundle against the identity and artifact digest.
	_, err = sev.Verify(b, verify.NewPolicy(
		verify.WithArtifactDigest("sha256", digest[:]),
		verify.WithCertificateIdentity(certID),
	))
	if err != nil {
		return fmt.Errorf("bundle verification failed: %w", err)
	}

	return nil
}

// loadBundleFromJSON parses a Sigstore bundle from JSON bytes.
func loadBundleFromJSON(data []byte) (*bundle.Bundle, error) {
	b := &bundle.Bundle{Bundle: new(protobundle.Bundle)}
	if err := b.UnmarshalJSON(data); err != nil {
		return nil, err
	}
	return b, nil
}
