import random
from dataclasses import dataclass, field
from enum import Enum, auto

from run_simulator.heroes import HEROES, Hero


class State(Enum):
    MENU = auto()
    RUNNING = auto()
    GAME_OVER = auto()


class Kind(Enum):
    FLYTRAP = auto()
    PITCHER = auto()
    ROSE = auto()
    STUMP = auto()
    CACTUS = auto()
    ROCK = auto()


KINDS: tuple[Kind, ...] = tuple(Kind)
KIND_SHAPES: dict[Kind, tuple[float, float, float]] = {
    Kind.FLYTRAP: (0.795, 106.0, 132.0),
    Kind.PITCHER: (0.79, 108.0, 136.0),
    Kind.ROSE: (0.98, 100.0, 124.0),
    Kind.STUMP: (1.188, 76.0, 96.0),
    Kind.CACTUS: (0.895, 104.0, 128.0),
    Kind.ROCK: (1.068, 90.0, 110.0),
}


@dataclass(frozen=True)
class Config:
    view_width: float = 960.0
    player_x: float = 120.0
    player_width: float = 88.0
    player_height: float = 120.0
    gravity: float = 3500.0
    jump_velocity: float = 1400.0
    start_speed: float = 360.0
    acceleration: float = 5.0
    max_speed: float = 900.0
    obstacle_min_width: float = 52.0
    obstacle_max_width: float = 124.0
    obstacle_min_height: float = 68.0
    obstacle_max_height: float = 140.0
    first_obstacle_delay: float = 1.2
    gap_extra_min: float = 0.35
    gap_extra_max: float = 1.1
    hitbox_inset: float = 12.0
    restart_delay: float = 1.2
    score_per_pixel: float = 0.1

    @property
    def jump_airtime(self) -> float:
        return 2 * self.jump_velocity / self.gravity


@dataclass
class Player:
    altitude: float = 0.0
    velocity: float = 0.0
    on_ground: bool = True


@dataclass
class Obstacle:
    x: float
    width: float
    height: float
    kind: Kind
    seed: float


@dataclass
class World:
    config: Config
    rng: random.Random
    state: State = State.MENU
    hero: Hero = Hero.FOOTBALLER
    highlighted: Hero = Hero.FOOTBALLER
    best_score: int = 0
    player: Player = field(default_factory=Player)
    obstacles: list[Obstacle] = field(default_factory=list)
    speed: float = 0.0
    distance: float = 0.0
    elapsed: float = 0.0
    time_since_game_over: float = 0.0
    next_spawn_in: float = 0.0
    crash: Obstacle | None = None

    def __post_init__(self) -> None:
        self._reset()

    @property
    def score(self) -> int:
        return int(self.distance * self.config.score_per_pixel)

    def proximity(self, obstacle: Obstacle, reach: float = 260.0) -> float:
        config = self.config
        front = config.player_x + config.player_width
        gap = obstacle.x - front
        if gap < 0:
            gap = max(0.0, config.player_x - (obstacle.x + obstacle.width))
        return min(1.0, max(0.0, 1 - gap / reach))

    @property
    def can_restart(self) -> bool:
        return (
            self.state is State.GAME_OVER and self.time_since_game_over >= self.config.restart_delay
        )

    def highlight(self, hero: Hero) -> None:
        if self.state is State.MENU:
            self.highlighted = hero

    def highlight_next(self, step: int) -> None:
        if self.state is State.MENU:
            index = HEROES.index(self.highlighted)
            self.highlighted = HEROES[(index + step) % len(HEROES)]

    def choose(self, hero: Hero) -> None:
        if self.state is State.MENU:
            self.hero = hero
            self.highlighted = hero
            self._reset()
            self.state = State.RUNNING

    def jump(self) -> None:
        if self.state is State.RUNNING:
            self._jump()

    def restart(self) -> None:
        if self.can_restart:
            self._reset()
            self.state = State.RUNNING

    def open_menu(self) -> None:
        if self.can_restart:
            self.highlighted = self.hero
            self._reset()
            self.state = State.MENU

    def update(self, dt: float) -> None:
        if self.state is State.GAME_OVER:
            self.time_since_game_over += dt
            return
        if self.state is not State.RUNNING:
            return
        self.elapsed += dt
        self.speed = min(
            self.config.max_speed,
            self.config.start_speed + self.config.acceleration * self.elapsed,
        )
        step = self.speed * dt
        self.distance += step
        self._move_player(dt)
        self._move_obstacles(step)
        self._spawn_obstacle(step)
        crash = self._collision()
        if crash is not None:
            self.crash = crash
            self.state = State.GAME_OVER
            self.best_score = max(self.best_score, self.score)

    def _reset(self) -> None:
        self.player = Player()
        self.obstacles = []
        self.speed = self.config.start_speed
        self.distance = 0.0
        self.elapsed = 0.0
        self.time_since_game_over = 0.0
        self.crash = None
        self.next_spawn_in = self.config.start_speed * self.config.first_obstacle_delay

    def _jump(self) -> None:
        if self.player.on_ground:
            self.player.velocity = self.config.jump_velocity
            self.player.on_ground = False

    def _move_player(self, dt: float) -> None:
        player = self.player
        if player.on_ground:
            return
        player.velocity -= self.config.gravity * dt
        player.altitude += player.velocity * dt
        if player.altitude <= 0:
            player.altitude = 0.0
            player.velocity = 0.0
            player.on_ground = True

    def _move_obstacles(self, step: float) -> None:
        for obstacle in self.obstacles:
            obstacle.x -= step
        self.obstacles = [o for o in self.obstacles if o.x + o.width > 0]

    def _spawn_obstacle(self, step: float) -> None:
        self.next_spawn_in -= step
        if self.next_spawn_in > 0:
            return
        config = self.config
        kind = self.rng.choice(KINDS)
        aspect, min_height, max_height = KIND_SHAPES[kind]
        height = self.rng.uniform(min_height, max_height)
        obstacle = Obstacle(
            x=config.view_width + self.next_spawn_in,
            width=aspect * height,
            height=height,
            kind=kind,
            seed=self.rng.random(),
        )
        self.obstacles.append(obstacle)
        extra = self.rng.uniform(config.gap_extra_min, config.gap_extra_max)
        gap_time = config.jump_airtime + extra
        self.next_spawn_in += obstacle.width + self.speed * gap_time

    def _collision(self) -> Obstacle | None:
        config = self.config
        left = config.player_x + config.hitbox_inset
        right = config.player_x + config.player_width - config.hitbox_inset
        bottom = self.player.altitude
        for o in self.obstacles:
            if o.x < right and o.x + o.width > left and bottom < o.height - config.hitbox_inset:
                return o
        return None
