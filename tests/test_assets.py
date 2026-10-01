import json
from collections.abc import Iterator

import pygame
import pytest

from run_simulator.animation import SEQUENCE_LENGTHS
from run_simulator.assets import ASSETS, load_backdrop, load_sheet
from run_simulator.heroes import HEROES, Hero
from run_simulator.world import KIND_SHAPES, Config, Kind

CONFIG = Config()
CRASHES = {f"hit_{kind.name.lower()}" for kind in Kind}


@pytest.fixture(scope="module", autouse=True)
def display() -> Iterator[None]:
    pygame.init()
    pygame.display.set_mode((4, 4))
    yield
    pygame.quit()


def bounds(image: pygame.Surface) -> pygame.Rect:
    return image.get_bounding_rect(min_alpha=128)


@pytest.mark.parametrize("hero", HEROES)
def test_hero_sheet_has_every_animation_and_crash_reaction(hero: Hero) -> None:
    sheet = load_sheet(ASSETS / "heroes" / hero.name.lower(), 1.0)
    lengths = {name: len(frames) for name, frames in sheet.frames.items()}

    assert {name: lengths[name] for name in SEQUENCE_LENGTHS} == SEQUENCE_LENGTHS
    assert set(lengths) >= CRASHES
    assert all(lengths[name] == 4 for name in CRASHES)
    assert len({frame.get_size() for frames in sheet.frames.values() for frame in frames}) == 1


@pytest.mark.parametrize("hero", HEROES)
def test_running_hero_matches_hitbox_and_stands_on_the_anchor(hero: Hero) -> None:
    sheet = load_sheet(ASSETS / "heroes" / hero.name.lower(), 1.0)
    anchor_x, anchor_y = sheet.anchor
    heights = []
    for frame in sheet.frames["run"]:
        rect = bounds(frame)
        heights.append(rect.height)
        assert abs(anchor_y - rect.bottom) <= 3
        assert rect.left < anchor_x < rect.right
    assert max(heights) == pytest.approx(CONFIG.player_height, abs=4)
    assert min(heights) >= CONFIG.player_height * 0.85


@pytest.mark.parametrize("kind", list(Kind))
def test_obstacle_sheet_matches_its_hitbox_shape(kind: Kind) -> None:
    sheet = load_sheet(ASSETS / "obstacles" / kind.name.lower(), 1.0)
    aspect, _, max_height = KIND_SHAPES[kind]
    width, height = sheet.size

    assert height == pytest.approx(max_height)
    assert width / height == pytest.approx(aspect, abs=0.03)
    assert len(sheet.frames["loop"]) == 4
    assert len(sheet.frames["react"]) == 4
    anchor_x, anchor_y = sheet.anchor
    rects = [bounds(frame) for frame in sheet.frames["loop"]]
    assert all(rect.bottom == pytest.approx(anchor_y, abs=3) for rect in rects)
    assert min(rect.height for rect in rects) == pytest.approx(height, abs=3)
    assert all(
        rect.centerx == pytest.approx(anchor_x + width / 2, abs=width * 0.25) for rect in rects
    )


def test_obstacle_loops_are_animated() -> None:
    for kind in Kind:
        frames = load_sheet(ASSETS / "obstacles" / kind.name.lower(), 1.0).frames["loop"]
        distinct = {pygame.image.tobytes(frame, "RGBA") for frame in frames}
        assert len(distinct) == len(frames)


def test_background_layers_cover_the_view_and_tile() -> None:
    backdrop = load_backdrop(1.0)
    metadata = json.loads((ASSETS / "background" / "layers.json").read_text())

    assert backdrop.sky.get_height() == 540
    assert backdrop.sky.get_width() >= 960
    assert backdrop.hills.get_width() >= 960
    assert backdrop.ground.get_width() >= 960
    assert 0 < backdrop.parallax["sky"] < backdrop.parallax["hills"] < 1
    overhang = metadata["ground"]["overhang"]
    assert 0 < overhang < backdrop.ground.get_height()
    assert backdrop.ground.get_height() - overhang >= 540 - 440
