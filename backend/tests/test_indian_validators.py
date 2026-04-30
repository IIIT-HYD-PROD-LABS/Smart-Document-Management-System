"""LIFE-03: Indian identifier validators — GSTIN/PAN/CIN/DIN regex."""



def test_valid_gstin_accepted():
    from app.compliance.utils.indian_validators import validate_gstin
    assert validate_gstin("27AAAAA0000A1Z5") is True


def test_invalid_gstin_rejected():
    from app.compliance.utils.indian_validators import validate_gstin
    assert validate_gstin("INVALID-GSTIN") is False
    assert validate_gstin("99AAAAA0000A1Z5") is True   # Centre = 99
    assert validate_gstin("38AAAAA0000A1Z5") is False  # state code 38 invalid


def test_valid_pan_accepted():
    from app.compliance.utils.indian_validators import PAN_RX
    assert PAN_RX.match("AAAAA0000A") is not None


def test_invalid_pan_rejected():
    from app.compliance.utils.indian_validators import PAN_RX
    assert PAN_RX.match("INVALID") is None


def test_valid_cin_accepted():
    from app.compliance.utils.indian_validators import CIN_RX
    assert CIN_RX.match("U72200KA2010PTC053285") is not None


def test_din_is_8_digits():
    from app.compliance.utils.indian_validators import DIN_RX
    assert DIN_RX.match("12345678") is not None
    assert DIN_RX.match("1234567") is None
