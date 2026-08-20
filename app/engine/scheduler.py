from __future__ import annotations

import time
from dataclasses import dataclass

FILLER_ID = 0


@dataclass
class SwitchDecision:
    target: int
    mode: str  # normal | emergency | hold


class RotationScheduler:
    def __init__(self, source_ids: list[int], interval: float, now_fn=time.monotonic) -> None:
        self.ids = list(source_ids)
        self.interval = float(interval)
        self.now_fn = now_fn
        self.health: dict[int, bool | None] = {sid: None for sid in self.ids}
        self.health[FILLER_ID] = True
        self.current_id: int | None = self.ids[0] if self.ids else None
        self.paused = False
        self._next_deadline = self.now_fn() + self.interval

    def set_health(self, source_id: int, healthy: bool) -> None:
        if source_id in self.health or source_id == FILLER_ID:
            self.health[source_id] = healthy

    def update_sources(self, source_ids: list[int]) -> None:
        old = set(self.ids)
        new = list(source_ids)
        self.ids = new
        for sid in new:
            self.health.setdefault(sid, False)
        if self.current_id not in self.ids and self.current_id != FILLER_ID:
            self.current_id = new[0] if new else None
        self._next_deadline = self.now_fn() + self.interval

    def set_interval(self, interval: float) -> None:
        self.interval = max(1.0, float(interval))
        self._next_deadline = self.now_fn() + self.interval

    def current(self) -> int | None:
        return self.current_id

    def seconds_until_next(self) -> float:
        return max(0.0, self._next_deadline - self.now_fn())

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False
        self._next_deadline = self.now_fn() + self.interval

    def _healthy_candidates(self) -> list[int]:
        return [sid for sid in self.ids if self.health.get(sid) is not False]

    def _pick_next(self, direction: int = 1) -> int | None:
        candidates = self._healthy_candidates()
        if not candidates:
            return FILLER_ID
        if self.current_id in candidates:
            idx = candidates.index(self.current_id)
            return candidates[(idx + direction) % len(candidates)]
        return candidates[0]

    def tick(self) -> SwitchDecision:
        now = self.now_fn()
        if self.paused:
            return SwitchDecision(self.current_id or FILLER_ID, "hold")
        if self.health.get(self.current_id or -1) is False and not self._healthy_candidates():
            self.current_id = FILLER_ID
            self._next_deadline = now + self.interval
            return SwitchDecision(FILLER_ID, "emergency")
        if now < self._next_deadline:
            return SwitchDecision(self.current_id or FILLER_ID, "hold")
        self._next_deadline = now + self.interval
        if self.health.get(self.current_id or -1) is not False:
            nxt = self._pick_next(1)
            if nxt != self.current_id:
                self.current_id = nxt
                return SwitchDecision(nxt, "normal")
            return SwitchDecision(self.current_id, "hold")
        candidates = self._healthy_candidates()
        if candidates:
            self.current_id = candidates[0]
            return SwitchDecision(candidates[0], "emergency")
        self.current_id = FILLER_ID
        return SwitchDecision(FILLER_ID, "emergency")

    def next_manual(self) -> SwitchDecision:
        nxt = self._pick_next(1)
        if nxt is None:
            return SwitchDecision(FILLER_ID, "emergency")
        self.current_id = nxt
        self._next_deadline = self.now_fn() + self.interval
        return SwitchDecision(nxt, "normal")

    def prev_manual(self) -> SwitchDecision:
        nxt = self._pick_next(-1)
        if nxt is None:
            return SwitchDecision(FILLER_ID, "emergency")
        self.current_id = nxt
        self._next_deadline = self.now_fn() + self.interval
        return SwitchDecision(nxt, "normal")

    def force(self, source_id: int) -> SwitchDecision:
        if source_id not in self.ids and source_id != FILLER_ID:
            return SwitchDecision(self.current_id or FILLER_ID, "hold")
        self.current_id = source_id
        self._next_deadline = self.now_fn() + self.interval
        return SwitchDecision(source_id, "normal")
