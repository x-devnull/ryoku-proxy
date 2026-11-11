"""UTC-based key rotation never uses the skewed wall clock or removes old keys."""
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('github_utc', ROOT/'tools/github_utc.py')
utc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(utc)
RESPONSE = 'HTTP/2.0 200 OK\r\nDate: Wed, 11 Nov 2026 01:10:00 GMT\r\n\r\n{"login":"x-devnull"}\n'
EPOCH = int(datetime(2026,11,11,1,10,tzinfo=timezone.utc).timestamp())

class GitHubUtcTests(unittest.TestCase):
    def test_https_date_is_used(self):
        self.assertEqual(utc.parse_date(RESPONSE), EPOCH)

    def test_bad_or_missing_date_is_rejected(self):
        for value in ('HTTP/\n\n', RESPONSE.replace('200 OK','401 Unauthorized'),
                      RESPONSE.replace('Date:', 'Other:'),
                      RESPONSE.replace('Wed, 11 Nov 2026 01:10:00 GMT', 'invalid')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                utc.parse_date(value)

    def test_network_failure_does_not_use_local_clock(self):
        with patch.object(utc.subprocess,'run',return_value=subprocess.CompletedProcess([],1,stdout='',stderr='reset')):
            with self.assertRaisesRegex(RuntimeError,'no local-clock fallback'):
                utc.github_epoch()

    def test_request_is_fresh_and_bounded(self):
        with patch.object(utc.subprocess,'run',return_value=subprocess.CompletedProcess([],0,stdout=RESPONSE)) as run:
            self.assertEqual(utc.github_epoch(), EPOCH)
            self.assertIn('Cache-Control: no-cache',run.call_args.args[0])
            self.assertTrue(any(value.startswith('user?clock_probe=') for value in run.call_args.args[0]))
            self.assertEqual(run.call_args.kwargs['timeout'],30)

    def test_rotation_preserves_old_key_and_passes_server_time_to_gpg(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp); bin_dir=tmp/'bin';bin_dir.mkdir()
            old=tmp/'data/ryoku-proxy-signing';old.mkdir(parents=True)
            (old/'keep').write_text('old key stays here')
            gh=bin_dir/'gh'
            gh.write_text('''#!/bin/sh
if [ "$1" = api ]; then
  case " $* " in
    *" --include "*) printf 'HTTP/2.0 200 OK\\nDate: Wed, 11 Nov 2026 01:10:00 GMT\\n\\n{}\\n' ;;
    *) echo x-devnull ;;
  esac
elif [ "$1" = secret ] && [ "$2" = set ]; then
  cat >/dev/null
elif [ "$1" = secret ] && [ "$2" = list ]; then
  :
fi
''')
            gh.chmod(0o755)
            gpg=bin_dir/'gpg'
            gpg.write_text('''#!/bin/sh
printf '%s\\n' "$*" >> "$GPG_ARGS"
case " $* " in
  *" --list-secret-keys "*) echo 'fpr:::::::::AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA:' ;;
  *" --export-secret-keys "*) cat >/dev/null; echo 'PRIVATE-TEST-FIXTURE' ;;
  *" --quick-generate-key "*) cat >/dev/null ;;
  *" --export "*) echo 'PUBLIC-TEST-FIXTURE' ;;
esac
''')
            gpg.chmod(0o755)
            env=dict(os.environ, PATH=str(bin_dir)+':'+os.environ['PATH'],
                     XDG_DATA_HOME=str(tmp/'data'),GPG_ARGS=str(tmp/'args'))
            result=subprocess.run(['bash',str(ROOT/'tools/setup-repository.sh'),'--rotate-github-time'],
                                  env=env,input='\n\n',text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual((old/'keep').read_text(),'old key stays here')
            calls=(tmp/'args').read_text().splitlines()
            self.assertTrue(calls)
            self.assertTrue(all(f'--faked-system-time {EPOCH-60}' in call for call in calls))
            self.assertEqual(len(list((tmp/'data').glob('ryoku-proxy-signing-rotated.*'))),1)
            self.assertNotIn('PRIVATE-TEST-FIXTURE',result.stdout+result.stderr)

if __name__ == '__main__': unittest.main()
