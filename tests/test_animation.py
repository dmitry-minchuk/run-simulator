import pytest

from run_simulator.animation import (
    BASE_CADENCE,
    LANDING_TIME,
    SEQUENCE_LENGTHS,
    Animator,
    Mode,
    Motion,
    SpriteFrame,
    cadence,
)

START = 360.0
TOP = 900.0
JUMP = 900.0
DT = 1 / 120


def motion(
    mode: Mode = Mode.RUN, on_ground: bool = True, vy: float = 0.0, speed: float = START
) -> Motion:
    return Motion(mode, on_ground, vy, JUMP, speed, START)


def run_for(animator: Animator, seconds: float, state: Motion) -> None:
    for _ in range(round(seconds / DT)):
        animator.update(DT, state)


def test_cadence_grows_with_speed() -> None:
    assert cadence(START, START) == pytest.approx(BASE_CADENCE)
    assert cadence(TOP, START) > cadence(600, START) > cadence(START, START)


def test_run_frames_advance_and_loop_with_cadence() -> None:
    animator = Animator()
    seen = []
    for _ in range(round(1 / cadence(START, START) / DT)):
        animator.update(DT, motion())
        seen.append(animator.sprite())

    indexes = [frame.index for frame in seen]
    assert {frame.sequence for frame in seen} == {"run"}
    assert set(indexes) == set(range(SEQUENCE_LENGTHS["run"]))
    assert indexes == sorted(indexes)


def test_faster_speed_plays_run_cycle_faster() -> None:
    slow = Animator()
    fast = Animator()
    run_for(slow, 0.1, motion(speed=START))
    run_for(fast, 0.1, motion(speed=TOP))

    assert fast.phase > slow.phase > 0


def test_idle_cycles_breathing_frames_without_running() -> None:
    animator = Animator()
    indexes = set()
    for _ in range(round(2.4 / DT)):
        animator.update(DT, motion(Mode.IDLE))
        indexes.add(animator.sprite().index)
        assert animator.sprite().sequence == "idle"

    assert indexes == set(range(SEQUENCE_LENGTHS["idle"]))
    assert animator.phase == 0.0


def test_air_frames_go_from_takeoff_to_falling() -> None:
    animator = Animator()
    frames = []
    vy = JUMP
    while vy > -JUMP:
        animator.update(DT, motion(on_ground=False, vy=vy))
        frames.append(animator.sprite())
        vy -= 2600 * DT

    assert frames[0] == SpriteFrame("air", 0)
    assert frames[-1] == SpriteFrame("air", SEQUENCE_LENGTHS["air"] - 1)
    assert [frame.index for frame in frames] == sorted(frame.index for frame in frames)


def test_landing_plays_landing_frames_then_returns_to_run() -> None:
    animator = Animator()
    animator.update(DT, motion(on_ground=False, vy=-JUMP))
    sequences = []
    for _ in range(round(0.3 / DT)):
        animator.update(DT, motion())
        sequences.append(animator.sprite())

    landing = [frame for frame in sequences if frame.sequence == "land"]
    assert sequences[0] == SpriteFrame("land", 0)
    assert {frame.index for frame in landing} == set(range(SEQUENCE_LENGTHS["land"]))
    assert len(landing) == pytest.approx(LANDING_TIME / DT, abs=2)
    assert sequences[-1].sequence == "run"


def test_crash_mode_falls_back_to_a_pose_that_every_sheet_has() -> None:
    animator = Animator()
    animator.update(DT, motion(Mode.HIT))

    assert animator.sprite() == SpriteFrame("land", 0)
    assert animator.squash() == (1.0, 1.0)


def test_starting_a_run_from_menu_does_not_play_landing() -> None:
    animator = Animator()
    run_for(animator, 1.0, motion(Mode.IDLE))
    animator.update(DT, motion())

    assert animator.sprite().sequence == "run"


def test_restart_after_mid_air_crash_does_not_play_landing() -> None:
    animator = Animator()
    animator.update(DT, motion(on_ground=False, vy=JUMP / 2))
    animator.update(DT, motion(Mode.HIT, on_ground=False, vy=JUMP / 2))
    animator.update(DT, motion())

    assert animator.sprite().sequence == "run"


def test_takeoff_stretches_and_landing_squashes_then_settles() -> None:
    animator = Animator()
    animator.update(DT, motion())
    run_for(animator, 0.06, motion(on_ground=False, vy=JUMP))
    stretched = animator.squash()
    run_for(animator, 0.7, motion(on_ground=False, vy=-JUMP))
    run_for(animator, 0.05, motion())
    squashed = animator.squash()
    run_for(animator, 0.6, motion())

    assert stretched[1] > 1.05 > 1 > stretched[0]
    assert squashed[1] < 0.9 < 1 < squashed[0]
    assert animator.squash() == pytest.approx((1.0, 1.0), abs=0.01)
