#!/usr/bin/env bash
# Build script for Render deployment
# This script installs Python dependencies AND Playwright browsers

set -e

echo "=== Installing Python dependencies ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Installing Playwright browsers and dependencies ==="
# Install system dependencies for Playwright (Render uses Debian/Ubuntu)
# Playwright install-deps installs system libraries needed for browser automation
playwright install-deps chromium || true

# Install Chromium browser for Playwright
playwright install chromium

echo "=== Creating required directories ==="
mkdir -p sessions logs media_library backups uploads

echo "=== Build completed successfully ==="
