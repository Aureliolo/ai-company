package verify

import (
	"context"
	"errors"
	"fmt"
	"io"
	"regexp"
	"strings"

	protobundle "github.com/sigstore/protobuf-specs/gen/pb-go/bundle/v1"
	"github.com/sigstore/sigstore-go/pkg/bundle"
	"github.com/sigstore/sigstore-go/pkg/verify"
)

// digestPattern validates an OCI content digest (algorithm:hex).
var digestPattern = regexp.MustCompile(`^sha256:[a-f0-9]{64}$`)

// sigstoreBundle is a type alias for the sigstore-go bundle type.
type sigstoreBundle = bundle.Bundle

// newBundle creates a new empty Sigstore bundle for JSON unmarshalling.
func newBundle() *sigstoreBundle {
	return &bundle.Bundle{Bundle: new(protobundle.Bundle)}
}

// ImageRef identifies a container image with an optional resolved digest.
type ImageRef struct {
	Registry   string // e.g. "ghcr.io"
	Repository string // e.g. "aureliolo/synthorg-backend"
	Tag        string // e.g. "0.3.0" or "latest"
	Digest     string // e.g. "sha256:abc..." — filled after resolution
}

// String returns the full image reference with tag.
// If Tag is empty, returns registry/repository without a trailing colon.
func (r ImageRef) String() string {
	if r.Tag == "" {
		return fmt.Sprintf("%s/%s", r.Registry, r.Repository)
	}
	return fmt.Sprintf("%s/%s:%s", r.Registry, r.Repository, r.Tag)
}

// DigestRef returns the full image reference pinned to its digest.
// Returns an error if Digest is empty.
func (r ImageRef) DigestRef() (string, error) {
	if r.Digest == "" {
		return "", fmt.Errorf("digest not resolved for %s", r)
	}
	return fmt.Sprintf("%s/%s@%s", r.Registry, r.Repository, r.Digest), nil
}

// Name returns the short image name suffix (e.g. "backend" from
// "aureliolo/synthorg-backend").
func (r ImageRef) Name() string {
	_, after, ok := strings.Cut(r.Repository, ImageRepoPrefix)
	if ok {
		return after
	}
	return r.Repository
}

// VerifyResult holds the outcome of verifying a single image.
// CosignVerified is always true when returned from VerifyImages because cosign
// failure returns an error — the result is only constructed on success.
type VerifyResult struct {
	Ref                ImageRef
	ProvenanceVerified bool
}

// VerifyOptions configures the image verification behavior.
type VerifyOptions struct {
	Images []ImageRef
	Output io.Writer // user-visible progress output
}

// NewImageRef creates an ImageRef for a SynthOrg service image.
// name is the service name (e.g. "backend", "web", "sandbox").
func NewImageRef(name, tag string) ImageRef {
	return ImageRef{
		Registry:   RegistryHost,
		Repository: ImageRepoPrefix + name,
		Tag:        tag,
	}
}

// BuildImageRefs creates ImageRef values for the standard SynthOrg images.
// If sandbox is false, the sandbox image is excluded.
func BuildImageRefs(tag string, sandbox bool) []ImageRef {
	refs := []ImageRef{
		NewImageRef("backend", tag),
		NewImageRef("web", tag),
	}
	if sandbox {
		refs = append(refs, NewImageRef("sandbox", tag))
	}
	return refs
}

// IsValidDigest reports whether d is a valid sha256 OCI digest.
func IsValidDigest(d string) bool {
	return digestPattern.MatchString(d)
}

// VerifyImages verifies cosign signatures and SLSA provenance for all images
// in opts. Returns verified results with resolved digests, or an error if
// any verification fails.
//
// A single Sigstore verifier and identity policy is built once and reused
// across all images to avoid redundant TUF root fetches.
//
// Callers are responsible for checking skip conditions (e.g. --skip-verify)
// before calling this function.
//
// Progress is printed to opts.Output during verification.
func VerifyImages(ctx context.Context, opts VerifyOptions) ([]VerifyResult, error) {
	if len(opts.Images) == 0 {
		return nil, nil
	}

	w := opts.Output
	if w == nil {
		w = io.Discard
	}

	// Build verifier and identity once — reuse for all images.
	sev, err := BuildVerifier()
	if err != nil {
		return nil, fmt.Errorf("building sigstore verifier: %w", err)
	}
	certID, err := BuildIdentityPolicy()
	if err != nil {
		return nil, fmt.Errorf("building identity policy: %w", err)
	}

	results := make([]VerifyResult, 0, len(opts.Images))
	for _, img := range opts.Images {
		result, err := verifyOneImage(ctx, img, sev, certID, w)
		if err != nil {
			return nil, fmt.Errorf("verifying %s: %w", img, err)
		}
		results = append(results, result)
	}
	return results, nil
}

// verifyOneImage resolves the digest and verifies cosign + SLSA for one image.
func verifyOneImage(ctx context.Context, ref ImageRef, sev *verify.Verifier, certID verify.CertificateIdentity, w io.Writer) (VerifyResult, error) {
	_, _ = fmt.Fprintf(w, "Verifying %s...\n", ref)

	// Step 1: Resolve tag to digest.
	digest, err := ResolveDigest(ctx, ref)
	if err != nil {
		return VerifyResult{}, fmt.Errorf("resolving digest: %w", err)
	}
	ref.Digest = digest
	_, _ = fmt.Fprintf(w, "  Resolved digest: %s\n", digest)

	// Step 2: Verify cosign signature.
	if err := VerifyCosignSignature(ctx, ref, sev, certID); err != nil {
		return VerifyResult{}, fmt.Errorf("cosign signature: %w", err)
	}
	_, _ = fmt.Fprintf(w, "  Cosign signature: verified\n")

	// Step 3: Verify SLSA provenance.
	// Missing attestations are warn-only (pre-SLSA images may not have them).
	// Cryptographic failures (tampered attestation, wrong identity) are hard errors.
	provenanceVerified := true
	if err := VerifyProvenance(ctx, ref, sev, certID); err != nil {
		if isProvenanceMissing(err) {
			provenanceVerified = false
			_, _ = fmt.Fprintf(w, "  SLSA provenance:  not available (warn)\n")
		} else {
			return VerifyResult{}, fmt.Errorf("SLSA provenance verification: %w", err)
		}
	} else {
		_, _ = fmt.Fprintf(w, "  SLSA provenance:  verified\n")
	}

	_, _ = fmt.Fprintf(w, "  %s: OK\n", ref.Name())

	return VerifyResult{
		Ref:                ref,
		ProvenanceVerified: provenanceVerified,
	}, nil
}

// isProvenanceMissing returns true when the provenance error indicates that
// attestations are absent (the image was published before SLSA provenance was
// configured), as opposed to a cryptographic or structural verification
// failure that indicates tampering.
func isProvenanceMissing(err error) bool {
	return errors.Is(err, ErrNoProvenanceAttestations)
}
