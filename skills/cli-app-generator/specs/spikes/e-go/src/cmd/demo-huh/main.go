// Probe: charm.land/huh/v2 select picker.
// Tests: render stream (stdout vs stderr), non-TTY behavior, Ctrl-C restore.
// Env switches for instrumentation:
//
//	HUH_STDERR=1  -> form.WithOutput(os.Stderr)
//	HUH_INPUT=<fd> -> unused; stdin comes from the shell redirection
package main

import (
	"errors"
	"fmt"
	"os"

	"charm.land/huh/v2"
)

func main() {
	var choice string
	sel := huh.NewSelect[string]().
		Title("Pick an output format").
		Description("Arrow keys + enter, q to quit").
		Options(
			huh.NewOption("table", "table"),
			huh.NewOption("json", "json"),
			huh.NewOption("csv", "csv"),
			huh.NewOption("tsv", "tsv"),
		).
		Value(&choice)

	form := huh.NewForm(huh.NewGroup(sel)).WithShowHelp(true)
	if os.Getenv("HUH_STDERR") != "" {
		form = form.WithOutput(os.Stderr)
	}

	switch err := form.Run(); {
	case err == nil:
		// selected: value to stdout (data-only), everything else stays away
		fmt.Println(choice)
	case errors.Is(err, huh.ErrUserAborted):
		fmt.Fprintln(os.Stderr, "picker: aborted by user")
		os.Exit(130)
	case errors.Is(err, huh.ErrTimeout):
		fmt.Fprintln(os.Stderr, "picker: timeout")
		os.Exit(4)
	default:
		fmt.Fprintf(os.Stderr, "picker: %v\n", err)
		os.Exit(1)
	}
}
