import json
from pathlib import Path

from app import _real_command, parse_pronto_capture, split_pronto_sequences

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


def test_parse_pronto_capture_does_not_strip_header_when_repeat_length_is_zero():
    """Regression: the repeat-length header field is '0000' for any code
    without a repeat section; splitting on every '0000' cut the header off
    (pronto '0000 00AD ...' + fake repeat '0000 006D 0027')."""
    code = "0000 006D 0027 0000 00AD 00AD 0012 0014 0012 003B 0012 0181"
    main, repeat = parse_pronto_capture(f"Received pronto: {code}")
    assert main == code
    assert repeat == ""


# A complete NEC frame (34 pairs) and its separate repeat code, as found in
# ir-database/ before this was fixed.
NEC_FRAME = "0000 006D 0022 0000 015A 00AE " + "0015 0016 " * 16 + "0015 0041 " * 16 + "0015 0181"
NEC_REPEAT = "0000 006D 0002 0000 0159 0057 0015 0181"


def test_parse_pronto_capture_frame_then_repeat():
    main, repeat = parse_pronto_capture(f"Received Pronto: data={NEC_FRAME} {NEC_REPEAT}")
    assert main == NEC_FRAME.strip()
    assert repeat == NEC_REPEAT


def test_parse_pronto_capture_repeat_logged_first_still_picks_the_frame():
    main, repeat = parse_pronto_capture(f"{NEC_REPEAT}\n{NEC_FRAME}")
    assert main == NEC_FRAME.strip()
    assert repeat == NEC_REPEAT


def test_parse_pronto_capture_ignores_log_noise_and_line_breaks():
    words = NEC_FRAME.split()
    log = (
        "[12:00:01.123][I][remote.pronto:229]: Received Pronto: data=" + " ".join(words[:40]) + "\n"
        "[12:00:01.124][I][remote.pronto:229]: Received Pronto: data=" + " ".join(words[40:])
    )
    main, repeat = parse_pronto_capture(log)
    assert main == " ".join(words)
    assert repeat == ""


def test_split_pronto_sequences_skips_tokens_that_cannot_start_a_code():
    tokens = ["ABCD", "0000", "0000", "0001", "0000"] + NEC_REPEAT.split()
    assert split_pronto_sequences(tokens) == [NEC_REPEAT]


# ---------------------------------------------------------------------------
# docs/ir-database/ content
# ---------------------------------------------------------------------------


def _database_codes():
    root = Path(__file__).resolve().parent.parent / "docs" / "ir-database"
    for path in sorted(root.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        for brand in data["brands"]:
            for model in brand["models"]:
                for cmd_id, cmd in model.get("commands", {}).items():
                    where = f"{path.name}: {brand['brand_name']} {model['model_name']} / {cmd_id}"
                    yield where, cmd


def test_database_pronto_codes_have_an_intact_header():
    """Guards against the old split-on-'0000' capture bug, which stored the
    header-less rest of a code as `pronto` (second word = first burst,
    giving a ~12 kHz "carrier") and `0000 006D 00xx` as `pronto_repeat`."""
    broken = []
    for where, cmd in _database_codes():
        for field in ("pronto", "pronto_repeat"):
            words = cmd.get(field, "").split()
            if not words:
                continue
            freq = int(words[1], 16) if len(words) > 1 else 0
            carrier_ok = freq != 0 and 20_000 < 4_145_146 / freq < 60_000
            if words[0] != "0000" or not carrier_ok or len(words) <= 4:
                broken.append(f"{where} [{field}]")
    assert broken == []
