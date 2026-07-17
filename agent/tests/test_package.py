import re
from pathlib import Path

import runmon


def test_version():
    """__version__ 与 pyproject 保持一致,避免发版时漏改其中一处。"""
    pyproject = Path(__file__).resolve().parent.parent / "pyproject.toml"
    declared = re.search(r'^version = "([^"]+)"', pyproject.read_text(), re.M).group(1)
    assert runmon.__version__ == declared
