import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

root=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(root/'src'))
loader=importlib.machinery.SourceFileLoader('ryoku_recovery_helper',str(root/'src'/'ryoku-proxy-helper'))
spec=importlib.util.spec_from_loader('ryoku_recovery_helper',loader)
helper=importlib.util.module_from_spec(spec)
loader.exec_module(helper)

class RecoveryTests(unittest.TestCase):
    def test_expired_trial_removes_only_ryoku_state(self):
        with tempfile.TemporaryDirectory() as d:
            trial=Path(d)/'trial';state=Path(d)/'state'
            trial.write_text('pending\n');state.write_text('state')
            with patch.object(helper.firewall,'TRIAL_PATH',trial), \
                 patch.object(helper.firewall,'STATE_PATH',state), \
                 patch.object(helper.firewall,'remove_rules') as remove, \
                 patch.object(helper.firewall,'present',return_value=False), \
                 patch.object(helper,'cmd',return_value=MagicMock(returncode=0)) as system:
                result=helper.fw_recover()
                self.assertEqual(result,{'enabled':False})
                self.assertFalse(trial.exists());self.assertFalse(state.exists())
                remove.assert_called_once()
                self.assertIn('disable',system.call_args.args)

    def test_confirmation_keeps_policy_and_clears_trial(self):
        with tempfile.TemporaryDirectory() as d:
            trial=Path(d)/'trial';trial.write_text('pending\n')
            with patch.object(helper.firewall,'TRIAL_PATH',trial), \
                 patch.object(helper.firewall,'present',return_value=True), \
                 patch.object(helper,'cmd',return_value=MagicMock(returncode=0)):
                result=helper.fw_confirm()
                self.assertEqual(result,{'enabled':True,'trial':False})
                self.assertFalse(trial.exists())

    def test_confirmation_without_trial_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            with patch.object(helper.firewall,'TRIAL_PATH',Path(d)/'absent'):
                with self.assertRaises(RuntimeError): helper.fw_confirm()

if __name__=='__main__':unittest.main()
