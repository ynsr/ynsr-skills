package main

import (
	"bytes"
	"encoding/json"
	"errors"
	"strings"
	"testing"
)

func resetOutput(format string, asjson bool) {
	output, asJSON = format, asjson
}

func TestEmitTableHasHeaderAndRows(t *testing.T) {
	resetOutput("table", false)
	var b bytes.Buffer
	if err := emit(sample, &b); err != nil {
		t.Fatalf("emit table: %v", err)
	}
	out := b.String()
	if !strings.Contains(out, "NAME") || !strings.Contains(out, "alpha") {
		t.Errorf("table missing header/rows:\n%s", out)
	}
}

func TestEmitCSVAndTSVHeaders(t *testing.T) {
	for format, header := range map[string]string{"csv": "NAME,SIZE,STATUS", "tsv": "NAME\tSIZE\tSTATUS"} {
		resetOutput(format, false)
		var b bytes.Buffer
		if err := emit(sample, &b); err != nil {
			t.Fatalf("emit %s: %v", format, err)
		}
		if got := strings.SplitN(b.String(), "\n", 2)[0]; got != header {
			t.Errorf("%s header = %q, want %q", format, got, header)
		}
	}
}

func TestEmitJSONRoundtrip(t *testing.T) {
	resetOutput("", true) // --json alias forces json regardless of --output
	var b bytes.Buffer
	if err := emit(sample, &b); err != nil {
		t.Fatalf("emit json: %v", err)
	}
	var items []item
	if err := json.Unmarshal(b.Bytes(), &items); err != nil {
		t.Fatalf("json output does not parse: %v (%s)", err, b.String())
	}
	if len(items) != len(sample) || items[0].Name != "alpha" {
		t.Errorf("unexpected items: %+v", items)
	}
}

func TestEmitInvalidFormatIsUsageError(t *testing.T) {
	resetOutput("bogus", false)
	var b bytes.Buffer
	err := emit(sample, &b)
	var c cerr
	if !errors.As(err, &c) || c.code != 2 {
		t.Fatalf("want cerr{2}, got %v", err)
	}
}

func TestEnvelopeShape(t *testing.T) {
	got := envelope(cerr{2, "boom", "try this"})
	var parsed struct {
		Error struct {
			Code, Message, Hint string
		} `json:"error"`
	}
	if err := json.Unmarshal([]byte(got), &parsed); err != nil {
		t.Fatalf("envelope not JSON: %v (%s)", err, got)
	}
	if parsed.Error.Code != "usage" || parsed.Error.Message != "boom" || parsed.Error.Hint != "try this" {
		t.Errorf("envelope fields wrong: %+v", parsed.Error)
	}
}

func TestCodeOfClassifiesUsageErrors(t *testing.T) {
	for s, want := range map[string]int{
		`unknown command "x" for "sample"`: 2,
		"unknown flag: --bogus":            2,
		"accepts 1 arg(s), received 0":     2,
		"requires at least 1 arg(s)":       2,
		"some runtime failure":             1,
	} {
		if got := codeOf(errors.New(s)); got != want {
			t.Errorf("codeOf(%q) = %d, want %d", s, got, want)
		}
	}
	if got := codeOf(cerr{4, "partial", ""}); got != 4 {
		t.Errorf("codeOf(cerr) = %d, want 4", got)
	}
}
