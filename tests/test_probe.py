import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
import network_probe


class FakeSocket:
    def __init__(self, content):
        self.content = bytearray(content)
        self.outgoing = bytearray()

    def recv(self, count):
        payload = self.content[:count]
        del self.content[:count]
        return bytes(payload)

    def sendall(self, payload):
        self.outgoing.extend(payload)


class ProtocolProbeTests(unittest.TestCase):
    def test_connect_http_basic(self):
        sock = FakeSocket(b'HTTP/1.1 200 Connection Established\r\n\r\n')
        network_probe._connect_http(sock, {'username':'user', 'password':'pass'})
        self.assertIn(b'CONNECT example.com:443 HTTP/1.1', sock.outgoing)
        self.assertIn(b'Proxy-Authorization: Basic dXNlcjpwYXNz', sock.outgoing)

    def test_connect_http_invalid_credentials(self):
        sock = FakeSocket(b'HTTP/1.1 407 Proxy Authentication Required\r\n\r\n')
        with self.assertRaisesRegex(RuntimeError, '407'):
            network_probe._connect_http(sock, {'username':'user', 'password':'bad'})

    def test_socks5_auth(self):
        # SOCKS5 method, user auth success, CONNECT success (IPv4 + port)
        sock = FakeSocket(b'\x05\x02' + b'\x01\x00' + b'\x05\x00\x00\x01\x7f\x00\x00\x01\x01\xbb')
        network_probe._connect_socks5(sock, {'username':'user', 'password':'pass'})
        self.assertIn(b'\x01\x04user\x04pass', sock.outgoing)
        self.assertIn(b'\x05\x01\x00\x03\x0bexample.com\x01\xbb', sock.outgoing)

    def test_unoffered_auth_is_rejected(self):
        with self.assertRaises(RuntimeError):
            network_probe._connect_socks5(FakeSocket(b'\x05\x02'), {'username':'', 'password':''})

    def test_socks5_bad_auth(self):
        sock = FakeSocket(b'\x05\x02\x01\x01')
        with self.assertRaisesRegex(RuntimeError, 'авторизации'):
            network_probe._connect_socks5(sock, {'username':'user', 'password':'bad'})

    def test_curl_config_quote(self):
        value = network_probe._curl_config_value('x"\\y')
        self.assertEqual(value, '"x\\"\\\\y"')
        with self.assertRaises(ValueError):
            network_probe._curl_config_value('user\nfoo')

    @patch('network_probe.subprocess.run')
    def test_https_proxy_auth_not_in_argv(self, mock_run):
        mock_run.return_value.returncode = 0
        t = {'host':'proxy.example', 'port': 8443, 'username':'username',
             'password':'Secur3!', 'protocol':'http', 'tls': True}
        network_probe._probe_https_http(t, 6)
        args, kwargs = mock_run.call_args
        self.assertEqual(args[0][:2], ['/usr/bin/curl', '--disable'])
        self.assertNotIn('Secur3!', ' '.join(args[0]))
        self.assertIn('proxy-user = "username:Secur3!"', kwargs['input'])


if __name__ == '__main__':
    unittest.main()
