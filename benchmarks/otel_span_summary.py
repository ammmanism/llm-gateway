"""Extract gateway span attributes from an OpenTelemetry Collector file export."""

import argparse
import csv
import json
from pathlib import Path

FIELDS = [
    "trace_id",
    "span_id",
    "service_name",
    "environment",
    "span_name",
    "status_code",
    "tenant_id",
    "provider",
    "model",
    "prompt_tokens",
    "completion_tokens",
    "cost_usd",
    "latency_ms",
    "cache_hit",
]


def decode_value(value: dict):
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return value[key]
    return ""


def extract(source: Path) -> list[dict]:
    payload = json.loads(source.read_text(encoding="utf-8"))
    rows = []
    for resource_spans in payload.get("resourceSpans", []):
        resource = {
            item["key"]: decode_value(item["value"])
            for item in resource_spans.get("resource", {}).get("attributes", [])
        }
        for scope_spans in resource_spans.get("scopeSpans", []):
            for span in scope_spans.get("spans", []):
                attributes = {
                    item["key"]: decode_value(item["value"])
                    for item in span.get("attributes", [])
                }
                row = {field: "" for field in FIELDS}
                row.update(
                    {
                        "trace_id": span.get("traceId", ""),
                        "span_id": span.get("spanId", ""),
                        "service_name": resource.get("service.name", ""),
                        "environment": resource.get("deployment.environment", ""),
                        "span_name": span.get("name", ""),
                        "status_code": span.get("status", {}).get("code", ""),
                    }
                )
                row.update({key: attributes.get(key, "") for key in FIELDS[6:]})
                rows.append(row)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("deploy/observability/otel-data/spans.json"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/evidence/otel_span_sample.csv")
    )
    args = parser.parse_args()

    rows = extract(args.input)
    if not rows:
        raise SystemExit("no spans found in collector export")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} spans to {args.output}")


if __name__ == "__main__":
    main()
