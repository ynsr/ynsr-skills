// Probe: hashicorp/go-retryablehttp on a flaky handler (500, 500, 200),
// with retry logs bridged to slog on stderr. stdout carries data only.
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

	"github.com/hashicorp/go-retryablehttp"
)

// slogAdapter bridges retryablehttp.LeveledLogger -> slog (stderr handler).
type slogAdapter struct{ l *slog.Logger }

func (a slogAdapter) Error(msg string, kvs ...any) { a.l.Error(msg, kvs...) }
func (a slogAdapter) Info(msg string, kvs ...any)  { a.l.Info(msg, kvs...) }
func (a slogAdapter) Debug(msg string, kvs ...any) { a.l.Debug(msg, kvs...) }
func (a slogAdapter) Warn(msg string, kvs ...any)  { a.l.Warn(msg, kvs...) }

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

	// slog with a stderr handler — the contract's log stream.
	logger := slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelDebug}))
	logger.Info("starting flaky fetch", "url", srv.URL)

	c := retryablehttp.NewClient()
	c.RetryMax = 2 // initial + 2 retries = 3 attempts
	c.RetryWaitMin = 10 * time.Millisecond
	c.RetryWaitMax = 50 * time.Millisecond
	c.Logger = slogAdapter{logger}

	resp, err := c.Get(srv.URL)
	if err != nil {
		fmt.Fprintln(os.Stderr, "error:", err)
		os.Exit(1)
	}
	defer resp.Body.Close()
	body, _ := io.ReadAll(resp.Body)

	// stdout: data only. stderr: the slog/retry lines above.
	fmt.Printf("status=%d attempts=%d body=%q\n", resp.StatusCode, calls.Load(), string(body))
}
