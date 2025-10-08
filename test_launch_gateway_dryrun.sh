#!/bin/bash
# Dry-run tester for SPYDER gateway launch flow
set -e

echo "== DRY RUN: launch_gateway_with_credentials.sh =="
bash ./launch_gateway_with_credentials.sh paper || true

echo "== DRY RUN: launch_spyder_gateway.sh --test-only =="
bash ./launch_spyder_gateway.sh --test-only || true

echo "Dry-run complete. Check logs or output for expected behavior."