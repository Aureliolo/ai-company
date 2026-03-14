package health

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestWaitForHealthySuccess(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"data":{"status":"ok"}}`))
	}))
	defer srv.Close()

	err := WaitForHealthy(context.Background(), srv.URL, 5*time.Second, 100*time.Millisecond, 0)
	if err != nil {
		t.Fatalf("expected healthy, got: %v", err)
	}
}

func TestWaitForHealthyDegraded(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"data":{"status":"degraded"}}`))
	}))
	defer srv.Close()

	ctx, cancel := context.WithTimeout(context.Background(), 500*time.Millisecond)
	defer cancel()

	err := WaitForHealthy(ctx, srv.URL, 500*time.Millisecond, 100*time.Millisecond, 0)
	if err == nil {
		t.Fatal("expected error for degraded status")
	}
}

func TestWaitForHealthyTimeout(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusServiceUnavailable)
	}))
	defer srv.Close()

	err := WaitForHealthy(context.Background(), srv.URL, 300*time.Millisecond, 50*time.Millisecond, 0)
	if err == nil {
		t.Fatal("expected timeout error")
	}
}

func TestWaitForHealthyEventualSuccess(t *testing.T) {
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls++
		if calls < 3 {
			w.WriteHeader(http.StatusServiceUnavailable)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"data":{"status":"ok"}}`))
	}))
	defer srv.Close()

	err := WaitForHealthy(context.Background(), srv.URL, 5*time.Second, 100*time.Millisecond, 0)
	if err != nil {
		t.Fatalf("expected eventual success, got: %v", err)
	}
}
