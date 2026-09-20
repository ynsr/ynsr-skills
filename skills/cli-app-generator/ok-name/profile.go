// profile.go — optional profiles add-on (spec §2.4; scaffolded with --profiles): 0600 JSON
// store under os.UserConfigDir()/<tool>/profiles. Secrets come from the environment only —
// never flags, never stdout; the store holds the URL and a token captured at create time
// from OK_NAME_TOKEN if exported, else an empty token.

package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log/slog"
	"net/url"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/jedib0t/go-pretty/v6/table"
	"github.com/spf13/cobra"
)

type profile struct {
	Name    string `json:"name"`
	URL     string `json:"url"`
	Token   string `json:"token"`
	Default bool   `json:"default"`
}

func init() { extraCmds = append(extraCmds, profileCmd()) }

func profileDir() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(base, "ok-name", "profiles"), nil
}

func profilePath(name string) (string, error) {
	if name == "" {
		return "", errors.New("empty profile name")
	}
	dir, err := profileDir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, name+".json"), nil
}

func saveProfile(p profile) error { // 0600: profile stores may carry captured tokens
	path, err := profilePath(p.Name)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o700); err != nil {
		return err
	}
	body, err := json.MarshalIndent(p, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(body, '\n'), 0o600)
}

func loadProfile(name string) (profile, error) {
	path, err := profilePath(name)
	if err != nil {
		return profile{}, err
	}
	body, err := os.ReadFile(path)
	if err != nil {
		return profile{}, err
	}
	var p profile
	return p, json.Unmarshal(body, &p)
}

func listProfiles() []profile {
	dir, err := profileDir()
	if err != nil {
		return nil
	}
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil
	}
	var out []profile
	for _, e := range entries {
		if !strings.HasSuffix(e.Name(), ".json") {
			continue
		}
		if p, err := loadProfile(strings.TrimSuffix(e.Name(), ".json")); err == nil {
			out = append(out, p)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

func defaultProfile() (profile, error) {
	for _, p := range listProfiles() {
		if p.Default {
			return p, nil
		}
	}
	if len(listProfiles()) == 1 {
		return listProfiles()[0], nil // single profile acts as default
	}
	return profile{}, errors.New("no default profile")
}

// tokenShape masks secrets in list output: set/unset plus a length hint, never the value.
func tokenShape(token string) string {
	if token == "" {
		return "unset"
	}
	return fmt.Sprintf("set(%d chars)", len(token))
}

// profileEmit renders profile rows through the same global --output machinery as emit
// (identical go-pretty ASCII style — box-drawing styles would taint stdout).
func profileEmit(ps []profile, w io.Writer) error {
	if asJSON {
		return json.NewEncoder(w).Encode(ps) // []profile already carries the JSON tags
	}
	tw := table.NewWriter()
	tw.SetStyle(table.StyleDefault)
	tw.AppendHeader(table.Row{"NAME", "URL", "TOKEN", "DEFAULT"})
	for _, p := range ps {
		tw.AppendRow(table.Row{p.Name, p.URL, tokenShape(p.Token), fmt.Sprintf("%v", p.Default)})
	}
	render, ok := map[string]func() string{"table": tw.Render, "csv": tw.RenderCSV, "tsv": tw.RenderTSV}[output]
	if !ok {
		return cerr{2, fmt.Sprintf("invalid --output %q", output), "want table|json|csv|tsv"}
	}
	_, _ = fmt.Fprintln(w, render())
	return nil
}


func profileCmd() *cobra.Command {
	cmd := &cobra.Command{Use: "profile", Short: "Manage connection profiles (0600 store, secrets via env)"}
	cp := &cobra.Command{Use: "create NAME --url URL", Short: "Create a profile (token from the environment)", Args: cobra.ExactArgs(1), RunE: createProfile}
	cp.Flags().String("url", "", "API base URL (http/https)")
	_ = cp.MarkFlagRequired("url")
	cp.Flags().Bool("default", false, "make this the default profile")
	rp := &cobra.Command{Use: "remove [NAME]", Short: "Remove a profile (--dry-run previews; --yes executes)",
		Args: cobra.MaximumNArgs(1), RunE: removeProfile}
	rp.Flags().BoolVar(&dryRun, "dry-run", false, "print the plan to stdout; change nothing")
	rp.Flags().BoolVarP(&yes, "yes", "y", false, "execute; the tool never prompts, it refuses without --yes")
	cmd.AddCommand(cp,
		&cobra.Command{Use: "list", Short: "List profiles (honors --output/--json)", RunE: func(*cobra.Command, []string) error {
			return profileEmit(listProfiles(), os.Stdout)
		}},
		rp,
	)
	return cmd
}

func createProfile(cp *cobra.Command, args []string) error {
	name := args[0]
	for _, r := range name { // profile names become file names in the 0600 store
		switch {
		case r >= 'a' && r <= 'z', r >= '0' && r <= '9', r == '-', r == '_':
		default:
			return cerr{2, fmt.Sprintf("invalid profile name %q", name), "use lowercase letters, digits, - or _"}
		}
	}
	raw, _ := cp.Flags().GetString("url")
	u, err := url.Parse(raw)
	if err != nil || (u.Scheme != "http" && u.Scheme != "https") || u.Host == "" {
		return cerr{2, fmt.Sprintf("invalid --url %q", raw), "want http(s)://host[:port]/..."}
	}
	def, _ := cp.Flags().GetBool("default")
	p := profile{Name: name, URL: raw, Token: os.Getenv("OK_NAME_TOKEN"), Default: def}
	if err := saveProfile(p); err != nil {
		return cerr{1, err.Error(), "check the profile store permissions"}
	}
	path, err := profilePath(p.Name)
	if err != nil {
		return cerr{1, err.Error(), "check the profile store permissions"}
	}
	_, _ = fmt.Fprintln(os.Stdout, path) // data → stdout
	return nil
}

func removeProfile(_ *cobra.Command, args []string) error {
	name := ""
	if len(args) == 1 {
		name = args[0]
	} else {
		return cerr{2, "profile remove requires a NAME", "profile remove <name> [--yes]"}
	}
	if _, err := loadProfile(name); err != nil {
		return cerr{1, err.Error(), "profile list shows stored names"}
	}
	if dryRun {
		_, _ = fmt.Fprintf(os.Stdout, "plan: rm %s\n", mustPath(name)) // the plan is data → stdout
		return nil
	}
	if !yes {
		return cerr{2, "refusing to remove profile without --yes", "append --yes to execute; --dry-run previews the plan"}
	}
	if err := os.Remove(mustPath(name)); err != nil {
		return cerr{1, err.Error(), "check the path"}
	}
	slog.Info("removed profile", "name", name)
	return nil
}

func mustPath(name string) string {
	path, err := profilePath(name)
	if err != nil {
		return name
	}
	return path
}
