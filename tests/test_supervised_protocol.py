"""Launcher handshake and ID persistence without real root operations."""
import unittest
from jatayu_update_manager.supervised_protocol import parse_launcher_reply, MAX_LAUNCH_OUTPUT


class ProtocolTests(unittest.TestCase):
    def test_exact_response_accepted(self):
        self.assertEqual(parse_launcher_reply(b'TRANSACTION_ID=' + b'a' * 32 + b'\n', 0), 'a'*32)

    def test_failed_launch_cannot_be_adopted(self):
        with self.assertRaises(ValueError):
            parse_launcher_reply(b'TRANSACTION_ID=' + b'a' * 32 + b'\n', 1)

    def test_invalid_or_extra_output_rejected(self):
        outputs = (b'bad', b'TRANSACTION_ID=' + b'A' * 32 + b'\n',
                   b'TRANSACTION_ID=' + b'a' * 32 + b'\nmore\n',
                   b'TRANSACTION_ID=' + b'a' * 32, b'\xff',
                   b'X' * (MAX_LAUNCH_OUTPUT + 1))
        for data in outputs:
            with self.subTest(data=data[:30]), self.assertRaises(ValueError):
                parse_launcher_reply(data, 0)
