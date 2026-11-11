# Ryoku Proxy — ED 1.0

First public edition. Git tag: **v1.0**. Package version: **1.0.0**.
Earlier 4.x names were development labels; saved-data schema versions are unchanged.

A native Qt6/Wayland control panel for an existing sing-box TUN setup:

- HTTP, HTTPS and SOCKS5 profiles, import and connection checks.
- Per-destination routing and explicit direct exceptions.
- nftables Kill Switch with a recoverable 120-second activation trial.
- TUN throughput, local authenticated connection monitoring and service logs.
- English/Russian UI, Ryoku styling and tray controls.

Download the ready-to-install **ryoku-proxy-1.0.0-2-any.pkg.tar.zst**, verify
its checksum from SHA256SUMS, and install with:

```sh
sudo pacman -U ./ryoku-proxy-1.0.0-2-any.pkg.tar.zst
```

Pacman installs the host helper, desktop entry and dependencies. Normal polkit
password prompts are the default. No install script is required. No AUR listing
or official pacman repository is claimed. Source archives, PKGBUILD and its
install scriptlet are also attached for local builds with `makepkg -si`.

Manual Debian packages are also included. A separate signed pacman repository
workflow supports automatic updates after maintainer key setup. See
[package publishing](https://github.com/x-devnull/ryoku-proxy/blob/main/docs/PACKAGES.md).

Automated tests include offscreen Qt checks. Live Wayland, packet-level firewall,
recovery and clean-system package scenarios remain to be validated. The app
requires an existing sing-box configuration with a `proxy` outbound and DNS/TUN
routing; it does not provision a fresh VPN or promise general UDP over HTTP.
