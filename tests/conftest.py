import json

import pytest

from src import OUTPUTS
from src.engine import main as run_engine
from src.generate import main as run_generate


@pytest.fixture(scope="session", autouse=True)
def pack():
    run_generate()
    run_engine()
    with open(OUTPUTS / "insight_pack.json", encoding="utf-8") as handle:
        return json.load(handle)
