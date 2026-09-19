// Probe: cobra command wrapped with charm.land/fang/v2.
// Tests: --help rendering, NO_COLOR/TERM=dumb output, non-TTY behavior,
// error paths, exit codes, completion + man generation.
package main

import (
	"context"
	"fmt"
	"os"

	"charm.land/fang/v2"
	"github.com/spf13/cobra"
)

type opts struct {
	output  string
	asJSON  bool
	verbose int
	quiet   bool
	dryRun  bool
	yes     bool
}

var sample = []string{"alpha", "beta", "gamma"}

func main() {
	o := &opts{}
	root := &cobra.Command{
		Use:     "demo-fang",
		Short:   "Spike E probe: cobra + fang rendering",
		Long:    "A probe binary for the Go CLI stack spike. Emits sample rows.",
		Version: "0.1.0-spike",
	}
	root.PersistentFlags().StringVarP(&o.output, "output", "o", "table", "output format (table|json|csv|tsv)")
	root.PersistentFlags().BoolVar(&o.asJSON, "json", false, "shorthand for --output json")
	root.PersistentFlags().CountVarP(&o.verbose, "verbose", "v", "increase verbosity (repeatable)")
	root.PersistentFlags().BoolVarP(&o.quiet, "quiet", "q", false, "suppress non-essential output")
	root.PersistentFlags().BoolVar(&o.dryRun, "dry-run", false, "show what would run, change nothing")
	root.PersistentFlags().BoolVarP(&o.yes, "yes", "y", false, "assume yes; skip confirmation prompts")

	getCmd := &cobra.Command{
		Use:               "get",
		Short:             "Fetch sample items",
		Args:              cobra.NoArgs,
		DisableAutoGenTag: true,
		RunE: func(cmd *cobra.Command, args []string) error {
			format := o.output
			if o.asJSON {
				format = "json"
			}
			switch format {
			case "table":
				for i, s := range sample {
					fmt.Printf("%d  %-8s\n", i+1, s)
				}
			case "json":
				fmt.Println(`{"items":["alpha","beta","gamma"]}`)
			case "csv":
				fmt.Println("idx,name")
				for i, s := range sample {
					fmt.Printf("%d,%s\n", i+1, s)
				}
			case "tsv":
				fmt.Println("idx\tname")
				for i, s := range sample {
					fmt.Printf("%d\t%s\n", i+1, s)
				}
			default:
				return fmt.Errorf("invalid format %q: want table|json|csv|tsv", format)
			}
			return nil
		},
	}
	root.AddCommand(getCmd)

	if err := fang.Execute(context.Background(), root); err != nil {
		os.Exit(1)
	}
}
