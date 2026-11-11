import ast
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'src'))
import i18n

class I18nV4Tests(unittest.TestCase):
    def test_every_ui_key_has_both_languages(self):
        code=(Path(__file__).resolve().parent.parent/'src'/'ryoku_proxy.py').read_text()
        tree=ast.parse(code)
        literals=[]
        for node in ast.walk(tree):
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='tr':
                if node.args and isinstance(node.args[0],ast.Constant):
                    literals.append(node.args[0].value)
        for key in literals:
            self.assertIn(key,i18n.LANGUAGES)
        self.assertTrue(all(len(v)==2 and v[0] and v[1] for v in i18n.LANGUAGES.values()))

    def test_english_default_russian_env(self):
        original=dict(os.environ)
        try:
            os.environ['RYOKU_PROXY_LANG']='ru'
            self.assertEqual(i18n.current_language(),'ru')
            os.environ['RYOKU_PROXY_LANG']='en'
            self.assertEqual(i18n.current_language(),'en')
            del os.environ['RYOKU_PROXY_LANG']
            os.environ['LC_ALL']='ru_RU.UTF-8'
            self.assertEqual(i18n.current_language(),'ru')
        finally:
            os.environ.clear();os.environ.update(original)

if __name__=='__main__':unittest.main()
