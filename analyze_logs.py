import json
from collections import Counter

events = []
with open('logs/decisions/paper/2026-05-15.jsonl') as f:
    for line in f:
        events.append(json.loads(line))

# Counts by reason and stage
stage_counts = Counter(e.get('stage') for e in events)
reason_counts = Counter(e.get('reason') for e in events)

# Duplicate open position timing relative to dispatch_submitted
first_dispatch_ts = None
for e in events:
    if e.get('event') == 'dispatch_submitted':
        first_dispatch_ts = e.get('ts_utc')
        break

dup_before = []
dup_after = []
for e in events:
    if e.get('event') == 'duplicate_open_position':
        if first_dispatch_ts and e.get('ts_utc') < first_dispatch_ts:
            dup_before.append(e.get('ts_utc'))
        else:
            dup_after.append(e.get('ts_utc'))

# paper_startup_regime_wait
startup_wait = any('paper_startup_regime_wait' in str(e) for e in events)

# entry_trust or data-quality failures
trust_failures = [e for e in events if 'entry_trust' in str(e) and ('fail' in str(e).lower() or 'drop' in str(e).lower())]
dq_failures = [e for e in events if 'data-quality' in str(e).lower() or 'data_quality' in str(e).lower()]

print("Stage Counts:", dict(stage_counts))
print("Reason Counts:", dict(reason_counts))
print(f"Duplicate open positions: {len(dup_before)} before first dispatch, {len(dup_after)} after")
print(f"paper_startup_regime_wait found: {startup_wait}")
print(f"Entry trust failures found: {len(trust_failures)}")
print(f"Data quality failures found: {len(dq_failures)}")
