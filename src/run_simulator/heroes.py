from enum import Enum


class Hero(Enum):
    FOOTBALLER = "Footballer"
    PRINCESS = "Princess"

    @property
    def title(self) -> str:
        return self.value


HEROES: tuple[Hero, ...] = tuple(Hero)
