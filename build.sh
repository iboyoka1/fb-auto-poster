#!/usr/bin/env bash
# Build script for Render deployment
# This script installs Python dependencies AND Playwright browsers

set -e

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Installing Playwright Chromium browser ==="
# On Render, we can't use install-deps (requires sudo)
# Instead, install the browser only - Render's base image has most deps
python -m playwright install chromium

echo "=== Creating required directories ==="
mkdir -p sessions logs media_library backups uploads

echo "=== Build completed successfully ==="
