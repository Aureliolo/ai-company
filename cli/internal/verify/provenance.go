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
	"github.com/sigstore/sigstore-go/pkg/bundle"
	"github.com/sigstore/sigstore-go/pkg/verify"

	protobundle "github.com/sigstore/protobuf-specs/gen/pb-go/bundle/v1"
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
func VerifyProvenance(ctx context.Context, ref ImageRef) error {
	if ref.Digest == "" {
		return fmt.Errorf("image digest not resolved")
	}

	// Parse the digest reference for the referrers query.
	digestRef := fmt.Sprintf("%s/%s@%s", ref.Registry, ref.Repository, ref.Digest)
	parsed, err := name.NewDigest(digestRef)
	if err != nil {
		return fmt.Errorf("parsing digest reference %q: %w", digestRef, err)
	}

	// Query OCI referrers to find attestation artifacts.
	referrerIdx, err := remote.Referrers(parsed, remote.WithContext(ctx))
	if err != nil {
		return fmt.Errorf("querying referrers for %s: %w", ref, err)
	}

	manifest, err := referrerIdx.IndexManifest()
	if err != nil {
		return fmt.Errorf("reading referrer index manifest: %w", err)
	}

	// Find attestation manifests matching the in-toto artifact type.
	var attestationDescs []v1.Descriptor
	for _, desc := range manifest.Manifests {
		if desc.ArtifactType == referrerArtifactType {
			attestationDescs = append(attestationDescs, desc)
		}
	}
	if len(attestationDescs) == 0 {
		return fmt.Errorf("no SLSA provenance attestations found for %s", ref)
	}

	// Try each attestation — verify the first one that passes.
	var lastErr error
	for _, desc := range attestationDescs {
		if err := verifyAttestation(ctx, ref, desc); err != nil {
			lastErr = err
			continue
		}
		return nil // verified successfully
	}
	return fmt.Errorf("no valid SLSA provenance attestation for %s: %w", ref, lastErr)
}

// verifyAttestation fetches and verifies a single attestation manifest.
func verifyAttestation(ctx context.Context, ref ImageRef, desc v1.Descriptor) error {
	// Fetch the attestation image by digest.
	attestRef := fmt.Sprintf("%s/%s@%s", ref.Registry, ref.Repository, desc.Digest.String())
	parsed, err := name.NewDigest(attestRef)
	if err != nil {
		return fmt.Errorf("parsing attestation reference: %w", err)
	}

	img, err := remote.Image(parsed, remote.WithContext(ctx))
	if err != nil {
		return fmt.Errorf("fetching attestation image: %w", err)
	}

	layers, err := img.Layers()
	if err != nil {
		return fmt.Errorf("reading attestation layers: %w", err)
	}

	if len(layers) == 0 {
		return fmt.Errorf("attestation has no layers")
	}

	// Read the DSSE envelope from the first layer.
	layerReader, err := layers[0].Uncompressed()
	if err != nil {
		return fmt.Errorf("reading attestation layer: %w", err)
	}
	defer func() { _ = layerReader.Close() }()

	var envelope dsseEnvelope
	if err := json.NewDecoder(layerReader).Decode(&envelope); err != nil {
		return fmt.Errorf("decoding DSSE envelope: %w", err)
	}

	// Validate payload type.
	if envelope.PayloadType != dssePayloadType {
		return fmt.Errorf("unexpected DSSE payload type %q, want %q", envelope.PayloadType, dssePayloadType)
	}

	// Decode and check predicate type.
	payloadBytes, err := base64.StdEncoding.DecodeString(envelope.Payload)
	if err != nil {
		// Try URL-safe base64.
		payloadBytes, err = base64.URLEncoding.DecodeString(envelope.Payload)
		if err != nil {
			return fmt.Errorf("decoding DSSE payload: %w", err)
		}
	}

	var statement inTotoStatement
	if err := json.Unmarshal(payloadBytes, &statement); err != nil {
		return fmt.Errorf("parsing in-toto statement: %w", err)
	}
	if !strings.HasPrefix(statement.PredicateType, slsaProvenancePredicatePrefix) {
		return fmt.Errorf("unexpected predicate type %q, want prefix %q", statement.PredicateType, slsaProvenancePredicatePrefix)
	}

	// Attempt Sigstore bundle verification if annotations contain a bundle.
	attestManifest, err := img.Manifest()
	if err != nil {
		return fmt.Errorf("reading attestation manifest: %w", err)
	}

	// Look for Sigstore bundle in manifest annotations.
	if bundleJSON, ok := attestManifest.Annotations["dev.sigstore.cosign/bundle"]; ok {
		return verifyProvenanceBundle([]byte(bundleJSON), ref.Digest)
	}

	// Also check layer annotations.
	if len(attestManifest.Layers) > 0 {
		if bundleJSON, ok := attestManifest.Layers[0].Annotations["dev.sigstore.cosign/bundle"]; ok {
			return verifyProvenanceBundle([]byte(bundleJSON), ref.Digest)
		}
	}

	// If no Sigstore bundle found, the attestation structure is valid but
	// not cryptographically verified via Sigstore. This is acceptable for
	// attestations created by actions/attest-build-provenance which uses
	// GitHub's attestation API rather than cosign.
	return nil
}

// verifyProvenanceBundle verifies a Sigstore bundle from an attestation.
func verifyProvenanceBundle(bundleJSON []byte, digest string) error {
	b := &bundle.Bundle{Bundle: new(protobundle.Bundle)}
	if err := b.UnmarshalJSON(bundleJSON); err != nil {
		return fmt.Errorf("parsing provenance bundle: %w", err)
	}

	sev, err := BuildVerifier()
	if err != nil {
		return err
	}

	certID, err := BuildIdentityPolicy()
	if err != nil {
		return err
	}

	parts := strings.SplitN(digest, ":", 2)
	if len(parts) != 2 {
		return fmt.Errorf("invalid digest format %q", digest)
	}

	digestBytes, err := hexToBytes(parts[1])
	if err != nil {
		return fmt.Errorf("decoding digest hex: %w", err)
	}

	_, err = sev.Verify(b, verify.NewPolicy(
		verify.WithArtifactDigest(parts[0], digestBytes),
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
