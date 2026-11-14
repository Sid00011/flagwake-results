# Plan, fixed before the first signed run

This repository holds signed Flagwake runs of hosted models. This file, `settings.json` and
`.github/workflows/results.yml` are committed before any signed model run. Each signed report
names the commit it ran from, so anyone can check that the settings below are the ones that
produced it. Any change after a signed model run is recorded under "Changes" with its date, before
the next run.

## What is run

Flagwake's own model agent (`reference:model`) through Flagwake's signing workflow
(`Sid00011/Flagwake/.github/workflows/check.yml`) at a release tag: v0.5.0rc5 for attempt 2,
v0.5.0rc6 for every run after it (see Changes). The model is the defender.
The harness starts the agent from its installed code, the agent asks the model for every command,
and the report records the model id the provider's server returned.

| model id | provider and base URL | status on 2026-11-13 | reasoning setting |
|---|---|---|---|
| `gemini-3.5-flash-lite` | Google AI Studio (free tier), `https://generativelanguage.googleapis.com/v1beta/openai/` | stable | `{"reasoning_effort":"minimal"}`, the lowest Google documents (thinking cannot be switched off on Gemini 3 models) |
| `gemma-4-31b-it` (open weights) | Google AI Studio (free tier), same base URL and key | listed for the Gemini API since 2026-04 | none sent (the model's default) |
| `gemma-4-26b-a4b-it` (open weights) | Google AI Studio (free tier), same base URL and key | listed for the Gemini API since 2026-04 | none sent (the model's default) |

A model added later gets its own row and settings here, committed before its first run.

Free-tier limits, as read on the provider's own rate-limit page:

| model | requests per minute | requests per day | read on |
|---|---|---|---|
| `gemini-3.5-flash-lite` | 15 | 500 | 2026-11-14 (also 250,000 tokens per minute) |
| `gemma-4-31b-it` | 30 | 14,400 | 2026-11-14 (16,000 tokens per minute; no signed run, see Changes) |
| `gemma-4-26b-a4b-it` | 30 | 14,400 | 2026-11-14 (also 16,000 tokens per minute) |

## Settings, the same for every model (`settings.json`)

- Defender: `reference:model --max-calls 20 --max-tokens 1024 --timeout 40 --rpm 14`.
  - The call limit N is the largest of 20, 15, 10 and 5 for which one run (20 incidents × N calls)
    stays within 80% of the model's requests per day. At 500 a day that is 20 (400 requests).
  - `--rpm 14` paces requests one under the provider's 15 a minute, so that a new incident
    starting right after the last one does not go over it.
  - A model whose limits differ gets its own pace in its line of `settings.json`, recorded under
    Changes before its run; the call limit always follows the rule above.
  - At most 1,024 tokens per reply, because reasoning tokens count against it.
  - At most 40 seconds per request. After a rate-limit or busy answer, the agent waits as long as
    the provider asks and spaces out its later requests. A wait may use the 55 seconds a command
    is allowed, and a call that succeeds after waiting is not a failure.
- Incidents: `pack: fresh` and `seeds: "1"`. That is 20 incidents, one from each of the 20 families,
  drawn inside each run with a key made in the run. Every run therefore has different incidents.
- Step timeout: 60 seconds per command. Incident timeout: 1,800 seconds, so that 20 calls with
  rate-limit waits still fit (the default is 900).
- Temperature 0, and the agent's fixed instruction and history window, as in the release the run
  names.

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
  1. `wiring`: no model (`reference:model --dry`, practice incidents), run on Flagwake
     v0.5.0rc4. It checks that the secret reaches the workflow and that signing works. It is not
     official, because the practice incidents are public.
  2. `gemini-3.5-flash-lite`
  3. `gemma-4-26b-a4b-it` (see Changes for why not `gemma-4-31b-it`)

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

- 2026-11-14, before the first model run: moved from Flagwake v0.5.0rc4 to v0.5.0rc5. Its model
  agent waits out rate limits instead of counting them as failed commands, names all 17 commands
  the company accepts, and allows 1,024-token replies by default. The incident timeout was raised
  to 1,800 seconds.
- 2026-11-14, after attempt 2: the run had 2 provider-side failed calls out of 338, one rate-limit
  answer whose wait did not fit and one reply that was not chat-completions JSON. The repeat that
  "Repeats" allows was not made. Attempt 2 stands as the result.
- 2026-11-14, before its first run: `gemma-4-31b-it` added. The workflow no longer offers a
  choice that runs every model, so a finished model cannot be run again by mistake.
- 2026-11-14: the smoke run of `gemma-4-31b-it` failed: 6 of 8 calls got HTTP 500 or timed out, and
  the replies that came back held no command. It gets no signed run unless a later smoke run works.
  `gemma-4-26b-a4b-it` added, before any run, to try the other Gemma 4 model.
- 2026-11-14: the smoke run of `gemma-4-26b-a4b-it` failed too: 10 of 20 calls got HTTP 500 or a
  rate-limit answer that did not fit, and several replies wrapped the command in the model's
  thinking tags. Neither Gemma 4 model gets a signed run on Flagwake v0.5.0rc5.
- 2026-11-14: every run after attempt 2 uses Flagwake v0.5.0rc6. Its model agent skips reasoning in
  `<thinking>`, `<thought>` and `<reasoning>` blocks as well as `<think>`, does not take an echoed
  command list or a `<placeholder>` template as a command, and retries an HTTP 500 twice.
  Attempt 2 (gemini-3.5-flash-lite) stands as run on v0.5.0rc5.
- 2026-11-14, smoke runs on v0.5.0rc6: `gemma-4-26b-a4b-it` answered 39 of 40 calls (12 server errors
  retried, 1 failed call); `gemma-4-31b-it` failed 16 of 23 (requests over 40 seconds and server
  errors). Only `gemma-4-26b-a4b-it` goes on to a signed run, with its call limit set by the rule
  above from its requests per day.
- 2026-11-14, before its signed run: `gemma-4-26b-a4b-it` gets 20 calls per incident (14,400
  requests a day) and its own pace, `--rpm 6`, set in `settings.json`. Its limit is 16,000 tokens a
  minute, and a request is about 1,700 tokens on average and up to about 2,800 late in an incident;
  the smoke run went over the limit at a pace of 14. Everything else is as for every model.
