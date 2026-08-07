"""Heuristic search for OOTB content JSON files matching a bug report."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTENT_DIRS = ("navigators", "group", "detector")

STOPWORDS = frozenset(
    {
        "the",
        "a",
        "an",
        "and",
        "or",
        "for",
        "in",
        "on",
        "at",
        "to",
        "of",
        "is",
        "are",
        "was",
        "were",
        "be",
        "with",
        "from",
        "that",
        "this",
        "it",
        "not",
        "bug",
        "fix",
        "wrong",
        "issue",
        "report",
        "shows",
        "show",
        "instead",
        "expected",
        "actual",
        "ootb",
        "content",
    }
)


@dataclass
class FileMatch:
    path: str
    score: int
    reasons: list[str] = field(default_factory=list)


def tokenize(text: str) -> list[str]:
    raw = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]*", text.lower())
    return [t for t in raw if len(t) >= 3 and t not in STOPWORDS]


def iter_content_json() -> Iterable[Path]:
    for dirname in CONTENT_DIRS:
        root = REPO_ROOT / dirname
        if root.is_dir():
            yield from root.rglob("*.json")


def search_repo(bug_text: str, *, limit: int = 5) -> list[FileMatch]:
    tokens = tokenize(bug_text)
    if not tokens:
        return []

    matches: list[FileMatch] = []
    for path in iter_content_json():
        rel = str(path.relative_to(REPO_ROOT))
        name_lower = path.name.lower()
        try:
            body = path.read_text(encoding="utf-8").lower()
        except OSError:
            continue

        score = 0
        reasons: list[str] = []

        for token in tokens:
            if token in name_lower:
                score += 8
                reasons.append(f"filename contains '{token}'")
            count = body.count(token)
            if count:
                score += min(count, 5)
                reasons.append(f"content mentions '{token}' ({count}x)")

        # Boost if multi-word product names appear in path (e.g. k8s + node + cpu)
        joined = " ".join(tokens)
        if "k8s" in joined and "k8s" in rel.lower():
            score += 5
            reasons.append("Kubernetes-related path")

        if score > 0:
            matches.append(FileMatch(path=rel, score=score, reasons=reasons[:4]))

    matches.sort(key=lambda m: m.score, reverse=True)
    return matches[:limit]


def build_rca(bug_text: str, matches: list[FileMatch]) -> str:
    lines = [
        "## Root cause analysis (automated)",
        "",
        f"**Reported issue:** {bug_text.strip()}",
        "",
    ]
    if not matches:
        lines.extend(
            [
                "**Findings:** No strong match in `navigators/`, `group/`, or `detector/` JSON.",
                "",
                "**Suggested next steps:**",
                "- Add product keywords (dashboard, detector, navigator name) to the report.",
                "- Manually identify the content file and update the MR branch.",
            ]
        )
        return "\n".join(lines)

    top = matches[0]
    lines.append("**Likely affected content (heuristic search):**")
    for m in matches:
        lines.append(f"- `{m.path}` (score {m.score})")
    lines.extend(
        [
            "",
            f"**Primary suspect:** `{top.path}`",
            "",
            "**Probable cause:** Report text matches this OOTB export; verify thresholds, "
            "labels, import qualifiers, or chart/detector rules in that file.",
            "",
            "**Suggested fix:** Edit the JSON on the MR branch, then run "
            "`python -m syncer.cli plan` and `python -m syncer.cli apply --yes --refresh-local`.",
        ]
    )
    return "\n".join(lines)


def summarize_for_jira(bug_text: str, matches: list[FileMatch], rca: str) -> str:
    parts = [bug_text.strip(), "", rca]
    if matches:
        parts.extend(["", "Affected files:", *[f"- {m.path}" for m in matches]])
    return "\n".join(parts)
