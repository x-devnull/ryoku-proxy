import copy
import importlib.machinery
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

path = str(Path(__file__).resolve().parent.parent / 'src' / 'ryoku-proxy-helper')
loader = importlib.machinery.SourceFileLoader('transaction_helper', path)
spec = importlib.util.spec_from_loader('transaction_helper', loader)
helper = importlib.util.module_from_spec(spec)
loader.exec_module(helper)

CONF = {
 'dns': {'servers': [{'type':'udp', 'tag':'bootstrap-dns', 'server':'1.1.1.1'}]},
 'inbounds': [{'type':'tun', 'tag':'tun-in'}],
 'outbounds':[{'type':'http', 'tag':'proxy', 'server':'old.example', 'server_port':9999,
               'domain_resolver':'bootstrap-dns'}],
 'route': {'default_domain_resolver':'bootstrap-dns', 'rules':[
          {'port':53,'action':'hijack-dns'}, {'network':'udp','action':'reject'}], 'final':'proxy'}
}
P1 = {'protocol':'socks5','host':'new.example','port':1080,'username':'a', 'password':'b',
      'tls': False, 'udp': True}
P2 = {'protocol':'http','host':'new.example','port':8080,'username':'a', 'password':'b',
      'tls': False, 'udp': False}


class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / 'config.json'
        self.config.write_text(json.dumps(CONF))
        self.patch_path = patch.object(helper, 'CONFIG', self.config)
        self.patch_path.start()
        self.patch_cmd = patch.object(helper, 'cmd', return_value=MagicMock(returncode=0))
        self.patch_cmd.start()
        self.patch_restart = patch.object(helper, 'restart')
        self.patch_restart.start()

    def tearDown(self):
        self.patch_restart.stop()
        self.patch_cmd.stop()
        self.patch_path.stop()
        self.tmp.cleanup()

    def test_success_persists_new_server(self):
        with patch.object(helper, 'ip_test', return_value='203.0.113.2'):
            result = helper.apply([P2])
        self.assertEqual(result['protocol'], 'http')
        self.assertEqual(json.loads(self.config.read_text())['outbounds'][0]['server'], 'new.example')

    def test_failed_validation_reverts_to_original(self):
        with patch.object(helper, 'ip_test', side_effect=RuntimeError('No connection')):
            with self.assertRaisesRegex(RuntimeError, 'восстановлена'):
                helper.apply([P2])
        self.assertEqual(json.loads(self.config.read_text()), CONF)

    def test_auto_fallback(self):
        with patch.object(helper, 'ip_test', side_effect=[RuntimeError('No SOCKS'), '203.0.113.2']):
            result = helper.apply([P1, P2])
        self.assertEqual(result['protocol'], 'http')
        current = json.loads(self.config.read_text())
        self.assertEqual(current['outbounds'][0]['type'], 'http')
        self.assertTrue(any(helper.udp_rule(v) for v in current['route']['rules']))


if __name__ == '__main__':
    unittest.main()

class FirewallTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.config = Path(self.tmp.name) / 'config.json'
        self.config.write_text(json.dumps(CONF))
        self.paths = patch.object(helper, 'CONFIG', self.config)
        self.paths.start()
        self.command = patch.object(helper, 'cmd', return_value=MagicMock(returncode=0))
        self.command.start()
        self.restart_patch = patch.object(helper, 'restart')
        self.restart_patch.start()

    def tearDown(self):
        self.restart_patch.stop()
        self.command.stop()
        self.paths.stop()
        self.tmp.cleanup()

    def test_success_restricts_after_connect(self):
        with patch.object(helper.firewall, 'extend_for_candidates', return_value={'version': 1}):
            with patch.object(helper.firewall, 'set_active') as lock:
                with patch.object(helper.firewall, 'restore') as restore:
                    with patch.object(helper, 'ip_test', return_value='203.0.113.10'):
                        result = helper.apply([P2])
        self.assertEqual(result['ip'], '203.0.113.10')
        lock.assert_called_once()
        restore.assert_not_called()

    def test_failure_restores_firewall(self):
        with patch.object(helper.firewall, 'extend_for_candidates', return_value={'version': 1}):
            with patch.object(helper.firewall, 'restore') as restore:
                with patch.object(helper, 'ip_test', side_effect=RuntimeError('failed route')):
                    with self.assertRaises(RuntimeError):
                        helper.apply([P2])
        restore.assert_called_once_with({'version': 1})
