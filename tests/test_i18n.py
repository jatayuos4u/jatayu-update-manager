import unittest
from jatayu_update_manager.i18n import STRINGS, tr

class TranslationTests(unittest.TestCase):
    def test_languages_have_same_keys(self):
        self.assertEqual(set(STRINGS['en']), set(STRINGS['hi']))

    def test_interpolation(self):
        self.assertIn('3', tr('hi', 'count', count=3))

    def test_fallback(self):
        self.assertEqual(tr('xx', 'check'), tr('en', 'check'))
