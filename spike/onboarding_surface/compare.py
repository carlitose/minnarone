"""Summarize explicit prototype surface measurements."""

from __future__ import annotations

import json
from pathlib import Path

import probes


def summarize(path: Path) -> dict[str, object]:
    data = json.loads(path.read_text(encoding="utf-8"))
    traps = set(probes.TRAPS)
    enforced = probes.run_enforced_probes()
    tutorial = probes.run_tutorial_probes()
    rows = {}
    for name, surface in data["surfaces"].items():
        results = tutorial if name == "tutorial_templates" else enforced
        caught = {trap for trap, passed in results.items() if passed}
        rows[name] = {
            "estimated_human_steps": len(surface["human_steps"]),
            "estimated_agent_steps": len(surface["agent_steps"]),
            "errors_avoided": len(caught & traps),
            "errors_missed": sorted(traps - caught),
            "estimated_duplicated_rules": len(surface["duplicated_rules"]),
            "probe_results": results,
        }
    eligible = [
        name for name, row in rows.items()
        if not row["errors_missed"]
    ]
    choice = min(
        eligible,
        key=lambda name: (
            rows[name]["estimated_duplicated_rules"],
            rows[name]["estimated_agent_steps"] + rows[name]["estimated_human_steps"],
        ),
    )
    return {
        "choice": choice,
        "measurement": "step and duplication counts are checklist estimates; hazard results are executable probes",
        "surfaces": rows,
    }


if __name__ == "__main__":
    print(json.dumps(summarize(Path(__file__).with_name("comparison.json")), indent=2, sort_keys=True))
