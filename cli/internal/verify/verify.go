package verify

import (
	"context"
	"fmt"
	"io"
	"regexp"
	"strings"
)

// digestPattern validates an OCI content digest (algorithm:hex).
var digestPattern = regexp.MustCompile(`^sha256:[a-f0-9]{64}$`)

// ImageRef identifies a container image with an optional resolved digest.
type ImageRef struct {
	Registry   string // e.g. "ghcr.io"
	Repository string // e.g. "aureliolo/synthorg-backend"
	Tag        string // e.g. "0.3.0" or "latest"
	Digest     string // e.g. "sha256:abc..." — filled after resolution
}

// String returns the full image reference with tag.
func (r ImageRef) String() string {
	return fmt.Sprintf("%s/%s:%s", r.Registry, r.Repository, r.Tag)
}

// DigestRef returns the full image reference pinned to its digest.
// Panics if Digest is empty — call only after successful resolution.
func (r ImageRef) DigestRef() string {
	return fmt.Sprintf("%s/%s@%s", r.Registry, r.Repository, r.Digest)
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
type VerifyResult struct {
	Ref                ImageRef
	CosignVerified     bool
	ProvenanceVerified bool
}

// VerifyOptions configures the image verification behavior.
type VerifyOptions struct {
	SkipVerify bool
	Images     []ImageRef
	Output     io.Writer // user-visible progress output
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
// When opts.SkipVerify is true, returns nil results immediately.
//
// Progress is printed to opts.Output during verification.
func VerifyImages(ctx context.Context, opts VerifyOptions) ([]VerifyResult, error) {
	if opts.SkipVerify {
		return nil, nil
	}
	if len(opts.Images) == 0 {
		return nil, nil
	}

	w := opts.Output
	if w == nil {
		w = io.Discard
	}

	results := make([]VerifyResult, 0, len(opts.Images))
	for _, img := range opts.Images {
		result, err := verifyOneImage(ctx, img, w)
		if err != nil {
			return nil, fmt.Errorf("verifying %s: %w", img, err)
		}
		results = append(results, result)
	}
	return results, nil
}

// verifyOneImage resolves the digest and verifies cosign + SLSA for one image.
func verifyOneImage(ctx context.Context, ref ImageRef, w io.Writer) (VerifyResult, error) {
	_, _ = fmt.Fprintf(w, "Verifying %s...\n", ref)

	// Step 1: Resolve tag to digest.
	digest, err := ResolveDigest(ctx, ref)
	if err != nil {
		return VerifyResult{}, fmt.Errorf("resolving digest: %w", err)
	}
	ref.Digest = digest
	_, _ = fmt.Fprintf(w, "  Resolved digest: %s\n", digest)

	// Step 2: Verify cosign signature.
	if err := VerifyCosignSignature(ctx, ref); err != nil {
		return VerifyResult{}, fmt.Errorf("cosign signature: %w", err)
	}
	_, _ = fmt.Fprintf(w, "  Cosign signature: verified\n")

	// Step 3: Verify SLSA provenance (warn-only on missing).
	provenanceVerified := true
	if err := VerifyProvenance(ctx, ref); err != nil {
		provenanceVerified = false
		_, _ = fmt.Fprintf(w, "  SLSA provenance:  not available (%v)\n", err)
	} else {
		_, _ = fmt.Fprintf(w, "  SLSA provenance:  verified\n")
	}

	_, _ = fmt.Fprintf(w, "  %s: OK\n", ref.Name())

	return VerifyResult{
		Ref:                ref,
		CosignVerified:     true,
		ProvenanceVerified: provenanceVerified,
	}, nil
}
