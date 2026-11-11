#!/usr/bin/env python3
"""Build a root-owned, architecture-independent Debian archive without root."""
import argparse
import gzip
import io
from pathlib import Path
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.0.0-2'

def archive(files):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w', format=tarfile.GNU_FORMAT) as tar:
        for name, content, mode in sorted(files):
            info = tarfile.TarInfo('./' + name)
            info.mode, info.size = mode, len(content)
            info.uid = info.gid = info.mtime = 0
            info.uname = info.gname = 'root'
            tar.addfile(info, io.BytesIO(content))
    return gzip.compress(buffer.getvalue(), mtime=0)

def build(output):
    files = []
    def add(source, target, mode=0o644):
        files.append((target, (ROOT / source).read_bytes(), mode))
    for module in ('profile_store', 'network_probe', 'monitoring', 'routing', 'i18n', 'ryoku_proxy'):
        add(f'src/{module}.py', f'usr/share/ryoku-proxy/{module}.py')
    for name in ('firewall.py', 'routing.py', 'ryoku-proxy-helper'):
        add('src/' + name, 'usr/lib/ryoku-proxy/' + name, 0o755 if name.endswith('helper') else 0o644)
    add('src/ryoku-proxy-access', 'usr/bin/ryoku-proxy-access', 0o755)
    add('packaging/check-removal', 'usr/lib/ryoku-proxy/check-removal', 0o755)
    add('packaging/ryoku-proxy', 'usr/bin/ryoku-proxy', 0o755)
    for source, target in (
        ('ryoku-proxy.desktop', 'applications/ryoku-proxy.desktop'),
        ('ryoku-proxy.svg', 'pixmaps/ryoku-proxy.svg'),
        ('ryoku-proxy.metainfo.xml', 'metainfo/ryoku-proxy.metainfo.xml'),
        ('polkit/org.ryoku.proxy.policy', 'polkit-1/actions/org.ryoku.proxy.policy')):
        add('packaging/' + source, 'usr/share/' + target)
    add('packaging/systemd/ryoku-proxy-killswitch.service', 'usr/lib/systemd/system/ryoku-proxy-killswitch.service')
    add('LICENSE', 'usr/share/doc/ryoku-proxy/copyright')
    add('README.md', 'usr/share/doc/ryoku-proxy/README.md')
    control = f'''Package: ryoku-proxy
Version: {VERSION}
Section: net
Priority: optional
Architecture: all
Maintainer: x_devnull <x-devnull@users.noreply.github.com>
Homepage: https://github.com/x-devnull/ryoku-proxy
Depends: python3 (>= 3.10), python3-pyside6.qtwidgets, qt6-wayland, libqt6svg6, sing-box (>= 1.14), nftables, iproute2, pkexec, polkitd, curl, systemd, libsecret-tools
Installed-Size: {(sum(len(data) for _, data, _ in files) + 1023) // 1024}
Description: Qt6 sing-box routing, monitoring and Kill Switch dashboard
 Native desktop interface for an existing sing-box TUN configuration.
 Includes a restricted polkit helper and recoverable nftables protection.
'''
    scripts = [('control', control.encode(), 0o644)]
    for name in ('postinst', 'prerm', 'postrm'):
        scripts.append((name, (ROOT / 'packaging/debian' / name).read_bytes(), 0o755))
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ryoku-deb-') as tmp:
        stage = Path(tmp)
        (stage / 'debian-binary').write_bytes(b'2.0\n')
        (stage / 'control.tar.gz').write_bytes(archive(scripts))
        (stage / 'data.tar.gz').write_bytes(archive(files))
        output.unlink(missing_ok=True)
        subprocess.run(['ar', 'crD', str(output), 'debian-binary', 'control.tar.gz', 'data.tar.gz'], cwd=stage, check=True)
    print(output)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', default=str(ROOT / f'dist/ryoku-proxy_{VERSION}_all.deb'))
    build(parser.parse_args().output)
