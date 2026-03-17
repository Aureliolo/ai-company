package verify

import (
	"context"
	"encoding/hex"
	"errors"
	"fmt"
	"strings"

	"github.com/google/go-containerregistry/pkg/name"
	v1 "github.com/google/go-containerregistry/pkg/v1"
	"github.com/google/go-containerregistry/pkg/v1/remote"
	"github.com/sigstore/sigstore-go/pkg/verify"
)

const (
	// cosignArtifactType is the OCI artifact type for cosign signatures
	// stored as OCI referrers (via --registry-referrers-mode=oci-1-1).
	cosignArtifactType = "application/vnd.dev.cosign.simplesigning.v1+json"

	// cosignBundleAnnotation is the annotation key where cosign stores the
	// Sigstore bundle in manifest or layer annotations.
	cosignBundleAnnotation = "dev.sigstore.cosign/bundle"
)

// ErrNoCosignSignatures indicates that no cosign signature referrers were
// found for an image. This is distinct from a cryptographic verification
// failure -- it means the image was published before OCI referrer-based
// cosign signing was configured.
var ErrNoCosignSignatures = errors.New("no cosign signatures found")

// VerifyCosignSignature fetches cosign keyless signatures for the given image
// via the OCI referrers API and verifies them against the Sigstore public
// transparency log. The image ref must have a resolved Digest.
// The provided verifier and identity policy are reused across images.
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

// findCosignSignatures queries OCI referrers and returns descriptors for
// cosign signature artifacts associated with the given image.
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
		if desc.ArtifactType == cosignArtifactType {
			descs = append(descs, desc)
		}
	}
	if len(descs) == 0 {
		return nil, fmt.Errorf("%w for %s", ErrNoCosignSignatures, ref)
	}
	return descs, nil
}

// verifyCosignReferrer fetches a single cosign signature referrer image,
// extracts the Sigstore bundle from annotations, and verifies it.
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

	sigManifest, err := img.Manifest()
	if err != nil {
		return fmt.Errorf("reading cosign signature manifest: %w", err)
	}

	// Check manifest-level annotations first, then layer annotations.
	// Accumulate errors so callers can diagnose verification failures.
	var bundleErrs []error

	if bundleJSON, ok := sigManifest.Annotations[cosignBundleAnnotation]; ok {
		if err := verifyCosignBundleWith([]byte(bundleJSON), ref.Digest, sev, certID); err != nil {
			bundleErrs = append(bundleErrs, fmt.Errorf("manifest bundle: %w", err))
		} else {
			return nil
		}
	}

	for i := range sigManifest.Layers {
		if bundleJSON, ok := sigManifest.Layers[i].Annotations[cosignBundleAnnotation]; ok {
			if err := verifyCosignBundleWith([]byte(bundleJSON), ref.Digest, sev, certID); err != nil {
				bundleErrs = append(bundleErrs, fmt.Errorf("layer[%d] bundle: %w", i, err))
			} else {
				return nil
			}
		}
	}

	if len(bundleErrs) > 0 {
		return fmt.Errorf("cosign bundle verification failed in referrer %s: %w", desc.Digest, errors.Join(bundleErrs...))
	}
	return fmt.Errorf("no cosign bundle annotation in signature referrer %s", desc.Digest)
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
