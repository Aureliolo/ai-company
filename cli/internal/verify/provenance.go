package verify

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"strings"

	"github.com/google/go-containerregistry/pkg/name"
	v1 "github.com/google/go-containerregistry/pkg/v1"
	"github.com/google/go-containerregistry/pkg/v1/remote"
	"github.com/sigstore/sigstore-go/pkg/verify"
)

const (
	// slsaProvenancePredicatePrefix is the prefix for SLSA provenance predicates.
	slsaProvenancePredicatePrefix = "https://slsa.dev/provenance/"

	// dssePayloadType is the expected DSSE envelope payload type for in-toto statements.
	dssePayloadType = "application/vnd.in-toto+json"

	// referrerArtifactType is the OCI artifact type for SLSA provenance attestations
	// created by actions/attest-build-provenance.
	referrerArtifactType = "application/vnd.in-toto+json"
)

// VerifyProvenance fetches SLSA provenance attestations from the OCI registry
// (pushed as referrers by actions/attest-build-provenance) and verifies the
// DSSE envelope against the Sigstore transparency log and expected identity.
//
// The image ref must have a resolved Digest.
func VerifyProvenance(ctx context.Context, ref ImageRef, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	if ref.Digest == "" {
		return fmt.Errorf("image digest not resolved")
	}

	attestationDescs, err := findAttestations(ctx, ref)
	if err != nil {
		return err
	}

	// Try each attestation — verify the first one that passes.
	var lastErr error
	for _, desc := range attestationDescs {
		if err := verifyAttestation(ctx, ref, desc, sev, certID); err != nil {
			lastErr = err
			continue
		}
		return nil // verified successfully
	}
	return fmt.Errorf("no valid SLSA provenance attestation for %s: %w", ref, lastErr)
}

// findAttestations queries OCI referrers and returns descriptors for in-toto
// attestation artifacts associated with the given image.
func findAttestations(ctx context.Context, ref ImageRef) ([]v1.Descriptor, error) {
	digestRef := fmt.Sprintf("%s/%s@%s", ref.Registry, ref.Repository, ref.Digest)
	parsed, err := name.NewDigest(digestRef)
	if err != nil {
		return nil, fmt.Errorf("parsing digest reference %q: %w", digestRef, err)
	}

	referrerIdx, err := remote.Referrers(parsed, remote.WithContext(ctx))
	if err != nil {
		return nil, fmt.Errorf("querying referrers for %s: %w", ref, err)
	}

	manifest, err := referrerIdx.IndexManifest()
	if err != nil {
		return nil, fmt.Errorf("reading referrer index manifest: %w", err)
	}

	var descs []v1.Descriptor
	for _, desc := range manifest.Manifests {
		if desc.ArtifactType == referrerArtifactType {
			descs = append(descs, desc)
		}
	}
	if len(descs) == 0 {
		return nil, fmt.Errorf("no SLSA provenance attestations found for %s", ref)
	}
	return descs, nil
}

// verifyAttestation fetches and verifies a single attestation manifest.
func verifyAttestation(ctx context.Context, ref ImageRef, desc v1.Descriptor, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	img, err := fetchAttestationImage(ctx, ref, desc)
	if err != nil {
		return err
	}

	envelope, err := extractDSSEEnvelope(img)
	if err != nil {
		return err
	}

	if err := validateSLSAPredicate(envelope); err != nil {
		return err
	}

	return verifyAttestationBundle(img, ref.Digest, sev, certID)
}

// fetchAttestationImage fetches the attestation image by its descriptor digest.
func fetchAttestationImage(ctx context.Context, ref ImageRef, desc v1.Descriptor) (v1.Image, error) {
	attestRef := fmt.Sprintf("%s/%s@%s", ref.Registry, ref.Repository, desc.Digest.String())
	parsed, err := name.NewDigest(attestRef)
	if err != nil {
		return nil, fmt.Errorf("parsing attestation reference: %w", err)
	}

	img, err := remote.Image(parsed, remote.WithContext(ctx))
	if err != nil {
		return nil, fmt.Errorf("fetching attestation image: %w", err)
	}
	return img, nil
}

// extractDSSEEnvelope reads and parses the DSSE envelope from the first layer
// of an attestation image.
func extractDSSEEnvelope(img v1.Image) (dsseEnvelope, error) {
	layers, err := img.Layers()
	if err != nil {
		return dsseEnvelope{}, fmt.Errorf("reading attestation layers: %w", err)
	}
	if len(layers) == 0 {
		return dsseEnvelope{}, fmt.Errorf("attestation has no layers")
	}

	layerReader, err := layers[0].Uncompressed()
	if err != nil {
		return dsseEnvelope{}, fmt.Errorf("reading attestation layer: %w", err)
	}
	defer func() { _ = layerReader.Close() }()

	var envelope dsseEnvelope
	if err := json.NewDecoder(layerReader).Decode(&envelope); err != nil {
		return dsseEnvelope{}, fmt.Errorf("decoding DSSE envelope: %w", err)
	}
	return envelope, nil
}

// validateSLSAPredicate checks that a DSSE envelope contains a SLSA provenance
// predicate type.
func validateSLSAPredicate(envelope dsseEnvelope) error {
	if envelope.PayloadType != dssePayloadType {
		return fmt.Errorf("unexpected DSSE payload type %q, want %q", envelope.PayloadType, dssePayloadType)
	}

	payloadBytes, err := base64.StdEncoding.DecodeString(envelope.Payload)
	if err != nil {
		return fmt.Errorf("decoding DSSE payload: %w", err)
	}

	var statement inTotoStatement
	if err := json.Unmarshal(payloadBytes, &statement); err != nil {
		return fmt.Errorf("parsing in-toto statement: %w", err)
	}
	if !strings.HasPrefix(statement.PredicateType, slsaProvenancePredicatePrefix) {
		return fmt.Errorf("unexpected predicate type %q, want prefix %q", statement.PredicateType, slsaProvenancePredicatePrefix)
	}
	return nil
}

// verifyAttestationBundle looks for a Sigstore bundle in the attestation
// manifest or layer annotations and verifies it. Returns an error if no
// bundle is found — structural validation alone is insufficient.
func verifyAttestationBundle(img v1.Image, digest string, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	attestManifest, err := img.Manifest()
	if err != nil {
		return fmt.Errorf("reading attestation manifest: %w", err)
	}

	// Look for Sigstore bundle in manifest annotations.
	if bundleJSON, ok := attestManifest.Annotations["dev.sigstore.cosign/bundle"]; ok {
		return verifyProvenanceBundleWith([]byte(bundleJSON), digest, sev, certID)
	}

	// Also check layer annotations.
	if len(attestManifest.Layers) > 0 {
		if bundleJSON, ok := attestManifest.Layers[0].Annotations["dev.sigstore.cosign/bundle"]; ok {
			return verifyProvenanceBundleWith([]byte(bundleJSON), digest, sev, certID)
		}
	}

	return fmt.Errorf("no sigstore bundle found in attestation — cannot cryptographically verify provenance")
}

// verifyProvenanceBundleWith verifies a Sigstore bundle from an attestation
// using the provided verifier and identity policy.
func verifyProvenanceBundleWith(bundleJSON []byte, digest string, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	b, err := loadBundle(bundleJSON)
	if err != nil {
		return fmt.Errorf("parsing provenance bundle: %w", err)
	}

	digestAlgo, digestHex, err := parseDigest(digest)
	if err != nil {
		return err
	}

	_, err = sev.Verify(b, verify.NewPolicy(
		verify.WithArtifactDigest(digestAlgo, digestHex),
		verify.WithCertificateIdentity(certID),
	))
	if err != nil {
		return fmt.Errorf("provenance bundle verification failed: %w", err)
	}

	return nil
}

// dsseEnvelope is a minimal DSSE (Dead Simple Signing Envelope) structure.
type dsseEnvelope struct {
	PayloadType string `json:"payloadType"`
	Payload     string `json:"payload"`
}

// inTotoStatement is a minimal in-toto statement for predicate type extraction.
type inTotoStatement struct {
	PredicateType string `json:"predicateType"`
}
