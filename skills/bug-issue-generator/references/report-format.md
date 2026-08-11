# Bug Report Format & Claim Filtering

## Filter claims first
Exclude a claim if, later in the source, any of these appear:
- Explicit correction/retraction ("actually not it," "false alarm," "my mistake")
- Uncorrected contradiction
- Resolution statement saying it wasn't a bug ("user error," "not reproducible," "working as intended")
- Off-topic/joking content, not a genuine technical claim

Don't mention excluded claims or explain the exclusion — write as if only the valid claims existed.

## Missing info
No evidence for a field → write exactly `Not provided in thread`. Never invent logs, timestamps, versions, or steps.

## Output template
Output only this, filled in, no preamble, no process explanation:

```markdown
## Title
[component] — [short symptom]. No vague standalone words like "issue"/"problem". Use the resolved glossary term where one exists, not the source's loose wording.

## Description
2–5 sentences, your own words — what's happening, observed impact.

## Steps to Reproduce
Numbered, only if reconstructable. Else: "Not provided in thread".

## Expected vs Actual Behavior
- **Expected:** [one sentence]
- **Actual:** [one sentence]

## Environment / Affected Service
Service, environment, version if mentioned. Else: "Not provided in thread".

## Logs & Evidence
Bullet list, quoted verbatim — the one section left un-normalized. Else: "Not provided in thread".

## Severity
Critical/High/Medium/Low + one-sentence justification.
```

## Out of scope
- No real names — use roles ("reporter," "on-call").
- No tracker-specific markup — plain Markdown only.
- No text outside the six sections.
