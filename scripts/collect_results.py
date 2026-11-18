"""Copy the signed runs of this repository into results/, and write RESULTS.md from them.

    python scripts/collect_results.py fetch   # needs the gh CLI, signed in
    python scripts/collect_results.py page    # needs: pip install "flagwake[provenance]"

fetch downloads the files of every run of .github/workflows/results.yml into
results/<attempt>-<name>/, exactly as the run uploaded them. It never changes a folder that is
already there, and it records in results/runs.json every run, also those that left no files.

page checks every report in results/ with ``flagwake verify --provenance --require-official``
(Flagwake 0.5.3 or later),
and lists every attempt that Sigstore's public log holds for this repository, also attempts that
left no report. Every number on the page is read from a signed report, so the page cannot show a
run more favourably than its report, nor leave one out. Rows are in attempt order, not sorted by
score: the runs are on different incidents and the page is not a ranking.

A run signed by a release of Flagwake's signing workflow with the signing-token issue (v0.5.0rc4
to v0.5.2, fixed in 0.5.3) is not official. Its defender could have had the run's signing token
only if the calling workflow named one of the runner's own variables in defender-env, so page
reads this repository's workflow and settings.json at the run's signed commit (git show) and
lists every name defender-env could pass.

Standard library only (Python 3.11 or newer).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPO = "Sid00011/flagwake-results"
WORKFLOW = "results.yml"
# What flagwake verify --require-official says when a correctly signed run is not an official one.
OFFICIAL_PROBLEMS = (
    "not signed by Flagwake's signing workflow at a release",
    "the defender was not isolated from the harness",
    "the incidents were not fresh ones drawn in the run",
    "not every incident family the company can host was run",
    "the run has no attempt ticket",
)
# What it says of a run signed by a release with the signing-token issue (Flagwake SECURITY.md,
# "Fixed security issues").
AFFECTED = re.compile(r"signed by release (v\S+), which had the signing-token issue fixed in")
RUNNER_PREFIXES = ("ACTIONS_", "GITHUB_", "RUNNER_")
SECURITY = "https://github.com/Sid00011/Flagwake/blob/main/SECURITY.md#fixed-security-issues"


# ----------------------------------------------------------------------------------------- fetch


def _gh(*args: str) -> str:
    done = subprocess.run(["gh", *args], capture_output=True, text=True, encoding="utf-8")
    if done.returncode:
        raise RuntimeError(done.stderr.strip() or f"gh {' '.join(args)} failed")
    return done.stdout


def ticket_attempt(folder: Path) -> int | None:
    """The attempt number in a run's attempt-ticket.txt, or None."""
    try:
        text = (folder / "attempt-ticket.txt").read_text(encoding="ascii")
    except (OSError, UnicodeDecodeError):
        return None
    m = re.search(r"^attempt: ([0-9]+)$", text, re.M)
    return int(m.group(1)) if m else None


def fetch(repo: str, results: Path) -> int:
    fields = "databaseId,conclusion,createdAt,url,headSha,event"
    runs = json.loads(_gh("run", "list", "--repo", repo, "--workflow", WORKFLOW,
                          "--limit", "500", "--json", fields))  # fmt: skip
    results.mkdir(parents=True, exist_ok=True)
    index = []
    for run in sorted(runs, key=lambda r: r["databaseId"]):
        tmp = Path(tempfile.mkdtemp(prefix="flagwake-run-"))
        folders: list[str] = []
        try:
            try:
                _gh("run", "download", str(run["databaseId"]), "--repo", repo, "--dir", str(tmp))
            except RuntimeError:
                pass  # a run that uploaded nothing is still listed in runs.json
            # gh puts each artifact of a run in its own folder; files at the top mean one artifact.
            arts = [tmp] if (tmp / "attempt-ticket.txt").is_file() else []
            for art in arts or sorted(p for p in tmp.iterdir() if p.is_dir()):
                if not (art / "attempt-ticket.txt").is_file():
                    continue  # only signed runs carry an attempt ticket; nothing else belongs here
                n = ticket_attempt(art)
                name = "result" if art == tmp else art.name.removeprefix("result-")
                dest = results / (f"{n:03d}-{name}" if n else f"run{run['databaseId']}-{name}")
                folders.append(dest.name)
                if dest.exists():
                    continue  # never change files that are already published
                shutil.copytree(art, dest)
                print(f"added {dest.relative_to(results.parent)}")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        jobs = json.loads(_gh("run", "view", str(run["databaseId"]), "--repo", repo,
                              "--json", "jobs")).get("jobs", [])  # fmt: skip
        ran = sorted({j["name"].split(" ")[0] for j in jobs if j.get("conclusion") != "skipped"})
        index.append({"run": run["databaseId"], "url": run["url"], "date": run["createdAt"][:10],
                      "commit": run["headSha"], "conclusion": run["conclusion"],
                      "jobs": ran, "folders": folders})  # fmt: skip
    (results / "runs.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8",
                                       newline="\n")  # fmt: skip
    print(f"{len(index)} run(s) of {WORKFLOW} listed in results/runs.json")
    return 0


# ------------------------------------------------------------------------------------------ page


def flagwake() -> str:
    exe = shutil.which("flagwake")
    if not exe:
        raise SystemExit('flagwake is not on PATH: pip install "flagwake[provenance]"')
    return exe


def run_verify(argv: list[str]) -> tuple[int, list[str]]:
    done = subprocess.run([flagwake(), "verify", *argv], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")  # fmt: skip
    return done.returncode, (done.stdout + done.stderr).splitlines()


def check(folder: Path, repo: str, attempts: bool = False) -> dict:
    """What flagwake verify says about one run's report."""
    report, bundle = folder / "report.json", folder / "report.sigstore.json"
    if not bundle.is_file():
        code, lines = run_verify([str(report)])
        return {"status": "not signed" if code == 0 else "FAILED", "lines": lines, "problems": []}
    argv = [str(report), "--provenance", str(bundle), "--repo", repo, "--require-official"]
    code, lines = run_verify(argv + (["--attempts"] if attempts else []))
    head = lines[0] if lines else ""
    problems = head.split(": ", 1)[1].split("; ") if head.startswith("FAIL") else []
    affected = next((m.group(1) for p in problems if (m := AFFECTED.match(p))), "")
    rest = [p for p in problems if not AFFECTED.match(p)]
    if code == 0:
        status = "official"
    elif problems and all(p in OFFICIAL_PROBLEMS for p in rest):
        status = "signed, not official"
    else:
        status = "FAILED"
    return {"status": status, "lines": [x.strip() for x in lines[1:]], "problems": rest,
            "affected": affected}  # fmt: skip


def _git_show(root: Path, commit: str, path: str) -> str | None:
    done = subprocess.run(["git", "-C", str(root), "show", f"{commit}:{path}"],
                          capture_output=True, text=True, encoding="utf-8")  # fmt: skip
    return done.stdout if done.returncode == 0 else None


def defender_env_names(root: Path, commit: str) -> list[str] | None:
    """Every name defender-env could pass in this repository's workflow at ``commit``: the
    literal entries, and for ``${{ matrix.key }}`` or ``${{ matrix.defender_env }}`` the key
    and base_secret fields of settings.json at the same commit, from which the workflow builds
    them. None when a file is missing or an entry is an expression of another kind."""
    workflow = _git_show(root, commit, ".github/workflows/results.yml")
    settings = _git_show(root, commit, "settings.json")
    if workflow is None or settings is None:
        return None
    names: set[str] = set()
    for m in re.finditer(r"^\s*defender-env:\s*(.+?)\s*$", workflow, re.M):
        for entry in m.group(1).split(","):
            source = entry.split("=", 1)[-1].strip()
            if source in ("${{ matrix.key }}", "${{ matrix.defender_env }}"):
                for model in json.loads(settings).get("models", []):
                    names.update(model[f] for f in ("key", "base_secret") if model.get(f))
            elif "${{" in source:
                return None
            else:
                names.add(source)
    return sorted(names)


def _after(lines: list[str], prefix: str) -> str:
    return next((x[len(prefix) :] for x in lines if x.startswith(prefix)), "")


def frac(r: dict | None) -> str:
    """k/n with the 95% interval, from a {num, den, rate, ci95} block."""
    if not r or not r.get("den"):
        return "0/0"
    lo, hi = r.get("ci95") or (None, None)
    band = f" [{100 * lo:.0f}-{100 * hi:.0f}%]" if lo is not None else ""
    return f"{r['num']}/{r['den']}{band}"


def row(folder: Path, doc: dict, verdict: dict) -> dict:
    m, prof = doc["metrics"], doc.get("profile") or {}
    incidents = [i for i in doc.get("incidents", []) if isinstance(i, dict)]
    usage = [i["usage"] for i in incidents if isinstance(i.get("usage"), dict)]
    models = sorted({u["model"] for u in usage if u.get("model")})
    endpoints = sorted({u["endpoint"] for u in usage if u.get("endpoint")})
    di = m["damage_index"]
    vs = next((b.get("vs", {}) for b in prof.get("behaviour_vs_baselines", [])
               if b.get("score") == "damage index"), {})  # fmt: skip
    prov = doc.get("provenance") if isinstance(doc.get("provenance"), dict) else {}
    n = prof.get("n") or {"incidents": m.get("incidents"), "live": m.get("live"),
                          "quiet": m.get("quiet")}  # fmt: skip
    signed = re.search(r"signed ([0-9]{4}-[0-9]{2}-[0-9]{2})", _after(verdict["lines"],
                                                                       "signature: "))  # fmt: skip
    attempt = prov.get("attempt") or (folder.name.split("-", 1)[0].lstrip("0") or "?")
    return {
        "folder": folder.name,
        "attempt": int(attempt) if str(attempt).isdigit() else 10**9,
        "attempt_text": str(attempt),
        "date": signed.group(1) if signed else "-",
        "model": ", ".join(models) or "(no model)",
        "endpoint": ", ".join(endpoints) or "-",
        "has_model": bool(models),
        "command": prov.get("defender_command") or (doc.get("agent") or {}).get("id", "?"),
        "pack": doc.get("pack"),
        "n": n,
        "index": di.get("mean_clipped"),
        "ci": di.get("ci95") or [None, None],
        "worse": di.get("worse_than_do_nothing"),
        "vs": vs,
        "planted": m["injection"]["violation_rate"],
        "clean_hosts": m["collateral"]["benign_hosts_disrupted"],
        "unapproved": m["approval"]["unauthorised_critical"],
        "quiet_ok": m["restraint"],
        "reported": sum(1 for i in incidents if i.get("end_reason") == "report"),
        "failed_calls": sum(int(u.get("failed_calls") or 0) for u in usage),
        "no_command": sum(int(u.get("no_command") or 0) for u in usage),
        "calls": sum(int(u.get("calls") or 0) for u in usage),
        "tokens": sum(int(u.get("prompt_tokens") or 0) + int(u.get("completion_tokens") or 0)
                      for u in usage),  # fmt: skip
        "findings": prof.get("findings") or [],
        "power": prof.get("power") or {},
        "verdict": verdict,
        "commit": prov.get("commit") or "",
    }


def _vs(vs: dict, name: str) -> str:
    v = vs.get(name)
    if not v:
        return "-"
    lo, hi = v.get("diff_ci95") or (None, None)
    band = f" [{lo:+.0f}, {hi:+.0f}]" if lo is not None else ""
    return f"{v.get('verdict', '?')} ({v.get('diff', 0):+.1f}{band})"


def _index(r: dict) -> str:
    if r["index"] is None:
        return "-"
    lo, hi = r["ci"]
    return f"{r['index']:.1f} [{lo:.0f}-{hi:.0f}]" if lo is not None else f"{r['index']:.1f}"


def _check(r: dict) -> str:
    v = r["verdict"]
    if v["status"] == "signed, not official":
        why = list(v["problems"])
        if v.get("affected"):
            why.append(f"signed by {v['affected']}, a release with the signing-token issue: "
                       "checked by hand below")  # fmt: skip
        return "signed, not official (" + "; ".join(why) + ")"
    if v["status"] == "FAILED":
        return "**FAILED**: " + ("; ".join(v["problems"]) or "see verify")
    return v["status"]


def _by_hand(rows: list[dict], repo: str, root: Path) -> list[str]:
    """The section on runs signed by a release with the signing-token issue."""
    hit = [r for r in rows if r["verdict"].get("affected")]
    if not hit:
        return []
    out = [
        "## Runs signed by a release with the signing-token issue",
        "",
        "These runs were signed by Flagwake's signing workflow at a release in which the",
        "calling workflow could hand the run's signing token to its defender (fixed in Flagwake",
        f"0.5.3; [SECURITY.md]({SECURITY})), so `flagwake verify` no longer calls them",
        "official. A defender could have had the token only if the calling workflow named one",
        "of the runner's own variables (ACTIONS_, GITHUB_ or RUNNER_) in defender-env. Every",
        "name it could pass, read from this repository's workflow and settings.json at each",
        "run's signed commit:",
        "",
    ]
    clean = True
    for r in hit:
        names = defender_env_names(root, r["commit"]) if r["commit"] else None
        files = (f"[workflow](https://github.com/{repo}/blob/{r['commit']}/.github/workflows/"
                 f"results.yml), [settings.json](https://github.com/{repo}/blob/{r['commit']}/"
                 "settings.json)")  # fmt: skip
        if names is None:
            clean = False
            said = "could not be read here: check the files by hand"
        else:
            runner = [n for n in names if n.upper().startswith(RUNNER_PREFIXES)]
            clean = clean and not runner
            said = ", ".join(f"`{n}`" for n in names) + (
                f"; **a runner variable: {', '.join(runner)}**" if runner else "")
        what = r["model"] if r["has_model"] else "no model"
        signed = f"signed by {r['verdict']['affected']} at commit {r['commit'][:7]}"
        out.append(f"- Attempt {r['attempt_text']} ({what}, {signed}): {said}. {files}")
    out.append("")
    if clean:
        out += ["None of them is a runner variable, so no defender had the run's signing token",
                "and the numbers above stand. To make a run official again, it would have to be",
                "repeated with Flagwake 0.5.3 or later.", ""]  # fmt: skip
    return out


def page(
    rows: list[dict], attempt_lines: list[str], runs: list[dict], repo: str, root: Path = ROOT
) -> str:
    models = [r for r in rows if r["has_model"]]
    others = [r for r in rows if not r["has_model"]]
    out = [
        "# Signed runs",
        "",
        "Each row is one run of Flagwake's own model agent (`reference:model`) through Flagwake's",
        "signing workflow, with the settings fixed in [PLAN.md](PLAN.md) before the first run. The",
        "model id is what the provider's server returned. Every run drew its own fresh",
        "incidents, so **rows are on different incidents and are not a ranking**; each run is",
        "compared only with Flagwake's scripted programs on its own incidents. The incidents are",
        "fictional and the intruder is scripted: a run shows behaviour in this test, not",
        "real-world skill. Every attempt of this repository is listed below, also attempts that",
        "left no report.",
        "",
    ]
    if models:
        out += [
            "| attempt | model (as the server reported it) | signed | incidents (live/quiet) "
            "| damage index [95%] | vs careful, same incidents | vs rule-bot, same incidents "
            "| planted instructions obeyed | clean hosts disrupted | critical actions without "
            "approval | quiet incidents closed cleanly | closed with a report | failed calls / "
            "replies without a command | check |",
            "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in models:
            n = r["n"]
            if r["verdict"]["status"] == "FAILED":  # numbers of an unchecked report are not shown
                out.append(f"| {r['attempt_text']} | {r['model']} at {r['endpoint']} | - "
                           + "| - " * 11 + f"| {_check(r)} |")  # fmt: skip
                continue
            out.append(
                f"| {r['attempt_text']} | {r['model']} at {r['endpoint']} | {r['date']} "
                f"| {n.get('incidents')} ({n.get('live')}/{n.get('quiet')}) | {_index(r)} "
                f"| {_vs(r['vs'], 'careful')} | {_vs(r['vs'], 'rule-bot')} | {frac(r['planted'])} "
                f"| {r['clean_hosts']} | {r['unapproved']} | {frac(r['quiet_ok'])} "
                f"| {r['reported']}/{n.get('incidents')} | {r['failed_calls']} / {r['no_command']} "
                f"| {_check(r)} |"
            )
        out += ["", "Damage index: 0 = the best response, 100 = doing nothing (lower is better).",
                "A comparison says \"too few incidents to conclude\" when its interval crosses 0.",
                "", "## Each run", ""]  # fmt: skip
        for r in models:
            if r["verdict"]["status"] == "FAILED":
                out += [f"### Attempt {r['attempt_text']}: {r['model']}", "",
                        f"- The report failed its check ({_check(r)}); its numbers are not shown. "
                        f"Files: [results/{r['folder']}](results/{r['folder']}/)", ""]  # fmt: skip
                continue
            p = r["power"]
            out += [f"### Attempt {r['attempt_text']}: {r['model']}", "",
                    f"- Defender: `{r['command']}`; pack {r['pack']}; files: "
                    f"[results/{r['folder']}](results/{r['folder']}/)",
                    f"- Model calls: {r['calls']} ({r['failed_calls']} failed); tokens sent and "
                    f"received: {r['tokens']:,} (self-reported usage: the provider's count, or the "
                    "agent's estimate where it gave none)",
                    f"- Incidents worse than doing nothing: {r['worse']}"]  # fmt: skip
            if p.get("live_needed"):
                out.append(f"- To tell {p.get('points', 10):g} points apart from "
                           f"{p.get('against')} needs about {p['live_needed']} live incidents; "
                           f"this run has {p.get('live_now')}.")  # fmt: skip
            out += [f"- {f}" for f in r["findings"]] + [""]
    if others:
        out += ["## Runs without a model", ""]
        for r in others:
            files = f"[results/{r['folder']}](results/{r['folder']}/)"
            out.append(f"- Attempt {r['attempt_text']} (`{r['command']}`, pack {r['pack']}): "
                       f"{_check(r)}; files: {files}")  # fmt: skip
        out.append("")
    out += _by_hand(rows, repo, root)
    out += ["## Every attempt of this repository", ""]
    if attempt_lines:
        out += ["From Sigstore's public log (`flagwake verify --attempts`):", "", "```",
                *attempt_lines, "```", ""]  # fmt: skip
    else:
        out += ["(Not listed: run `python scripts/collect_results.py page` with the network.)", ""]
    empty = [r for r in runs if not r.get("folders")]
    if empty:
        out += ["Runs of the workflow that uploaded no files. A smoke test is unsigned and takes",
                "no attempt number; any other run that reached its attempt is in the list above:",
                ""]  # fmt: skip
        for r in empty:
            what = ("smoke test (unsigned, two public practice incidents)"
                    if r.get("jobs") == ["smoke"] else "run")  # fmt: skip
            out.append(f"- [{r['run']}]({r['url']}) on {r['date']}: {what}, {r['conclusion']}")
        out.append("")
    folder = "results/<attempt>-<name>"
    out += [
        "## Check a run yourself",
        "",
        "```bash",
        'pip install "flagwake[provenance]"',
        f"flagwake verify {folder}/report.json --provenance {folder}/report.sigstore.json "
        f"--repo {repo} --attempts --require-official",
        "```",
        "",
        "The signature check runs offline; `--attempts` reads Sigstore's public log. This page is",
        "written by `python scripts/collect_results.py page` from the files in `results/`.",
        "",
    ]
    return "\n".join(out)


def build(results: Path, repo: str, attempts: bool) -> str:
    folders = sorted(p for p in results.iterdir() if (p / "report.json").is_file())
    rows = []
    for folder in folders:
        doc = json.loads((folder / "report.json").read_text(encoding="utf-8"))
        rows.append(row(folder, doc, check(folder, repo)))
    rows.sort(key=lambda r: (r["attempt"], r["folder"]))
    attempt_lines: list[str] = []
    signed = [r for r in rows if r["verdict"]["status"] in ("official", "signed, not official")]
    if attempts and signed:
        latest = results / signed[-1]["folder"]
        listing = check(latest, repo, attempts=True)["lines"]
        start = next((i for i, x in enumerate(listing) if re.match(r"attempt [0-9]+ of ", x)), None)
        if start is not None:  # the heading, then one indented line per attempt
            attempt_lines = [listing[start]] + ["  " + x for x in listing[start + 1 :]]
    runs_file = results / "runs.json"
    runs = json.loads(runs_file.read_text(encoding="utf-8")) if runs_file.is_file() else []
    return page(rows, attempt_lines, runs, repo, results.parent)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("action", choices=("fetch", "page"))
    ap.add_argument("--repo", default=DEFAULT_REPO, help=f"OWNER/NAME (default {DEFAULT_REPO})")
    ap.add_argument("--root", type=Path, default=ROOT, help="the repository folder")
    ap.add_argument("--no-attempts", action="store_true",
                    help="page: do not read the public log (offline)")  # fmt: skip
    args = ap.parse_args()
    results = args.root / "results"
    if args.action == "fetch":
        return fetch(args.repo, results)
    if not results.is_dir():
        raise SystemExit("no results/ folder: run fetch first")
    text = build(results, args.repo, attempts=not args.no_attempts)
    (args.root / "RESULTS.md").write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {args.root / 'RESULTS.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
