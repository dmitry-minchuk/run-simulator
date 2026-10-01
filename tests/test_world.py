import math
import random
from itertools import pairwise

import pytest

from run_simulator.heroes import Hero
from run_simulator.world import KIND_SHAPES, Config, Kind, Obstacle, State, World

DT = 1 / 120
NO_OBSTACLES = Config(first_obstacle_delay=1e9)


def make_world(config: Config | None = None, seed: int = 0) -> World:
    return World(config or Config(), random.Random(seed))


def running_world(config: Config | None = None, seed: int = 0) -> World:
    world = make_world(config, seed)
    world.choose(Hero.FOOTBALLER)
    return world


def state_of(world: World) -> State:
    return world.state


def highlighted_of(world: World) -> Hero:
    return world.highlighted


def autopilot_wants_jump(world: World) -> bool:
    config = world.config
    left = config.player_x + config.hitbox_inset
    right = config.player_x + config.player_width - config.hitbox_inset
    ahead = [o for o in world.obstacles if o.x + o.width > left]
    if not ahead or not world.player.on_ground:
        return False
    target = min(ahead, key=lambda o: o.x)
    clearance = target.height - config.hitbox_inset
    velocity, gravity = config.jump_velocity, config.gravity
    root = math.sqrt(velocity * velocity - 2 * gravity * clearance)
    rise, fall = (velocity - root) / gravity, (velocity + root) / gravity
    overlap = (target.width + right - left) / world.speed
    lead = (rise + fall - overlap) / 2
    return target.x - right <= world.speed * lead


def simulate(world: World, seconds: float, autopilot: bool = False) -> None:
    for _ in range(round(seconds / DT)):
        if autopilot and autopilot_wants_jump(world):
            world.jump()
        world.update(DT)
        if world.state is State.GAME_OVER:
            return


def test_menu_waits_for_hero_choice_and_start_does_not_jump() -> None:
    world = make_world()
    world.update(1.0)
    world.jump()

    assert state_of(world) is State.MENU
    assert world.distance == 0
    assert world.obstacles == []
    assert world.player.on_ground

    world.choose(Hero.PRINCESS)

    assert state_of(world) is State.RUNNING
    assert world.hero is Hero.PRINCESS
    assert world.player.on_ground


def test_highlight_cycles_through_heroes_only_in_menu() -> None:
    world = make_world()

    assert highlighted_of(world) is Hero.FOOTBALLER

    world.highlight_next(1)

    assert highlighted_of(world) is Hero.PRINCESS

    world.highlight_next(1)

    assert highlighted_of(world) is Hero.FOOTBALLER

    world.highlight_next(-1)

    assert highlighted_of(world) is Hero.PRINCESS

    world.highlight(Hero.FOOTBALLER)
    world.choose(Hero.FOOTBALLER)
    world.highlight_next(1)
    world.highlight(Hero.PRINCESS)
    world.choose(Hero.PRINCESS)

    assert highlighted_of(world) is Hero.FOOTBALLER
    assert world.hero is Hero.FOOTBALLER


def test_jump_rises_above_tallest_obstacle_and_lands() -> None:
    world = running_world(NO_OBSTACLES)
    world.jump()
    apex = 0.0
    airtime = 0.0
    while not world.player.on_ground:
        world.update(DT)
        airtime += DT
        apex = max(apex, world.player.altitude)

    assert apex > world.config.obstacle_max_height * 1.5
    assert airtime == pytest.approx(world.config.jump_airtime, abs=2 * DT)
    assert world.player.altitude == 0


def test_space_in_air_does_not_double_jump() -> None:
    world = running_world(NO_OBSTACLES)
    world.jump()
    for _ in range(10):
        world.update(DT)
    velocity = world.player.velocity

    world.jump()

    assert world.player.velocity == velocity


def test_speed_grows_smoothly_and_is_capped() -> None:
    world = running_world(NO_OBSTACLES)
    config = world.config
    speeds = []
    for _ in range(round(120 / DT)):
        world.update(DT)
        speeds.append(world.speed)

    assert speeds[0] == pytest.approx(config.start_speed + config.acceleration * DT)
    deltas = [b - a for a, b in pairwise(speeds)]
    assert all(0 <= delta <= config.acceleration * DT + 1e-9 for delta in deltas)
    assert speeds[-1] == config.max_speed


def test_score_grows_with_distance() -> None:
    world = running_world(NO_OBSTACLES)
    scores = []
    for _ in range(round(5 / DT)):
        world.update(DT)
        scores.append(world.score)

    assert scores == sorted(scores)
    assert scores[-1] == int(world.distance * world.config.score_per_pixel)
    assert scores[-1] > 0


def test_obstacles_leave_time_to_land_before_next_jump() -> None:
    world = running_world()
    spawned: dict[int, Obstacle] = {}
    for _ in range(round(60 / DT)):
        if autopilot_wants_jump(world):
            world.jump()
        world.update(DT)
        spawned.update((id(o), o) for o in world.obstacles)
        ordered = sorted(world.obstacles, key=lambda o: o.x)
        for current, following in pairwise(ordered):
            assert (following.x - current.x) / world.speed >= world.config.jump_airtime

    assert state_of(world) is State.RUNNING
    assert len(spawned) > 30


@pytest.mark.parametrize("seed", range(5))
def test_perfect_timing_survives_past_max_speed(seed: int) -> None:
    world = running_world(seed=seed)

    simulate(world, 120, autopilot=True)

    assert state_of(world) is State.RUNNING
    assert world.speed == world.config.max_speed


def test_runner_without_jumps_crashes_and_sets_best_score() -> None:
    world = running_world()

    simulate(world, 10)

    assert state_of(world) is State.GAME_OVER
    assert world.best_score == world.score > 0


def test_obstacle_hits_only_when_runner_is_low() -> None:
    world = running_world(NO_OBSTACLES)
    config = world.config
    obstacle = Obstacle(x=config.player_x, width=40, height=50, kind=Kind.ROCK, seed=0.0)
    world.obstacles = [obstacle]
    world.player.altitude = 60
    world.player.on_ground = False
    world.player.velocity = 1000

    world.update(DT)

    assert state_of(world) is State.RUNNING

    world.obstacles = [Obstacle(x=config.player_x, width=40, height=50, kind=Kind.ROCK, seed=0.0)]
    world.player.altitude = 0
    world.player.velocity = 0
    world.player.on_ground = True

    world.update(DT)

    assert state_of(world) is State.GAME_OVER


def test_restart_needs_delay_and_keeps_hero_and_best_score() -> None:
    world = make_world()
    world.choose(Hero.PRINCESS)
    simulate(world, 10)
    best = world.best_score

    world.restart()

    assert state_of(world) is State.GAME_OVER

    world.update(world.config.restart_delay)
    world.restart()

    assert state_of(world) is State.RUNNING
    assert world.hero is Hero.PRINCESS
    assert world.score == 0
    assert world.obstacles == []
    assert world.speed == world.config.start_speed
    assert world.player.on_ground
    assert world.best_score == best > 0


def test_restart_is_ignored_while_running() -> None:
    world = running_world(NO_OBSTACLES)
    simulate(world, 1)
    distance = world.distance

    world.restart()

    assert world.distance == distance


def test_open_menu_after_game_over_highlights_current_hero() -> None:
    world = make_world()
    world.choose(Hero.PRINCESS)
    world.open_menu()

    assert state_of(world) is State.RUNNING

    simulate(world, 30)
    best = world.best_score
    world.update(world.config.restart_delay)
    world.open_menu()

    assert state_of(world) is State.MENU
    assert world.highlighted is Hero.PRINCESS
    assert world.obstacles == []
    assert world.distance == 0
    assert world.best_score == best > 0


def test_obstacle_kind_shapes_stay_within_global_limits() -> None:
    config = Config()

    assert set(KIND_SHAPES) == set(Kind)
    for aspect, min_height, max_height in KIND_SHAPES.values():
        assert config.obstacle_min_height <= min_height < max_height <= config.obstacle_max_height
        assert config.obstacle_min_width <= aspect * min_height
        assert aspect * max_height <= config.obstacle_max_width


def test_spawned_obstacles_cover_all_kinds_with_their_shapes() -> None:
    world = running_world(seed=1)
    spawned: dict[int, Obstacle] = {}
    for _ in range(round(60 / DT)):
        if autopilot_wants_jump(world):
            world.jump()
        world.update(DT)
        spawned.update((id(o), o) for o in world.obstacles)

    assert {o.kind for o in spawned.values()} == set(Kind)
    for obstacle in spawned.values():
        aspect, min_height, max_height = KIND_SHAPES[obstacle.kind]
        assert min_height <= obstacle.height <= max_height
        assert obstacle.width == pytest.approx(aspect * obstacle.height)
        assert 0.0 <= obstacle.seed < 1.0


def test_proximity_rises_as_obstacle_approaches_and_fades_after_passing() -> None:
    world = running_world(NO_OBSTACLES)
    config = world.config
    front = config.player_x + config.player_width

    def at(x: float) -> float:
        return world.proximity(Obstacle(x=x, width=40, height=40, kind=Kind.FLYTRAP, seed=0.0))

    assert at(front + 1000) == 0.0
    assert at(front + 130) == pytest.approx(0.5)
    assert at(front) == pytest.approx(1.0)
    assert at(config.player_x - 20) == pytest.approx(1.0)
    assert at(-1000) == 0.0


def test_speed_grows_by_five_pixels_per_second_squared() -> None:
    world = running_world(NO_OBSTACLES)

    simulate(world, 60)

    assert world.speed == pytest.approx(360 + 5 * 60, abs=0.5)


def test_crash_remembers_the_obstacle_that_was_hit() -> None:
    world = running_world(NO_OBSTACLES)
    config = world.config
    rock = Obstacle(x=config.player_x + 20, width=100, height=80, kind=Kind.ROCK, seed=0.0)
    world.obstacles = [rock]

    world.update(DT)

    assert state_of(world) is State.GAME_OVER
    assert world.crash is rock

    world.update(config.restart_delay)
    world.restart()

    assert world.crash is None


def test_menu_cannot_skip_the_crash_scene() -> None:
    world = running_world(NO_OBSTACLES)
    config = world.config
    world.obstacles = [
        Obstacle(x=config.player_x + 20, width=100, height=80, kind=Kind.ROCK, seed=0.0)
    ]
    world.update(DT)

    world.open_menu()

    assert state_of(world) is State.GAME_OVER

    world.update(config.restart_delay)
    world.open_menu()

    assert state_of(world) is State.MENU


@pytest.mark.parametrize("kind", list(Kind))
def test_every_obstacle_leaves_at_least_a_tenth_of_a_second_to_time_the_jump(kind: Kind) -> None:
    config = Config()
    aspect, _, max_height = KIND_SHAPES[kind]
    width = aspect * max_height
    clearance = max_height - config.hitbox_inset
    velocity, gravity = config.jump_velocity, config.gravity
    root = math.sqrt(velocity * velocity - 2 * gravity * clearance)
    above = 2 * root / gravity
    for speed in (config.start_speed, config.max_speed):
        overlap = (width + config.player_width - 2 * config.hitbox_inset) / speed
        assert above - overlap >= 0.1
