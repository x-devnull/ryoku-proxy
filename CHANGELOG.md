## Distribution updates (unreleased)

- Add signed pacman repository publishing and preserve it during landing deployments.
- Keep manual Arch release packages and add a Debian 13 package builder.
- Document key verification, CI signing setup and both installation routes in English and Russian.

# 1.0.0 — ED 1.0

First public edition, with release tag `v1.0`. Earlier 4.x labels below refer
to private development builds; profile and firewall data formats retain their
existing versions for compatibility.

- Native Qt6 dashboard with English and Russian interfaces.
- HTTP(S)/SOCKS5 profiles, routing, monitoring and recoverable Kill Switch.
- Improved Ryoku styling, worker lifecycle and low-overhead refresh.
- GitHub Pages landing, release automation and deterministic source archives.

# Local pre-release improvements (2026-11-11)

- Reduce redundant list/tray updates and hidden-window monitoring.
- Fix stale counters, active-profile presentation, status messages and worker shutdown.
- Align typography, focus and shape with current Ryoku primitives.
- Harden text rendering, SOCKS5 negotiation and HTTPS probe curl configuration.
- Add offscreen GUI tests, root-free permission fixtures and deterministic source packaging.
- See docs/RELEASE.md for validation and outstanding release requirements.

## 4.1.0 — one-time desktop authorization

- Scoped polkit action bound to the installed Ryoku root helper path.
- On installer upgrade, the invoking desktop user is granted access only to this action; avoids repeat password prompts in active local sessions.
- `ryoku-proxy-access grant|revoke|status` CLI with atomic managed local rule, restricted to verified local accounts and root-owned helper.
- Optional `install.sh --require-password` and `--no-permission-change`.
- New translated Administrator Access status panel in Security (checked without prompting).
- Uninstaller cleans only the Ryoku-specific policy, grant and rule.
- No changes to sing-box, TUN, proxy profiles or nftables policy during installation.

# Changelog

## 4.0.0 — source candidate (unpublished)

- Renamed and normalized interface strings with a complete English/Russian catalogue, system locale detection and desktop translations.
- Aligned all pages with Ryoku visual grammar; adapted Monitor and cards to narrow windows, scrollable live connection table.
- Author x_devnull and https://github.com/x-devnull displayed in About and release metadata.
- Added guarded 120-second nftables Kill Switch trial with independent systemd recovery and manual persistent confirmation.
- Removed Ryoku's old FORWARD hook restriction for more conservative impact on Docker and VMs, kept isolated OUTPUT filter.
- Added explicit backup proxy endpoint authorization with persistence, retained during profile rotation.
- Added managed route exceptions for IP/CIDR, exact IDNA domains, anchored wildcard suffixes, HTTP(S) URL hostname, and auto-detected local subnets.
- Added transaction/rollback logic for routing edits, upgraded firewall state v1 → v2 without resetting working profiles.
- Prepared bilingual documentation, release checklist, MIT attribution, CI test workflow and local package metadata.
- Added regression tests for domain masks, migration, firewall rules, network discovery, and locale catalogue.

## 3.0.0 — previous version

Native Ryoku style, isolated nftables Kill Switch and optional Clash API monitor.
