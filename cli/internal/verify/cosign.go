package verify

import (
	"context"
	"encoding/hex"
	"fmt"
	"strings"

	"github.com/google/go-containerregistry/pkg/name"
	"github.com/google/go-containerregistry/pkg/v1/remote"
	"github.com/sigstore/sigstore-go/pkg/verify"
)

// cosignTagSuffix is the OCI tag suffix cosign uses to store signatures.
// For an image with digest sha256:abcd..., cosign stores the signature
// artifact at the tag sha256-abcd....sig in the same repository.
const cosignTagSuffix = ".sig"

// VerifyCosignSignature fetches the cosign keyless signature for the given
// image (identified by ref.Digest) and verifies it against the Sigstore
// public transparency log. The image ref must have a resolved Digest.
// The provided verifier and identity policy are reused across images.
func VerifyCosignSignature(ctx context.Context, ref ImageRef, sev *verify.Verifier, certID verify.CertificateIdentity) error {
	if ref.Digest == "" {
		return fmt.Errorf("image digest not resolved")
	}

	// Cosign stores signatures at a deterministic tag derived from the digest.
	// e.g. sha256:abcdef... → sha256-abcdef....sig
	sigTag := cosignSigTag(ref.Digest)
	sigRef := fmt.Sprintf("%s/%s:%s", ref.Registry, ref.Repository, sigTag)

	tagRef, err := name.ParseReference(sigRef)
	if err != nil {
		return fmt.Errorf("parsing signature reference %q: %w", sigRef, err)
	}

	// Fetch the cosign signature manifest.
	img, err := remote.Image(tagRef, remote.WithContext(ctx))
	if err != nil {
		return fmt.Errorf("fetching cosign signature for %s: %w", ref, err)
	}

	// Extract the signature bundle from the image layers.
	manifest, err := img.Manifest()
	if err != nil {
		return fmt.Errorf("reading signature manifest: %w", err)
	}

	layers, err := img.Layers()
	if err != nil {
		return fmt.Errorf("reading signature layers: %w", err)
	}

	if len(layers) == 0 || len(manifest.Layers) == 0 {
		return fmt.Errorf("no cosign signature layers found for %s", ref)
	}

	// Try each layer — cosign may store the bundle in layer annotations.
	var lastErr error
	for i := range layers {
		annotations := manifest.Layers[i].Annotations
		bundleJSON, ok := annotations["dev.sigstore.cosign/bundle"]
		if !ok {
			continue
		}

		if err := verifyCosignBundleWith([]byte(bundleJSON), ref.Digest, sev, certID); err != nil {
			lastErr = err
			continue
		}
		return nil // verified successfully
	}

	if lastErr != nil {
		return fmt.Errorf("cosign signature verification failed for %s: %w", ref, lastErr)
	}
	return fmt.Errorf("no cosign signature bundle found for %s", ref)
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

// cosignSigTag converts a digest to the cosign signature tag.
// "sha256:abcdef..." → "sha256-abcdef....sig"
func cosignSigTag(digest string) string {
	tag := strings.ReplaceAll(digest, ":", "-")
	return tag + cosignTagSuffix
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
