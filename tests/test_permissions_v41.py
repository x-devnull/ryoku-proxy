"""Root-free tests for narrowly scoped polkit authorization management."""
import importlib.machinery
import importlib.util
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader('ryoku_permission_manager', str(ROOT/'src'/'ryoku-proxy-access'))
spec = importlib.util.spec_from_loader('ryoku_permission_manager', loader)
manager = importlib.util.module_from_spec(spec)
loader.exec_module(manager)


class PermissionManagerTests(unittest.TestCase):
    def setUp(self):
        self.ctx = tempfile.TemporaryDirectory()
        self.addCleanup(self.ctx.cleanup)
        d = Path(self.ctx.name)
        self.helper_dir = d / 'usr' / 'lib' / 'ryoku-proxy'
        self.helper_dir.mkdir(parents=True)
        self.helper_file = self.helper_dir / 'ryoku-proxy-helper'
        self.helper_file.write_text('#!/usr/bin/python3 -I\n')
        self.helper_file.chmod(0o755)
        self.state_dir = d / 'etc' / 'ryoku-proxy'
        self.state_file = self.state_dir / 'authorized-users.json'
        self.rule_file = d / 'etc' / 'polkit-1' / 'rules.d' / '20-ryoku-proxy-local.rules'
        for attr, value in [('HELPER_DIR', self.helper_dir), ('HELPER_FILE', self.helper_file),
                            ('STATE_DIR', self.state_dir), ('STATE_FILE', self.state_file),
                            ('RULE_FILE', self.rule_file)]:
            p = patch.object(manager, attr, value)
            p.start()
            self.addCleanup(p.stop)
        user = patch.object(manager.pwd, 'getpwnam',
                            side_effect=lambda name: SimpleNamespace(pw_uid=1000) if name in ('tester','other') else (_ for _ in ()).throw(KeyError()))
        user.start()
        self.addCleanup(user.stop)
        # Simulate root ownership only inside the temporary fixture. Keep real
        # mode bits so writable-helper rejection remains covered.
        real_stat = Path.stat
        def fixture_stat(path, *args, **kwargs):
            info = real_stat(path, *args, **kwargs)
            if path.is_relative_to(d):
                values = list(info)
                values[4] = 0
                return os.stat_result(values)
            return info
        owned = patch.object(Path, 'stat', fixture_stat)
        owned.start()
        self.addCleanup(owned.stop)
        chown = patch.object(manager.os, 'fchown')
        chown.start()
        self.addCleanup(chown.stop)

    def test_policy_binds_only_the_helper(self):
        root = ElementTree.parse(ROOT/'packaging'/'polkit'/'org.ryoku.proxy.policy').getroot()
        actions = root.findall('.//action')
        self.assertEqual([a.attrib['id'] for a in actions], ['org.ryoku.proxy.manage'])
        self.assertEqual(actions[0].findtext(".//annotate[@key='org.freedesktop.policykit.exec.path']"),
                         '/usr/lib/ryoku-proxy/ryoku-proxy-helper')
        self.assertEqual(actions[0].findtext('defaults/allow_any'), 'no')

    def test_grant_and_revoke_two_users(self):
        manager.check_installation()
        manager.save_users(['tester'])
        self.assertEqual(manager.load_users(), ['tester'])
        self.assertEqual(json.loads(self.state_file.read_text())['users'], ['tester'])
        rule = self.rule_file.read_text()
        self.assertIn('org.ryoku.proxy.manage', rule)
        self.assertIn('subject.local', rule)
        self.assertIn('subject.active', rule)
        self.assertIn('"tester"', rule)
        self.assertNotIn('org.freedesktop.policykit.exec"', rule)
        manager.save_users(['other', 'tester', 'other'])
        self.assertEqual(manager.load_users(), ['other', 'tester'])
        manager.save_users([])
        self.assertFalse(self.rule_file.exists())
        self.assertEqual(manager.load_users(), [])

    def test_file_modes(self):
        manager.save_users(['tester'])
        self.assertEqual(stat.S_IMODE(self.state_file.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.rule_file.stat().st_mode), 0o644)
        self.assertEqual(stat.S_IMODE(self.state_dir.stat().st_mode), 0o700)

    def test_user_restrictions(self):
        self.assertEqual(manager.check_user('tester'), 'tester')
        for user in ('root', 'tester\nfoo', 'some.user', 'other/evil', '$(command)', 'bad name'):
            with self.assertRaises(ValueError):
                manager.check_user(user)

    def test_symlink_state_is_rejected(self):
        self.state_dir.mkdir(parents=True)
        target = self.state_dir / 'elsewhere'
        target.write_text('untouched')
        self.state_file.symlink_to(target)
        with self.assertRaises(RuntimeError):
            manager.save_users(['tester'])
        self.assertEqual(target.read_text(), 'untouched')

    def test_helper_cannot_be_writable_by_other_users(self):
        self.helper_file.chmod(0o777)
        with self.assertRaises(RuntimeError):
            manager.check_installation()

    def test_no_passwordless_permission_for_other_actions(self):
        rule = manager.render_rule(['tester'])
        self.assertIn('if (action.id !== "org.ryoku.proxy.manage") return;', rule)
        self.assertIn('if (!subject.local || !subject.active) return;', rule)
        self.assertIn('return polkit.Result.YES;', rule)
        self.assertNotIn('org.freedesktop.policykit.exec"', rule)


if __name__ == '__main__':
    unittest.main()
