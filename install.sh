#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
# The installing desktop user is explicitly granted access to ONLY the Ryoku
# helper's polkit action. Use --require-password to retain normal prompts.
AUTH_MODE=grant
AUTH_USER="${SUDO_USER:-}"
while (( $# )); do
  case "$1" in
    --require-password) AUTH_MODE=revoke; shift ;;
    --grant-user) [[ $# -ge 2 ]] || { echo '--grant-user requires username' >&2; exit 2; }; AUTH_USER="$2"; shift 2 ;;
    --no-permission-change) AUTH_MODE=skip; shift ;;
    *) echo "Unknown option: $1" >&2; exit 2 ;;
  esac
done
if (( EUID != 0 )); then echo 'Usage: sudo bash install.sh' >&2; exit 1; fi
for file in src/{profile_store.py,network_probe.py,monitoring.py,firewall.py,routing.py,i18n.py,ryoku_proxy.py,ryoku-proxy-helper,ryoku-proxy-access} packaging/{ryoku-proxy,ryoku-proxy.desktop,ryoku-proxy.svg,ryoku-proxy.metainfo.xml} packaging/systemd/ryoku-proxy-killswitch.service packaging/polkit/org.ryoku.proxy.policy; do
  [[ -f "$file" ]] || { echo "Missing $file" >&2; exit 1; }
done
for binary in /usr/bin/python3 /usr/bin/sing-box /usr/bin/pkexec /usr/bin/systemctl /usr/bin/curl /usr/bin/nft /usr/bin/ip /usr/bin/systemd-run; do
  [[ -x "$binary" ]] || { echo "Required binary missing: $binary" >&2; exit 1; }
done
/usr/bin/python3 -c 'import PySide6' >/dev/null || { echo 'Install pyside6 using pacman' >&2; exit 1; }
install -d -m 0755 /usr/share/ryoku-proxy /usr/lib/ryoku-proxy /usr/local/bin /usr/share/applications /usr/share/pixmaps /usr/share/metainfo /etc/systemd/system /usr/share/polkit-1/actions /usr/lib/ryoku-proxy
for f in profile_store.py network_probe.py monitoring.py routing.py i18n.py ryoku_proxy.py; do
  install -o root -g root -m 0644 "src/$f" "/usr/share/ryoku-proxy/$f"
done
install -o root -g root -m 0644 src/firewall.py /usr/lib/ryoku-proxy/firewall.py
install -o root -g root -m 0644 src/routing.py /usr/lib/ryoku-proxy/routing.py
install -o root -g root -m 0755 src/ryoku-proxy-helper /usr/lib/ryoku-proxy/ryoku-proxy-helper
install -o root -g root -m 0755 src/ryoku-proxy-access /usr/local/bin/ryoku-proxy-access
install -o root -g root -m 0644 packaging/polkit/org.ryoku.proxy.policy /usr/share/polkit-1/actions/org.ryoku.proxy.policy
install -o root -g root -m 0755 packaging/ryoku-proxy /usr/local/bin/ryoku-proxy
install -o root -g root -m 0644 packaging/ryoku-proxy.desktop /usr/share/applications/ryoku-proxy.desktop
install -o root -g root -m 0644 packaging/ryoku-proxy.svg /usr/share/pixmaps/ryoku-proxy.svg
install -o root -g root -m 0644 packaging/ryoku-proxy.metainfo.xml /usr/share/metainfo/ryoku-proxy.metainfo.xml
install -o root -g root -m 0644 packaging/systemd/ryoku-proxy-killswitch.service /etc/systemd/system/ryoku-proxy-killswitch.service
# Retire only known v2 launchers; do not touch old profiles, config, or running sing-box.
if [[ -f /usr/local/bin/ryoka-proxy ]] && grep -q '/usr/share/ryoka-proxy/ryoka_proxy.py' /usr/local/bin/ryoka-proxy; then
  rm -f /usr/local/bin/ryoka-proxy
fi
if [[ -f /usr/share/applications/ryoka-proxy.desktop ]] && grep -q '^Name=Ryoka Proxy$' /usr/share/applications/ryoka-proxy.desktop; then
  rm -f /usr/share/applications/ryoka-proxy.desktop
fi
systemctl daemon-reload
# The only password prompt required for normal local usage is the sudo prompt
# at this installation step. Existing grants for other users are preserved.
if [[ "$AUTH_MODE" != skip ]]; then
  if [[ -n "$AUTH_USER" && "$AUTH_USER" != root ]]; then
    /usr/local/bin/ryoku-proxy-access "$AUTH_MODE" "$AUTH_USER"
  else
    echo 'No desktop user identified (run with sudo or --grant-user USER); normal polkit prompts remain.'
  fi
fi
cat <<'MSG'
Ryoku Proxy v1.0 installed.
Run as normal user: ryoku-proxy
Old Ryoka v1/v2 profiles auto-migrate to ~/.config/ryoku-proxy/profiles.json on first save.
No running sing-box config, firewall policy or existing user profile is modified by installation.
New Kill Switch activations start with a 120-second recoverable trial.
Your existing Kill Switch configuration is preserved if already enabled.
Local desktop user access is managed by: sudo ryoku-proxy-access grant|revoke USER
Only org.ryoku.proxy.manage is authorized; no global sudo or polkit bypass is installed.
Use install.sh --require-password to require a password for each privileged action.
IMPORTANT: Enable it only at the local machine; LAN/SSH traffic may be blocked.
MSG
