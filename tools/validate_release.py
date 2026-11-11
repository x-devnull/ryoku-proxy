#!/usr/bin/env python3
"""Validate release identifiers, sensitive-file exclusion and local site assets."""
from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(__file__).resolve().parents[1]

class Landing(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        if 'id' in attributes:
            if attributes['id'] in self.ids:
                raise ValueError('Duplicate HTML id: ' + attributes['id'])
            self.ids.add(attributes['id'])
        for key in ('href', 'src'):
            if key in attributes:
                self.links.append(attributes[key])

def main():
    app = (ROOT / 'src/ryoku_proxy.py').read_text()
    assert "app.setApplicationVersion('1.0.0')" in app
    assert 'ED 1.0' in app and 'ED. 004' not in app
    assert 'pkgver=1.0.0' in (ROOT / 'packaging/PKGBUILD').read_text()
    metadata = ElementTree.parse(ROOT / 'packaging/ryoku-proxy.metainfo.xml')
    assert metadata.find('releases/release').get('version') == '1.0.0'
    import re
    english = (ROOT / 'README.md').read_text()
    russian = (ROOT / 'README.ru.md').read_text()
    for page in ('overview', 'security'):
        assert f'docs/previews/{page}-en.png' in english
        assert f'docs/previews/{page}-ru.png' in russian
    assert '-ru.png' not in english
    assert not (ROOT / 'docs/REVIEW.ru.md').exists()
    for path in (ROOT / 'site/index.html', ROOT / 'site/script.js'):
        assert not re.search('[А-Яа-яЁё]', path.read_text()), path
    html = Landing()
    html.feed((ROOT / 'site/index.html').read_text())
    for link in html.links:
        if link.startswith(('https://', 'http://')) or link == '#':
            continue
        if link.startswith('#'):
            assert link[1:] in html.ids, link
        else:
            assert (ROOT / 'site' / link).is_file(), link
    forbidden = {'profiles.json','monitor.json','killswitch.json','authorized-users.json','.env'}
    for folder in ('src','site','packaging','tools','tests','docs','.github'):
        for path in (ROOT / folder).rglob('*'):
            assert not path.is_symlink(), path
            assert path.name not in forbidden, path
    print('Release 1.0.0 / ED 1.0: metadata, landing assets and source inputs verified.')

if __name__ == '__main__':
    main()
