// httpx.go — own retry helper (DECISIONS row E, spike-proven on a flaky handler):
// retries transport errors and 5xx with WaitMin*2^attempt capped at WaitMax,
// replays bodies via GetBody, logs retry decisions at debug to the injected logger.
// Limits (by design): no 429/Retry-After handling, no metrics hooks — retryablehttp
// (v0.7.8, 15-mo-old release) is the documented fallback if those appear.
package main

import (
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
func (c *RetryClient) Do(req *http.Request) (*http.Response, error) {
	for attempt := 0; ; attempt++ {
		resp, err := c.HTTP.Do(req)
		if (err == nil && resp.StatusCode < 500) || attempt >= c.RetryMax {
			return resp, err // done: success, client error, or out of attempts
		}
		if err != nil {
			c.Logger.Debug("retry: transport error", "attempt", attempt+1, "err", err)
		} else {
			_ = resp.Body.Close() // drain/close so the connection can be reused
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
