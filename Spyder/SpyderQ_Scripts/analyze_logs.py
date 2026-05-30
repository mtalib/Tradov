import json
from collections import Counter
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    events_path = repo_root / "logs" / "decisions" / "paper" / "2026-05-15.jsonl"
    events = []
    with events_path.open() as handle:
        for line in handle:
            events.append(json.loads(line))

    stage_counts = Counter(event.get("stage") for event in events)
    reason_counts = Counter(event.get("reason") for event in events)

    first_dispatch_ts = None
    for event in events:
        if event.get("event") == "dispatch_submitted":
            first_dispatch_ts = event.get("ts_utc")
            break

    dup_before = []
    dup_after = []
    for event in events:
        if event.get("event") == "duplicate_open_position":
            if first_dispatch_ts and event.get("ts_utc") < first_dispatch_ts:
                dup_before.append(event.get("ts_utc"))
            else:
                dup_after.append(event.get("ts_utc"))

    startup_wait = any("paper_startup_regime_wait" in str(event) for event in events)
    trust_failures = [
        event
        for event in events
        if "entry_trust" in str(event)
        and ("fail" in str(event).lower() or "drop" in str(event).lower())
    ]
    dq_failures = [
        event
        for event in events
        if "data-quality" in str(event).lower() or "data_quality" in str(event).lower()
    ]

    print("Stage Counts:", dict(stage_counts))
    print("Reason Counts:", dict(reason_counts))
    print(
        f"Duplicate open positions: {len(dup_before)} before first dispatch, {len(dup_after)} after"
    )
    print(f"paper_startup_regime_wait found: {startup_wait}")
    print(f"Entry trust failures found: {len(trust_failures)}")
    print(f"Data quality failures found: {len(dq_failures)}")


if __name__ == "__main__":
    main()
