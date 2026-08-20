from app.engine.scheduler import FILLER_ID, RotationScheduler


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_rotation_skips_unhealthy():
    clock = FakeClock()
    s = RotationScheduler([1, 2, 3], interval=20.0, now_fn=clock)
    s.set_health(2, False)
    assert s.tick().mode == "hold"  # 未到点
    clock.t += 20.0
    d = s.tick()
    assert d.mode == "normal" and d.target == 3  # 跳过 2
    clock.t += 20.0
    assert s.tick().target == 1


def test_all_down_emergency_filler():
    clock = FakeClock()
    s = RotationScheduler([1, 2], interval=20.0, now_fn=clock)
    s.set_health(1, False)
    s.set_health(2, False)
    clock.t += 3.0
    d = s.tick()
    assert d.mode == "emergency" and d.target == FILLER_ID


def test_manual_next_and_force():
    clock = FakeClock()
    s = RotationScheduler([1, 2, 3], interval=20.0, now_fn=clock)
    assert s.next_manual().target == 2
    assert s.force(3).target == 3
    s.pause()
    clock.t += 100
    assert s.tick().mode == "hold"
    s.resume()
    assert s.current() == 3
