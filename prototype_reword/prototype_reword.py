"""PROTOTYPE — throwaway. Not production code; lives only on the prototype/reword branch.

Question (fairPath-planning: "Prototype: is reword worth including in Phase 1, and with what context"):
does rewording a flagged snippet with no context invent facts, and does section-level
context plus a no-invented-facts rule fix that?

  A = current spec: snippet + issue description only
  B = the snippet's section + issue description + no-invented-facts rule with [X]-style placeholders

Each rewrite is checked automatically for numbers / proper nouns / tech names that appear
nowhere in the resume (placeholders in [brackets] are ignored).

Run (LM Studio serving on :1234):
    ../.venv/bin/python prototype_reword.py              # all cases, 3 runs per variant
    ../.venv/bin/python prototype_reword.py --runs 1 --only wri-003
    ../.venv/bin/python prototype_reword.py --dry-run    # print prompts, no LLM calls
Writes out/report-<timestamp>.md. Input resumes are synthetic.
"""

import argparse
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).parent
# Deliberately NOT reading .env: defaults point at local LM Studio only.
BASE_URL = os.environ.get("PROTO_BASE_URL", "http://localhost:1234/v1")
MODEL = os.environ.get("PROTO_MODEL", "google/gemma-4-e4b")
TEMPERATURE = 0.7

PROMPT_A = """You improve resume bullet points.

Issue found: {description}
Suggested fix: {suggestion}

Original text:
{snippet}

Rewrite the original text to fix the issue. Reply with the rewritten bullet only, no quotes, no explanation."""

PROMPT_B = """You improve resume bullet points.

Rules:
- Use ONLY facts stated in the original text or the surrounding section. Never invent numbers, percentages, tools, technologies, team sizes, users, or outcomes.
- Where a concrete metric or detail would strengthen the bullet but is not given, insert a short bracketed placeholder for the candidate to fill in, e.g. [X%], [N users], [tool].
- Keep the candidate's meaning; do not claim more than the original does.
- One bullet, one sentence, starting with a strong past-tense action verb (present tense if the role is current).

Surrounding section (for context only; rewrite only the original text):
---
{section}
---

Issue found: {description}
Suggested fix: {suggestion}

Original text:
{snippet}

Reply with the rewritten bullet only, no quotes, no explanation."""


def section_for(resume_text: str, snippet: str) -> str:
    """The blank-line-delimited block containing the snippet (role header + its bullets)."""
    for block in re.split(r"\n\s*\n", resume_text):
        if snippet in block:
            return block.strip()
    raise ValueError(f"snippet not found: {snippet!r}")


NUMBER_RE = re.compile(r"\$?\d[\d,.]*\s?(?:%|ms|s|k|K|M|x|\+)?")
WORDISH_RE = re.compile(r"[A-Za-z][A-Za-z0-9+#./-]*")
PLACEHOLDER_RE = re.compile(r"\[[^\]]*\]")


def invented_tokens(rewrite: str, resume_text: str) -> list[str]:
    """Numbers and capitalised/tech-looking words in the rewrite that never appear in the resume."""
    hay = resume_text.lower()
    text = PLACEHOLDER_RE.sub(" ", rewrite)
    flagged = []
    for m in NUMBER_RE.finditer(text):
        tok = m.group().strip()
        digits = re.sub(r"[^\d.]", "", tok).strip(".")
        if digits and digits not in hay:
            flagged.append(tok)
    words = WORDISH_RE.findall(text)
    for i, w in enumerate(words):
        w = w.rstrip(".,;:-/")
        if i == 0 or len(w) < 2:
            continue  # first word is the action verb
        looks_proper = w[0].isupper() or any(c.isdigit() for c in w) or any(c in w for c in "+#")
        if looks_proper and w.lower() not in hay:
            flagged.append(w)
    return sorted(set(flagged))


def rewrite(client, prompt: str) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    out = (resp.choices[0].message.content or "").strip()
    return out.strip().strip('"').lstrip("-• ").strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--only", nargs="*", help="issue_ids to run")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    cases = json.loads((HERE / "cases.json").read_text())
    if args.only:
        cases = [c for c in cases if c["issue_id"] in args.only]

    client = None
    if not args.dry_run:
        from openai import OpenAI
        client = OpenAI(base_url=BASE_URL, api_key="lm-studio")

    lines = [f"# Reword prototype run — {datetime.now():%Y-%m-%d %H:%M}",
             f"Model `{MODEL}` at `{BASE_URL}`, temperature {TEMPERATURE}, {args.runs} run(s) per variant. Synthetic resumes.\n"]
    stats = {v: {"runs": 0, "invented_runs": 0, "invented_tokens": 0, "placeholders": 0, "secs": 0.0} for v in "AB"}

    for c in cases:
        resume = (HERE / "resumes" / c["resume"]).read_text()
        section = section_for(resume, c["snippet"])
        prompts = {
            "A": PROMPT_A.format(**c),
            "B": PROMPT_B.format(section=section, **c),
        }
        print(f"\n=== {c['issue_id']} ({c['resume']}) ===\nORIGINAL: {c['snippet']}")
        lines += [f"## {c['issue_id']} — {c['resume']}",
                  f"**Original:** {c['snippet']}  ",
                  f"**Issue:** {c['description']}\n",
                  "<details><summary>Section given to B</summary>\n\n```\n" + section + "\n```\n</details>\n"]

        if args.dry_run:
            for v, p in prompts.items():
                print(f"\n--- prompt {v} ---\n{p}")
            continue

        for v, p in prompts.items():
            lines.append(f"**Variant {v}**\n")
            for r in range(args.runs):
                t0 = time.time()
                out = rewrite(client, p)
                dt = time.time() - t0
                inv = invented_tokens(out, resume)
                ph = PLACEHOLDER_RE.findall(out)
                s = stats[v]
                s["runs"] += 1
                s["invented_runs"] += bool(inv)
                s["invented_tokens"] += len(inv)
                s["placeholders"] += len(ph)
                s["secs"] += dt
                flag = f"  ⚠ invented: {', '.join(inv)}" if inv else ""
                print(f"{v}{r + 1}: {out}{flag}")
                lines.append(f"- {out}" + (f"  \n  ⚠ **invented:** `{'`, `'.join(inv)}`" if inv else ""))
            lines.append("")

    if not args.dry_run:
        lines += ["## Summary", "",
                  "| Variant | Runs | Runs with invented tokens | Invented tokens | Placeholders | Avg secs |",
                  "|---|---|---|---|---|---|"]
        for v, s in stats.items():
            avg = s["secs"] / s["runs"] if s["runs"] else 0
            lines.append(f"| {v} | {s['runs']} | {s['invented_runs']} | {s['invented_tokens']} | {s['placeholders']} | {avg:.1f} |")
        out_dir = HERE / "out"
        out_dir.mkdir(exist_ok=True)
        path = out_dir / f"report-{datetime.now():%Y%m%d-%H%M%S}.md"
        path.write_text("\n".join(lines) + "\n")
        print("\n" + "\n".join(lines[-4:]))
        print(f"\nReport: {path}")


if __name__ == "__main__":
    main()
