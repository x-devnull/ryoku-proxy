#!/usr/bin/env bash
# Shared read-only account check. Source this file; never invoke key operations here.
github_require_account() {
  local expected="$1" response attempt
  for attempt in 1 2 3; do
    if response=$(gh api user --jq .login 2>&1); then
      if [[ "$response" != "$expected" ]]; then
        printf 'Expected GitHub account %s; authenticated as %s.\n' "$expected" "$response" >&2
        return 1
      fi
      return 0
    fi
    case "$response" in
      *'HTTP 401'*|*'HTTP 403'*|*'gh auth login'*|*'not logged'*) break ;;
    esac
    if (( attempt < 3 )); then
      printf 'GitHub account check failed; retrying (%s/3)...\n' "$attempt" >&2
      sleep "$attempt"
    fi
  done
  printf '%s\n' "$response" >&2
  printf '%s\n' \
    'Could not verify the GitHub account. This does not mean the account is wrong.' \
    'Check connectivity to api.github.com, proxy/VPN settings, and authentication if an HTTP 401/403 was returned.' \
    'No signing key has been created or uploaded by this account check. Retry after: gh api user --jq .login' >&2
  return 1
}
