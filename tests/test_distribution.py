"""Distribution checks: Debian payload, removal lifecycle, signed Pages bundle."""
import importlib.util
import io
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

class DistributionTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ar'), 'ar is required')
    def test_debian_payload_and_removal_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / 'app.deb'
            module('build_deb').build(output)
            def members(part):
                data = subprocess.check_output(['ar', 'p', str(output), part])
                return tarfile.open(fileobj=io.BytesIO(data), mode='r:gz')
            with members('control.tar.gz') as tar:
                control = tar.extractfile('./control').read().decode()
                self.assertIn('Architecture: all', control)
                self.assertIn('sing-box (>= 1.14)', control)
                script = tar.extractfile('./prerm').read().decode()
                guard = Path(tmp) / 'guard'
                guard.write_text('#!/bin/sh\nexit 7\n')
                guard.chmod(0o755)
                script = script.replace('/usr/lib/ryoku-proxy/check-removal', str(guard))
                self.assertEqual(subprocess.run(['sh', '-c', script, 'prerm', 'remove']).returncode, 7)
                self.assertEqual(subprocess.run(['sh', '-c', script, 'prerm', 'upgrade']).returncode, 0)
            with members('data.tar.gz') as tar:
                helper = tar.getmember('./usr/lib/ryoku-proxy/ryoku-proxy-helper')
                self.assertEqual((helper.uid, helper.gid, helper.mode), (0, 0, 0o755))
                self.assertIsNotNone(tar.getmember('./usr/share/applications/ryoku-proxy.desktop'))

    def test_pages_rejects_archive_traversal(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            bundle = tmp / 'bad.tar.gz'
            with tarfile.open(bundle, 'w:gz') as tar:
                info = tarfile.TarInfo('repo/../../outside')
                info.size = 1
                tar.addfile(info, io.BytesIO(b'x'))
            with self.assertRaises(ValueError):
                module('prepare_pages').prepare(ROOT/'site', tmp/'pages', bundle)
            self.assertFalse((tmp/'outside').exists())

    def test_landing_only_before_first_repository(self):
        with tempfile.TemporaryDirectory() as tmp:
            module('prepare_pages').prepare(ROOT/'site', Path(tmp)/'pages')
            self.assertTrue((Path(tmp)/'pages/index.html').is_file())

    @unittest.skipUnless(shutil.which('repo-add'), 'repo-add is required')
    def test_database_embedding_without_gpg_agent(self):
        # Metadata-only fixture: a synthetic signature checks embedding, not crypto.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            package = tmp / 'ryoku-proxy-1.0.0-1-any.pkg.tar.gz'
            content = b'pkgname = ryoku-proxy\npkgver = 1.0.0-1\npkgdesc = Metadata fixture\narch = any\nsize = 1\n'
            with tarfile.open(package, 'w:gz') as tar:
                info = tarfile.TarInfo('.PKGINFO'); info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
            signature = Path(str(package) + '.sig')
            signature.write_bytes(b'metadata-only-test-signature')
            database = tmp / 'test.db.tar.gz'
            subprocess.run(['repo-add', '--include-sigs', str(database), str(package)],
                           check=True, capture_output=True)
            builder = module('build_repository')
            builder.verify_embedded_signatures(database, [str(package)])
            signature.write_bytes(b'different-signature')
            with self.assertRaisesRegex(ValueError, 'mismatched'):
                builder.verify_embedded_signatures(database, [str(package)])
            # Exercise the production builder with only GPG stubbed, so removing
            # --include-sigs from its real repo-add call is detected locally too.
            def command(*args, **kwargs):
                if args[0] != 'gpg':
                    return subprocess.run(args, check=True, **kwargs)
                if '--detach-sign' in args:
                    Path(args[args.index('--output') + 1]).write_bytes(b'metadata-signature')
                return subprocess.CompletedProcess(args, 0, stdout=b'public-key-fixture')
            # The builder only accepts .zst packages; repo-add detects gzip content.
            renamed = package.with_name('ryoku-proxy-1.0.0-1-any.pkg.tar.zst')
            package.rename(renamed)
            with patch.object(builder, 'run', side_effect=command):
                builder.build([str(renamed)], tmp / 'output', 'A' * 40)
            builder.verify_embedded_signatures(tmp / 'output/repo/arch/any/ryoku-proxy.db',
                [str(tmp / 'output/repo/arch/any' / renamed.name)])

    @unittest.skipUnless(all(shutil.which(t) for t in ('gpg', 'repo-add', 'zstd')), 'Arch signing tools are required')
    def test_signed_repository_and_pages_preservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            home = tmp/'gnupg'; home.mkdir(mode=0o700)
            env = dict(os.environ, GNUPGHOME=str(home))
            generated = subprocess.run(['gpg','--batch','--pinentry-mode','loopback','--passphrase','',
                            '--quick-generate-key','Distribution test <test@example.invalid>',
                            'ed25519','sign','1d'], env=env, capture_output=True)
            if generated.returncode:
                if b'No agent running' in generated.stderr and not os.environ.get('RYOKU_REQUIRE_SIGNING_TEST'):
                    self.skipTest('This environment cannot start gpg-agent; signing is required in Arch CI')
                self.fail(generated.stderr.decode())
            keys = subprocess.check_output(['gpg','--with-colons','--list-secret-keys'],env=env,text=True)
            fingerprint = next(line.split(':')[9] for line in keys.splitlines() if line.startswith('fpr:'))
            plain = tmp/'package.tar'
            content=b'pkgname = ryoku-proxy\npkgver = 1.0.0-1\npkgdesc = Test package\narch = any\nsize = 1\n'
            with tarfile.open(plain,'w') as tar:
                info=tarfile.TarInfo('.PKGINFO'); info.size=len(content)
                tar.addfile(info,io.BytesIO(content))
            package=tmp/'ryoku-proxy-1.0.0-1-any.pkg.tar.zst'
            subprocess.run(['zstd','-q',str(plain),'-o',str(package)],check=True)
            subprocess.run(['python3',str(ROOT/'tools/build_repository.py'),'--fingerprint',fingerprint,
                            '--output',str(tmp/'signed'),str(package)],env=env,check=True,capture_output=True)
            bundle=tmp/'signed/pacman-repository.tar.gz'
            module('prepare_pages').prepare(ROOT/'site',tmp/'pages',bundle)
            repo=tmp/'pages/repo/arch/any'
            self.assertFalse(any(p.is_symlink() for p in (tmp/'pages').rglob('*')))
            subprocess.run(['gpg','--verify',str(repo/'ryoku-proxy.db.sig'),str(repo/'ryoku-proxy.db')],
                           env=env,check=True,capture_output=True)
            self.assertTrue((repo/package.name).is_file())
            with tarfile.open(repo/'ryoku-proxy.db') as tar:
                self.assertIn('%PGPSIG%',tar.extractfile(next(m for m in tar.getmembers() if m.name.endswith('/desc'))).read().decode())
            subprocess.run(['gpgconf','--kill','all'],env=env,check=False)

if __name__ == '__main__':
    unittest.main()
