# Contributing

This source package is currently unpublished. It is designed to be reviewed before any public release.

- Use Python 3.11+ (Arch/CachyOS Python is recommended), Qt 6 / PySide6 and sing-box 1.14+.
- Keep privileged code (`src/ryoku-proxy-helper`, `src/firewall.py`, `src/routing.py`) separate from unprivileged UI; never run the whole GUI as root.
- Every new user-facing UI key must be added to both columns in `src/i18n.py`. Keep English the source locale, Russian complete.
- Test network changes with `sing-box check` and rollback. Any nftables edit must target only `inet ryoku_proxy` and provide a local recovery path.
- Run `python -m unittest discover -s tests -v`, `python -m compileall -q src` and `bash -n install.sh uninstall.sh`.
- Never add real proxy usernames, passwords, API tokens or device addresses to tests, screenshots or logs.

Maintainer: [x_devnull](https://github.com/x-devnull).
