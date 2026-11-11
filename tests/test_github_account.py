"""Account checks distinguish transport failures from a verified wrong user."""
import os
import shlex
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class GitHubAccountTests(unittest.TestCase):
    def run_check(self, responses, setup=False):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            fake = tmp/'gh'
            cases = []
            for index, (code, text) in enumerate(responses, 1):
                cases.append(f'{index}) printf "%s\\n" {shlex.quote(text)}; exit {code} ;;')
            fake.write_text('#!/bin/sh\nn=0\n[ ! -f "$COUNT_FILE" ] || n=$(cat "$COUNT_FILE")\nn=$((n+1))\nprintf "%s" "$n" > "$COUNT_FILE"\ncase "$n" in\n' + '\n'.join(cases) + '\n*) exit 99 ;;\nesac\n')
            fake.chmod(0o755)
            for name in ('gpg', 'sleep'):
                executable=tmp/name
                executable.write_text('#!/bin/sh\n' + ('touch "$GPG_CALLED"\nexit 88\n' if name=='gpg' else 'exit 0\n'))
                executable.chmod(0o755)
            env=dict(os.environ, PATH=str(tmp)+':'+os.environ['PATH'],
                     COUNT_FILE=str(tmp/'count'), GPG_CALLED=str(tmp/'gpg-called'),
                     XDG_DATA_HOME=str(tmp/'data'))
            command = ['bash', str(ROOT/'tools/setup-repository.sh')] if setup else [
                'bash','-c','source "$1"; github_require_account x-devnull','check',str(ROOT/'tools/github-account.sh')]
            result=subprocess.run(command,env=env,capture_output=True,text=True)
            return result, int((tmp/'count').read_text()), (tmp/'data/ryoku-proxy-signing').exists(), (tmp/'gpg-called').exists()

    def test_reset_does_not_claim_wrong_account_or_create_key(self):
        result,count,key,gpg=self.run_check([(1,'connection reset by peer')]*3,setup=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(count,3)
        self.assertIn('Could not verify',result.stderr)
        self.assertNotIn('authenticated as',result.stderr)
        self.assertFalse(key)
        self.assertFalse(gpg)

    def test_retry_recovers(self):
        result,count,_,_=self.run_check([(1,'connection reset by peer'),(0,'x-devnull')])
        self.assertEqual(result.returncode,0)
        self.assertEqual(count,2)

    def test_verified_other_account(self):
        result,count,_,_=self.run_check([(0,'someone-else')])
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(count,1)
        self.assertIn('authenticated as someone-else',result.stderr)

    def test_auth_failure_is_not_retried(self):
        result,count,_,_=self.run_check([(1,'Bad credentials (HTTP 401)')])
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(count,1)
        self.assertIn('HTTP 401',result.stderr)
