#!/usr/bin/env python3
"""Combine the landing with a signed repository bundle, rejecting unsafe paths."""
import argparse
from pathlib import Path
import shutil
import tarfile

def prepare(site, output, bundle=None):
    output = Path(output)
    if output.exists():
        raise ValueError('Pages output must not exist')
    shutil.copytree(site, output)
    if bundle:
        with tarfile.open(bundle) as tar:
            for item in tar.getmembers():
                path = Path(item.name)
                if (path.is_absolute() or '..' in path.parts or not path.parts or
                        path.parts[0] != 'repo' or not (item.isfile() or item.isdir())):
                    raise ValueError('Unsafe repository archive entry: ' + item.name)
            tar.extractall(output, filter='data')
        repo = output / 'repo'
        for required in ('ryoku-proxy.asc', 'FINGERPRINT', 'arch/any/ryoku-proxy.db',
                         'arch/any/ryoku-proxy.db.sig'):
            if not (repo / required).is_file():
                raise ValueError('Incomplete signed repository: ' + required)
    print(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', default='site')
    parser.add_argument('--output', default='dist/pages')
    parser.add_argument('--bundle')
    args = parser.parse_args()
    prepare(args.site, args.output, args.bundle)
