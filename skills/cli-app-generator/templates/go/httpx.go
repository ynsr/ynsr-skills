// httpx.go — own retry helper (DECISIONS row E, spike-proven on a flaky handler):
// retries transport errors and 5xx with WaitMin*2^attempt capped at WaitMax,
// replays bodies via GetBody, logs retry decisions at debug to the injected logger.
// 5xx bodies are drained (io.Discard) before Close so keep-alive survives retries.
// Limits (by design): no 429/Retry-After handling, no metrics hooks — retryablehttp
// (v0.7.8, 15-mo-old release) is the documented fallback if those appear.
package main

import (
	"fmt"
	"io"
	"log/slog"
	"math"
	"net/http"
	"time"
)

// RetryClient wraps *http.Client with retry + exponential backoff.
type RetryClient struct {
	HTTP     *http.Client
	RetryMax int // retries after the first attempt; attempts = RetryMax+1
	WaitMin  time.Duration
	WaitMax  time.Duration
	Logger   *slog.Logger // stderr handler; retry decisions logged at debug
}

// Do sends req, retrying with exponential backoff while attempts remain.
// Terminal states: success/client-error response, exhausted transport error, or an
// error when attempts exhaust on persistent 5xx (callers never see an error page).
func (c *RetryClient) Do(req *http.Request) (*http.Response, error) {
	for attempt := 0; ; attempt++ {
		resp, err := c.HTTP.Do(req)
		if err == nil && resp.StatusCode < 500 {
			return resp, nil // success or client error — caller decides
		}
		if err != nil {
			if attempt >= c.RetryMax {
				return nil, err // out of attempts on transport errors
			}
			c.Logger.Debug("retry: transport error", "attempt", attempt+1, "err", err)
		} else {
			_, _ = io.Copy(io.Discard, resp.Body)
			_ = resp.Body.Close()
			if attempt >= c.RetryMax {
				return nil, fmt.Errorf("giving up after %d attempt(s): HTTP %d from %s",
					attempt+1, resp.StatusCode, req.URL)
			}
			c.Logger.Debug("retrying request", "status", resp.StatusCode,
				"timeout", c.wait(attempt), "remaining", c.RetryMax-attempt)
		}
		time.Sleep(c.wait(attempt))
		if req.GetBody != nil {
			req.Body, _ = req.GetBody()
		}
	}
}

func (c *RetryClient) wait(attempt int) time.Duration {
	return min(time.Duration(float64(c.WaitMin)*math.Pow(2, float64(attempt))), c.WaitMax)
}
