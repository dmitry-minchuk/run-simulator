import math
from collections import OrderedDict
from dataclasses import dataclass

import pygame
from pygame._sdl2 import video

from run_simulator.animation import Animator, Mode, Motion
from run_simulator.assets import ASSETS, load_backdrop, load_sheet
from run_simulator.heroes import HEROES
from run_simulator.layout import change_hero_button, hero_cards
from run_simulator.world import Kind, Obstacle, State, World

Color = tuple[int, int, int]

LOGICAL_SIZE = (960, 540)
GROUND_Y = 440
TEXT: Color = (255, 255, 255)
SHADOW: Color = (42, 26, 20)
CARD: Color = (40, 60, 40)
CARD_ACTIVE: Color = (70, 120, 60)
HIGHLIGHT: Color = (255, 200, 61)
BUTTON: Color = (60, 140, 70)
BUTTON_HOVER: Color = (90, 180, 90)
OBSTACLE_FPS = 6.0
BITE_BOOST = 2.0
OVERLAY_FADE = 0.3
HAZE: Color = (236, 244, 252)
HAZE_SKY = 96
HAZE_GROUND = 40
HAZE_BLEND = 20
BLEND = pygame.BLENDMODE_BLEND
MODES = {State.MENU: Mode.IDLE, State.RUNNING: Mode.RUN, State.GAME_OVER: Mode.HIT}
BITERS = (Kind.FLYTRAP, Kind.PITCHER, Kind.ROSE)
SWAY = {
    Kind.FLYTRAP: 2.5,
    Kind.PITCHER: 1.5,
    Kind.ROSE: 2.5,
    Kind.STUMP: 0.0,
    Kind.CACTUS: 1.2,
    Kind.ROCK: 0.0,
}


@dataclass
class Sheet:
    frames: dict[str, list[video.Texture]]
    anchor: tuple[float, float]
    size: tuple[float, float]


def scene_frame(world: World, count: int) -> int:
    progress = world.time_since_game_over / world.config.restart_delay
    return min(count - 1, int(progress * count))


def crash_pose(kind: Kind, t: float, start_altitude: float) -> tuple[float, float, float]:
    t = min(1.0, max(0.0, t))
    dx, lift, angle = crash_motion(kind, t)
    altitude = start_altitude * (1 - t * t) - lift
    return dx, max(0.0, altitude), angle


def crash_motion(kind: Kind, t: float) -> tuple[float, float, float]:
    arc = math.sin(math.pi * min(1.0, t))
    if kind is Kind.FLYTRAP:
        return -110 * t, -130 * arc, -20 * arc
    if kind is Kind.PITCHER:
        return -30 * t + 6 * math.sin(40 * t) * arc, -90 * arc, 0.0
    if kind is Kind.ROSE:
        return -50 * t, -60 * arc, -10 * arc
    if kind is Kind.STUMP:
        return 90 * t, -60 * arc, 25 * arc
    if kind is Kind.CACTUS:
        return -30 * t, -170 * arc, 0.0
    return -70 * t, -45 * arc, -15 * arc


class Renderer:
    def __init__(self, gpu: video.Renderer) -> None:
        self.gpu = gpu
        viewport = gpu.get_viewport()
        self.size = (viewport.width, viewport.height)
        self.scale = viewport.width / LOGICAL_SIZE[0]
        self._time = 0.0
        self._white = self._texture(self._surface_filled((4, 4), (255, 255, 255, 255)))
        self._haze = self._build_haze()
        backdrop = load_backdrop(self.scale)
        self._sky = self._texture(backdrop.sky)
        self._hills = self._texture(backdrop.hills)
        self._ground = self._texture(backdrop.ground)
        self._parallax = backdrop.parallax
        self._ground_overhang = backdrop.ground_overhang
        self._heroes = {
            hero: self._sheet("heroes", hero.name.lower(), self.scale) for hero in HEROES
        }
        self._previews = {
            hero: self._sheet("heroes", hero.name.lower(), self.scale * 1.6, ("run", "idle"))
            for hero in HEROES
        }
        self._obstacles = {
            kind: self._sheet("obstacles", kind.name.lower(), self.scale) for kind in Kind
        }
        self._text_cache: OrderedDict[tuple[str, int], video.Texture] = OrderedDict()
        self._panel_cache: dict[tuple[object, ...], video.Texture] = {}
        self._fonts = {
            size: pygame.font.Font(None, round(size * self.scale)) for size in (30, 40, 80)
        }
        self._animator = Animator()
        self._preview_animators = {hero: Animator() for hero in HEROES}
        self._phases: dict[int, float] = {}

    def _texture(self, surface: pygame.Surface) -> video.Texture:
        texture = video.Texture.from_surface(self.gpu, surface)
        texture.blend_mode = BLEND
        return texture

    @staticmethod
    def _surface_filled(size: tuple[int, int], color: tuple[int, int, int, int]) -> pygame.Surface:
        surface = pygame.Surface(size, pygame.SRCALPHA)
        surface.fill(color)
        return surface

    def _sheet(
        self, group: str, name: str, scale: float, sequences: tuple[str, ...] | None = None
    ) -> Sheet:
        sheet = load_sheet(ASSETS / group / name, scale, sequences)
        frames = {
            key: [self._texture(frame) for frame in images] for key, images in sheet.frames.items()
        }
        return Sheet(frames, sheet.anchor, sheet.size)

    def update(self, world: World, dt: float) -> None:
        self._time += dt
        config = world.config
        self._animator.update(
            dt,
            Motion(
                mode=MODES[world.state],
                on_ground=world.player.on_ground,
                vertical_velocity=world.player.velocity,
                jump_velocity=config.jump_velocity,
                speed=world.speed,
                start_speed=config.start_speed,
            ),
        )
        for hero, animator in self._preview_animators.items():
            active = world.state is State.MENU and hero is world.highlighted
            animator.update(
                dt,
                Motion(
                    mode=Mode.RUN if active else Mode.IDLE,
                    on_ground=True,
                    vertical_velocity=0.0,
                    jump_velocity=config.jump_velocity,
                    speed=config.start_speed,
                    start_speed=config.start_speed,
                ),
            )
        alive = {id(obstacle): obstacle for obstacle in world.obstacles}
        self._phases = {key: phase for key, phase in self._phases.items() if key in alive}
        if world.state is State.GAME_OVER:
            return
        for key, obstacle in alive.items():
            rate = OBSTACLE_FPS
            if obstacle.kind in BITERS:
                rate *= 1 + BITE_BOOST * world.proximity(obstacle)
            self._phases[key] = self._phases.get(key, obstacle.seed * 4) + dt * rate

    def draw(self, world: World, pointer: tuple[int, int]) -> None:
        self.gpu.draw_color = (0, 0, 0, 255)
        self.gpu.clear()
        self._draw_backdrop(world.distance)
        for obstacle in world.obstacles:
            self._draw_obstacle(world, obstacle)
        if world.state is State.MENU:
            self._draw_menu(world)
            return
        self._draw_hero(world)
        self._draw_hud(world)
        crash_time = world.config.restart_delay
        if world.state is State.GAME_OVER and world.time_since_game_over >= crash_time:
            fade = min(1.0, (world.time_since_game_over - crash_time) / OVERLAY_FADE)
            self._draw_game_over(world, pointer, fade)

    def _draw(
        self,
        texture: video.Texture,
        x: float,
        y: float,
        width: float | None = None,
        height: float | None = None,
        angle: float = 0.0,
        origin: tuple[float, float] | None = None,
        alpha: int = 255,
    ) -> None:
        texture.alpha = alpha
        rect = pygame.FRect(
            x,
            y,
            width if width is not None else texture.width,
            height if height is not None else texture.height,
        )
        pivot = None if origin is None else (round(origin[0]), round(origin[1]))
        texture.draw(dstrect=rect, angle=angle, origin=pivot)

    def _fill(self, rect: pygame.FRect, color: tuple[int, int, int], alpha: int) -> None:
        self._white.color = color
        self._draw(self._white, rect.x, rect.y, rect.width, rect.height, alpha=alpha)
        self._white.color = (255, 255, 255)

    def _tile(self, texture: video.Texture, offset: float, top: float) -> None:
        width = texture.width
        x = -((offset * self.scale) % width)
        while x < self.size[0]:
            self._draw(texture, x, top)
            x += width

    def _build_haze(self) -> video.Texture:
        height = self.size[1]
        surface = pygame.Surface((4, height), pygame.SRCALPHA)
        ground = GROUND_Y * self.scale
        blend = HAZE_BLEND * self.scale
        for y in range(height):
            t = min(1.0, max(0.0, (y - ground + blend) / (2 * blend)))
            alpha = round(HAZE_SKY + (HAZE_GROUND - HAZE_SKY) * t)
            surface.fill((*HAZE, alpha), pygame.Rect(0, y, 4, 1))
        return self._texture(surface)

    def _draw_layers(self, distance: float) -> None:
        self._tile(self._sky, distance * self._parallax["sky"] + self._time * 4, 0.0)
        ground = GROUND_Y * self.scale
        self._tile(
            self._hills,
            distance * self._parallax["hills"],
            ground - self._hills.height + 20 * self.scale,
        )
        self._tile(self._ground, distance, ground - self._ground_overhang * self.scale)

    def _draw_backdrop(self, distance: float) -> None:
        self._draw_layers(distance)
        self._draw(self._haze, 0.0, 0.0, self.size[0], self.size[1])

    def _obstacle_frame(
        self, world: World, obstacle: Obstacle, sheet: Sheet
    ) -> tuple[video.Texture, str]:
        crashed = world.crash is obstacle and world.state is State.GAME_OVER
        if crashed and "react" in sheet.frames:
            frames = sheet.frames["react"]
            index = scene_frame(world, len(frames))
            return frames[index], "react"
        frames = sheet.frames["loop"]
        return frames[int(self._phases.get(id(obstacle), obstacle.seed * 4)) % len(frames)], "loop"

    def _draw_obstacle(self, world: World, obstacle: Obstacle) -> None:
        sheet = self._obstacles[obstacle.kind]
        texture, _ = self._obstacle_frame(world, obstacle, sheet)
        factor = obstacle.height / sheet.size[1]
        width, height = texture.width * factor, texture.height * factor
        anchor_x, anchor_y = sheet.anchor[0] * factor, sheet.anchor[1] * factor
        left = obstacle.x * self.scale - anchor_x
        top = GROUND_Y * self.scale - anchor_y
        phase = self._time * 1.3 + obstacle.seed * math.tau
        sway = SWAY[obstacle.kind] * math.sin(phase)
        breath = 1 + 0.015 * math.sin(phase * 1.7)
        stretched = height * breath
        base_x = left + anchor_x + obstacle.width * self.scale / 2
        self._draw(
            texture,
            left,
            top - (stretched - height),
            width,
            stretched,
            angle=sway,
            origin=(base_x - left, stretched),
        )

    def _hero_texture(self, world: World, sheet: Sheet) -> video.Texture:
        if world.state is State.GAME_OVER and world.crash is not None:
            frames = sheet.frames[f"hit_{world.crash.kind.name.lower()}"]
            index = scene_frame(world, len(frames))
            return frames[index]
        frame = self._animator.sprite()
        return sheet.frames[frame.sequence][frame.index]

    def _draw_hero(self, world: World) -> None:
        config = world.config
        sheet = self._heroes[world.hero]
        center_x = (config.player_x + config.player_width / 2) * self.scale
        altitude = world.player.altitude
        angle = 0.0
        if world.state is State.GAME_OVER and world.crash is not None:
            t = world.time_since_game_over / config.restart_delay
            dx, altitude, angle = crash_pose(world.crash.kind, t, altitude)
            center_x += dx * self.scale
        feet_y = (GROUND_Y - altitude) * self.scale
        shadow_width = 80 * self.scale * max(0.35, 1 - altitude / 320)
        self._fill_ellipse(
            center_x, GROUND_Y * self.scale + 2 * self.scale, shadow_width, 12 * self.scale
        )
        texture = self._hero_texture(world, sheet)
        sx, sy = self._animator.squash()
        width, height = texture.width * sx, texture.height * sy
        anchor_x, anchor_y = sheet.anchor[0] * sx, sheet.anchor[1] * sy
        self._draw(
            texture,
            center_x - anchor_x,
            feet_y - anchor_y,
            width,
            height,
            angle=angle,
            origin=(anchor_x, anchor_y - 40 * self.scale),
        )

    def _fill_ellipse(self, cx: float, cy: float, width: float, height: float) -> None:
        key = ("shadow",)
        texture = self._panel_cache.get(key)
        if texture is None:
            surface = pygame.Surface((128, 24), pygame.SRCALPHA)
            pygame.draw.ellipse(surface, (40, 50, 30, 90), surface.get_rect())
            texture = self._texture(surface)
            self._panel_cache[key] = texture
        self._draw(texture, cx - width / 2, cy - height / 2, width, height)

    def _text(self, text: str, size: int, color: Color = TEXT) -> video.Texture:
        key = (f"{text}|{color}", size)
        texture = self._text_cache.get(key)
        if texture is None:
            texture = self._texture(self._fonts[size].render(text, True, color))
            self._text_cache[key] = texture
            if len(self._text_cache) > 256:
                self._text_cache.popitem(last=False)
        else:
            self._text_cache.move_to_end(key)
        return texture

    def _draw_text(
        self, text: str, size: int, anchor: str, x: float, y: float, alpha: int = 255
    ) -> None:
        image = self._text(text, size)
        shadow = self._text(text, size, SHADOW)
        width, height = image.width, image.height
        px, py = x * self.scale, y * self.scale
        if anchor == "center":
            px, py = px - width / 2, py - height / 2
        elif anchor == "topright":
            px -= width
        offset = 2 * self.scale
        self._draw(shadow, px + offset, py + offset, alpha=alpha)
        self._draw(image, px, py, alpha=alpha)

    def _panel(
        self, size: tuple[int, int], fill: Color, border: Color | None, radius: int, width: int = 0
    ) -> video.Texture:
        key = (size, fill, border, radius, width)
        texture = self._panel_cache.get(key)
        if texture is None:
            surface = pygame.Surface(size, pygame.SRCALPHA)
            rect = surface.get_rect()
            pygame.draw.rect(surface, (*fill, 235), rect, border_radius=radius)
            if border is not None:
                pygame.draw.rect(surface, border, rect, width=width, border_radius=radius)
            texture = self._texture(surface)
            self._panel_cache[key] = texture
        return texture

    def _draw_panel(
        self, rect: pygame.Rect, fill: Color, border: Color | None, alpha: int = 255
    ) -> None:
        size = (round(rect.width * self.scale), round(rect.height * self.scale))
        texture = self._panel(
            size, fill, border, round(18 * self.scale), max(2, round(4 * self.scale))
        )
        self._draw(texture, rect.x * self.scale, rect.y * self.scale, alpha=alpha)

    def _draw_counter(self, label: str, value: int, right: float, top: float) -> None:
        digits = str(value)
        widths = [self._text(digit, 30).width for digit in digits]
        x = right * self.scale - sum(widths)
        offset = 2 * self.scale
        for digit, width in zip(digits, widths, strict=True):
            self._draw(self._text(digit, 30, SHADOW), x + offset, top * self.scale + offset)
            self._draw(self._text(digit, 30), x, top * self.scale)
            x += width
        label_width = self._text(label, 30).width
        self._draw_text(
            label, 30, "topleft", (right * self.scale - sum(widths) - label_width) / self.scale, top
        )

    def _draw_hud(self, world: World) -> None:
        right = LOGICAL_SIZE[0] - 20
        self._draw_counter("Score: ", world.score, right, 16)
        self._draw_counter("Best: ", world.best_score, right, 46)
        self._draw_counter("Speed: ", round(world.speed), right, 76)

    def _draw_menu(self, world: World) -> None:
        self._fill(pygame.FRect(0, 0, *self.size), (20, 30, 20), 90)
        self._draw_text("Choose your hero", 80, "center", LOGICAL_SIZE[0] / 2, 60)
        for hero, card in hero_cards(LOGICAL_SIZE).items():
            active = hero is world.highlighted
            self._draw_panel(card, CARD_ACTIVE if active else CARD, HIGHLIGHT if active else None)
            sheet = self._previews[hero]
            frame = self._preview_animators[hero].sprite()
            texture = sheet.frames[frame.sequence][frame.index]
            ground = (card.bottom - 64) * self.scale
            self._fill_ellipse(card.centerx * self.scale, ground, 150 * self.scale, 18 * self.scale)
            anchor_x, anchor_y = sheet.anchor
            self._draw(texture, card.centerx * self.scale - anchor_x, ground - anchor_y)
            self._draw_text(hero.title, 40, "center", card.centerx, card.bottom - 32)
        self._draw_text(
            "Arrows or mouse to choose, Enter or click to start",
            30,
            "center",
            LOGICAL_SIZE[0] / 2,
            LOGICAL_SIZE[1] - 40,
        )
        self._draw_text(f"Best: {world.best_score}", 30, "topright", LOGICAL_SIZE[0] - 20, 16)

    def _draw_game_over(self, world: World, pointer: tuple[int, int], fade: float) -> None:
        alpha = round(255 * fade)
        self._fill(pygame.FRect(0, 0, *self.size), (20, 30, 20), round(100 * fade))
        middle_x = LOGICAL_SIZE[0] / 2
        middle_y = LOGICAL_SIZE[1] / 2
        self._draw_text("Game over", 80, "center", middle_x, middle_y - 110, alpha)
        self._draw_text(
            f"Score: {world.score}    Best: {world.best_score}",
            40,
            "center",
            middle_x,
            middle_y - 45,
            alpha,
        )
        if world.can_restart:
            self._draw_text("Space to play again", 30, "center", middle_x, middle_y + 5, alpha)
        button = change_hero_button(LOGICAL_SIZE)
        hovered = button.collidepoint(pointer)
        self._draw_panel(button, BUTTON_HOVER if hovered else BUTTON, HIGHLIGHT, alpha)
        self._draw_text("Change hero (Enter)", 30, "center", button.centerx, button.centery, alpha)
