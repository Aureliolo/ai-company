package verify

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/sigstore/sigstore-go/pkg/verify"
)

const (
	// SLSAProvenancePredicatePrefix is the prefix for SLSA provenance predicates.
	// Exported so selfupdate can reuse the same constant.
	SLSAProvenancePredicatePrefix = "https://slsa.dev/provenance/"

	// DSSEPayloadType is the expected DSSE envelope payload type for in-toto statements.
	// Exported so selfupdate can reuse the same constant.
	DSSEPayloadType = "application/vnd.in-toto+json"

	// defaultGitHubAPIBase is the base URL for the GitHub REST API.
	defaultGitHubAPIBase = "https://api.github.com"

	// githubAttestationOwnerRepo is the GitHub owner/repo for attestation lookups.
	// Derived from the image repository prefix (aureliolo/synthorg-*).
	githubAttestationOwnerRepo = "Aureliolo/synthorg"

	// attestationHTTPTimeout bounds individual HTTP requests to the GitHub API.
	attestationHTTPTimeout = 30 * time.Second

	// maxAttestationResponseBytes caps the GitHub attestation API response
	// to prevent memory exhaustion from malicious or oversized responses.
	maxAttestationResponseBytes = 5 << 20 // 5MB
)

// ErrNoProvenanceAttestations indicates that no SLSA provenance attestations
// were found for an image via the GitHub attestation API. This is distinct
// from a cryptographic verification failure.
var ErrNoProvenanceAttestations = errors.New("no SLSA provenance attestations found")

// githubAPIBase is the effective base URL for the GitHub REST API.
// Defaults to the production URL; tests override via setGitHubAPIBase.
var githubAPIBase = defaultGitHubAPIBase //nolint:gochecknoglobals // test override

// setGitHubAPIBase overrides the GitHub API base URL (for tests only).
func setGitHubAPIBase(base string) { githubAPIBase = base }

// VerifyProvenance fetches SLSA provenance attestations from the GitHub
// attestation API and verifies the Sigstore bundle against the public
// transparency log and expected identity.
//
// The image ref must have a resolved Digest.
func VerifyProvenance(ctx context.Context, ref ImageRef, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	if ref.Digest == "" {
		return fmt.Errorf("image digest not resolved")
	}

	bundles, err := fetchGitHubAttestations(ctx, ref.Digest)
	if err != nil {
		return err
	}

	// Try each attestation bundle -- first successful verification wins.
	var errs []error
	for i, bundleJSON := range bundles {
		if err := verifyProvenanceBundle(bundleJSON, ref.Digest, sev, certID); err != nil {
			errs = append(errs, fmt.Errorf("attestation[%d]: %w", i, err))
			continue
		}
		return nil
	}
	return fmt.Errorf("no valid SLSA provenance attestation for %s: %w", ref, errors.Join(errs...))
}

// githubAttestationResponse is the structure returned by the GitHub
// attestation API (GET /repos/OWNER/REPO/attestations/SUBJECT_DIGEST).
type githubAttestationResponse struct {
	Attestations []struct {
		Bundle json.RawMessage `json:"bundle"`
	} `json:"attestations"`
}

// fetchGitHubAttestations queries the GitHub attestation API for Sigstore
// bundles associated with the given image digest.
func fetchGitHubAttestations(ctx context.Context, digest string) ([]json.RawMessage, error) {
	url := fmt.Sprintf("%s/repos/%s/attestations/%s", githubAPIBase, githubAttestationOwnerRepo, digest)

	reqCtx, cancel := context.WithTimeout(ctx, attestationHTTPTimeout)
	defer cancel()

	req, err := http.NewRequestWithContext(reqCtx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("creating attestation request: %w", err)
	}
	req.Header.Set("Accept", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("fetching attestations from GitHub API: %w", err)
	}
	defer func() { _ = resp.Body.Close() }()

	if resp.StatusCode == http.StatusNotFound {
		return nil, fmt.Errorf("%w via GitHub API for digest %s", ErrNoProvenanceAttestations, digest)
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("GitHub attestation API returned HTTP %d for digest %s", resp.StatusCode, digest)
	}

	body, err := io.ReadAll(io.LimitReader(resp.Body, maxAttestationResponseBytes+1))
	if err != nil {
		return nil, fmt.Errorf("reading attestation response: %w", err)
	}
	if int64(len(body)) > maxAttestationResponseBytes {
		return nil, fmt.Errorf("attestation response too large (>%d bytes)", maxAttestationResponseBytes)
	}

	var apiResp githubAttestationResponse
	if err := json.Unmarshal(body, &apiResp); err != nil {
		return nil, fmt.Errorf("parsing attestation response: %w", err)
	}

	if len(apiResp.Attestations) == 0 {
		return nil, fmt.Errorf("%w via GitHub API for digest %s", ErrNoProvenanceAttestations, digest)
	}

	bundles := make([]json.RawMessage, 0, len(apiResp.Attestations))
	for _, a := range apiResp.Attestations {
		if len(a.Bundle) > 0 {
			bundles = append(bundles, a.Bundle)
		}
	}
	if len(bundles) == 0 {
		return nil, fmt.Errorf("%w (no bundles in response) for digest %s", ErrNoProvenanceAttestations, digest)
	}
	return bundles, nil
}

// verifyProvenanceBundle parses and verifies a single Sigstore bundle from
// the GitHub attestation API against the expected identity and image digest.
func verifyProvenanceBundle(bundleJSON json.RawMessage, digest string, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	b, err := loadBundle(bundleJSON)
	if err != nil {
		return fmt.Errorf("parsing provenance bundle: %w", err)
	}

	digestAlgo, digestHex, err := parseDigest(digest)
	if err != nil {
		return err
	}

	// Verify the bundle cryptographically: check the signature, certificate
	// identity (must be our docker.yml workflow), and artifact digest.
	_, err = sev.Verify(b, verify.NewPolicy(
		verify.WithArtifactDigest(digestAlgo, digestHex),
		verify.WithCertificateIdentity(certID),
	))
	if err != nil {
		return fmt.Errorf("provenance bundle verification failed: %w", err)
	}

	return nil
}
