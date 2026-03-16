package verify

import (
	"context"
	"fmt"

	"github.com/google/go-containerregistry/pkg/name"
	"github.com/google/go-containerregistry/pkg/v1/remote"
)

// ResolveDigest queries the registry to resolve a tagged image reference to
// its content digest (sha256:...). The digest uniquely identifies the image
// manifest and is used for signature and provenance verification.
//
// Uses HEAD first (efficient), with a fallback to GET for registries that
// return 405 Method Not Allowed for manifest HEAD requests.
func ResolveDigest(ctx context.Context, ref ImageRef) (string, error) {
	tagRef, err := name.ParseReference(ref.String())
	if err != nil {
		return "", fmt.Errorf("parsing image reference %q: %w", ref.String(), err)
	}

	desc, err := remote.Head(tagRef, remote.WithContext(ctx))
	if err != nil {
		// Fallback to GET for registries that don't support HEAD.
		rd, getErr := remote.Get(tagRef, remote.WithContext(ctx))
		if getErr != nil {
			return "", fmt.Errorf("fetching manifest for %s: %w", ref, getErr)
		}
		desc = &rd.Descriptor
	}

	digest := desc.Digest.String()
	if !IsValidDigest(digest) {
		return "", fmt.Errorf("registry returned invalid digest %q for %s", digest, ref)
	}
	return digest, nil
}
