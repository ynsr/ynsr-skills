// Probe: the in-module retry helper (httpx.go) on the same flaky handler
// the retryablehttp probe used (500, 500, 200). App logs via slog→stderr;
// stdout carries data only.
package main

import (
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"os"
	"sync/atomic"
	"time"
)

func main() {
	var calls atomic.Int32
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		if calls.Add(1) < 3 {
			w.WriteHeader(http.StatusInternalServerError) // fails #1, #2
			return
		}
		w.WriteHeader(http.StatusOK) // succeeds #3
		_, _ = io.WriteString(w, "payload")
	}))
	defer srv.Close()

	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelDebug}))
	logger.Info("starting flaky fetch", "url", srv.URL)

	c := &RetryClient{
		HTTP:     http.DefaultClient,
		RetryMax: 2, // initial + 2 retries = 3 attempts
		WaitMin:  10 * time.Millisecond,
		WaitMax:  50 * time.Millisecond,
		Logger:   logger,
	}

	req, err := http.NewRequest(http.MethodGet, srv.URL, nil)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
	resp, err := c.Do(req)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	// stdout: data only.
	fmt.Printf("status=%d attempts=%d body=%q\n", resp.StatusCode, calls.Load(), string(body))
}
