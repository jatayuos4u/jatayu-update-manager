import unittest
from jatayu_update_manager.i18n import tr

class TestUIStrings(unittest.TestCase):
    def test_states_translated(self):
        for language in ("en", "hi"):
            for key in ("search", "failed_generic", "working", "wait", "none_detail", "not_checked", "check_prompt"):
                self.assertNotEqual(tr(language, key), key)
