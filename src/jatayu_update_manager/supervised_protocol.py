"""Strict, bounded launcher handshake for experimental supervised APT.

The launcher exits when a systemd unit starts, not when APT succeeds.
Transaction IDs are locators, never authorization tokens.
"""
import re

_ID = re.compile(r'[0-9a-f]{32}\\Z')
MAX_LAUNCH_OUTPUT = 4096


def parse_launcher_reply(output, exit_code):
    if exit_code != 0:
        raise ValueError('Supervised launch was not authorized or failed')
    if not isinstance(output, (bytes, bytearray)) or len(output) > MAX_LAUNCH_OUTPUT:
        raise ValueError('Malformed or oversized launcher response')
    try:
        message = bytes(output).decode('utf-8')
    except UnicodeDecodeError as exc:
        raise ValueError('Invalid launcher encoding') from exc
    # Reject stray output; a successful launcher must emit exactly one ID line.
    if not message.startswith('TRANSACTION_ID=') or message.count('\n') != 1:
        raise ValueError('Invalid supervised launcher response')
    identifier = message.removeprefix('TRANSACTION_ID=').strip()
    if not _ID.fullmatch(identifier):
        raise ValueError('Invalid supervised transaction ID')
    return identifier
