# Release checklist — Ryoku Proxy 1.0.0

This is a **pre-publication checklist**, not a claim the package has been released.

- [x] License, author and URL, changelog, bilingual README, contribution and security docs.
- [x] Stable system installation paths and v3 upgrade compatibility.
- [x] Unit tests for routing, firewall migration, locale selection, profiles, helper, transport probes.
- [x] No automatic modification of sing-box config or enablement of firewall during install.
- [x] Built-in recovery commands and 120-second trial.
- [x] Run Qt offscreen smoke/regression tests (PySide6 6.12.0); inspect desktop and narrow-window previews.
- [ ] Run on Ryoku / Wayland at 100%, 125%, 150%, 200% scaling.
- [ ] Verify nftables syntax and packet behavior in network namespaces with sing-box 1.14+ on CachyOS.
- [ ] Verify `SO_MARK` direct exceptions for HTTPS SNI, host DNS mappings, wildcard domains and physical interface policy routes.
- [ ] Verify systemd trial on first enable, expiry, explicit confirmation, reboot persistence, DNS outage and Wi-Fi roaming.
- [ ] Verify HTTPS/SOCKS5 live transport rotation while proxy offline, TCP/UDP behavior and rollback.
- [ ] Verify no regressions with Steam, Discord, KDE NetworkManager, Hyprland tray and systemd-resolved.
- [ ] Verify encrypted secret storage availability and multi-user permissions.
- [ ] Test custom polkit action with pkexec on physical Ryoku/Wayland (active/local session, KDE/Hyprland, switching, SSH refusal, revoke).
- [ ] Audit all helper command paths and payload validations for the passwordless account permission model.
- [ ] Review the supply chain, security audit of root helper, and reproducible signed package generation.
- [ ] Create release tag and publish package only after explicit maintainer approval.

## Local source distribution

`ryoku-proxy-1.0.0.tar.gz` is the source archive. A `PKGBUILD` template is provided for local package development, but has not been submitted to AUR. CI checks pushes and pull requests. Separate workflows deploy GitHub Pages from main and publish release assets for tag v1.0.

Generate deterministic source archives with `python tools/source_archive.py`. The generated `dist/PKGBUILD` contains the actual archive checksum; the in-tree recipe remains a template.


## First publication from the maintainer host

The prepared repository target is `x-devnull/ryoku-proxy` (public). With GitHub
CLI authenticated as `x-devnull`, run `bash tools/publish.sh` from the checkout.
It validates sources, creates the repository if absent, pushes `main`, enables
Actions-based Pages, pushes `v1.0`, and waits for Pages and release workflows.
It refuses an unrelated existing repository, unexpected origin or another account.
Publication replaces main and v1.0 using force-with-lease, as requested for the
English-first history rewrite. No credentials are written to the project.
The release title is **v1.0 — ED 1.0**, package version **1.0.0**.

Release CI builds the native Arch package in archlinux:base-devel as an
unprivileged user. The binary package and SHA256SUMS are attached to v1.0.
The pacman PreTransaction removal hook aborts if Kill Switch state is active.
