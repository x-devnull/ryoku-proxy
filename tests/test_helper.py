import copy
import importlib.machinery
import importlib.util
import sys
import unittest
from pathlib import Path

path = str(Path(__file__).resolve().parent.parent / 'src' / 'ryoku-proxy-helper')
loader = importlib.machinery.SourceFileLoader('helper', path)
spec = importlib.util.spec_from_loader('helper', loader)
helper = importlib.util.module_from_spec(spec)
loader.exec_module(helper)

BASE = {
  'dns': {'servers': [{'type': 'udp', 'tag': 'bootstrap-dns', 'server': '1.1.1.1'},
                      {'type': 'https', 'tag': 'remote-dns', 'server': '1.1.1.1', 'detour': 'proxy'}]},
  'inbounds': [{'type': 'tun', 'interface_name': 'tun0', 'auto_redirect': True}],
  'outbounds': [{'type': 'http', 'tag': 'proxy', 'server': 'old.example', 'server_port': 7777,
                 'username': 'x', 'password': 'y', 'domain_resolver': 'bootstrap-dns'},
                {'type': 'direct', 'tag': 'direct'}],
  'route': {'default_domain_resolver': 'bootstrap-dns', 'final': 'proxy',
            'rules': [{'port': 53, 'action': 'hijack-dns'},
                      {'network': 'udp', 'action': 'reject'},
                      {'network': 'icmp', 'action': 'reject'}]}
}


class HelperTests(unittest.TestCase):
    def payload(self, **extra):
        p = {'protocol': 'http', 'host': 'dc04.steelproxy.com', 'port': 8999,
             'username': 'new', 'password': 'secret', 'tls': False, 'udp': False}
        p.update(extra)
        return helper.validate_transport(p)

    def test_http_maintains_dns_and_tun(self):
        before = copy.deepcopy(BASE)
        result = helper.build_config(BASE, self.payload())
        self.assertEqual(result['inbounds'], BASE['inbounds'])
        self.assertEqual(result['dns'], BASE['dns'])
        self.assertEqual(result['route']['rules'][0]['action'], 'hijack-dns')
        self.assertEqual(result['outbounds'][0]['domain_resolver'], 'bootstrap-dns')
        self.assertTrue(any(helper.udp_rule(r) for r in result['route']['rules']))
        self.assertEqual(before, BASE)

    def test_socks_udp_unblocked(self):
        result = helper.build_config(BASE, self.payload(protocol='socks5', port=1080, udp=True))
        self.assertEqual(result['outbounds'][0]['type'], 'socks')
        self.assertEqual(result['outbounds'][0]['version'], '5')
        self.assertFalse(any(helper.udp_rule(r) for r in result['route']['rules']))

    def test_socks_udp_blocked(self):
        result = helper.build_config(BASE, self.payload(protocol='socks5', port=1080))
        self.assertTrue(any(helper.udp_rule(r) for r in result['route']['rules']))

    def test_https_tls(self):
        result = helper.build_config(BASE, self.payload(tls=True))
        self.assertTrue(result['outbounds'][0]['tls']['enabled'])

    def test_invalid(self):
        with self.assertRaises(ValueError):
            helper.validate_transport(self.payload().__class__({'protocol':'ftp'}))

    def test_no_bootstrap_refuses_implicit_resolver(self):
        conf = copy.deepcopy(BASE)
        conf['dns']['servers'] = []
        conf['route'].pop('default_domain_resolver')
        conf['outbounds'][0].pop('domain_resolver')
        with self.assertRaisesRegex(ValueError, 'bootstrap-dns'):
            helper.build_config(conf, self.payload())


if __name__ == '__main__':
    unittest.main()
