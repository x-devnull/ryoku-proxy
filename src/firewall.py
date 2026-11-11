"""Ryoku firewall controller: isolated nftables table, guarded trial & recovery.

Never changes user tables. A direct exemption is an intentional bypass of the
proxy and kill switch. A marked direct outbound is allowed for domain rules;
SO_MARK is not a cryptographic proof of process ownership.
"""
from __future__ import annotations

import copy
import ipaddress
import json
import os
import re
import socket
import stat
import subprocess
import tempfile
from pathlib import Path

STATE_PATH = Path('/etc/ryoku-proxy/killswitch.json')
TRIAL_PATH = Path('/run/ryoku-proxy-killswitch-trial')
NFT = '/usr/bin/nft'
TABLE = 'ryoku_proxy'
MAX_IPS = 12


def run(*args, input=None, timeout=10):
    return subprocess.run(args, input=input, text=True, capture_output=True, timeout=timeout)


def validated_ip(value):
    if not isinstance(value, str) or '%' in value:
        raise ValueError('Invalid IP address')
    return str(ipaddress.ip_address(value))


def resolve_host(host):
    try:
        return [validated_ip(host)]
    except ValueError:
        pass
    result = []
    for family, _, _, _, addr in socket.getaddrinfo(host, None, type=socket.SOCK_STREAM):
        if family in (socket.AF_INET, socket.AF_INET6):
            ip = validated_ip(addr[0])
            if ip not in result:
                result.append(ip)
    if not result:
        raise RuntimeError('Proxy hostname did not resolve')
    return result[:MAX_IPS]


def addresses_for(host, port):
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid proxy port')
    return [{'ip': x, 'port': port} for x in resolve_host(host)]


def proxy_endpoints(config):
    out = next((x for x in config.get('outbounds', []) if x.get('tag') == 'proxy'), None)
    if not out or out.get('type') not in ('http', 'socks'):
        raise ValueError('Missing managed proxy outbound')
    return addresses_for(out['server'], out['server_port'])


def bootstrap_endpoints(config):
    records = []
    for server in config.get('dns', {}).get('servers', []):
        if server.get('tag') != 'bootstrap-dns' or server.get('detour') not in (None, '', 'direct'):
            continue
        try:
            ip = validated_ip(server.get('server'))
        except (TypeError, ValueError):
            continue
        proto = server.get('type', 'udp')
        port = server.get('server_port', 53)
        if proto in ('tcp', 'udp') and type(port) is int and 1 <= port <= 65535:
            records.append({'ip': ip, 'port': port, 'protocol': proto})
    return records


def tun_name(config):
    tun = next((x for x in config.get('inbounds', []) if x.get('type') == 'tun'), None)
    name = tun.get('interface_name') if tun else None
    if not isinstance(name, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}', name):
        raise ValueError('Missing explicit TUN interface name')
    return name


def validate_state(value):
    from routing import ROUTING_MARK, validated_rules, by_type
    if not isinstance(value, dict) or value.get('version') not in (1, 2):
        raise ValueError('Unsupported Kill Switch state')
    tun = value.get('tun')
    if not isinstance(tun, str) or not re.fullmatch(r'[a-zA-Z0-9_.-]{1,15}', tun):
        raise ValueError('Invalid TUN name')
    endpoints = []
    for row in value.get('endpoints', []):
        if not isinstance(row, dict):
            raise ValueError('Invalid proxy endpoint')
        port = row.get('port')
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Invalid proxy port')
        endpoint = {'ip': validated_ip(row['ip']), 'port': port}
        if endpoint not in endpoints:
            endpoints.append(endpoint)
    backups = []
    for row in value.get('backups', []):
        port = row.get('port') if isinstance(row,dict) else None
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Invalid backup proxy endpoint')
        entry = {'ip': validated_ip(row['ip']), 'port': port}
        if entry not in backups:
            backups.append(entry)
    if not endpoints or len(endpoints) + len(backups) > 64:
        raise ValueError('Kill Switch needs 1–64 proxy endpoints')
    bootstrap = []
    for row in value.get('bootstrap', []):
        if not isinstance(row, dict) or row.get('protocol') not in ('tcp', 'udp'):
            raise ValueError('Invalid bootstrap endpoint')
        port = row.get('port')
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError('Invalid bootstrap DNS port')
        bootstrap.append({'ip': validated_ip(row['ip']), 'port': port, 'protocol': row['protocol']})
    bypass = validated_rules(value.get('exclusions', []))
    # All manual CIDRs are whitelisted explicitly; domain entries require
    # traffic from the dedicated SO_MARK sing-box direct outbound.
    nets, _, _ = by_type(bypass)
    if len(nets) > 96:
        raise ValueError('Too many direct network exceptions')
    return {'version': 2, 'tun': tun, 'endpoints': endpoints,
            'bootstrap': bootstrap, 'exclusions': bypass, 'backups': backups,
            'mark': ROUTING_MARK}


def build_state(conf, endpoints=None, exclusions=None):
    if exclusions is None:
        from routing import read_exclusions
        exclusions = read_exclusions()
    return validate_state({'version': 2, 'tun': tun_name(conf),
                           'endpoints': endpoints if endpoints is not None else proxy_endpoints(conf),
                           'bootstrap': bootstrap_endpoints(conf), 'exclusions': exclusions, 'backups': []})


def render_rules(state, exists=False):
    from routing import by_type
    state = validate_state(state)
    networks, exact_domains, wildcard_domains = by_type(state['exclusions'])
    lines = []
    if exists:
        lines.append('delete table inet ryoku_proxy')
    lines.extend([
        'add table inet ryoku_proxy',
        'add chain inet ryoku_proxy output { type filter hook output priority 0; policy drop; }',
        # No forward chain: avoid breaking containers/VMs and the host's unrelated routing.
        'add rule inet ryoku_proxy output oifname "lo" accept',
        f'add rule inet ryoku_proxy output oifname "{state["tun"]}" accept',
        'add rule inet ryoku_proxy output ip protocol udp udp sport 68 udp dport 67 accept',
        'add rule inet ryoku_proxy output ip6 nexthdr udp udp sport 546 udp dport 547 accept',
        'add rule inet ryoku_proxy output icmpv6 type { nd-router-solicit, nd-router-advert, nd-neighbor-solicit, nd-neighbor-advert } accept',
    ])
    if exact_domains or wildcard_domains:
        # This mark only comes from Ryoku's managed sing-box direct outbound
        # unless another privileged local process explicitly spoofs it.
        lines.append(f'add rule inet ryoku_proxy output meta mark 0x{state["mark"]:x} accept')
    for net in networks:
        fam = 'ip6' if ':' in net else 'ip'
        lines.append(f'add rule inet ryoku_proxy output {fam} daddr {net} accept')
    for ep in state['bootstrap']:
        fam = 'ip6' if ':' in ep['ip'] else 'ip'
        lines.append(f'add rule inet ryoku_proxy output {fam} daddr {ep["ip"]} {ep["protocol"]} dport {ep["port"]} accept')
    for ep in state['endpoints'] + state['backups']:
        fam = 'ip6' if ':' in ep['ip'] else 'ip'
        lines.append(f'add rule inet ryoku_proxy output {fam} daddr {ep["ip"]} tcp dport {ep["port"]} accept')
    return '\n'.join(lines) + '\n'


def present():
    return run(NFT, 'list', 'table', 'inet', TABLE).returncode == 0


def apply_rules(state):
    script = render_rules(state, exists=present())
    checked = run(NFT, '-c', '-f', '-', input=script)
    if checked.returncode:
        raise RuntimeError('nft validation failed: ' + (checked.stderr or checked.stdout)[-650:])
    result = run(NFT, '-f', '-', input=script)
    if result.returncode:
        raise RuntimeError('nft apply failed: ' + (result.stderr or result.stdout)[-650:])


def remove_rules():
    if present():
        proc = run(NFT, 'delete', 'table', 'inet', TABLE)
        if proc.returncode:
            raise RuntimeError('Cannot remove Ryoku table: ' + proc.stderr[-500:])


def save_state(value):
    value = validate_state(value)
    STATE_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(STATE_PATH.parent, 0o700)
    fd, tmp = tempfile.mkstemp(prefix='.killswitch-', dir=STATE_PATH.parent)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATE_PATH)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def read_state():
    if STATE_PATH.is_symlink():
        raise ValueError('Kill Switch state must not be a symlink')
    if not STATE_PATH.is_file():
        return None
    return validate_state(json.loads(STATE_PATH.read_text(encoding='utf-8')))


def provision(conf, exclusions=None):
    previous = read_state()
    state = build_state(conf, exclusions=exclusions)
    apply_rules(state)
    try:
        save_state(state)
    except Exception:
        if previous:
            apply_rules(previous)
        else:
            remove_rules()
        raise
    return state


def extend_for_candidates(conf, candidates):
    previous = read_state()
    if previous is None:
        return None
    expanded = copy.deepcopy(previous)
    for p in candidates:
        for ep in addresses_for(p['host'], p['port']):
            if ep not in expanded['endpoints']:
                expanded['endpoints'].append(ep)
    if len(expanded['endpoints']) > 64:
        raise ValueError('Too many candidate proxy endpoints')
    apply_rules(expanded)
    return previous


def set_active(conf):
    previous = read_state()
    if previous is None:
        return
    # Preserve backup endpoints pre-authorized by the administrator. Candidate
    # temporary endpoints are removed when switching succeeds.
    active = build_state(conf, exclusions=previous['exclusions'])
    active['backups'] = previous['backups']
    apply_rules(active)
    save_state(active)


def restore(previous):
    if previous is not None:
        apply_rules(previous)
        save_state(previous)


def set_backups(candidates):
    previous = read_state()
    if previous is None or not present():
        raise RuntimeError('Enable Kill Switch before adding backup proxy')
    if not isinstance(candidates, list) or len(candidates) > 8:
        raise ValueError('Too many backup proxy transports')
    endpoints = []
    for p in candidates:
        for ep in addresses_for(p['host'], p['port']):
            if ep not in endpoints:
                endpoints.append(ep)
    new = copy.deepcopy(previous)
    new['backups'] = endpoints
    new = validate_state(new)
    apply_rules(new)
    try:
        save_state(new)
    except Exception:
        apply_rules(previous)
        raise
    return {'backups': len(endpoints)}
