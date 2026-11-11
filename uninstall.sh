#!/usr/bin/env bash
set -euo pipefail
if (( EUID != 0 )); then echo 'Usage: sudo bash uninstall.sh' >&2; exit 1; fi
# Never silently dismantle an active fail-closed firewall.
if systemctl is-enabled --quiet ryoku-proxy-killswitch.service || systemctl is-active --quiet ryoku-proxy-killswitch.service || [[ -e /etc/ryoku-proxy/killswitch.json ]] || [[ -e /run/ryoku-proxy-killswitch-trial ]] || /usr/bin/nft list table inet ryoku_proxy >/dev/null 2>&1; then
  echo 'Kill Switch is enabled/active. First disable it in Ryoku Proxy GUI.' >&2
  echo 'Emergency: sudo systemctl disable --now ryoku-proxy-killswitch; sudo nft delete table inet ryoku_proxy' >&2
  exit 1
fi
# Remove only this app's polkit grant; never touch global polkit/sudo policy.
rm -f /etc/polkit-1/rules.d/20-ryoku-proxy-local.rules
rm -f /etc/ryoku-proxy/authorized-users.json
rm -f /usr/share/polkit-1/actions/org.ryoku.proxy.policy
rm -f /usr/local/bin/ryoku-proxy-access
rm -f /usr/local/bin/ryoku-proxy /usr/share/applications/ryoku-proxy.desktop /usr/share/pixmaps/ryoku-proxy.svg /usr/share/metainfo/ryoku-proxy.metainfo.xml
rm -f /etc/systemd/system/ryoku-proxy-killswitch.service
rm -f /usr/lib/ryoku-proxy/{ryoku-proxy-helper,firewall.py,routing.py}
rm -f /usr/share/ryoku-proxy/{profile_store,network_probe,monitoring,ryoku_proxy,routing,i18n}.py
rmdir /usr/lib/ryoku-proxy /usr/share/ryoku-proxy 2>/dev/null || true
systemctl daemon-reload
echo 'Ryoku Proxy GUI removed; sing-box and user profiles remain unchanged.'
