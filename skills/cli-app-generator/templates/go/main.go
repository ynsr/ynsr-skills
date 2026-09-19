// main.go — sample: cobra+fang skeleton. Replace the sample surface with real commands.
// Contract: stdout carries data only; errors surface as {"error":{code,message,hint}} on stderr.
package main

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/http"
	"os"
	"slices"
	"strings"
	"time"

	"charm.land/fang/v2"
	"github.com/jedib0t/go-pretty/v6/table"
	"github.com/spf13/cobra"
)

type item struct {
	Name   string `json:"name"`
	Size   int    `json:"size"`
	Status string `json:"status"`
}

var (
	sample                     = []item{{"alpha", 3, "ok"}, {"beta", 5, "ok"}, {"gamma", 8, "stale"}}
	output                     string
	asJSON, quiet, dryRun, yes bool
	exitCode                   int
)

// cerr carries a contract exit code through fang's error handler.
type cerr struct {
	code      int
	msg, hint string
}

func (c cerr) Error() string { return c.msg }

var slugByCode = map[int]string{2: "usage", 3: "network", 4: "partial"}

func (c cerr) slug() string {
	if s, ok := slugByCode[c.code]; ok {
		return s
	}
	return "error"
}

var usagePrefixes = []string{"unknown command", "unknown flag:", "unknown shorthand flag:",
	"invalid argument", "flag needs an argument:", "accepts", "requires"}

func codeOf(err error) int { // map usage-shaped errors → exit 2
	var c cerr
	if errors.As(err, &c) {
		return c.code
	}
	if slices.ContainsFunc(usagePrefixes, func(p string) bool { return strings.HasPrefix(err.Error(), p) }) {
		return 2
	}
	return 1
}

func envelope(c cerr) string { // agent-facing error object for stderr
	body, _ := json.Marshal(map[string]string{"code": c.slug(), "message": c.msg, "hint": c.hint})
	return `{"error":` + string(body) + "}"
}

// errHandler prints the contract error surface and records the exit code.
func errHandler(w io.Writer, _ fang.Styles, err error) {
	exitCode = codeOf(err)
	c := cerr{exitCode, err.Error(), "see --help"}
	errors.As(err, &c) // keep code/msg/hint when typed; defaults otherwise
	_, _ = fmt.Fprintln(w, envelope(c))
}

// emit renders one dataset in the requested format (stdout only).
func emit(items []item, w io.Writer) error {
	if asJSON {
		output = "json"
	}
	tw := table.NewWriter()
	tw.SetStyle(table.StyleDefault) // ASCII box: box-drawing styles would taint stdout
	tw.AppendHeader(table.Row{"NAME", "SIZE", "STATUS"})
	for _, it := range items {
		tw.AppendRow(table.Row{it.Name, it.Size, it.Status})
	}
	if output == "json" {
		return json.NewEncoder(w).Encode(items)
	}
	render, ok := map[string]func() string{"table": tw.Render, "csv": tw.RenderCSV, "tsv": tw.RenderTSV}[output]
	if !ok {
		return cerr{2, fmt.Sprintf("invalid --output %q", output), "want table|json|csv|tsv"}
	}
	_, _ = fmt.Fprintln(w, render())
	return nil
}

// fetchItems GETs a JSON []item with retry (transport errors + 5xx, exponential backoff).
func fetchItems(url string) ([]item, error) {
	client := RetryClient{HTTP: &http.Client{Timeout: 10 * time.Second}, RetryMax: 2,
		WaitMin: 100 * time.Millisecond, WaitMax: time.Second, Logger: slog.Default()}
	req, err := http.NewRequestWithContext(context.Background(), "GET", url, nil)
	if err != nil {
		return nil, err
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer func() { _ = resp.Body.Close() }()
	var items []item
	return items, json.NewDecoder(resp.Body).Decode(&items)
}

func main() {
	root := &cobra.Command{Use: "sample", Short: "Sample CLI (Go skeleton)",
		Long: `Sample CLI skeleton for the Go tier; wire real commands onto this shape.
Exit codes: 0 success, 1 error, 2 usage, 3 network, 4 partial. Stdout carries data only.`}
	pf := root.PersistentFlags()
	pf.StringVarP(&output, "output", "o", "table", "output format (table|json|csv|tsv)")
	pf.BoolVar(&asJSON, "json", false, "shorthand for --output json")
	pf.Bool("no-color", false, "disable ANSI output") // output is plain anyway; contract parity
	pf.BoolVarP(&quiet, "quiet", "q", false, "suppress non-essential stderr output")
	del := &cobra.Command{Use: "delete FILE", Short: "Delete a file (destructive)", Args: cobra.ExactArgs(1),
		RunE: func(_ *cobra.Command, args []string) error {
			if dryRun {
				_, _ = fmt.Printf("plan: rm %s\n", args[0]) // the plan is data → stdout
				return nil
			}
			if !yes {
				return cerr{2, "refusing to delete without --yes", "append --yes to execute; --dry-run previews the plan"}
			}
			if err := os.Remove(args[0]); err != nil {
				return cerr{1, err.Error(), "check the path"}
			}
			slog.Info("deleted", "path", args[0])
			return nil
		}}
	del.Flags().BoolVar(&dryRun, "dry-run", false, "print the plan to stdout; change nothing")
	del.Flags().BoolVarP(&yes, "yes", "y", false, "execute; the tool never prompts, it refuses without --yes")
	root.AddCommand(
		&cobra.Command{Use: "list [URL]", Short: "Emit sample rows (URL: fetch via RetryClient)",
			Args: cobra.MaximumNArgs(1),
			RunE: func(_ *cobra.Command, args []string) error {
				items := sample
				if len(args) == 1 {
					var err error
					if items, err = fetchItems(args[0]); err != nil {
						return cerr{3, err.Error(), "check the URL; 5xx and transport errors retry automatically"}
					}
				}
				slog.Debug("listing items", "count", len(items))
				return emit(items, os.Stdout)
			}}, del)
	root.PersistentPreRun = func(_ *cobra.Command, _ []string) {
		if quiet {
			slog.SetLogLoggerLevel(slog.LevelError)
		}
	}
	if err := fang.Execute(context.Background(), root,
		fang.WithVersion("0.1.0"), fang.WithErrorHandler(errHandler)); err != nil {
		os.Exit(max(exitCode, 1))
	}
}
