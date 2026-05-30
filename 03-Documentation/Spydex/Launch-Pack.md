# Spydex Launch Pack

This document captures the minimum practical setup for spinning up Spydex on a separate machine after Spyder has cleared the clone-readiness gate.

## Scope

Spydex is a separate application and should have its own machine, its own Tradier account, and its own runtime state. The goal is isolation first, customization second.

## 1. Machine Setup

1. Provision a dedicated machine for Spydex.
2. Install the same base dependencies used by Spyder.
3. Keep the host OS, Python environment, and application paths isolated from the Spyder machine.
4. Use a different hostname and service name so logs and alerts are unambiguous.

## 2. Tradier Account Setup

1. Create a second Tradier account for Spydex.
2. Rotate and store the new credentials separately from Spyder.
3. Set the Spydex account in a dedicated environment file.
4. Verify market-data and order-routing access before enabling any trading workflows.

## 3. Environment Isolation

1. Use a separate .env file for Spydex.
2. Keep logs, caches, databases, and PID files in Spydex-only paths.
3. Do not share runtime state between Spyder and Spydex.
4. Keep the process name, telemetry tags, and service labels distinct.
5. Keep secrets scoped to the new machine and rotate anything that was reused during setup.

## 4. First Boot Checklist

1. Confirm the app starts cleanly on the new machine.
2. Confirm the dashboard loads without sharing Spyder state.
3. Confirm the Tradier credentials work in the Spydex environment.
4. Confirm market data arrives and charts render.
5. Confirm shutdown is clean and does not leave background workers running.
6. Confirm no dual-control or shared-account behavior is present.

## 5. SPX Customization Path

1. Start from a known-good Spyder baseline commit.
2. Rebrand only the minimum app identity needed for Spydex.
3. Switch the active underlying to SPX in a single authoritative place.
4. Update strategy, risk, and market-data wiring incrementally.
5. Keep fail-closed behavior intact until the SPX path is fully validated.

## 6. Operational Rule

If Spyder is unstable again, stop the fork work and return to stabilization first. Spydex should only move forward when the baseline is boring and reliable.