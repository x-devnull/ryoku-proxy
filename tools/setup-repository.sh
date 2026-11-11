#!/usr/bin/env bash
# Create a dedicated key outside the checkout and configure GitHub Secrets.
set -euo pipefail
repo=x-devnull/ryoku-proxy
rotation=false
case "${1:-}" in
  '') ;;
  --rotate-github-time) rotation=true ;;
  *) echo 'Usage: bash tools/setup-repository.sh [--rotate-github-time]' >&2; exit 2 ;;
esac
key_dir="${XDG_DATA_HOME:-$HOME/.local/share}/ryoku-proxy-signing"
for binary in gpg gh python3; do command -v "$binary" >/dev/null || { echo "$binary is required" >&2; exit 1; }; done
source "$(dirname "${BASH_SOURCE[0]}")/github-account.sh"
github_require_account x-devnull
gpg_time=()
if [[ "$rotation" == true ]]; then
  # Fetch HTTPS time before creating a directory or prompting for a passphrase.
  key_epoch=$(python3 "$(dirname "${BASH_SOURCE[0]}")/github_utc.py")
  [[ "$key_epoch" =~ ^[0-9]+$ ]]
  printf 'New key creation time (GitHub UTC minus 60s): %s\n' "$(date -u -d "@$key_epoch" '+%Y-%m-%d %H:%M:%S UTC')"
  gpg_time=(--faked-system-time "$key_epoch")
  # A fresh directory preserves all previous signing keys and certificates.
  umask 077
  key_parent="${XDG_DATA_HOME:-$HOME/.local/share}"
  mkdir -p "$key_parent"
  key_dir=$(mktemp -d "$key_parent/ryoku-proxy-signing-rotated.XXXXXXXX")
elif [[ -e "$key_dir" || -L "$key_dir" ]]; then
  echo "Signing directory already exists: $key_dir" >&2
  echo 'Reuse its key using configure-signing.sh with GNUPGHOME set to this directory.' >&2
  exit 1
fi
umask 077
mkdir -p "$key_dir"
chmod 700 "$key_dir"
export GNUPGHOME="$key_dir"
read -r -s -p 'New dedicated signing-key passphrase (empty is allowed for a dedicated CI key): ' key_passphrase
printf '\n'
read -r -s -p 'Repeat passphrase: ' repeated_passphrase
printf '\n'
[[ "$key_passphrase" == "$repeated_passphrase" ]] || { echo 'Passphrases do not match.' >&2; exit 1; }
unset repeated_passphrase
printf '%s\n' "$key_passphrase" | gpg "${gpg_time[@]}" --batch --pinentry-mode loopback --passphrase-fd 0 --quick-generate-key 'Ryoku Proxy package signing' ed25519 sign 2y
fingerprint=$(gpg "${gpg_time[@]}" --batch --with-colons --list-secret-keys | awk -F: '$1 == "fpr" {print $10; exit}')
[[ "$fingerprint" =~ ^[A-Fa-f0-9]{40,64}$ ]]
printf '%s\n' "$key_passphrase" | gpg "${gpg_time[@]}" --batch --pinentry-mode loopback --passphrase-fd 0 --armor --export-secret-keys "$fingerprint" | gh secret set REPO_SIGNING_KEY --repo "$repo"
if [[ -n "$key_passphrase" ]]; then
  printf '%s' "$key_passphrase" | gh secret set REPO_SIGNING_PASSPHRASE --repo "$repo"
else
  # Remove an obsolete passphrase secret if configuring an unprotected CI key.
  existing=$(gh secret list --repo "$repo" --json name --jq '.[].name')
  if printf '%s\n' "$existing" | grep -qx REPO_SIGNING_PASSPHRASE; then
    gh secret delete REPO_SIGNING_PASSPHRASE --repo "$repo"
  fi
fi
unset key_passphrase
gh variable set REPO_SIGNING_FINGERPRINT --repo "$repo" --body "$fingerprint"
gpg "${gpg_time[@]}" --batch --armor --export "$fingerprint" > "$key_dir/ryoku-proxy.asc"
printf 'Configured GitHub signing. Public fingerprint: %s\nKey directory: %s\n' "$fingerprint" "$key_dir"
echo 'Back up this directory and its revocation certificate offline. Do not commit it.'
echo 'Publish the fingerprint through an independent trusted channel, then run bash tools/publish.sh.'
