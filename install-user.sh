#!/usr/bin/env bash
# Update the unprivileged GUI, reusing an already installed system helper.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"
if (( EUID == 0 )); then echo 'Run this installer as your desktop user.' >&2; exit 1; fi
/usr/bin/python3 -c 'import PySide6' || exit 1
helper=/usr/lib/ryoku-proxy/ryoku-proxy-helper
if [[ ! -x "$helper" ]]; then
  echo 'System helper is missing. First run: sudo bash install.sh' >&2
  exit 1
fi
# User installations must not mix a new helper contract with an old backend.
for component in ryoku-proxy-helper firewall.py routing.py; do
  if ! cmp -s "src/$component" "/usr/lib/ryoku-proxy/$component"; then
    echo 'System helper differs from this release. Update it first: sudo bash install.sh' >&2
    exit 1
  fi
done
app_dir="${XDG_DATA_HOME:-$HOME/.local/share}/ryoku-proxy"
bin_dir="$HOME/.local/bin"
apps_dir="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
icons_dir="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/scalable/apps"
install -d "$app_dir" "$bin_dir" "$apps_dir" "$icons_dir"
for component in profile_store.py network_probe.py monitoring.py routing.py i18n.py ryoku_proxy.py; do
  install -m 0644 "src/$component" "$app_dir/$component"
done
# Generate a launcher with a safely quoted absolute path, independent of PATH.
/usr/bin/python3 - "$app_dir" "$bin_dir" "$apps_dir" <<'PY'
from pathlib import Path
import shlex
import sys
app, binaries, applications = map(Path, sys.argv[1:])
launcher = binaries / 'ryoku-proxy'
launcher.write_text('#!/bin/sh\nexec /usr/bin/python3 ' + shlex.quote(str(app / 'ryoku_proxy.py')) + ' "$@"\n')
launcher.chmod(0o755)
entry = Path('packaging/ryoku-proxy.desktop').read_text()
# Desktop Exec syntax uses double quotes, not shell quoting.
quoted = str(launcher).replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%')
entry = entry.replace('Exec=ryoku-proxy', 'Exec="' + quoted + '"')
(applications / 'ryoku-proxy.desktop').write_text(entry)
PY
install -m 0644 packaging/ryoku-proxy.svg "$icons_dir/ryoku-proxy.svg"
if command -v update-desktop-database >/dev/null; then update-desktop-database "$apps_dir"; fi
"$bin_dir/ryoku-proxy" --version
echo "Installed user GUI: $bin_dir/ryoku-proxy (existing system helper reused)."
