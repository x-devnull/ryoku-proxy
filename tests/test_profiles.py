import json
import stat
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from profile_store import (new_profile, validate_profile, parse_proxy_url, load_store,
                           save_store, candidates, migrate_v1)


class ProfileTests(unittest.TestCase):
    def test_ipv6_url_and_escaping(self):
        p = parse_proxy_url('socks5h://user:p%40s%25@[2001:db8::1]:1081')
        self.assertEqual(p['host'], '2001:db8::1')
        self.assertEqual(p['password'], 'p@s%')
        self.assertEqual(p['socks_port'], 1081)
        self.assertEqual(p['http_port'], 0)

    def test_http_tls(self):
        p = parse_proxy_url('https://login:pass@proxy.example:443')
        self.assertEqual(p['http_port'], 443)
        self.assertTrue(p['http_tls'])
        self.assertEqual(p['preferred'], 'http')

    def test_reject_path(self):
        with self.assertRaises(ValueError):
            parse_proxy_url('http://proxy.example:8000/something')

    def test_dual_transport_auto(self):
        p = new_profile()
        p.update(host='dc04.steelproxy.com', socks_port=1080, preferred='auto', socks_udp=True)
        items = candidates(p)
        self.assertEqual([x['protocol'] for x in items], ['socks5', 'http'])
        self.assertTrue(items[0]['udp'])
        self.assertFalse(items[1]['udp'])

    def test_single_socks_no_http(self):
        p = new_profile()
        p.update(host='dc04.steelproxy.com', http_port=0, socks_port=1080, preferred='socks5')
        self.assertEqual(len(candidates(p)), 1)

    def test_migrate_v1_socks(self):
        old = {'id': str(uuid.uuid4()), 'name': 'Old', 'protocol': 'socks5',
               'host': 'dc04.steelproxy.com', 'port': 1099, 'username': 'x',
               'password': 'y', 'tls': False, 'udp': True}
        p = migrate_v1(old)
        self.assertEqual(p['socks_port'], 1099)
        self.assertEqual(p['http_port'], 0)
        self.assertEqual(p['preferred'], 'socks5')

    def test_roundtrip_private(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / 'profiles.json'
            p = new_profile()
            p.update(host='proxy.example', username='x', password='secret')
            data = {'version': 2, 'active_id': p['id'], 'active_mtime_ns': 123,
                    'profiles': [p]}
            save_store(data, file, secrets=False)
            self.assertEqual(stat.S_IMODE(file.stat().st_mode), 0o600)
            loaded = load_store(file, secrets=False)
            self.assertEqual(loaded['profiles'][0]['password'], 'secret')
            self.assertEqual(loaded['active_mtime_ns'], 123)

    def test_load_v1_store(self):
        with tempfile.TemporaryDirectory() as td:
            file = Path(td) / 'v1.json'
            old = {'id': str(uuid.uuid4()), 'name': 'Old', 'protocol': 'http',
                   'host': 'proxy.example', 'port': 8888, 'username': 'x',
                   'password': 'password', 'tls': False, 'udp': False}
            file.write_text(json.dumps({'version': 1, 'active_id': old['id'], 'profiles': [old]}))
            data = load_store(file, secrets=False)
            self.assertEqual(data['profiles'][0]['http_port'], 8888)
            self.assertEqual(data['active_id'], old['id'])


if __name__ == '__main__':
    unittest.main()
