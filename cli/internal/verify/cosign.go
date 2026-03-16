package verify

import (
	"context"
	"fmt"
	"strings"

	"github.com/google/go-containerregistry/pkg/name"
	"github.com/google/go-containerregistry/pkg/v1/remote"
	"github.com/sigstore/sigstore-go/pkg/bundle"
	"github.com/sigstore/sigstore-go/pkg/verify"

	protobundle "github.com/sigstore/protobuf-specs/gen/pb-go/bundle/v1"
)

// cosignTagSuffix is the OCI tag suffix cosign uses to store signatures.
// For an image with digest sha256:abcd..., cosign stores the signature
// artifact at the tag sha256-abcd....sig in the same repository.
const cosignTagSuffix = ".sig"

// VerifyCosignSignature fetches the cosign keyless signature for the given
// image (identified by ref.Digest) and verifies it against the Sigstore
// public transparency log. The image ref must have a resolved Digest.
func VerifyCosignSignature(ctx context.Context, ref ImageRef) error {
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
	for i := range layers {
		annotations := manifest.Layers[i].Annotations
		bundleJSON, ok := annotations["dev.sigstore.cosign/bundle"]
		if !ok {
			continue
		}

		if err := verifyCosignBundle([]byte(bundleJSON), ref.Digest); err == nil {
			return nil // verified successfully
		}
	}

	// Fallback: try simple payload verification on first layer.
	return fmt.Errorf("no valid cosign signature bundle found for %s", ref)
}

// verifyCosignBundle verifies a cosign Sigstore bundle against the expected
// identity and image digest.
func verifyCosignBundle(bundleJSON []byte, digest string) error {
	b := &bundle.Bundle{Bundle: new(protobundle.Bundle)}
	if err := b.UnmarshalJSON(bundleJSON); err != nil {
		return fmt.Errorf("parsing cosign bundle: %w", err)
	}

	sev, err := BuildVerifier()
	if err != nil {
		return err
	}

	certID, err := BuildIdentityPolicy()
	if err != nil {
		return err
	}

	// Parse the digest for verification.
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

// hexToBytes converts a hex string to a byte slice.
func hexToBytes(hex string) ([]byte, error) {
	if len(hex)%2 != 0 {
		return nil, fmt.Errorf("odd-length hex string")
	}
	b := make([]byte, len(hex)/2)
	for i := range b {
		hi, ok := hexVal(hex[2*i])
		if !ok {
			return nil, fmt.Errorf("invalid hex char %q", hex[2*i])
		}
		lo, ok := hexVal(hex[2*i+1])
		if !ok {
			return nil, fmt.Errorf("invalid hex char %q", hex[2*i+1])
		}
		b[i] = hi<<4 | lo
	}
	return b, nil
}

func hexVal(c byte) (byte, bool) {
	switch {
	case c >= '0' && c <= '9':
		return c - '0', true
	case c >= 'a' && c <= 'f':
		return c - 'a' + 10, true
	case c >= 'A' && c <= 'F':
		return c - 'A' + 10, true
	default:
		return 0, false
	}
}
