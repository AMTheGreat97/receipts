from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.make_fixtures import generate


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False, help="run OpenRouter live tests")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="pass --run-live to hit OpenRouter")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)


@pytest.fixture(scope="session")
def fixtures() -> dict[str, Path]:
    return generate()
