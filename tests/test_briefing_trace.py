"""Every briefing figure must already exist in the insight pack."""

import json
import re

from src import OUTPUTS
from src.briefing import load_pack, write_brief, _pid


def test_briefing_refs_are_in_pack(pack):
    record = write_brief(pack, live=False)
    assert record["source_refs"]
    assert record["requires_approval"] is True
    assert "No supply action" in record["human_gate"]

    pack_numbers = _pack_floats(pack)
    for ref in record["source_refs"]:
        value = ref["value"]
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and not isinstance(value, bool):
            if value in pack_numbers or float(value) in pack_numbers:
                continue
            if ref["path"].startswith("exceptions.type."):
                typ = ref["path"].rsplit(".", 1)[1]
                assert value == sum(1 for e in pack["exceptions"] if e["type"] == typ)
                continue
            raise AssertionError(ref)
        if isinstance(value, float):
            if any(abs(value - n) < 1e-8 for n in pack_numbers if isinstance(n, float)):
                continue
            if ref["path"].startswith("value_register."):
                pid = ref["path"].split(".", 1)[1]
                subset = []
                for row in pack["value_register"]:
                    row_pid = _pid(row.get("planted_id"))
                    if str(row_pid) == pid:
                        subset.append(float(row["value_at_risk"]))
                assert abs(sum(subset) - value) < 1e-4
                continue
            raise AssertionError(ref)


def test_briefing_markdown_numbers_are_cited(pack):
    record = write_brief(pack, live=False)
    displays = {ref["display"] for ref in record["source_refs"]}
    for token in re.findall(r"\$[0-9][0-9,]*|[0-9]+/[0-9]+|[0-9]+\.[0-9]+%|[0-9]{1,3}\.[0-9]{2}\b", record["markdown"]):
        assert token in displays


def test_cached_brief_files_exist(pack):
    write_brief(pack, live=False)
    assert (OUTPUTS / "briefing.json").exists()
    assert (OUTPUTS / "briefing.md").exists()
    with open(OUTPUTS / "briefing.json", encoding="utf-8") as handle:
        saved = json.load(handle)
    assert saved["agent_id"] == "sop_insight"
    assert saved["mode"] == "cached_from_pack"


def _pack_floats(obj, out=None):
    if out is None:
        out = []
    if isinstance(obj, dict):
        for value in obj.values():
            _pack_floats(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _pack_floats(value, out)
    elif isinstance(obj, bool):
        return out
    elif isinstance(obj, (int, float)):
        out.append(float(obj) if isinstance(obj, float) else obj)
    return out
