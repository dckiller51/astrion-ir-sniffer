import json

import pytest

from app import _real_command, parse_pronto_capture

# ---------------------------------------------------------------------------
# _real_command()
# ---------------------------------------------------------------------------


def test_real_command_prefers_action_command_over_name():
    """Regression test for the bug where the bulk-capture sniffer sent the
    hub's display name ("Select") instead of the real IR command ("OK"),
    silently producing an empty pronto capture for that button."""
    cmd = {
        "action": json.dumps({"command": "OK", "type": "IRCommand", "deviceId": "62845801"}),
        "name": "Select",
        "label": "Select",
    }
    assert _real_command(cmd) == "OK"


def test_real_command_falls_back_to_name_when_action_missing():
    cmd = {"name": "DirectionUp", "label": "Up"}
    assert _real_command(cmd) == "DirectionUp"


def test_real_command_falls_back_to_name_when_action_malformed():
    cmd = {"action": "not valid json", "name": "Menu", "label": "Menu"}
    assert _real_command(cmd) == "Menu"


def test_real_command_falls_back_to_name_when_action_has_no_command_field():
    cmd = {"action": json.dumps({"type": "IRCommand"}), "name": "Home", "label": "Home"}
    assert _real_command(cmd) == "Home"


# ---------------------------------------------------------------------------
# parse_pronto_capture()
# ---------------------------------------------------------------------------


def test_parse_pronto_capture_empty_input_returns_empty_strings():
    assert parse_pronto_capture("") == ("", "")
    assert parse_pronto_capture(None) == ("", "")


def test_parse_pronto_capture_no_pronto_tokens_returns_empty_strings():
    assert parse_pronto_capture("no ir signal seen, just log noise") == ("", "")


def test_parse_pronto_capture_single_burst_with_nonzero_repeat_length():
    """A code whose header genuinely has no '0000' token in the middle (its
    repeat-length field, byte index 3, is non-zero) round-trips untouched."""
    code = "0000 006D 0012 0005 00AD 00AD 0012 0014 0012 0014 0012 0181"
    main, repeat = parse_pronto_capture(f"Received pronto: {code}")
    assert main == code
    assert repeat == ""


@pytest.mark.xfail(
    reason=(
        "KNOWN ISSUE, not yet fixed: when a captured code's own repeat-length "
        "header field is literally '0000' (i.e. a one-shot code with no "
        "distinct repeat burst -- the shape of most captures in this "
        "project's own ir-database/, e.g. '0000 006D 0027 0000 00AD...'), "
        "parse_pronto_capture() misreads that field as a sequence boundary "
        "and splits there, stripping the type+carrier-frequency header off "
        "`main`. Reproduced with real capture shapes; not yet fixed because "
        "the exact raw `esphome logs` text format wasn't available to "
        "verify a fix against. See CHANGELOG.md 'Known issues'."
    ),
    strict=True,
)
def test_parse_pronto_capture_does_not_strip_header_when_repeat_length_is_zero():
    code = "0000 006D 0027 0000 00AD 00AD 0012 0014 0012 003B 0012 0181"
    main, _repeat = parse_pronto_capture(f"Received pronto: {code}")
    assert main == code
