import json
from dataclasses import dataclass
from pathlib import Path

import pygame

ASSETS = Path(__file__).resolve().parent / "assets"


@dataclass
class SpriteSheet:
    frames: dict[str, list[pygame.Surface]]
    anchor: tuple[float, float]
    size: tuple[float, float]


@dataclass
class Backdrop:
    sky: pygame.Surface
    hills: pygame.Surface
    ground: pygame.Surface
    ground_overhang: float
    parallax: dict[str, float]


def _image(path: Path, factor: float) -> pygame.Surface:
    image = pygame.image.load(path)
    if abs(factor - 1) < 1e-6:
        return image
    return pygame.transform.smoothscale_by(
        image.convert_alpha() if pygame.display.get_surface() else image, factor
    )


def load_sheet(folder: Path, scale: float, sequences: tuple[str, ...] | None = None) -> SpriteSheet:
    metadata = json.loads((folder / "sprite.json").read_text())
    factor = scale / metadata["scale"]
    frames = {
        sequence: [_image(folder / name, factor) for name in names]
        for sequence, names in metadata["frames"].items()
        if sequences is None or sequence in sequences
    }
    anchor_x, anchor_y = metadata["anchor"]
    width, height = metadata.get("size", metadata["canvas"])
    return SpriteSheet(frames, (anchor_x * scale, anchor_y * scale), (width, height))


def load_backdrop(scale: float) -> Backdrop:
    folder = ASSETS / "background"
    metadata = json.loads((folder / "layers.json").read_text())
    factor = scale / metadata["scale"]
    return Backdrop(
        sky=_image(folder / metadata["sky"]["file"], factor),
        hills=_image(folder / metadata["hills"]["file"], factor),
        ground=_image(folder / metadata["ground"]["file"], factor),
        ground_overhang=metadata["ground"]["overhang"],
        parallax={"sky": metadata["sky"]["parallax"], "hills": metadata["hills"]["parallax"]},
    )
