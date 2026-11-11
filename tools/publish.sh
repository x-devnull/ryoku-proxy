#!/usr/bin/env bash
# Run from a normal host terminal with GitHub CLI authenticated.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
command -v gh >/dev/null || { echo 'GitHub CLI (gh) is required.' >&2; exit 1; }
owner=$(gh api user --jq .login)
if [[ "$owner" != x-devnull ]]; then
  echo "Expected GitHub account x-devnull; current account: $owner" >&2
  exit 1
fi
repo="$owner/ryoku-proxy"
python3 tools/validate_release.py
python3 -m unittest discover -s tests -q
bash -n install.sh install-user.sh uninstall.sh packaging/PKGBUILD
python3 tools/source_archive.py
if [[ ! -d .git ]]; then git init -b main; fi
if [[ "$(git branch --show-current)" != main ]]; then echo 'Run from branch main.' >&2; exit 1; fi
# Use a repository-local public noreply identity; leave global Git config alone.
git config user.name x_devnull
git config user.email x-devnull@users.noreply.github.com
if ! git remote get-url origin >/dev/null 2>&1; then
  if gh repo view "$repo" >/dev/null 2>&1; then
    echo "Repository $repo already exists; verify and add its origin manually before retrying." >&2
    exit 1
  fi
  # Verify authentication/network before attempting repository creation.
  gh api user --jq .login >/dev/null
  gh repo create "$repo" --public --description 'Ryoku Proxy ED 1.0 — native Qt6 sing-box routing, monitoring and Kill Switch' --homepage 'https://x-devnull.github.io/ryoku-proxy/'
  git remote add origin "https://github.com/$repo.git"
fi
remote=$(git remote get-url origin)
if [[ "$remote" != "https://github.com/$repo.git" && "$remote" != "git@github.com:$repo.git" ]]; then
  echo "Unexpected origin: $remote" >&2; exit 1
fi
# Publish normal development history; preserve the existing v1.0 tag.
git add .github .gitignore CHANGELOG.md CONTRIBUTING.md LICENSE README.md README.ru.md SECURITY.md docs install.sh install-user.sh packaging site src tests tools uninstall.sh
if ! git diff --cached --quiet; then git commit -m 'Prepare Ryoku Proxy v1.0 — ED 1.0'; fi
git config --local credential.https://github.com.helper '!gh auth git-credential'
git push -u origin main
# Enable Actions-based Pages, or update the source if Pages was already enabled.
if gh api "repos/$repo/pages" >/dev/null 2>&1; then
  gh api --method PUT "repos/$repo/pages" -f build_type=workflow >/dev/null
else
  gh api --method POST "repos/$repo/pages" -f build_type=workflow >/dev/null
fi
gh workflow run pages.yml --repo "$repo" --ref main
gh workflow run release.yml --repo "$repo" --ref main
release_event=workflow_dispatch
# Observe workflow completion before reporting the public URLs as deployed.
wait_for_workflow() {
  local workflow="$1" event="$2" run_id="" attempt
  for attempt in {1..15}; do
    run_id=$(gh run list --repo "$repo" --workflow "$workflow" --commit "$(git rev-parse HEAD)" --event "$event" --limit 1 --json databaseId --jq '.[0].databaseId // empty')
    if [[ -n "$run_id" ]]; then break; fi
    sleep 2
  done
  [[ -n "$run_id" ]] || { echo "Workflow not found: $workflow" >&2; return 1; }
  gh run watch "$run_id" --repo "$repo" --exit-status
}
wait_for_workflow pages.yml workflow_dispatch
wait_for_workflow release.yml "$release_event"
wait_for_workflow repository.yml workflow_run
wait_for_workflow pages.yml workflow_run
gh release view v1.0 --repo "$repo" --json url --jq .url
gh api "repos/$repo/pages" --jq .html_url
printf 'Repository: https://github.com/%s\nRelease workflow: https://github.com/%s/actions\nExpected Pages URL: https://x-devnull.github.io/ryoku-proxy/\n' "$repo" "$repo"
echo 'Release, signed repository and Pages publication completed successfully.'
