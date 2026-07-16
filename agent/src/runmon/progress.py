from __future__ import annotations

import re
from dataclasses import dataclass

TQDM_RE = re.compile(r"(\d+)%\|[^|]*\|\s*(\d+)/(\d+)(?:\s*\[([\d:]+)<([\d:]+)[^\]]*\])?")
EPOCH_RE = re.compile(r"[Ee]poch[\s:=\[]*(\d+)\s*/\s*(\d+)")
LOSS_RE = re.compile(r"\bloss[\s:=]+([0-9]*\.?[0-9]+(?:[eE][+-]?[0-9]+)?)")


def parse_eta(text: str) -> int | None:
    parts = text.split(":")
    if not parts or not all(p.isdigit() for p in parts):
        return None
    nums = [int(p) for p in parts]
    while len(nums) < 3:
        nums.insert(0, 0)
    return nums[0] * 3600 + nums[1] * 60 + nums[2]


@dataclass
class Progress:
    percent: float | None = None
    eta_seconds: int | None = None
    loss: float | None = None
    epoch: tuple[int, int] | None = None


class ProgressParser:
    def __init__(self) -> None:
        self.state = Progress()

    def feed(self, text: str) -> bool:
        changed = False
        for line in re.split(r"[\r\n]", text):
            if m := TQDM_RE.search(line):
                self.state.percent = float(m.group(1))
                changed = True
                if m.group(5) and (eta := parse_eta(m.group(5))) is not None:
                    self.state.eta_seconds = eta
            if m := EPOCH_RE.search(line):
                self.state.epoch = (int(m.group(1)), int(m.group(2)))
                changed = True
            if m := LOSS_RE.search(line):
                self.state.loss = float(m.group(1))
                changed = True
        return changed
