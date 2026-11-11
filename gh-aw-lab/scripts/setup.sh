#!/usr/bin/env bash
# Lab 7 setup for macOS / Linux / WSL. Checks for the GitHub CLI, makes sure you are
# signed in, installs the gh-aw extension, then checks the repository. It never asks
# for, stores or prints a token.
#
#   bash gh-aw-lab/scripts/setup.sh
set -euo pipefail

GH_AW_VERSION="v1.2.2"   # the version this lab was written against

echo "== 1/4 GitHub CLI"
if ! command -v gh >/dev/null 2>&1; then
  echo "gh is not installed. Install it first:"
  echo "  macOS:          brew install gh"
  echo "  Ubuntu / WSL:   https://github.com/cli/cli/blob/trunk/docs/install_linux.md"
  exit 1
fi
gh --version | head -1

# Signing in comes before the extension step: `gh extension list` needs an account.
echo "== 2/4 Sign-in"
if ! gh auth status >/dev/null 2>&1; then
  echo "Not signed in. Run this yourself, then re-run the script:"
  echo "    gh auth login --scopes repo,workflow"
  exit 1
fi
echo "Signed in."

echo "== 3/4 gh-aw extension (${GH_AW_VERSION})"
if ! gh extension list 2>/dev/null | grep -q gh-aw; then
  gh extension install github/gh-aw --pin "${GH_AW_VERSION}"
fi
gh aw version

# Diagnostics only: report problems, but do not stop on them.
echo "== 4/4 Repository check (run from the repo root)"
gh aw doctor || true
gh aw secrets bootstrap --non-interactive || true

echo
echo "Done. If COPILOT_GITHUB_TOKEN is listed as missing, create a fine-grained token with"
echo "Account permissions > Copilot Requests = Read-only, then run:  gh aw secrets set COPILOT_GITHUB_TOKEN"
