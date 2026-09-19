// Probe: charm.land/lipgloss/v2/table — same []Item emitted as table +
// CSV + JSON. lipgloss renders the table only; CSV and JSON are manual.
package main

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"

	"charm.land/lipgloss/v2/table"
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
	// convert []Item -> [][]string (needed for both table and csv below)
	rows := make([][]string, len(items))
	for i, it := range items {
		rows[i] = []string{it.Name, fmt.Sprint(it.Count), it.Status}
	}

	// ---- table (lipgloss) --------------------------------------------
	t := table.New().
		Headers("NAME", "COUNT", "STATUS").
		Rows(rows...)
	fmt.Println(t.Render())

	// ---- csv (manual: encoding/csv, same [][]string) -----------------
	w := csv.NewWriter(os.Stdout)
	_ = w.Write([]string{"NAME", "COUNT", "STATUS"})
	_ = w.WriteAll(rows)
	w.Flush()

	// ---- json (stdlib, from the struct slice) ------------------------
	b, err := json.Marshal(items)
	if err != nil {
		fmt.Fprintln(os.Stderr, "json:", err)
		os.Exit(1)
	}
	os.Stdout.WriteString(string(b) + "\n")
}
