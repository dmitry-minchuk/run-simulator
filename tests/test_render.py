import random
from collections.abc import Callable, Iterator
from itertools import pairwise

import pygame
import pytest
from pygame._sdl2 import video

from run_simulator.heroes import Hero
from run_simulator.render import GROUND_Y, Renderer, crash_pose
from run_simulator.world import Config, Kind, Obstacle, State, World


@pytest.fixture
def gpu() -> Iterator[video.Renderer]:
    pygame.init()
    window = pygame.Window("test", (960, 540))
    yield video.Renderer(window)
    pygame.quit()


def running_world() -> World:
    world = World(Config(first_obstacle_delay=1e9), random.Random(0))
    world.choose(Hero.FOOTBALLER)
    return world


def painted_rows(
    gpu: video.Renderer,
    renderer: Renderer,
    world: World,
    draw: Callable[[], None],
    columns: range,
) -> list[int]:
    gpu.clear()
    renderer._draw_backdrop(world.distance)
    reference = gpu.to_surface()
    gpu.clear()
    renderer._draw_backdrop(world.distance)
    draw()
    frame = gpu.to_surface()
    return [
        y
        for y in range(frame.get_height())
        if any(frame.get_at((x, y)) != reference.get_at((x, y)) for x in columns)
    ]


def test_renderer_uses_the_window_resolution(gpu: video.Renderer) -> None:
    renderer = Renderer(gpu)

    assert renderer.scale == 1
    assert renderer.size == (960, 540)


def test_obstacle_is_drawn_standing_on_the_ground_at_its_height(gpu: video.Renderer) -> None:
    world = running_world()
    obstacle = Obstacle(x=600.0, width=0.6 * 110, height=110.0, kind=Kind.CACTUS, seed=0.0)
    world.obstacles = [obstacle]
    renderer = Renderer(gpu)
    columns = range(round(obstacle.x), round(obstacle.x + obstacle.width))

    rows = painted_rows(
        gpu, renderer, world, lambda: renderer._draw_obstacle(world, obstacle), columns
    )

    assert min(rows) == pytest.approx(GROUND_Y - obstacle.height, abs=6)
    assert max(rows) == pytest.approx(GROUND_Y, abs=6)


def test_hero_is_drawn_at_its_altitude(gpu: video.Renderer) -> None:
    world = running_world()
    renderer = Renderer(gpu)
    columns = range(
        round(world.config.player_x), round(world.config.player_x + world.config.player_width)
    )

    grounded = painted_rows(gpu, renderer, world, lambda: renderer._draw_hero(world), columns)
    world.player.altitude = 150
    airborne = painted_rows(gpu, renderer, world, lambda: renderer._draw_hero(world), columns)

    assert GROUND_Y - 135 <= min(grounded) <= GROUND_Y - 95
    assert min(airborne) == pytest.approx(min(grounded) - 150, abs=3)


def test_crash_plays_the_reaction_of_the_obstacle_that_was_hit(gpu: video.Renderer) -> None:
    world = running_world()
    rock = Obstacle(x=world.config.player_x + 30, width=110, height=84, kind=Kind.ROCK, seed=0.0)
    world.obstacles = [rock]
    world.update(1 / 120)
    renderer = Renderer(gpu)
    sheet = renderer._heroes[Hero.FOOTBALLER]

    assert world.state is State.GAME_OVER
    assert renderer._hero_texture(world, sheet) is sheet.frames["hit_rock"][0]
    assert renderer._obstacle_frame(world, rock, renderer._obstacles[Kind.ROCK])[1] == "react"

    world.update(world.config.restart_delay)

    assert renderer._hero_texture(world, sheet) is sheet.frames["hit_rock"][-1]


def test_game_over_panel_appears_only_after_the_crash_scene(
    gpu: video.Renderer, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = running_world()
    world.obstacles = [
        Obstacle(x=world.config.player_x + 30, width=110, height=84, kind=Kind.ROCK, seed=0.0)
    ]
    world.update(1 / 120)
    renderer = Renderer(gpu)
    drawn: list[float] = []
    monkeypatch.setattr(
        renderer, "_draw_game_over", lambda _world, _pointer, fade: drawn.append(fade)
    )

    renderer.draw(world, (0, 0))
    world.update(world.config.restart_delay + 0.15)
    renderer.draw(world, (0, 0))
    world.update(1.0)
    renderer.draw(world, (0, 0))

    assert drawn == [pytest.approx(0.5, abs=0.02), 1.0]


def test_carnivorous_plants_bite_faster_when_runner_is_near(gpu: video.Renderer) -> None:
    world = running_world()
    config = world.config
    far = Obstacle(x=900.0, width=70, height=120, kind=Kind.FLYTRAP, seed=0.0)
    near = Obstacle(
        x=config.player_x + config.player_width + 5,
        width=70,
        height=120,
        kind=Kind.PITCHER,
        seed=0.0,
    )
    world.obstacles = [far, near]
    renderer = Renderer(gpu)

    renderer.update(world, 0.5)

    assert renderer._phases[id(near)] > renderer._phases[id(far)] > 0


@pytest.mark.parametrize("kind", list(Kind))
def test_each_obstacle_kind_plays_its_own_crash_reaction(gpu: video.Renderer, kind: Kind) -> None:
    world = running_world()
    world.obstacles = [
        Obstacle(x=world.config.player_x + 30, width=90, height=90, kind=kind, seed=0.0)
    ]
    world.update(1 / 120)
    renderer = Renderer(gpu)
    sheet = renderer._heroes[Hero.FOOTBALLER]
    frames = sheet.frames[f"hit_{kind.name.lower()}"]

    seen = []
    for _ in range(12):
        seen.append(renderer._hero_texture(world, sheet))
        world.update(world.config.restart_delay / 12)

    assert world.crash is not None and world.crash.kind is kind
    assert [texture for texture in frames if texture in seen] == frames


@pytest.mark.parametrize("kind", list(Kind))
@pytest.mark.parametrize("altitude", [0.0, 160.0])
def test_crash_motion_is_continuous_and_ends_on_the_ground(kind: Kind, altitude: float) -> None:
    steps = 600
    poses = [crash_pose(kind, i / steps, altitude) for i in range(steps + 1)]

    assert poses[0][1] == pytest.approx(altitude, abs=1e-6)
    assert poses[-1][1] == pytest.approx(0.0, abs=1e-6)
    for before, after in pairwise(poses):
        assert abs(after[0] - before[0]) < 3
        assert abs(after[1] - before[1]) < 3
        assert abs(after[2] - before[2]) < 3


def test_background_is_hazed_but_hero_and_obstacles_stay_vivid(gpu: video.Renderer) -> None:
    world = running_world()
    obstacle = Obstacle(x=600.0, width=0.795 * 120, height=120.0, kind=Kind.FLYTRAP, seed=0.0)
    world.obstacles = [obstacle]
    renderer = Renderer(gpu)

    def frame(backdrop: Callable[[float], None]) -> pygame.Surface:
        gpu.clear()
        backdrop(world.distance)
        renderer._draw_obstacle(world, obstacle)
        renderer._draw_hero(world)
        return gpu.to_surface()

    plain = frame(renderer._draw_layers)
    hazed = frame(renderer._draw_backdrop)

    def lightness(pixel: pygame.Color) -> int:
        return pixel.r + pixel.g + pixel.b

    def saturation(pixel: pygame.Color) -> int:
        return max(pixel.r, pixel.g, pixel.b) - min(pixel.r, pixel.g, pixel.b)

    for point in ((40, 200), (900, 390), (400, 300)):
        before, after = plain.get_at(point), hazed.get_at(point)
        assert lightness(after) > lightness(before)
        assert saturation(after) < saturation(before)
    sky_gain = lightness(hazed.get_at((900, 390))) - lightness(plain.get_at((900, 390)))
    ground_gain = lightness(hazed.get_at((900, 520))) - lightness(plain.get_at((900, 520)))
    assert 0 < ground_gain < sky_gain

    def close(a: pygame.Color, b: pygame.Color) -> bool:
        return all(abs(a[i] - b[i]) <= 8 for i in range(3))

    def foreground_on(color: tuple[int, int, int, int]) -> pygame.Surface:
        gpu.draw_color = color
        gpu.clear()
        renderer._draw_obstacle(world, obstacle)
        renderer._draw_hero(world)
        return gpu.to_surface()

    on_black = foreground_on((0, 0, 0, 255))
    on_magenta = foreground_on((255, 0, 255, 255))
    opaque = [
        (x, y)
        for x in range(0, 960, 3)
        for y in range(200, 450, 3)
        if close(on_black.get_at((x, y)), on_magenta.get_at((x, y)))
    ]
    assert len(opaque) > 500
    assert all(close(plain.get_at(point), hazed.get_at(point)) for point in opaque)
