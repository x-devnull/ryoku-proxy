import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
from firewall import validate_state, render_rules, build_state

S1={'version':1,'tun':'tun0','endpoints':[{'ip':'203.0.113.2','port':1080}],
    'bootstrap':[{'ip':'1.1.1.1','protocol':'udp','port':53}]}

class FirewallV4Tests(unittest.TestCase):
    def test_migrates_old_state(self):
        state=validate_state(copy.deepcopy(S1))
        self.assertEqual(state['version'],2)
        self.assertEqual(state['exclusions'],[])
        self.assertEqual(state['backups'],[])

    def test_does_not_flush_unrelated_tables(self):
        text=render_rules(S1,exists=True)
        self.assertIn('delete table inet ryoku_proxy',text)
        self.assertNotIn('flush ruleset',text)
        self.assertNotIn('hook forward',text)
        self.assertIn('policy drop',text)

    def test_backup_and_direct(self):
        s=validate_state({**S1,'version':2,'exclusions':['10.10.1.0/24','example.ru','*.ru'],
                          'backups':[{'ip':'203.0.113.3','port':1081}]})
        text=render_rules(s)
        self.assertIn('ip daddr 10.10.1.0/24 accept',text)
        self.assertIn('meta mark 0x52594b accept',text)
        self.assertIn('203.0.113.3 tcp dport 1081 accept',text)
        self.assertIn('203.0.113.2 tcp dport 1080 accept',text)

    def test_no_mark_without_domain_exception(self):
        text=render_rules({**S1,'version':2,'exclusions':['10.10.1.0/24']})
        self.assertNotIn('meta mark',text)

    def test_reject_unbounded_exception(self):
        with self.assertRaises(ValueError):
            validate_state({**S1,'version':2,'exclusions':['0.0.0.0/0']})

if __name__=='__main__':unittest.main()
