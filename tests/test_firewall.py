import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
import firewall

CONF = {
    'inbounds': [{'type': 'tun', 'interface_name': 'tun0'}],
    'outbounds': [{'tag': 'proxy', 'type': 'socks', 'server': '198.51.100.17', 'server_port': 1080}],
    'dns': {'servers': [{'tag': 'bootstrap-dns', 'type': 'udp', 'server': '1.1.1.1', 'server_port': 53}]}
}

class FirewallTests(unittest.TestCase):
    def test_state_uses_exact_proxy_and_dns(self):
        state = firewall.build_state(CONF)
        self.assertEqual(state['endpoints'], [{'ip': '198.51.100.17', 'port': 1080}])
        self.assertEqual(state['bootstrap'], [{'ip': '1.1.1.1', 'port': 53, 'protocol': 'udp'}])

    def test_fail_closed_output_and_forward_rules(self):
        script = firewall.render_rules(firewall.build_state(CONF))
        self.assertIn('policy drop', script)
        self.assertIn('oifname "tun0" accept', script)
        self.assertIn('ip daddr 198.51.100.17 tcp dport 1080 accept', script)
        self.assertNotIn('tcp dport 443 accept', script)
        self.assertNotIn('flush ruleset', script)

    def test_invalid_endpoint_injection_rejected(self):
        state = firewall.build_state(CONF)
        state['endpoints'][0]['ip'] = '1.2.3.4; delete table inet other'
        with self.assertRaises(ValueError):
            firewall.render_rules(state)

    def test_ipv6_scope_rejected(self):
        with self.assertRaises(ValueError):
            firewall.validated_ip('fe80::1%eth0')

    def test_unrelated_nft_tables_not_changed(self):
        state = firewall.build_state(CONF)
        script = firewall.render_rules(state, exists=True)
        self.assertIn('delete table inet ryoku_proxy', script)
        self.assertNotIn('delete table inet filter', script)

    def test_dns_domain_is_not_allowed_as_bootstrap(self):
        conf = json.loads(json.dumps(CONF))
        conf['dns']['servers'][0]['server'] = 'dns.example'
        self.assertEqual(firewall.build_state(conf)['bootstrap'], [])

    def test_provision_persists_only_if_rules_applied(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(firewall, 'STATE_PATH', Path(td) / 'state.json'):
                with patch.object(firewall, 'apply_rules', side_effect=RuntimeError('no nft')):
                    with self.assertRaises(RuntimeError):
                        firewall.provision(CONF)
                self.assertFalse((Path(td) / 'state.json').exists())

    def test_candidate_extension_and_restore(self):
        with tempfile.TemporaryDirectory() as td:
            state = firewall.build_state(CONF)
            p = Path(td) / 'state.json'
            p.write_text(json.dumps(state))
            with patch.object(firewall, 'STATE_PATH', p):
                with patch.object(firewall, 'apply_rules') as applied:
                    previous = firewall.extend_for_candidates(CONF, [{
                        'host': '203.0.113.44', 'port': 3128}])
                    self.assertEqual(previous, state)
                    opened = applied.call_args[0][0]
                    self.assertIn({'ip': '203.0.113.44', 'port': 3128}, opened['endpoints'])
                    self.assertIn({'ip': '198.51.100.17', 'port': 1080}, opened['endpoints'])
                    self.assertEqual(json.loads(p.read_text()), state)
                    firewall.restore(previous)
                    self.assertEqual(json.loads(p.read_text()), state)

if __name__ == '__main__': unittest.main()
