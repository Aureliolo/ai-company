package verify

import (
	"context"
	"encoding/hex"
	"errors"
	"fmt"
	"io"
	"strings"

	"github.com/google/go-containerregistry/pkg/name"
	v1 "github.com/google/go-containerregistry/pkg/v1"
	"github.com/google/go-containerregistry/pkg/v1/remote"
	"github.com/sigstore/sigstore-go/pkg/verify"
)

const (
	// cosignV3BundleArtifactType is the OCI artifact type for cosign v3
	// signatures stored using the new bundle format (default in cosign v3).
	// The bundle is stored as a layer, not in annotations.
	cosignV3BundleArtifactType = "application/vnd.dev.sigstore.bundle.v0.3+json"

	// cosignV2ArtifactType is the legacy OCI artifact type for cosign v2
	// signatures stored as simplesigning payloads with bundle in annotations.
	cosignV2ArtifactType = "application/vnd.dev.cosign.simplesigning.v1+json"

	// cosignBundleAnnotation is the annotation key where cosign v2 stores
	// the Sigstore bundle in manifest or layer annotations.
	cosignBundleAnnotation = "dev.sigstore.cosign/bundle"

	// maxBundleBytes caps the size of a cosign bundle read from a registry
	// layer to prevent memory exhaustion from malicious registries.
	// Typical Sigstore bundles are ~10KB; 1MB is generous.
	maxBundleBytes = 1 << 20
)

// ErrNoCosignSignatures indicates that no cosign signature referrers were
// found for an image. This is distinct from a cryptographic verification
// failure -- it means the image was not signed or signatures are not
// discoverable via the OCI referrers API.
var ErrNoCosignSignatures = errors.New("no cosign signatures found")

// isCosignSignatureArtifact returns true if the descriptor's artifact type
// matches a known cosign signature format (v3 bundle or v2 simplesigning).
func isCosignSignatureArtifact(desc v1.Descriptor) bool {
	return desc.ArtifactType == cosignV3BundleArtifactType || desc.ArtifactType == cosignV2ArtifactType
}

// VerifyCosignSignature fetches cosign keyless signatures for the given image
// via the OCI referrers API (with tag-based fallback) and verifies them
// against the Sigstore public transparency log.
//
// Supports both cosign v3 (bundle as layer) and cosign v2 (bundle in
// annotations) signature formats.
//
// The image ref must have a resolved Digest. The provided verifier and
// identity policy are reused across images.
func VerifyCosignSignature(ctx context.Context, ref ImageRef, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	if ref.Digest == "" {
		return fmt.Errorf("image digest not resolved")
	}

	sigDescs, err := findCosignSignatures(ctx, ref)
	if err != nil {
		return err
	}

	// Try each signature referrer -- first successful verification wins.
	var errs []error
	for i, desc := range sigDescs {
		if err := verifyCosignReferrer(ctx, ref, desc, sev, certID); err != nil {
			errs = append(errs, fmt.Errorf("referrer[%d]: %w", i, err))
			continue
		}
		return nil
	}
	return fmt.Errorf("no valid cosign signature for %s: %w", ref, errors.Join(errs...))
}

// findCosignSignatures queries OCI referrers (with tag-based fallback) and
// returns descriptors for cosign signature artifacts associated with the
// given image.
func findCosignSignatures(ctx context.Context, ref ImageRef) ([]v1.Descriptor, error) {
	digestRef := fmt.Sprintf("%s/%s@%s", ref.Registry, ref.Repository, ref.Digest)
	parsed, err := name.NewDigest(digestRef)
	if err != nil {
		return nil, fmt.Errorf("parsing digest reference %q: %w", digestRef, err)
	}

	referrerIdx, err := remote.Referrers(parsed, remote.WithContext(ctx))
	if err != nil {
		return nil, fmt.Errorf("querying referrers for cosign signatures of %s: %w", ref, err)
	}

	manifest, err := referrerIdx.IndexManifest()
	if err != nil {
		return nil, fmt.Errorf("reading referrer index manifest: %w", err)
	}

	var descs []v1.Descriptor
	for _, desc := range manifest.Manifests {
		if isCosignSignatureArtifact(desc) {
			descs = append(descs, desc)
		}
	}
	if len(descs) == 0 {
		return nil, fmt.Errorf("%w for %s", ErrNoCosignSignatures, ref)
	}
	return descs, nil
}

// verifyCosignReferrer fetches a single cosign signature referrer image,
// extracts the Sigstore bundle, and verifies it. Supports both v3 (bundle
// as layer content) and v2 (bundle in annotations) formats.
func verifyCosignReferrer(ctx context.Context, ref ImageRef, desc v1.Descriptor, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	sigRef := fmt.Sprintf("%s/%s@%s", ref.Registry, ref.Repository, desc.Digest.String())
	parsed, err := name.NewDigest(sigRef)
	if err != nil {
		return fmt.Errorf("parsing signature reference: %w", err)
	}

	img, err := remote.Image(parsed, remote.WithContext(ctx))
	if err != nil {
		return fmt.Errorf("fetching cosign signature image: %w", err)
	}

	// Try v3 bundle format first (bundle is raw layer content).
	if desc.ArtifactType == cosignV3BundleArtifactType {
		return verifyCosignV3Bundle(img, ref.Digest, sev, certID)
	}

	// Fall back to v2 format (bundle in annotations).
	return verifyCosignV2Bundle(img, ref.Digest, sev, certID)
}

// verifyCosignV3Bundle extracts and verifies a cosign v3 Sigstore bundle
// stored as the first layer of the referrer image.
func verifyCosignV3Bundle(img v1.Image, digest string, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	layers, err := img.Layers()
	if err != nil {
		return fmt.Errorf("reading signature layers: %w", err)
	}
	if len(layers) == 0 {
		return fmt.Errorf("cosign v3 signature has no layers")
	}

	// The bundle is the raw content of the first layer.
	reader, err := layers[0].Uncompressed()
	if err != nil {
		return fmt.Errorf("reading bundle layer: %w", err)
	}
	defer func() { _ = reader.Close() }()

	bundleJSON, err := io.ReadAll(io.LimitReader(reader, maxBundleBytes+1))
	if err != nil {
		return fmt.Errorf("reading bundle content: %w", err)
	}
	if int64(len(bundleJSON)) > maxBundleBytes {
		return fmt.Errorf("cosign bundle too large (>%d bytes)", maxBundleBytes)
	}

	return verifyCosignBundleWith(bundleJSON, digest, sev, certID)
}

// verifyCosignV2Bundle extracts and verifies a cosign v2 Sigstore bundle
// stored in manifest or layer annotations.
func verifyCosignV2Bundle(img v1.Image, digest string, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	sigManifest, err := img.Manifest()
	if err != nil {
		return fmt.Errorf("reading cosign signature manifest: %w", err)
	}

	// Check manifest-level annotations first, then layer annotations.
	var bundleErrs []error

	if bundleJSON, ok := sigManifest.Annotations[cosignBundleAnnotation]; ok {
		if err := verifyCosignBundleWith([]byte(bundleJSON), digest, sev, certID); err != nil {
			bundleErrs = append(bundleErrs, fmt.Errorf("manifest bundle: %w", err))
		} else {
			return nil
		}
	}

	for i := range sigManifest.Layers {
		if bundleJSON, ok := sigManifest.Layers[i].Annotations[cosignBundleAnnotation]; ok {
			if err := verifyCosignBundleWith([]byte(bundleJSON), digest, sev, certID); err != nil {
				bundleErrs = append(bundleErrs, fmt.Errorf("layer[%d] bundle: %w", i, err))
			} else {
				return nil
			}
		}
	}

	if len(bundleErrs) > 0 {
		return fmt.Errorf("cosign v2 bundle verification failed: %w", errors.Join(bundleErrs...))
	}
	return fmt.Errorf("no cosign bundle annotation found in signature manifest")
}

// verifyCosignBundleWith verifies a cosign Sigstore bundle against the expected
// identity and image digest using the provided verifier and identity policy.
func verifyCosignBundleWith(bundleJSON []byte, digest string, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	b, err := loadBundle(bundleJSON)
	if err != nil {
		return fmt.Errorf("parsing cosign bundle: %w", err)
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
		return fmt.Errorf("cosign bundle verification failed: %w", err)
	}

	return nil
}

// parseDigest splits a digest string into algorithm and hex bytes.
// Only sha256 is supported; other algorithms are rejected.
func parseDigest(digest string) (string, []byte, error) {
	parts := strings.SplitN(digest, ":", 2)
	if len(parts) != 2 {
		return "", nil, fmt.Errorf("invalid digest format %q", digest)
	}
	if parts[0] != "sha256" {
		return "", nil, fmt.Errorf("unsupported digest algorithm %q, only sha256 supported", parts[0])
	}

	digestBytes, err := hex.DecodeString(parts[1])
	if err != nil {
		return "", nil, fmt.Errorf("decoding digest hex: %w", err)
	}
	return parts[0], digestBytes, nil
}

// loadBundle parses a Sigstore bundle from JSON bytes.
func loadBundle(data []byte) (*sigstoreBundle, error) {
	b := newBundle()
	if err := b.UnmarshalJSON(data); err != nil {
		return nil, err
	}
	return b, nil
}
