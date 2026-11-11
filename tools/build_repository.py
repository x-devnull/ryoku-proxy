#!/usr/bin/env python3
"""Sign Arch packages and build a Pages-ready pacman repository bundle.

Uses an imported dedicated CI key in GNUPGHOME. No key generation or export
of private material. The passphrase is supplied to gpg through stdin.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)

def build(packages, output, fingerprint):
    if not re.fullmatch(r'[A-Fa-f0-9]{40,64}', fingerprint):
        raise ValueError('A complete signing key fingerprint is required')
    output = Path(output).resolve()
    if output.exists() and any(output.iterdir()):
        raise ValueError('Repository output must be empty')
    repo = output / 'repo'
    arch = repo / 'arch/any'
    arch.mkdir(parents=True)
    def sign(path):
        run('gpg', '--batch', '--yes', '--pinentry-mode', 'loopback',
            '--passphrase-fd', '0', '--local-user', fingerprint,
            '--output', str(path) + '.sig', '--detach-sign', str(path),
            input=os.environ.get('REPO_SIGNING_PASSPHRASE', '').encode())
        run('gpg', '--batch', '--verify', str(path) + '.sig', str(path))
    paths = []
    for source in packages:
        source = Path(source).resolve()
        if not source.name.endswith('.pkg.tar.zst') or source.is_symlink():
            raise ValueError('Expected a regular Arch package')
        dest = arch / source.name
        shutil.copyfile(source, dest)
        sign(dest)
        paths.append(str(dest))
    if not paths:
        raise ValueError('At least one package is required')
    run('repo-add', str(arch / 'ryoku-proxy.db.tar.gz'), *paths)
    for kind in ('db', 'files'):
        path = arch / f'ryoku-proxy.{kind}.tar.gz'
        sign(path)
        # Pages artifacts must not contain the symlinks produced by repo-add.
        alias = arch / f'ryoku-proxy.{kind}'
        alias.unlink(missing_ok=True)
        shutil.copyfile(path, alias)
        shutil.copyfile(str(path) + '.sig', str(alias) + '.sig')
    public = run('gpg', '--batch', '--armor', '--export', fingerprint, capture_output=True).stdout
    if not public:
        raise ValueError('Public signing key is missing')
    (repo / 'ryoku-proxy.asc').write_bytes(public)
    (repo / 'FINGERPRINT').write_text(fingerprint.upper() + '\n')
    bundle = output / 'pacman-repository.tar.gz'
    with tarfile.open(bundle, 'w:gz') as tar:
        tar.add(repo, arcname='repo')
    print(bundle)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fingerprint', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('packages', nargs='+')
    args = parser.parse_args()
    build(args.packages, args.output, args.fingerprint)
