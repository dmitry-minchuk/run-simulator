import pygame

from run_simulator.__main__ import main


def test_main_opens_game_and_returns_zero_when_window_closed() -> None:
    pygame.init()
    pygame.event.post(pygame.event.Event(pygame.QUIT))

    assert main() == 0
    assert not pygame.get_init()
