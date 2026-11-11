"""Ryoku Proxy profile model with v1 migration and Secret Service integration.

Passwords are kept in memory while editing. Prefer Secret Service (KWallet on
KDE); if unavailable, fall back to a 0600 file with an explicit UI warning.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path
from urllib.parse import unquote, urlsplit

VERSION = 2
PREFERENCES = ('auto', 'socks5', 'http')


def store_path() -> Path:
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'ryoku-proxy' / 'profiles.json'


def empty_store() -> dict:
    return {'version': VERSION, 'active_id': None, 'active_mtime_ns': None, 'profiles': []}


def new_profile(name='Новый сервер') -> dict:
    return {
        'id': str(uuid.uuid4()), 'name': name, 'host': '',
        'username': '', 'password': '', 'http_port': 8080, 'http_tls': False,
        'socks_port': 0, 'socks_udp': False, 'preferred': 'auto',
        'password_storage': 'file', 'secret_missing': False,
    }


def normalized_host(host):
    if not isinstance(host, str):
        raise ValueError('Адрес сервера должен быть строкой')
    host = host.strip()
    if host.startswith('[') and host.endswith(']'):
        host = host[1:-1]
    if not host:
        return host
    try:
        ipaddress.ip_address(host)
    except ValueError:
        if (len(host) > 253 or '..' in host or host.startswith(('-', '.')) or
                not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*', host)):
            raise ValueError('Недопустимый IP или домен прокси')
    return host


def validate_profile(v: dict, require_host=True) -> dict:
    if not isinstance(v, dict):
        raise ValueError('Неверный формат профиля')
    try:
        pid = str(uuid.UUID(str(v.get('id'))))
    except (TypeError, ValueError, AttributeError) as e:
        raise ValueError('Некорректный ID профиля') from e
    name = v.get('name', '')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError('Название: от 1 до 80 символов')
    host = normalized_host(v.get('host', ''))
    if require_host and not host:
        raise ValueError('Укажи IP-адрес или домен прокси')
    ports = {}
    for key in ('http_port', 'socks_port'):
        try:
            val = int(v.get(key, 0))
        except (TypeError, ValueError) as e:
            raise ValueError('Порт должен быть числом') from e
        if not 0 <= val <= 65535:
            raise ValueError('Порт должен быть от 0 до 65535')
        ports[key] = val
    if require_host and ports['http_port'] == ports['socks_port'] == 0:
        raise ValueError('Укажи хотя бы один порт: HTTP или SOCKS5')
    preferred = v.get('preferred', 'auto')
    if preferred not in PREFERENCES:
        raise ValueError('Некорректный способ подключения')
    if require_host and preferred != 'auto' and not ports['http_port' if preferred == 'http' else 'socks_port']:
        raise ValueError('Для выбранного протокола не указан порт')
    username = v.get('username', '')
    password = v.get('password', '')
    if any(not isinstance(x, str) or '\x00' in x or len(x) > 4096 for x in (username, password)):
        raise ValueError('Некорректный логин или пароль')
    if type(v.get('http_tls', False)) is not bool or type(v.get('socks_udp', False)) is not bool:
        raise ValueError('Неверные TLS/UDP настройки')
    storage = v.get('password_storage', 'file')
    if storage not in ('file', 'secret-service'):
        raise ValueError('Неизвестный тип хранения пароля')
    return {
        'id': pid, 'name': name.strip(), 'host': host, 'username': username,
        'password': password, **ports, 'http_tls': v.get('http_tls', False),
        'socks_udp': v.get('socks_udp', False), 'preferred': preferred,
        'password_storage': storage, 'secret_missing': bool(v.get('secret_missing', False)),
    }


def migrate_v1(v):
    p = new_profile(v.get('name', 'Импортированный прокси'))
    p['id'] = v['id']
    p['host'] = v.get('host', '')
    p['username'] = v.get('username', '')
    p['password'] = v.get('password', '')
    p['http_port'] = v.get('port', 8080) if v.get('protocol', 'http') == 'http' else 0
    p['socks_port'] = v.get('port', 1080) if v.get('protocol') == 'socks5' else 0
    p['http_tls'] = v.get('tls', False)
    p['socks_udp'] = v.get('udp', False)
    p['preferred'] = v.get('protocol', 'http')
    return validate_profile(p, require_host=False)


def parse_proxy_url(text):
    raw = text.strip()
    try:
        url = urlsplit(raw)
        schemes = {'http': ('http', False, 8080), 'https': ('http', True, 443),
                   'socks5': ('socks5', False, 1080), 'socks5h': ('socks5', False, 1080)}
        if url.scheme.lower() not in schemes:
            raise ValueError('Нужен http://, https://, socks5:// или socks5h://')
        if url.path not in ('', '/') or url.query or url.fragment:
            raise ValueError('В URL прокси не должно быть пути или параметров')
        protocol, tls, port = schemes[url.scheme.lower()]
        host = url.hostname or ''
        p = new_profile(f'{host} · {protocol.upper()}')
        p.update(host=host, username=unquote(url.username or ''),
                 password=unquote(url.password or ''), preferred=protocol,
                 http_port=(url.port or port) if protocol == 'http' else 0,
                 socks_port=(url.port or port) if protocol == 'socks5' else 0,
                 http_tls=tls)
        return validate_profile(p)
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f'Не удалось прочитать URL: {exc}') from exc


def _secret_tool(action, profile_id, value=None):
    binary = shutil.which('secret-tool')
    if not binary:
        raise RuntimeError('secret-tool не установлен')
    args = [binary, action]
    if action == 'store':
        args += [f'--label=Ryoku Proxy · {profile_id}']
    args += ['application', 'ryoku-proxy', 'profile', profile_id]
    result = subprocess.run(args, input=value if action == 'store' else None,
                            capture_output=True, text=True, timeout=6)
    if action == 'lookup' and (result.returncode or not result.stdout):
        args[-3] = 'ryoka-proxy'  # import existing v2 KWallet entries
        result = subprocess.run(args, capture_output=True, text=True, timeout=6)
    if action == 'clear':
        args[-3] = 'ryoka-proxy'
        subprocess.run(args, capture_output=True, text=True, timeout=6)
    if result.returncode:
        raise RuntimeError('KWallet / Secret Service недоступен')
    return result.stdout.rstrip('\n')


def delete_password(p: dict):
    if p.get('password_storage') == 'secret-service':
        try:
            _secret_tool('clear', p['id'])
        except (OSError, RuntimeError, subprocess.TimeoutExpired):
            pass


def load_store(path=None, secrets=True):
    p = Path(path or store_path())
    if path is None and not p.exists():
        old_path = p.parent.parent / 'ryoka-proxy' / 'profiles.json'
        if old_path.exists():
            p = old_path  # read-only migration; new save always uses ryoku-proxy
    if not p.exists():
        return empty_store()
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        if not isinstance(data, dict) or not isinstance(data.get('profiles'), list):
            raise ValueError('Неверный формат файла')
        version = data.get('version')
        if version not in (1, VERSION):
            raise ValueError('Неизвестная версия профилей')
        profiles = []
        for raw in data['profiles']:
            if version == 1:
                v = migrate_v1(raw)
            else:
                v = validate_profile(raw, require_host=False)
                if v['password_storage'] == 'secret-service':
                    try:
                        if secrets:
                            v['password'] = _secret_tool('lookup', v['id'])
                        v['secret_missing'] = not bool(v['password']) if secrets else False
                    except (OSError, RuntimeError, subprocess.TimeoutExpired):
                        v['password'] = ''
                        v['secret_missing'] = True
            profiles.append(v)
        ids = [v['id'] for v in profiles]
        if len(ids) != len(set(ids)):
            raise ValueError('Повторяющиеся ID профилей')
        active_id = data.get('active_id')
        if active_id not in ids:
            active_id = None
        return {'version': VERSION, 'profiles': profiles, 'active_id': active_id,
                'active_mtime_ns': data.get('active_mtime_ns') if version == VERSION else None}
    except (OSError, ValueError, TypeError) as e:
        raise RuntimeError(f'Ошибка чтения профилей: {e}') from e


def save_store(data, path=None, secrets=True):
    p = Path(path or store_path())
    p.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(p.parent, 0o700)
    profiles = [validate_profile(v, require_host=False) for v in data['profiles']]
    serialized = []
    for profile in profiles:
        record = {k: v for k, v in profile.items() if k not in ('password', 'secret_missing')}
        passwd = profile['password']
        if secrets and (passwd or profile['password_storage'] == 'secret-service'):
            if profile['secret_missing'] and not passwd:
                record['password_storage'] = 'secret-service'
            else:
                try:
                    if passwd:
                        _secret_tool('store', profile['id'], passwd)
                        record['password_storage'] = 'secret-service'
                    elif profile['password_storage'] == 'secret-service':
                        _secret_tool('clear', profile['id'])
                        record['password_storage'] = 'file'
                except (OSError, RuntimeError, subprocess.TimeoutExpired):
                    record['password_storage'] = 'file'
        if record['password_storage'] == 'file':
            record['password'] = passwd
        profile['password_storage'] = record['password_storage']
        profile['secret_missing'] = False if passwd else profile['secret_missing']
        serialized.append(record)
    wire = {'version': VERSION, 'active_id': data.get('active_id'),
            'active_mtime_ns': data.get('active_mtime_ns'), 'profiles': serialized}
    fd, temp = tempfile.mkstemp(prefix='.profiles-', dir=p.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(wire, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, p)
        data['profiles'][:] = profiles
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def candidates(profile):
    p = validate_profile(profile)
    order = ['socks5', 'http'] if p['preferred'] in ('auto', 'socks5') else ['http', 'socks5']
    if p['preferred'] != 'auto':
        order = [p['preferred']]
    result = []
    for protocol in order:
        port = p['socks_port'] if protocol == 'socks5' else p['http_port']
        if not port:
            continue
        result.append({'protocol': protocol, 'host': p['host'], 'port': port,
                       'username': p['username'], 'password': p['password'],
                       'tls': p['http_tls'] if protocol == 'http' else False,
                       'udp': p['socks_udp'] if protocol == 'socks5' else False})
    if not result:
        raise ValueError('Не задан доступный способ подключения')
    return result
