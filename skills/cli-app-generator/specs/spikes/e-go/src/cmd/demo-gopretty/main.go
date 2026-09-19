// Probe: jedib0t/go-pretty/v6 v6.8.3 — one []Item definition emitted as
// ASCII table + CSV + JSON. v6.8.x has no json/ package (verified via zip
// contents); JSON emission is stdlib encoding/json from the same slice.
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"github.com/jedib0t/go-pretty/v6/table"
)

type Item struct {
	Name   string `json:"name"`
	Count  int    `json:"count"`
	Status string `json:"status"`
}

var items = []Item{
	{"alpha", 3, "active"},
	{"beta", 12, "pending"},
	{"gamma", 7, "error"},
	{"delta", 0, "active"},
	{"epsilon", 42, "done"},
}

func main() {
	// ---- table + csv (go-pretty) ------------------------------------
	w := table.NewWriter()
	w.AppendHeader(table.Row{"NAME", "COUNT", "STATUS"})
	rows := make([]table.Row, len(items))
	for i, it := range items {
		rows[i] = table.Row{it.Name, it.Count, it.Status}
	}
	w.AppendRows(rows)
	w.SetStyle(table.StyleLight)
	fmt.Print(w.Render())   // ASCII box table
	fmt.Print(w.RenderCSV()) // RFC 4180-escaped CSV, header included

	// ---- json (stdlib; go-pretty v6.8.3 ships no json renderer) -----
	b, err := json.Marshal(items)
	if err != nil {
		fmt.Fprintln(os.Stderr, "json:", err)
		os.Exit(1)
	}
	os.Stdout.WriteString(string(b) + "\n")
}
