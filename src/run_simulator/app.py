import gc
import os
import random

import pygame
from pygame._sdl2 import video

from run_simulator.layout import change_hero_button, hero_at
from run_simulator.render import LOGICAL_SIZE, Renderer
from run_simulator.world import Config, State, World

WINDOW_SIZE = LOGICAL_SIZE
TITLE = "Run Simulator"
STEP = 1 / 120
MAX_STEPS = 8
MAX_FPS = 240
SNAP = 0.002
ENTER_KEYS = (pygame.K_RETURN, pygame.K_KP_ENTER)


class App:
    def __init__(self, rng: random.Random | None = None, vsync: bool = True) -> None:
        self.window = pygame.Window(TITLE, WINDOW_SIZE, allow_high_dpi=True)
        os.environ.setdefault("SDL_RENDER_SCALE_QUALITY", "linear")
        self.gpu = video.Renderer(self.window, vsync=vsync)
        self.world = World(Config(view_width=WINDOW_SIZE[0]), rng or random.Random())
        self._renderer = Renderer(self.gpu)
        gc.collect()
        gc.freeze()
        self._clock = pygame.time.Clock()
        self._backlog = 0.0

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type in (pygame.QUIT, pygame.WINDOWCLOSE):
            return False
        if self.world.state is State.MENU:
            self._handle_menu(event)
        elif self.world.state is State.RUNNING:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                self.world.jump()
        else:
            self._handle_game_over(event)
        return True

    def process_events(self) -> bool:
        return all([self.handle_event(event) for event in pygame.event.get()])

    def advance(self, elapsed: float) -> int:
        self._backlog = min(self._backlog + elapsed, MAX_STEPS * STEP)
        steps = int((self._backlog + SNAP) / STEP)
        self._backlog -= steps * STEP
        for _ in range(steps):
            self.world.update(STEP)
            self._renderer.update(self.world, STEP)
        self._present()
        return steps

    def step(self, dt: float = STEP) -> None:
        self.world.update(dt)
        self._renderer.update(self.world, dt)
        self._present()

    def _present(self) -> None:
        self._renderer.draw(self.world, pygame.mouse.get_pos())
        self.gpu.present()

    def snapshot(self) -> pygame.Surface:
        self._renderer.draw(self.world, pygame.mouse.get_pos())
        return self.gpu.to_surface()

    def loop(self) -> None:
        while self.process_events():
            self.advance(self._clock.tick(MAX_FPS) / 1000)

    def _handle_menu(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_LEFT:
                self.world.highlight_next(-1)
            elif event.key == pygame.K_RIGHT:
                self.world.highlight_next(1)
            elif event.key in ENTER_KEYS:
                self.world.choose(self.world.highlighted)
        elif event.type == pygame.MOUSEMOTION:
            hero = hero_at(WINDOW_SIZE, event.pos)
            if hero is not None:
                self.world.highlight(hero)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hero = hero_at(WINDOW_SIZE, event.pos)
            if hero is not None:
                self.world.choose(hero)

    def _handle_game_over(self, event: pygame.event.Event) -> None:
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE:
                self.world.restart()
            elif event.key in ENTER_KEYS:
                self.world.open_menu()
        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
            and change_hero_button(WINDOW_SIZE).collidepoint(event.pos)
        ):
            self.world.open_menu()


def run() -> int:
    pygame.init()
    try:
        App().loop()
    finally:
        pygame.quit()
    return 0
