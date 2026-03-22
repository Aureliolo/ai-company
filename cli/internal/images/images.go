// Package images provides shared types and functions for discovering and
// referencing SynthOrg container images across CLI commands.
package images

import (
	"context"
	"strings"

	"github.com/Aureliolo/synthorg/cli/internal/docker"
	"github.com/Aureliolo/synthorg/cli/internal/verify"
)

// RepoPrefix is the full GHCR repository prefix for all SynthOrg images
// (e.g. "ghcr.io/aureliolo/synthorg-").
const RepoPrefix = verify.RegistryHost + "/" + verify.ImageRepoPrefix

// ServiceNames returns the canonical SynthOrg service names.
// The sandbox service is included only when sandbox is true.
func ServiceNames(sandbox bool) []string {
	if sandbox {
		return []string{"backend", "web", "sandbox"}
	}
	return []string{"backend", "web"}
}

// RefForService returns the Docker image reference for a SynthOrg service.
// When verifiedDigests contains a digest for the service, returns a
// digest-pinned reference (repo@sha256:...). Otherwise returns a
// tag-based reference (repo:tag).
func RefForService(svc, imageTag string, verifiedDigests map[string]string) string {
	repo := RepoPrefix + svc
	if d, ok := verifiedDigests[svc]; ok && d != "" {
		return repo + "@" + d
	}
	return repo + ":" + imageTag
}

// LocalImage holds parsed information about a SynthOrg image found locally.
type LocalImage struct {
	Repository string // full repo, e.g. "ghcr.io/aureliolo/synthorg-backend"
	Tag        string // e.g. "0.4.6" or "<none>"
	Size       string // human-readable size from Docker (e.g. "646MB")
	ID         string // Docker short ID (12 hex chars)
	Digest     string // e.g. "sha256:abc..." or "<none>"
}

// ServiceName extracts the short service name (e.g. "backend") from
// the full repository path.
func (img LocalImage) ServiceName() string {
	return strings.TrimPrefix(img.Repository, RepoPrefix)
}

// ListLocal lists all SynthOrg images present in the local Docker daemon.
//
// Unlike Docker's --filter "reference=..." (which misses digest-only images
// that have no tag), this function lists all images and filters by repository
// prefix in Go, reliably finding both tagged and digest-only images.
func ListLocal(ctx context.Context, dockerPath string) ([]LocalImage, error) {
	out, err := docker.RunCmd(ctx, dockerPath, "images",
		"--format", "{{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.ID}}\t{{.Digest}}")
	if err != nil {
		return nil, err
	}

	return parseImageList(out), nil
}

// parseImageList parses the tab-delimited output of docker images into
// LocalImage values, keeping only rows whose repository starts with
// RepoPrefix.
func parseImageList(raw string) []LocalImage {
	var images []LocalImage
	for line := range strings.SplitSeq(strings.TrimSpace(strings.ReplaceAll(raw, "\r\n", "\n")), "\n") {
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "\t", 5)
		if len(parts) < 5 {
			continue
		}
		repo := parts[0]
		if !strings.HasPrefix(repo, RepoPrefix) {
			continue
		}
		images = append(images, LocalImage{
			Repository: repo,
			Tag:        parts[1],
			Size:       parts[2],
			ID:         parts[3],
			Digest:     parts[4],
		})
	}
	return images
}

// InspectID returns the Docker image ID for the given image reference.
// Works with both digest-pinned (@sha256:...) and tag-based (:tag) references.
func InspectID(ctx context.Context, dockerPath, ref string) (string, error) {
	out, err := docker.RunCmd(ctx, dockerPath, "image", "inspect", ref, "--format", "{{.ID}}")
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(out), nil
}
