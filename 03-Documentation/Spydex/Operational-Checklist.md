# Spydex Operational Checklist

Use this checklist while Spyder is still the only active codebase and while preparing for the future Spydex fork.

## Before Forking

1. Confirm Spyder has passed the clone-readiness scorecard.
2. Confirm zero open P0 issues.
3. Confirm zero open P1 issues in startup, data, risk, execution, or shutdown.
4. Confirm the last 3 trading weeks met the stability gate.
5. Confirm the second machine is ready.
6. Confirm the second Tradier account is provisioned.
7. Confirm separate env, logs, caches, state, and service names are planned.

## At Fork Time

1. Tag the Spyder baseline commit.
2. Copy the codebase into the Spydex project space.
3. Rebrand only the minimum set of identifiers needed for the new application.
4. Verify startup and shutdown on the new machine.
5. Verify the new Tradier credentials work.
6. Verify the new app does not share state with Spyder.

## After Forking

1. Keep Spyder and Spydex on separate machines.
2. Keep Tradier accounts separate.
3. Keep logs, caches, and state directories separate.
4. Keep safety fixes synchronized.
5. Allow strategy specialization for SPX only after the new baseline is stable.

## Go / No-Go Reminder

If Spyder becomes unstable again, pause the fork plan and return to stabilization work first.