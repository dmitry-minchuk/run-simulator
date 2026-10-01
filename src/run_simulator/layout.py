import pygame

from run_simulator.heroes import HEROES, Hero

CARD_SIZE = (260, 300)
CARD_GAP = 60
BUTTON_SIZE = (300, 50)


def hero_cards(screen_size: tuple[int, int]) -> dict[Hero, pygame.Rect]:
    width, height = screen_size
    total = len(HEROES) * CARD_SIZE[0] + (len(HEROES) - 1) * CARD_GAP
    left = (width - total) // 2
    top = (height - CARD_SIZE[1]) // 2 + 10
    return {
        hero: pygame.Rect(left + index * (CARD_SIZE[0] + CARD_GAP), top, *CARD_SIZE)
        for index, hero in enumerate(HEROES)
    }


def hero_at(screen_size: tuple[int, int], position: tuple[int, int]) -> Hero | None:
    for hero, rect in hero_cards(screen_size).items():
        if rect.collidepoint(position):
            return hero
    return None


def change_hero_button(screen_size: tuple[int, int]) -> pygame.Rect:
    width, height = screen_size
    rect = pygame.Rect(0, 0, *BUTTON_SIZE)
    rect.center = (width // 2, height - 70)
    return rect
