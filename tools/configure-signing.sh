#!/usr/bin/env bash
# Execute on the maintainer's host. Existing dedicated signing key required.
set -euo pipefail
fingerprint="${1:?Usage: bash tools/configure-signing.sh FULL_FINGERPRINT}"
[[ "$fingerprint" =~ ^[A-Fa-f0-9]{40,64}$ ]] || { echo 'Use the complete key fingerprint.' >&2; exit 1; }
repo=x-devnull/ryoku-proxy
# Private material goes directly through stdin to GitHub Secrets, never into Git.
gpg --armor --export-secret-keys "$fingerprint" | gh secret set REPO_SIGNING_KEY --repo "$repo"
gh variable set REPO_SIGNING_FINGERPRINT --repo "$repo" --body "$fingerprint"
echo 'Key stored in GitHub Secrets. Set REPO_SIGNING_PASSPHRASE separately if needed.'
echo "Confirm the public fingerprint through a separate trusted channel: $fingerprint"
