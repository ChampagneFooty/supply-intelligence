from src.pack import REQUIRED_KEYS


def test_pack_has_required_keys(pack):
    for key in REQUIRED_KEYS:
        assert key in pack


def test_planted_problems_detected(pack):
    assert pack["planted"]["P1"] is True
    assert pack["planted"]["P2"] is True
    assert pack["planted"]["P3"] is True
    assert pack["planted"]["detected_count"] == 3


def test_value_register_cites_keys(pack):
    assert pack["value_register"]
    for row in pack["value_register"]:
        assert row["exception_id"]
        assert "volume_at_risk" in row
        assert "asp_per_case" in row
        assert "value_at_risk" in row
        assert row["calc_id"].startswith("val:")
