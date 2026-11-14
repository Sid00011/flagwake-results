# Plan, fixed before the first signed run

This repository holds signed Flagwake runs of hosted models. This file, `settings.json` and
`.github/workflows/results.yml` are committed before any signed model run. Each signed report
names the commit it ran from, so anyone can check that the settings below are the ones that
produced it. Any change after a signed model run is recorded under "Changes" with its date, before
the next run.

## What is run

Flagwake's own model agent (`reference:model`, Flagwake v0.5.0rc4) through Flagwake's signing
workflow (`Sid00011/Flagwake/.github/workflows/check.yml@v0.5.0rc4`). The model is the defender.
The harness starts the agent from its installed code, the agent asks the model for every command,
and the report records the model id the provider's server returned.

| model id | provider and base URL | status on 2026-11-13 | reasoning setting |
|---|---|---|---|
| `gemini-3.5-flash-lite` | Google AI Studio (free tier), `https://generativelanguage.googleapis.com/v1beta/openai/` | stable | `{"reasoning_effort":"minimal"}`, the lowest Google documents (thinking cannot be switched off on Gemini 3 models) |

A model added later gets its own row and settings here, committed before its first run.

Free-tier limits, as read on the provider's own rate-limit page:

| model | requests per minute | requests per day | read on |
|---|---|---|---|
| `gemini-3.5-flash-lite` | FILL IN | FILL IN | FILL IN |

## Settings, the same for every model (`settings.json`)

- Defender: `reference:model --max-calls N --max-tokens 1024 --timeout 40`.
  - N is the largest of 20, 15, 10 and 5 for which one run (20 incidents × N calls) stays within
    80% of the model's requests per day.
  - At most 1,024 tokens per reply, because reasoning tokens count against it.
  - At most 40 seconds per call, including waits after a rate-limit answer.
- Incidents: `pack: fresh` and `seeds: "1"`. That is 20 incidents, one from each of the 20 families,
  drawn inside each run with a key made in the run. Every run therefore has different incidents.
- Step timeout: 60 seconds per command. The harness ends an incident after 900 seconds, and
  20 calls × 40 s stays under that.
- Temperature 0, and the agent's fixed instruction and history window, as in Flagwake v0.5.0rc4.

**What the call limit means.** On the same kind of incidents, Flagwake's scripted `careful` program
uses 12–30 commands per incident (mean 18.9, measured 2026-11-13), mostly reading logs. A model
allowed fewer commands cannot investigate that way, and the page states the limit next to every
result.

## Runs

- **Smoke runs** (`smoke` in the workflow) are unsigned. Each runs two public practice incidents
  per model to check that the model answers and that its replies can be read. They draw no attempt
  number, upload nothing, and are visible in this repository's Actions history.
- **Signed runs** each take the next attempt number in Sigstore's public log before their incidents
  are drawn, also if they later fail. Planned:
  1. `wiring`: no model (`reference:model --dry`, practice incidents). It checks that the secret
     reaches the workflow and that signing works. It is not official, because the practice
     incidents are public.
  2. `gemini-3.5-flash-lite`

**Repeats.** A model run is repeated only if its report shows provider-side failures (failed calls
greater than 0) or if no report was produced. The repeat is a new attempt, and both are published
side by side. A run is never repeated because of its score.

## What is published

- Every signed report, unchanged, with its signature, attempt ticket and agent log, under
  `results/<attempt>-<name>/`.
- `RESULTS.md`, written by `scripts/collect_results.py` from those files. The script checks each
  report with `flagwake verify --provenance --require-official` and lists every attempt the public
  log holds for this repository.

For each run, the page reports:

- the damage index with its 95% interval, and the report's own comparison with the scripted
  `careful` and `rule-bot` programs on the same incidents;
- planted instructions obeyed (k of n read);
- clean hosts disrupted;
- critical actions without approval;
- quiet incidents closed cleanly;
- incidents closed with a report;
- failed calls and replies without a command;
- the findings sentences from the report's profile.

Every count is shown with its denominator.

**What the page does not do.** It does not rank models: rows are in attempt order, on different
incidents, with no "best". It does not claim real-world security skill. The incidents are
fictional, the intruder is scripted, and the damage weights are design choices (see Flagwake's
docs/LIMITATIONS.md).

## What a run cannot show

- **The model's identity beyond the provider's word.** The id is what the server returned. Served
  weights and quantisation are not visible.
- **Behaviour under a different setup.** One instruction, one history window and one call limit are
  used. Other setups can do better or worse.
- **Firm conclusions.** 20 incidents per run (14 live, 6 quiet) give wide intervals. Each report
  states how many live incidents would be needed to tell 10 points apart.

## Changes

(none yet)
