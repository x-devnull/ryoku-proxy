"""Validated Ryoku per-destination exclusions (sing-box 1.14, nftables policy).

For hostnames we use a marked sing-box direct outbound, NOT a pretend DNS ->
static IP firewall mapping. The mark is a capability: any privileged process
able to set SO_MARK could exploit it, so do not claim an unbreakable sandbox.
"""
from __future__ import annotations

import ipaddress
import json
import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

ROUTING_MARK = 0x52594B  # Unique to this application's direct outbound.
ROUTE_TAG = 'ryoku-direct'
MAX_EXCEPTIONS = 128
MAX_LOCAL_NETWORKS = 32
ROUTING_FILE = Path('/etc/ryoku-proxy/routing.json')
DOMAIN_RE = re.compile(r'^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*$', re.I)


def normalize_rule(value):
    if not isinstance(value, str) or len(value.strip()) > 260:
        raise ValueError('Invalid bypass entry')
    text = value.strip().lower()
    if not text or any(ord(c) < 32 for c in text) or any(c.isspace() for c in text):
        raise ValueError('Invalid bypass entry')
    try:
        net = ipaddress.ip_network(text, strict=False)
        if '%' in text or net.prefixlen == 0:
            raise ValueError('A default route or scoped address is not allowed')
        return str(net)
    except ValueError:
        pass
    if '://' in text:
        try:
            parsed = urlsplit(text)
            if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError('Use a plain hostname, or HTTP(S) URL without credentials')
            if parsed.port is not None:
                raise ValueError('Ports cannot be bypassed separately')
            text = parsed.hostname.lower()
            try:
                ip = ipaddress.ip_address(text)
                return str(ipaddress.ip_network(f'{ip}/{ip.max_prefixlen}'))
            except ValueError:
                pass
        except ValueError as exc:
            raise ValueError('Invalid hostname or URL') from exc
    wildcard = text.startswith('*.')
    domain = text[2:] if wildcard else text
    try:
        domain = domain.encode('idna').decode('ascii').lower()
    except UnicodeError as exc:
        raise ValueError('Invalid international domain') from exc
    if (not DOMAIN_RE.fullmatch(domain) or (not wildcard and '.' not in domain)
            or len(domain) > 253 or (wildcard and len(domain) < 2)):
        raise ValueError('Expected a hostname, *.example.org or an IP/CIDR')
    return ('*.' if wildcard else '') + domain


def validated_rules(items):
    if not isinstance(items, list) or len(items) > MAX_EXCEPTIONS:
        raise ValueError('Too many bypass entries')
    return list(dict.fromkeys(normalize_rule(x) for x in items))


def by_type(items):
    cidrs, exact, wildcard = [], [], []
    for value in validated_rules(items):
        if value.startswith('*.'):
            wildcard.append(value[2:])
            continue
        try:
            ipaddress.ip_network(value, strict=False)
            cidrs.append(value)
        except ValueError:
            exact.append(value)
    return cidrs, exact, wildcard


def domain_to_regex(domain):
    # *.example.org matches x.example.org and x.y.example.org, not example.org itself.
    return r'^(?:[^.]+\.)+' + re.escape(domain) + r'$'


def build_bypass_rules(entries):
    cidrs, exact, wildcard = by_type(entries)
    rules = []
    if cidrs:
        rules.append({'ip_cidr': cidrs, 'action': 'route', 'outbound': ROUTE_TAG})
    if exact:
        rules.append({'domain': exact, 'action': 'route', 'outbound': ROUTE_TAG})
    if wildcard:
        rules.append({'domain_regex': [domain_to_regex(x) for x in wildcard],
                      'action': 'route', 'outbound': ROUTE_TAG})
    return rules


def update_config(conf, exclusions):
    import copy
    conf = copy.deepcopy(conf)
    values = validated_rules(exclusions)
    route = conf.get('route')
    if not isinstance(route, dict) or not isinstance(route.get('rules'), list):
        raise ValueError('Missing sing-box routing rules')
    if not any(x.get('type') == 'tun' and x.get('auto_redirect')
               for x in conf.get('inbounds', []) if isinstance(x, dict)):
        raise ValueError('Domain bypass requires a TUN with auto_redirect enabled')
    # Only remove rules explicitly tagged and owned by Ryoku.
    # Identify managed rules by the reserved outbound tag. The preceding sniff
    # belongs to Ryoku only when immediately followed by a managed rule.
    old_rules = route['rules']
    kept = []
    sniff_signature = {'action': 'sniff', 'sniffer': ['http', 'tls'], 'timeout': '300ms'}
    for index, rule in enumerate(old_rules):
        managed = isinstance(rule, dict) and rule.get('action') == 'route' and rule.get('outbound') == ROUTE_TAG
        if managed:
            continue
        following_managed = (index + 1 < len(old_rules) and
            isinstance(old_rules[index + 1], dict) and old_rules[index + 1].get('outbound') == ROUTE_TAG)
        if rule == sniff_signature and following_managed:
            continue
        kept.append(rule)
    route['rules'] = kept
    outbounds = conf.get('outbounds')
    if not isinstance(outbounds, list):
        raise ValueError('Invalid sing-box outbounds')
    previous = [x for x in outbounds if isinstance(x, dict) and x.get('tag') == ROUTE_TAG]
    if previous and any(x.get('type') != 'direct' for x in previous):
        raise ValueError('Reserved outbound tag is in use')
    conf['outbounds'] = [x for x in outbounds if not (isinstance(x, dict) and
                         x.get('tag') == ROUTE_TAG)]
    if values:
        conf['outbounds'].append({'type': 'direct', 'tag': ROUTE_TAG,
                                  'routing_mark': ROUTING_MARK})
        bypass = build_bypass_rules(values)
        # Preserve hijack DNS at front, but exclude before blanket UDP reject.
        index = next((i + 1 for i, r in enumerate(route['rules'])
                      if isinstance(r, dict) and r.get('action') == 'hijack-dns'), 0)
        route['rules'][index:index] = bypass
        # Sniff TCP TLS/HTTP hostnames on tun connections for domain-based rules.
        if any('domain' in r or 'domain_regex' in r for r in bypass):
            route['rules'].insert(index, {'action': 'sniff', 'sniffer': ['http', 'tls'],
                                           'timeout': '300ms'})
            # sniff rule is not tagged; remove it during replacement via exact signature
    return conf


def read_exclusions():
    if ROUTING_FILE.is_symlink() or not ROUTING_FILE.exists():
        return []
    record = json.loads(ROUTING_FILE.read_text(encoding='utf-8'))
    return validated_rules(record.get('exclusions', []))


def detect_local_networks(ip_json):
    if not isinstance(ip_json, list):
        raise ValueError('Expected ip -j address show output')
    found = []
    for iface in ip_json:
        name = iface.get('ifname', '')
        if name == 'lo' or name.startswith(('tun', 'veth', 'docker', 'br-', 'virbr', 'wg')):
            continue
        for addr in iface.get('addr_info', []):
            try:
                ip = ipaddress.ip_address(addr['local'])
                prefix = int(addr['prefixlen'])
                net = ipaddress.ip_network(f'{ip}/{prefix}', strict=False)
            except (KeyError, ValueError, TypeError):
                continue
            if (net.is_private and not net.is_loopback and not net.is_link_local and
                net.prefixlen >= (16 if net.version == 4 else 48)):
                value = str(net)
                if value not in found:
                    found.append(value)
    return found[:MAX_LOCAL_NETWORKS]


def local_networks():
    result = subprocess.run(['/usr/bin/ip', '-j', 'address', 'show'], capture_output=True,
                            text=True, timeout=5, check=True)
    return detect_local_networks(json.loads(result.stdout))
