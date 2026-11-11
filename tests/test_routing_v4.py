import copy
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
from routing import (normalize_rule, validated_rules, by_type, domain_to_regex,
                     build_bypass_rules, update_config, detect_local_networks, ROUTING_MARK)

BASE = {
  'dns': {'servers': [{'type': 'udp','tag':'bootstrap-dns','server':'1.1.1.1'}]},
  'inbounds': [{'type':'tun','interface_name':'tun0','auto_redirect':True}],
  'outbounds': [{'type':'http','tag':'proxy','server':'proxy.example.org','server_port':8080},
                {'type':'direct','tag':'direct'}],
  'route': {'final':'proxy','rules':[{'port':53,'action':'hijack-dns'},
                                    {'network':'udp','action':'reject'}]}
}

class RoutingV4Tests(unittest.TestCase):
    def test_domain_patterns(self):
        self.assertEqual(normalize_rule('*.ru'),'*.ru')
        self.assertEqual(normalize_rule('*.example.ru'),'*.example.ru')
        self.assertEqual(normalize_rule('EXAMPLE.RU'),'example.ru')
        self.assertEqual(normalize_rule('https://пример.рф/path?a=1'),'xn--e1afmkfd.xn--p1ai')
        self.assertEqual(normalize_rule('https://192.168.1.2/path'),'192.168.1.2/32')

    def test_domain_patterns_regex_semantics(self):
        import re
        regex=domain_to_regex('example.ru')
        for name in ['x.example.ru','a.b.example.ru']:
            self.assertRegex(name,regex)
        for name in ['example.ru','fakeexample.ru','x.example.com']:
            self.assertNotRegex(name,regex)
        self.assertRegex('example.ru',domain_to_regex('ru'))
        self.assertRegex('a.b.ru',domain_to_regex('ru'))

    def test_cidr_and_dedupe(self):
        self.assertEqual(validated_rules(['10.10.1.5/24', '10.10.1.0/24','*.ru']),
                         ['10.10.1.0/24','*.ru'])
        self.assertEqual(by_type(['*.ru','example.ru','10.0.0.1/32']),
                         (['10.0.0.1/32'],['example.ru'],['ru']))

    def test_reject_invalid(self):
        for entry in ['0.0.0.0/0', '::/0', 'http://user:secret@example.ru',
                      '*.ru; delete table inet filter', '*.ru\nhttp://evil.test',
                      '', 'example', 'https://host.ru:8080/path']:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                normalize_rule(entry)

    def test_maximum(self):
        with self.assertRaises(ValueError):
            validated_rules(['x%d.ru'%i for i in range(129)])

    def test_update_preserves_existing(self):
        old=copy.deepcopy(BASE)
        out=update_config(BASE,['*.ru','example.org','10.10.1.0/24'])
        self.assertEqual(BASE,old)
        self.assertEqual(out['outbounds'][-1]['routing_mark'],ROUTING_MARK)
        rules=out['route']['rules']
        self.assertEqual(rules[0]['action'],'hijack-dns')
        self.assertEqual(rules[1]['action'],'sniff')
        self.assertEqual(rules[2]['outbound'],'ryoku-direct')
        self.assertEqual(rules[-1]['action'],'reject')
        again=update_config(out,['example.org'])
        self.assertEqual(len([x for x in again['outbounds'] if x['tag']=='ryoku-direct']),1)
        self.assertEqual(len([x for x in again['route']['rules'] if x.get('action')=='sniff']),1)
        clear=update_config(again,[])
        self.assertFalse(any(x['tag']=='ryoku-direct' for x in clear['outbounds']))
        self.assertFalse(any(x.get('outbound')=='ryoku-direct' for x in clear['route']['rules']))
        self.assertFalse(any(x.get('action')=='sniff' for x in clear['route']['rules']))

    def test_existing_unrelated_sniff_unchanged(self):
        base=copy.deepcopy(BASE)
        base['route']['rules'].insert(1,{'action':'sniff','sniffer':['http','tls'],'timeout':'300ms'})
        out=update_config(base,[])
        self.assertIn({'action':'sniff','sniffer':['http','tls'],'timeout':'300ms'},out['route']['rules'])

    def test_no_auto_redirect_rejected(self):
        base=copy.deepcopy(BASE)
        base['inbounds'][0].pop('auto_redirect')
        with self.assertRaises(ValueError):
            update_config(base,['*.ru'])

    def test_local_interfaces(self):
        fake=[{'ifname':'lo','addr_info':[{'local':'127.0.0.1','prefixlen':8}]},
              {'ifname':'wlan0','addr_info':[{'local':'10.10.1.55','prefixlen':24},
                                            {'local':'fd23:abcd::1','prefixlen':64}]},
              {'ifname':'tun0','addr_info':[{'local':'172.19.0.1','prefixlen':30}]},
              {'ifname':'wlan1','addr_info':[{'local':'8.8.8.8','prefixlen':24}]}]
        self.assertEqual(detect_local_networks(fake),['10.10.1.0/24','fd23:abcd::/64'])

if __name__ == '__main__': unittest.main()
