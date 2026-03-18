package verify

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	sigverify "github.com/sigstore/sigstore-go/pkg/verify"
)

func TestVerifyProvenanceEmptyDigest(t *testing.T) {
	ref := ImageRef{
		Registry:   "ghcr.io",
		Repository: "test/image",
		Tag:        "1.0.0",
	}
	err := VerifyProvenance(context.Background(), ref, nil, sigverify.CertificateIdentity{})
	if err == nil {
		t.Fatal("expected error for empty digest")
	}
	if !strings.Contains(err.Error(), "digest not resolved") {
		t.Errorf("unexpected error: %v", err)
	}
}

func TestFetchGitHubAttestationsNotFound(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()

	// Temporarily override the API base for testing.
	origBase := githubAPIBase
	defer func() { setGitHubAPIBase(origBase) }()
	setGitHubAPIBase(srv.URL)

	_, err := fetchGitHubAttestations(context.Background(), testDigest)
	if err == nil {
		t.Fatal("expected error for 404 response")
	}
	if !errors.Is(err, ErrNoProvenanceAttestations) {
		t.Errorf("expected ErrNoProvenanceAttestations, got: %v", err)
	}
}

func TestFetchGitHubAttestationsEmptyResponse(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"attestations": []}`))
	}))
	defer srv.Close()

	origBase := githubAPIBase
	defer func() { setGitHubAPIBase(origBase) }()
	setGitHubAPIBase(srv.URL)

	_, err := fetchGitHubAttestations(context.Background(), testDigest)
	if err == nil {
		t.Fatal("expected error for empty attestations")
	}
	if !errors.Is(err, ErrNoProvenanceAttestations) {
		t.Errorf("expected ErrNoProvenanceAttestations, got: %v", err)
	}
}

func TestFetchGitHubAttestationsSuccess(t *testing.T) {
	bundle := json.RawMessage(`{"mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json"}`)
	resp := githubAttestationResponse{
		Attestations: []struct {
			Bundle json.RawMessage `json:"bundle"`
		}{
			{Bundle: bundle},
		},
	}
	respJSON, err := json.Marshal(resp)
	if err != nil {
		t.Fatalf("marshaling response: %v", err)
	}

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Verify the URL path contains the digest.
		if !strings.Contains(r.URL.Path, testDigest) {
			t.Errorf("expected digest in URL path, got: %s", r.URL.Path)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(respJSON)
	}))
	defer srv.Close()

	origBase := githubAPIBase
	defer func() { setGitHubAPIBase(origBase) }()
	setGitHubAPIBase(srv.URL)

	bundles, err := fetchGitHubAttestations(context.Background(), testDigest)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(bundles) != 1 {
		t.Fatalf("expected 1 bundle, got %d", len(bundles))
	}
}

func TestFetchGitHubAttestationsServerError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusInternalServerError)
	}))
	defer srv.Close()

	origBase := githubAPIBase
	defer func() { setGitHubAPIBase(origBase) }()
	setGitHubAPIBase(srv.URL)

	_, err := fetchGitHubAttestations(context.Background(), testDigest)
	if err == nil {
		t.Fatal("expected error for 500 response")
	}
	if !strings.Contains(err.Error(), fmt.Sprintf("HTTP %d", http.StatusInternalServerError)) {
		t.Errorf("expected HTTP status in error, got: %v", err)
	}
}

func TestVerifyProvenanceInvalidBundle(t *testing.T) {
	// Mock GitHub API returning an invalid bundle.
	resp := `{"attestations": [{"bundle": {"invalid": "not a sigstore bundle"}}]}`

	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(resp))
	}))
	defer srv.Close()

	origBase := githubAPIBase
	defer func() { setGitHubAPIBase(origBase) }()
	setGitHubAPIBase(srv.URL)

	ref := ImageRef{
		Registry:   "ghcr.io",
		Repository: "test/image",
		Tag:        "1.0.0",
		Digest:     testDigest,
	}

	err := VerifyProvenance(context.Background(), ref, nil, sigverify.CertificateIdentity{})
	if err == nil {
		t.Fatal("expected error for invalid bundle")
	}
	if !strings.Contains(err.Error(), "no valid SLSA provenance attestation") {
		t.Errorf("expected provenance attestation error, got: %v", err)
	}
}
