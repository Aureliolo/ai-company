package verify

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestCosignSigTag(t *testing.T) {
	tests := []struct {
		digest string
		want   string
	}{
		{
			"sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
			"sha256-e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.sig",
		},
		{
			"sha256:0000000000000000000000000000000000000000000000000000000000000000",
			"sha256-0000000000000000000000000000000000000000000000000000000000000000.sig",
		},
	}
	for _, tt := range tests {
		if got := cosignSigTag(tt.digest); got != tt.want {
			t.Errorf("cosignSigTag(%q) = %q, want %q", tt.digest, got, tt.want)
		}
	}
}

func TestHexToBytes(t *testing.T) {
	tests := []struct {
		name    string
		hex     string
		wantLen int
		wantErr bool
	}{
		{"valid", "abcdef", 3, false},
		{"empty", "", 0, false},
		{"uppercase", "ABCDEF", 3, false},
		{"odd length", "abc", 0, true},
		{"invalid char", "xyz", 0, true},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := hexToBytes(tt.hex)
			if (err != nil) != tt.wantErr {
				t.Errorf("hexToBytes(%q) error = %v, wantErr %v", tt.hex, err, tt.wantErr)
				return
			}
			if !tt.wantErr && len(got) != tt.wantLen {
				t.Errorf("hexToBytes(%q) len = %d, want %d", tt.hex, len(got), tt.wantLen)
			}
		})
	}
}

func TestVerifyCosignSignatureEmptyDigest(t *testing.T) {
	ref := ImageRef{
		Registry:   "ghcr.io",
		Repository: "test/image",
		Tag:        "1.0.0",
	}
	err := VerifyCosignSignature(context.Background(), ref)
	if err == nil {
		t.Fatal("expected error for empty digest")
	}
	if !strings.Contains(err.Error(), "digest not resolved") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestVerifyCosignSignatureNoSigArtifact(t *testing.T) {
	// Mock registry that returns 404 for the signature tag.
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path == "/v2/" {
			w.WriteHeader(http.StatusOK)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	host := strings.TrimPrefix(srv.URL, "http://")
	ref := ImageRef{
		Registry:   host,
		Repository: "test/image",
		Tag:        "1.0.0",
		Digest:     testDigest,
	}

	err := VerifyCosignSignature(context.Background(), ref)
	if err == nil {
		t.Fatal("expected error when no signature artifact exists")
	}
}

// ociManifest is a minimal OCI image manifest for test fixtures.
type ociManifest struct {
	SchemaVersion int                  `json:"schemaVersion"`
	MediaType     string               `json:"mediaType"`
	Config        ociDescriptor        `json:"config"`
	Layers        []ociLayerDescriptor `json:"layers"`
}

type ociDescriptor struct {
	MediaType string `json:"mediaType"`
	Digest    string `json:"digest"`
	Size      int    `json:"size"`
}

type ociLayerDescriptor struct {
	MediaType   string            `json:"mediaType"`
	Digest      string            `json:"digest"`
	Size        int               `json:"size"`
	Annotations map[string]string `json:"annotations,omitempty"`
}

func TestVerifyCosignSignatureInvalidBundle(t *testing.T) {
	// Mock registry that returns a cosign signature image with an invalid bundle.
	repo := "test/image"
	sigTag := cosignSigTag(testDigest)

	configJSON := `{}`
	layerContent := "dummy-layer-content"

	manifest := ociManifest{
		SchemaVersion: 2,
		MediaType:     "application/vnd.oci.image.manifest.v1+json",
		Config: ociDescriptor{
			MediaType: "application/vnd.oci.image.config.v1+json",
			Digest:    "sha256:44136fa355b311bfa616a15e4e5e6d84e4f455ce82fb1ed83b tried",
			Size:      len(configJSON),
		},
		Layers: []ociLayerDescriptor{
			{
				MediaType: "application/vnd.dev.cosign.simplesigning.v1+json",
				Digest:    "sha256:0000000000000000000000000000000000000000000000000000000000000001",
				Size:      len(layerContent),
				Annotations: map[string]string{
					"dev.sigstore.cosign/bundle": `{"invalid": "bundle"}`,
				},
			},
		},
	}

	manifestJSON, _ := json.Marshal(manifest)

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.URL.Path == "/v2/":
			w.WriteHeader(http.StatusOK)
		case r.URL.Path == fmt.Sprintf("/v2/%s/manifests/%s", repo, sigTag):
			w.Header().Set("Content-Type", "application/vnd.oci.image.manifest.v1+json")
			w.Header().Set("Docker-Content-Digest", testDigest)
			_, _ = w.Write(manifestJSON)
		case strings.Contains(r.URL.Path, "/blobs/"):
			// Return config or layer content.
			if strings.Contains(r.URL.Path, "44136fa") {
				_, _ = w.Write([]byte(configJSON))
			} else {
				_, _ = w.Write([]byte(layerContent))
			}
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer srv.Close()

	host := strings.TrimPrefix(srv.URL, "http://")
	ref := ImageRef{
		Registry:   host,
		Repository: repo,
		Tag:        "1.0.0",
		Digest:     testDigest,
	}

	err := VerifyCosignSignature(context.Background(), ref)
	if err == nil {
		t.Fatal("expected error for invalid bundle JSON")
	}
}
