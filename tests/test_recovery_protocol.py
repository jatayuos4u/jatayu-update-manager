"""Strict recovery reply parser: no real authentication or APT operations."""
import unittest
from jatayu_update_manager.supervised_protocol import parse_recovery_reply, MAX_LAUNCH_OUTPUT


class RecoveryReplyTests(unittest.TestCase):
    def test_accepts_exact_locator(self):
        self.assertEqual(parse_recovery_reply(b'RECOVERY_ID=' + b'a'*32 + b'\n', 0), 'a'*32)

    def test_rejects_failed_or_malformed_response(self):
        valid = b'RECOVERY_ID=' + b'a'*32 + b'\n'
        for response, status in ((valid, 1), (b'ERROR\n' + valid, 0),
                                 (valid + b'extra\n', 0), (valid[:-1], 0),
                                 (b'RECOVERY_ID=' + b'A'*32 + b'\n', 0),
                                 (b'\xff', 0),
                                 (b'X' * (MAX_LAUNCH_OUTPUT+1), 0)):
            with self.subTest(response=response[:20], status=status), self.assertRaises(ValueError):
                parse_recovery_reply(response, status)
