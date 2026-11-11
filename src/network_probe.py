"""Low-footprint HTTP CONNECT / SOCKS5 TCP + TLS handshake probe.

Tests proxy credentials and TCP relay to example.com:443. It uses the
current system route; while sing-box is running this may chain via its TUN.
No UDP or kill-switch claims follow from a successful probe.
"""
from __future__ import annotations

import base64
import ipaddress
import os
import subprocess
import socket
import ssl
import time

TARGET = 'example.com'
TARGET_PORT = 443


def _receive_exact(sock, n):
    payload = b''
    while len(payload) < n:
        chunk = sock.recv(n - len(payload))
        if not chunk:
            raise RuntimeError('Прокси неожиданно закрыл соединение')
        payload += chunk
    return payload


def _connect_http(sock, transport):
    line = f'CONNECT {TARGET}:{TARGET_PORT} HTTP/1.1\r\nHost: {TARGET}:{TARGET_PORT}\r\n'
    if transport['username'] or transport['password']:
        raw = f"{transport['username']}:{transport['password']}".encode('utf-8')
        line += 'Proxy-Authorization: Basic ' + base64.b64encode(raw).decode('ascii') + '\r\n'
    sock.sendall((line + 'Proxy-Connection: close\r\n\r\n').encode('ascii'))
    response = b''
    while b'\r\n\r\n' not in response and len(response) < 8192:
        chunk = sock.recv(512)
        if not chunk:
            break
        response += chunk
    first_line = response.split(b'\r\n', 1)[0].decode('ascii', errors='replace')
    if b'\r\n\r\n' not in response or not first_line.startswith('HTTP/'):
        raise RuntimeError('Некорректный ответ HTTP CONNECT')
    chunks = first_line.split()
    if len(chunks) < 2 or chunks[1] != '200':
        if len(chunks) >= 2 and chunks[1] == '407':
            raise RuntimeError('HTTP 407: неправильный логин или пароль')
        raise RuntimeError('HTTP CONNECT отклонён: ' + first_line[:100])


def _connect_socks5(sock, transport):
    needs_auth = bool(transport['username'] or transport['password'])
    sock.sendall(b'\x05\x02\x00\x02' if needs_auth else b'\x05\x01\x00')
    version, method = _receive_exact(sock, 2)
    if version != 5 or method == 0xFF:
        raise RuntimeError('SOCKS5: нет подходящего способа авторизации')
    if method == 2 and not needs_auth:
        raise RuntimeError('SOCKS5: сервер выбрал непредложенный метод авторизации')
    if method == 2:
        user = transport['username'].encode('utf-8')
        password = transport['password'].encode('utf-8')
        if len(user) > 255 or len(password) > 255:
            raise RuntimeError('SOCKS5: логин или пароль длиннее 255 байт')
        sock.sendall(b'\x01' + bytes([len(user)]) + user + bytes([len(password)]) + password)
        if _receive_exact(sock, 2) != b'\x01\x00':
            raise RuntimeError('SOCKS5: ошибка авторизации')
    elif method != 0:
        raise RuntimeError('SOCKS5: неизвестный метод авторизации')
    destination = TARGET.encode('ascii')
    sock.sendall(b'\x05\x01\x00\x03' + bytes([len(destination)]) + destination +
                 TARGET_PORT.to_bytes(2, 'big'))
    header = _receive_exact(sock, 4)
    if header[0] != 5 or header[1] != 0:
        raise RuntimeError(f'SOCKS5 CONNECT отклонён (код {header[1]})')
    addr_len = {1: 4, 4: 16}.get(header[3])
    if header[3] == 3:
        addr_len = _receive_exact(sock, 1)[0]
    if addr_len is None:
        raise RuntimeError('SOCKS5: неизвестный тип адреса')
    _receive_exact(sock, addr_len + 2)


def _curl_config_value(value):
    """Safely quote a curl config value, never interpolated into a shell command."""
    if '\r' in value or '\n' in value:
        raise ValueError('Нельзя тестировать пароль с переносом строки через curl')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _probe_https_http(transport, timeout):
    """curl handles nested TLS for HTTPS-proxy -> HTTPS-site (SSL-in-SSL)."""
    host = transport['host']
    if ':' in host and not host.startswith('['):
        host = '[' + host + ']'
    url = f"https://{host}:{transport['port']}"
    values = [f'proxy = {_curl_config_value(url)}',
              'fail', 'silent', 'show-error', 'ipv4',
              f'max-time = {int(timeout) + 5}',
              'output = "/dev/null"',
              'url = "https://example.com/"']
    if transport['username'] or transport['password']:
        values.append('proxy-user = ' + _curl_config_value(
            transport['username'] + ':' + transport['password']))
    env = {k: v for k, v in os.environ.items() if k.lower() not in
           ('http_proxy', 'https_proxy', 'all_proxy', 'no_proxy')}
    result = subprocess.run(['/usr/bin/curl', '--disable', '--config', '-'],
                            input='\n'.join(values) + '\n', capture_output=True,
                            text=True, timeout=int(timeout) + 8, env=env)
    if result.returncode:
        raise RuntimeError('HTTPS-прокси: TLS или CONNECT проверка не прошла ('
                           + (result.stderr.strip()[-180:] or 'ошибка curl') + ')')


def probe(transport, timeout=7):
    """Returns elapsed milliseconds after CONNECT + certificate-checked HTTPS."""
    start = time.monotonic()
    if transport['protocol'] == 'http' and transport['tls']:
        _probe_https_http(transport, timeout)
        return round((time.monotonic() - start) * 1000)
    raw = socket.create_connection((transport['host'], transport['port']), timeout=timeout)
    try:
        raw.settimeout(timeout)
        if transport['protocol'] == 'http':
            _connect_http(raw, transport)
        else:
            _connect_socks5(raw, transport)
        with ssl.create_default_context().wrap_socket(raw, server_hostname=TARGET) as tls:
            tls.settimeout(timeout)
            tls.sendall(b'GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n')
            response = tls.recv(128)
            if not response.startswith(b'HTTP/'):
                raise RuntimeError('HTTPS-сайт не ответил через прокси')
        return round((time.monotonic() - start) * 1000)
    finally:
        try:
            raw.close()
        except OSError:
            pass
