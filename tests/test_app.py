import random
from collections.abc import Callable, Iterator

import pygame
import pytest

from run_simulator.app import MAX_STEPS, STEP, TITLE, WINDOW_SIZE, App
from run_simulator.heroes import Hero
from run_simulator.layout import change_hero_button, hero_cards
from run_simulator.world import State


@pytest.fixture
def app() -> Iterator[App]:
    pygame.init()
    try:
        yield App(random.Random(0), vsync=False)
    finally:
        pygame.quit()


def post_key(key: int) -> None:
    pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=key))


def post_click(position: tuple[int, int], button: int = 1) -> None:
    pygame.event.post(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=button, pos=position))


def post_motion(position: tuple[int, int]) -> None:
    pygame.event.post(pygame.event.Event(pygame.MOUSEMOTION, pos=position, rel=(0, 0), buttons=()))


def state_of(app: App) -> State:
    return app.world.state


def start(app: App) -> None:
    post_key(pygame.K_RETURN)
    app.process_events()
    app.step(1 / 60)


def crash(app: App) -> None:
    while app.world.state is State.RUNNING:
        app.world.update(1 / 60)
    app.world.update(app.world.config.restart_delay)


def card_center(hero: Hero) -> tuple[int, int]:
    center = hero_cards(WINDOW_SIZE)[hero].center
    return (center[0], center[1])


def count_pixels(
    surface: pygame.Surface, rect: pygame.Rect, matches: Callable[[pygame.Color], bool]
) -> int:
    area = rect.clip(surface.get_rect())
    return sum(
        1
        for x in range(area.left, area.right)
        for y in range(area.top, area.bottom)
        if matches(surface.get_at((x, y)))
    )


def is_jersey_green(pixel: pygame.Color) -> bool:
    return pixel.g > 130 and pixel.g > pixel.r + 60 and pixel.g > pixel.b + 50


def is_dress_pink(pixel: pygame.Color) -> bool:
    return pixel.r > 220 and 120 < pixel.g < 190 and pixel.b > pixel.g + 15


def test_window_has_expected_size_and_title(app: App) -> None:
    assert app.window.size == WINDOW_SIZE
    assert app.snapshot().get_width() % WINDOW_SIZE[0] == 0
    assert app.window.title == TITLE


def test_space_does_not_start_the_run_from_menu(app: App) -> None:
    post_key(pygame.K_SPACE)

    assert app.process_events()
    assert state_of(app) is State.MENU


def test_arrows_move_highlight_and_enter_starts_with_it(app: App) -> None:
    post_key(pygame.K_RIGHT)
    app.process_events()

    assert app.world.highlighted is Hero.PRINCESS

    post_key(pygame.K_LEFT)
    post_key(pygame.K_LEFT)
    app.process_events()

    assert app.world.highlighted is Hero.PRINCESS
    assert state_of(app) is State.MENU

    post_key(pygame.K_KP_ENTER)
    app.process_events()

    assert state_of(app) is State.RUNNING
    assert app.world.hero is Hero.PRINCESS


def test_mouse_hover_highlights_and_click_starts_with_clicked_hero(app: App) -> None:
    post_motion(card_center(Hero.PRINCESS))
    app.process_events()

    assert app.world.highlighted is Hero.PRINCESS
    assert state_of(app) is State.MENU

    post_click(card_center(Hero.FOOTBALLER))
    app.process_events()

    assert state_of(app) is State.RUNNING
    assert app.world.hero is Hero.FOOTBALLER


def test_clicks_outside_cards_and_right_clicks_do_nothing_in_menu(app: App) -> None:
    post_click((5, 5))
    post_click(card_center(Hero.PRINCESS), button=3)
    post_motion((5, 5))
    app.process_events()

    assert state_of(app) is State.MENU
    assert app.world.highlighted is Hero.FOOTBALLER


def test_space_key_while_running_makes_runner_jump(app: App) -> None:
    start(app)
    post_key(pygame.K_SPACE)

    app.process_events()

    assert not app.world.player.on_ground


@pytest.mark.parametrize(
    "key", [pygame.K_UP, pygame.K_RIGHT, pygame.K_RETURN, pygame.K_w, pygame.K_ESCAPE]
)
def test_other_input_is_ignored_while_running(app: App, key: int) -> None:
    start(app)
    post_key(key)
    post_click(card_center(Hero.PRINCESS))

    assert app.process_events()
    assert state_of(app) is State.RUNNING
    assert app.world.player.on_ground
    assert app.world.hero is Hero.FOOTBALLER


def test_space_after_game_over_restarts_same_hero_after_delay(app: App) -> None:
    post_key(pygame.K_RIGHT)
    start(app)
    while app.world.state is State.RUNNING:
        app.world.update(1 / 60)
    post_key(pygame.K_SPACE)
    app.process_events()

    assert state_of(app) is State.GAME_OVER

    app.world.update(app.world.config.restart_delay)
    post_key(pygame.K_SPACE)
    app.process_events()

    assert state_of(app) is State.RUNNING
    assert app.world.hero is Hero.PRINCESS


def test_enter_after_game_over_opens_hero_menu(app: App) -> None:
    start(app)
    crash(app)
    post_key(pygame.K_RETURN)
    app.process_events()

    assert state_of(app) is State.MENU
    assert app.world.highlighted is Hero.FOOTBALLER


def test_change_hero_button_click_opens_menu_and_other_clicks_do_not(app: App) -> None:
    start(app)
    crash(app)
    post_click((5, 5))
    app.process_events()

    assert state_of(app) is State.GAME_OVER

    post_click(change_hero_button(WINDOW_SIZE).center)
    app.process_events()

    assert state_of(app) is State.MENU


def test_closing_window_stops_loop(app: App) -> None:
    pygame.event.post(pygame.event.Event(pygame.QUIT))

    assert not app.process_events()


def test_double_click_on_change_hero_button_does_not_start_a_run(app: App) -> None:
    post_key(pygame.K_RIGHT)
    start(app)
    crash(app)
    button = change_hero_button(WINDOW_SIZE).center
    post_click(button)
    post_click(button)
    post_motion(button)
    app.process_events()

    assert state_of(app) is State.MENU
    assert app.world.highlighted is Hero.PRINCESS


def test_change_hero_button_does_not_overlap_hero_cards() -> None:
    button = change_hero_button(WINDOW_SIZE)

    assert all(not button.colliderect(card) for card in hero_cards(WINDOW_SIZE).values())


def test_step_advances_world_and_draws_hero(app: App) -> None:
    start(app)
    config = app.world.config
    frame = app.snapshot()
    scale = frame.get_width() // WINDOW_SIZE[0]
    hero_area = pygame.Rect(
        int(config.player_x - 20) * scale,
        (440 - 140) * scale,
        int(config.player_width + 40) * scale,
        140 * scale,
    )

    assert app.world.distance > 0
    assert count_pixels(frame, hero_area, is_jersey_green) > 200


def test_menu_shows_both_hero_previews(app: App) -> None:
    app.step()
    frame = app.snapshot()
    scale = frame.get_width() // WINDOW_SIZE[0]
    cards = {
        hero: pygame.Rect(rect.x * scale, rect.y * scale, rect.width * scale, rect.height * scale)
        for hero, rect in hero_cards(WINDOW_SIZE).items()
    }

    assert count_pixels(frame, cards[Hero.FOOTBALLER], is_jersey_green) > 300
    assert count_pixels(frame, cards[Hero.PRINCESS], is_dress_pink) > 300
    assert count_pixels(frame, cards[Hero.PRINCESS], is_jersey_green) < 30


def test_jittery_frames_around_one_step_advance_exactly_one_step_each(app: App) -> None:
    start(app)
    intervals = [STEP * factor for factor in (0.85, 1.15, 0.9, 1.1, 0.95, 1.05, 1.0, 1.0)] * 4

    steps = [app.advance(interval) for interval in intervals]

    assert steps == [1] * len(intervals)


@pytest.mark.parametrize("refresh", [60, 90, 100, 120, 144, 165])
def test_simulated_time_matches_real_time_at_any_refresh_rate(app: App, refresh: int) -> None:
    start(app)
    frames = refresh * 5

    total = sum(app.advance(1 / refresh) for _ in range(frames))

    assert total * STEP == pytest.approx(frames / refresh, rel=0.01)


def test_long_frame_pause_is_limited_to_a_few_steps(app: App) -> None:
    start(app)
    elapsed = app.world.elapsed

    steps = app.advance(5.0)

    assert steps == MAX_STEPS
    assert app.world.elapsed == pytest.approx(elapsed + MAX_STEPS * STEP)


def test_frames_shorter_than_half_a_step_wait_for_the_next_frame(app: App) -> None:
    start(app)
    distance = app.world.distance

    assert app.advance(STEP * 0.4) == 0
    assert app.world.distance == distance
    assert app.advance(STEP * 0.7) == 1
    assert app.world.distance > distance


def test_window_close_event_stops_loop(app: App) -> None:
    pygame.event.post(pygame.event.Event(pygame.WINDOWCLOSE))

    assert not app.process_events()
