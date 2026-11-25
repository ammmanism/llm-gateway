"""Convert coverage.py JSON output into a compact committed CSV summary."""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def summarize(source: Path) -> list[dict]:
    data = json.loads(source.read_text(encoding="utf-8"))
    groups = defaultdict(lambda: defaultdict(int))

    for filename, details in data["files"].items():
        normalized = filename.replace("\\", "/")
        marker = "src/llm_gateway/"
        if marker not in normalized:
            continue
        relative = normalized.split(marker, 1)[1]
        module = relative.split("/", 1)[0] if "/" in relative else "root"
        summary = details["summary"]
        for key in (
            "num_statements",
            "covered_lines",
            "missing_lines",
            "num_branches",
            "covered_branches",
            "missing_branches",
        ):
            groups[module][key] += summary.get(key, 0)

    rows = []
    for module in sorted(groups):
        values = groups[module]
        statements = values["num_statements"]
        covered = values["covered_lines"]
        rows.append(
            {
                "scope": module,
                "statements": statements,
                "covered_lines": covered,
                "missing_lines": values["missing_lines"],
                "branches": values["num_branches"],
                "covered_branches": values["covered_branches"],
                "missing_branches": values["missing_branches"],
                "covered_percent": round(covered / statements * 100, 2)
                if statements
                else 100.0,
            }
        )

    totals = data["totals"]
    rows.append(
        {
            "scope": "TOTAL",
            "statements": totals["num_statements"],
            "covered_lines": totals["covered_lines"],
            "missing_lines": totals["missing_lines"],
            "branches": totals.get("num_branches", 0),
            "covered_branches": totals.get("covered_branches", 0),
            "missing_branches": totals.get("missing_branches", 0),
            "covered_percent": round(totals["percent_covered"], 2),
        }
    )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input", type=Path, default=Path("data/evidence/coverage.json")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/evidence/coverage_summary.csv")
    )
    args = parser.parse_args()

    rows = summarize(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {args.output}")


if __name__ == "__main__":
    main()
