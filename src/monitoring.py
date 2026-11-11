"""Read-only sing-box connection snapshot and TUN host counters.

Clash API listens only on 127.0.0.1 with an explicit random Bearer token.
Never uses ambient HTTP_PROXY/HTTPS_PROXY to access loopback.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from urllib.request import build_opener, ProxyHandler, Request

MONITOR_FILE = 'monitor.json'
ADDRESS = 'http://127.0.0.1:19109'


def token_path():
    base = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config')
    return base / 'ryoku-proxy' / MONITOR_FILE


def get_token():
    p = token_path()
    if not p.is_file():
        return None
    data = json.loads(p.read_text(encoding='utf-8'))
    return data.get('token') if isinstance(data, dict) else None


def save_token(token):
    p = token_path()
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(p.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix='.monitor-', dir=p.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'token': token}, f)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, p)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def delete_token():
    token_path().unlink(missing_ok=True)


def api_snapshot(token, timeout=2.0):
    if not token:
        raise RuntimeError('Мониторинг соединений ещё не активирован')
    opener = build_opener(ProxyHandler({}))
    request = Request(ADDRESS + '/connections', headers={
        'Authorization': 'Bearer ' + token,
        'Accept': 'application/json',
    })
    with opener.open(request, timeout=timeout) as response:
        if response.status != 200:
            raise RuntimeError(f'API ответил HTTP {response.status}')
        data = json.loads(response.read(1024 * 1024))
    return summarize_connections(data)


def summarize_connections(data):
    if not isinstance(data, dict):
        raise ValueError('Неверный ответ API sing-box')
    raw_connections = data.get('connections') or []
    if not isinstance(raw_connections, list):
        raise ValueError('Неверный список соединений API')
    rows = []
    for item in raw_connections[:150]:
        if not isinstance(item, dict):
            continue
        meta = item.get('metadata') or {}
        if not isinstance(meta, dict):
            meta = {}
        dest = (meta.get('host') or meta.get('destinationIP') or '—')
        port = meta.get('destinationPort')
        destination = str(dest) + ((':' + str(port)) if port else '')
        rows.append({
            'destination': destination[:128],
            'type': str(meta.get('network') or meta.get('type') or '—').upper()[:15],
            'process': str(meta.get('process') or meta.get('processPath') or '—')[-96:],
            'upload': max(0, int(item.get('upload') or 0)),
            'download': max(0, int(item.get('download') or 0)),
            'chain': ' / '.join(map(str, (item.get('chains') or [])[:4]))[:100],
        })
    return {'active': len(raw_connections), 'connections': rows,
            'upload_total': max(0, int(data.get('uploadTotal', 0))),
            'download_total': max(0, int(data.get('downloadTotal', 0))),
            'memory': max(0, int(data.get('memory', 0)))}


def tun_counters(interface='tun0'):
    if not interface or '/' in interface or '..' in interface:
        raise ValueError('Неверное имя интерфейса')
    root = Path('/sys/class/net') / interface / 'statistics'
    return {'rx_bytes': int((root / 'rx_bytes').read_text().strip()),
            'tx_bytes': int((root / 'tx_bytes').read_text().strip()),
            'timestamp': time.monotonic()}


def pretty_size(n):
    for suffix in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(n) < 1024 or suffix == 'TiB':
            return (f'{n:.0f} {suffix}' if suffix == 'B' else f'{n:.1f} {suffix}')
        n /= 1024
