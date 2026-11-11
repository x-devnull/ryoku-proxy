#!/usr/bin/env python3
"""Create deterministic source archives without credentials or build outputs."""
import argparse
import gzip
import hashlib
import io
from pathlib import Path
import tarfile
ROOT = Path(__file__).resolve().parents[1]

def build(destination):
    paths = [ROOT / name for name in ('.gitignore', 'CHANGELOG.md', 'CONTRIBUTING.md',
             'LICENSE', 'README.md', 'README.ru.md', 'SECURITY.md', 'install.sh', 'install-user.sh', 'uninstall.sh')]
    paths += [p for name in ('src', 'tests', 'packaging', 'docs', 'tools', 'site', '.github')
              for p in (ROOT / name).rglob('*') if p.is_file()
              and '__pycache__' not in p.parts and p.suffix != '.pyc']
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.PAX_FORMAT) as archive:
        for path in sorted(paths):
            if path.is_symlink():
                raise ValueError(f'Release input must not be a symlink: {path}')
            content = path.read_bytes()
            info = tarfile.TarInfo('ryoku-proxy-1.0.0/' + path.relative_to(ROOT).as_posix())
            info.size = len(content)
            info.mode = 0o755 if path.stat().st_mode & 0o111 else 0o644
            info.mtime = 0
            archive.addfile(info, io.BytesIO(content))
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('wb') as output:
        with gzip.GzipFile(filename='', fileobj=output, mode='wb', mtime=0) as compressed:
            compressed.write(buffer.getvalue())
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    destination.with_name(destination.name + '.sha256').write_text(f'{digest}  {destination.name}\n')
    recipe = (ROOT / 'packaging/PKGBUILD').read_text()
    recipe = recipe.replace("source=('ryoku-proxy-1.0.0.tar.gz')", f"source=('{destination.name}')")
    recipe = recipe.replace("sha256sums=('SKIP')", f"sha256sums=('{digest}')")
    (destination.parent / 'PKGBUILD').write_text(recipe)
    (destination.parent / 'ryoku-proxy.install').write_bytes((ROOT / 'packaging/ryoku-proxy.install').read_bytes())
    print(f'{digest}  {destination}')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', default=str(ROOT / 'dist/ryoku-proxy-1.0.0.tar.gz'))
    build(parser.parse_args().output)
