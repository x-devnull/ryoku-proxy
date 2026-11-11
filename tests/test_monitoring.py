import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
import monitoring

class MonitoringTests(unittest.TestCase):
    def test_parse_active_connections(self):
        sample = {'uploadTotal': 2048, 'downloadTotal': 4096, 'memory': 1024,
                  'connections': [{'upload': 20, 'download': 400, 'chains': ['proxy'],
                                   'metadata': {'host': 'example.com', 'destinationPort': '443',
                                                'process': 'firefox', 'network': 'tcp'}}]}
        result = monitoring.summarize_connections(sample)
        self.assertEqual(result['active'], 1)
        self.assertEqual(result['connections'][0]['destination'], 'example.com:443')
        self.assertEqual(result['connections'][0]['process'], 'firefox')
        self.assertEqual(result['download_total'], 4096)

    def test_reject_bad_input(self):
        with self.assertRaises(ValueError):
            monitoring.summarize_connections([])

    def test_reject_non_list_connections(self):
        with self.assertRaises(ValueError):
            monitoring.summarize_connections({'connections': {'unexpected': 1}})

    def test_pretty(self):
        self.assertEqual(monitoring.pretty_size(1536), '1.5 KiB')

if __name__ == '__main__': unittest.main()
