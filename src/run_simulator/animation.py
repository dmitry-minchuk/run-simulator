import math
from dataclasses import dataclass
from enum import Enum, auto

BASE_CADENCE = 1.9
LANDING_TIME = 0.12
IDLE_PERIOD = 1.6
SEQUENCE_LENGTHS = {"run": 6, "air": 4, "land": 1, "idle": 4}


class Mode(Enum):
    IDLE = auto()
    RUN = auto()
    HIT = auto()


def cadence(speed: float, start_speed: float) -> float:
    return BASE_CADENCE * math.sqrt(max(speed, 0.0) / start_speed)


def envelope(t: float, attack: float) -> float:
    if t <= 0:
        return 0.0
    ratio = t / attack
    return ratio * math.exp(1 - ratio)


@dataclass(frozen=True)
class Motion:
    mode: Mode
    on_ground: bool
    vertical_velocity: float
    jump_velocity: float
    speed: float
    start_speed: float


@dataclass(frozen=True)
class SpriteFrame:
    sequence: str
    index: int


@dataclass
class Animator:
    mode: Mode = Mode.IDLE
    phase: float = 0.0
    time: float = 0.0
    on_ground: bool = True
    vertical_velocity: float = 0.0
    jump_velocity: float = 1.0
    since_landing: float = 10.0
    since_takeoff: float = 10.0

    def update(self, dt: float, motion: Motion) -> None:
        self.time += dt
        running = self.mode is Mode.RUN and motion.mode is Mode.RUN
        landed = motion.on_ground and not self.on_ground and running
        took_off = not motion.on_ground and self.on_ground and running
        self.since_landing = 0.0 if landed else self.since_landing + dt
        self.since_takeoff = 0.0 if took_off else self.since_takeoff + dt
        self.on_ground = motion.on_ground
        self.vertical_velocity = motion.vertical_velocity
        self.jump_velocity = motion.jump_velocity
        self.mode = motion.mode
        if motion.mode is Mode.RUN:
            self.phase = (self.phase + dt * cadence(motion.speed, motion.start_speed)) % 1.0

    def squash(self) -> tuple[float, float]:
        if self.mode is not Mode.RUN:
            return 1.0, 1.0
        stretch = 0.1 * envelope(self.since_takeoff, 0.06) - 0.14 * envelope(
            self.since_landing, 0.05
        )
        return 1 - stretch * 0.6, 1 + stretch

    def sprite(self) -> SpriteFrame:
        if self.mode is Mode.HIT:
            return SpriteFrame("land", 0)
        if self.mode is Mode.IDLE:
            count = SEQUENCE_LENGTHS["idle"]
            return SpriteFrame("idle", int(self.time / IDLE_PERIOD * count) % count)
        if not self.on_ground:
            progress = (self.jump_velocity - self.vertical_velocity) / (2 * self.jump_velocity)
            count = SEQUENCE_LENGTHS["air"]
            return SpriteFrame("air", min(count - 1, max(0, int(progress * count))))
        if self.since_landing < LANDING_TIME:
            return SpriteFrame("land", 0)
        count = SEQUENCE_LENGTHS["run"]
        return SpriteFrame("run", int(self.phase * count) % count)
