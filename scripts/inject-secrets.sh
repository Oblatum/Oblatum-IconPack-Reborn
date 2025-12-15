#!/bin/bash

# Inject secrets into blueprint_setup.xml at build time
# Usage: ./scripts/inject-secrets.sh

SETUP_FILE="app/src/main/res/values/blueprint_setup.xml"

if [ -z "$APPTRACKER_ACCESS_KEY" ]; then
    echo "Warning: APPTRACKER_ACCESS_KEY is not set"
fi

if [ -z "$APPTRACKER_BASE_URL" ]; then
    echo "Warning: APPTRACKER_BASE_URL is not set"
fi

# Replace placeholders with actual values
sed -i "s|INJECT_APPTRACKER_KEY|${APPTRACKER_ACCESS_KEY}|g" "$SETUP_FILE"
sed -i "s|INJECT_APPTRACKER_URL|${APPTRACKER_BASE_URL}|g" "$SETUP_FILE"

echo "Secrets injected into $SETUP_FILE"
