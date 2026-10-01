import json
import sys
from collections import deque
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art"
RAW = ART / "raw"
ASSETS = ROOT / "src" / "run_simulator" / "assets"
SCALE = 2
KEY = (255, 0, 255)
INNER = 60.0
OUTER = 118.0
PAD = 2
COARSE = 4
HERO_TALLEST = {"run": 1.0, "idle": 1.03, "jump": 1.08}


def latest(asset_id: str) -> Path:
    versions = sorted(RAW.glob(f"{asset_id}_v*.png"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
    if not versions:
        raise FileNotFoundError(asset_id)
    return versions[-1]


def key_out(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    pixels = rgba.load()
    width, height = rgba.size
    for y in range(height):
        for x in range(width):
            r, g, b, a = pixels[x, y]
            distance = ((KEY[0] - r) ** 2 + (KEY[1] - g) ** 2 + (KEY[2] - b) ** 2) ** 0.5
            alpha = min(1.0, max(0.0, (distance - INNER) / (OUTER - INNER)))
            if alpha <= 0.0:
                pixels[x, y] = (0, 0, 0, 0)
                continue
            if alpha < 1.0:
                r = round(min(255.0, max(0.0, (r - (1 - alpha) * KEY[0]) / alpha)))
                g = round(min(255.0, max(0.0, (g - (1 - alpha) * KEY[1]) / alpha)))
                b = round(min(255.0, max(0.0, (b - (1 - alpha) * KEY[2]) / alpha)))
            pixels[x, y] = (r, g, b, round(a * alpha))
    return despill(rgba)


def despill(image: Image.Image) -> Image.Image:
    edge = (
        image.getchannel("A")
        .point(lambda value: 255 if value < 250 else 0)
        .filter(ImageFilter.MaxFilter(7))
    )
    pixels = image.load()
    edges = edge.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            if edges[x, y]:
                r, g, b, a = pixels[x, y]
                spill = min(r, b) - g
                if a and spill > 40:
                    pixels[x, y] = (max(0, r - spill + 40), g, max(0, b - spill + 40), a)
    return image


def components(mask: Image.Image) -> list[list[tuple[int, int]]]:
    width, height = mask.size
    data = mask.load()
    seen = [[False] * width for _ in range(height)]
    groups = []
    for y in range(height):
        for x in range(width):
            if data[x, y] and not seen[y][x]:
                queue = deque([(x, y)])
                seen[y][x] = True
                group = []
                while queue:
                    cx, cy = queue.popleft()
                    group.append((cx, cy))
                    for nx in (cx - 1, cx, cx + 1):
                        for ny in (cy - 1, cy, cy + 1):
                            if (
                                0 <= nx < width
                                and 0 <= ny < height
                                and data[nx, ny]
                                and not seen[ny][nx]
                            ):
                                seen[ny][nx] = True
                                queue.append((nx, ny))
                groups.append(group)
    return groups


def slice_frames(sheet: Image.Image, count: int) -> list[Image.Image]:
    coarse = sheet.getchannel("A").resize(
        (sheet.width // COARSE, sheet.height // COARSE), Image.Resampling.BOX
    )
    mask = coarse.point(lambda value: 255 if value > 24 else 0)
    groups = sorted(components(mask), key=len, reverse=True)
    if len(groups) < count:
        raise ValueError(f"found {len(groups)} figures, expected {count}")
    if len(groups[count - 1]) < 0.2 * len(groups[0]):
        raise ValueError(
            f"figure {count} is too small, strip probably has fewer than {count} figures"
        )
    if len(groups) > count and len(groups[count]) > 0.3 * len(groups[0]):
        raise ValueError(f"strip has more than {count} figures")
    main = sorted(groups[:count], key=lambda g: sum(x for x, _ in g) / len(g))
    centers = [sum(x for x, _ in g) / len(g) for g in main]
    owners: dict[tuple[int, int], int] = {}
    for index, group in enumerate(main):
        for point in group:
            owners[point] = index
    for group in groups[count:]:
        if len(group) < 3:
            continue
        center = sum(x for x, _ in group) / len(group)
        index = min(range(count), key=lambda i: abs(centers[i] - center))
        for point in group:
            owners[point] = index
    frames = []
    for index in range(count):
        points = [point for point, owner in owners.items() if owner == index]
        left = max(0, (min(x for x, _ in points) - 1) * COARSE)
        right = min(sheet.width, (max(x for x, _ in points) + 2) * COARSE)
        top = max(0, (min(y for _, y in points) - 1) * COARSE)
        bottom = min(sheet.height, (max(y for _, y in points) + 2) * COARSE)
        frame = sheet.crop((left, top, right, bottom))
        pixels = frame.load()
        for y in range(frame.height):
            for x in range(frame.width):
                owner = owners.get(((left + x) // COARSE, (top + y) // COARSE))
                if owner is not None and owner != index:
                    pixels[x, y] = (0, 0, 0, 0)
        frames.append(trim(frame))
    return frames


def trim(image: Image.Image) -> Image.Image:
    box = image.getchannel("A").point(lambda value: 255 if value > 8 else 0).getbbox()
    if box is None:
        raise ValueError("empty frame")
    left, top, right, bottom = box
    return image.crop(
        (
            max(0, left - PAD),
            max(0, top - PAD),
            min(image.width, right + PAD),
            min(image.height, bottom + PAD),
        )
    )


def scaled(frames: list[Image.Image], factor: float) -> list[Image.Image]:
    return [
        frame.resize(
            (max(1, round(frame.width * factor)), max(1, round(frame.height * factor))),
            Image.Resampling.LANCZOS,
        )
        for frame in frames
    ]


def strip(asset_id: str, count: int) -> list[Image.Image]:
    return slice_frames(key_out(Image.open(latest(asset_id))), count)


def compose(
    folder: Path, sequences: dict[str, list[Image.Image]], anchor_width: float | None, size
) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.png"):
        old.unlink()
    width = max(frame.width for group in sequences.values() for frame in group)
    height = max(frame.height for group in sequences.values() for frame in group)
    canvas = (width + 8 * SCALE, height + 8 * SCALE)
    base = (canvas[0] / 2, canvas[1] - 4 * SCALE)
    names: dict[str, list[str]] = {}
    for name, group in sequences.items():
        names[name] = []
        for index, frame in enumerate(group):
            sheet = Image.new("RGBA", canvas, (0, 0, 0, 0))
            sheet.alpha_composite(
                frame, (round(base[0] - frame.width / 2), round(base[1] - frame.height))
            )
            file = f"{name}_{index:02d}.png"
            sheet.save(folder / file, optimize=True)
            names[name].append(file)
    anchor = base if anchor_width is None else (base[0] - anchor_width / 2, base[1])
    data = {
        "canvas": [canvas[0] / SCALE, canvas[1] / SCALE],
        "anchor": [anchor[0] / SCALE, anchor[1] / SCALE],
        "scale": SCALE,
        "frames": names,
    }
    if size is not None:
        data["size"] = list(size)
    (folder / "sprite.json").write_text(json.dumps(data, indent=2) + "\n")


def hero(name: str, spec: dict, counts: dict[str, int]) -> None:
    target = spec["height"] * SCALE
    sequences: dict[str, list[Image.Image]] = {}
    for sequence, asset_id in spec["strips"].items():
        frames = strip(asset_id, counts[asset_id])
        if sequence.startswith("hit_"):
            reference = frames[0].height
            factor = target / reference
        else:
            factor = target * HERO_TALLEST[sequence] / max(frame.height for frame in frames)
        sequences[sequence] = scaled(frames, factor)
    jump = sequences.pop("jump")
    sequences["land"] = jump[:1]
    sequences["air"] = jump[1:]
    compose(ASSETS / "heroes" / name, sequences, None, None)


def obstacle(name: str, spec: dict, counts: dict[str, int]) -> float:
    target = spec["height"] * SCALE
    idle = [ImageOps.mirror(frame) for frame in strip(spec["idle"], counts[spec["idle"]])]
    factor = target / min(frame.height for frame in idle)
    loop = scaled(idle, factor)
    react = [ImageOps.mirror(frame) for frame in strip(spec["react"], counts[spec["react"]])]
    react = scaled(react, loop[0].height / react[0].height)
    width = sorted(frame.width for frame in loop)[len(loop) // 2]
    size = (width / SCALE, target / SCALE)
    compose(ASSETS / "obstacles" / name, {"loop": loop, "react": react}, width, size)
    return size[0] / size[1]


def mirrored(image: Image.Image) -> Image.Image:
    out = Image.new("RGBA", (image.width * 2, image.height), (0, 0, 0, 0))
    out.alpha_composite(image, (0, 0))
    out.alpha_composite(ImageOps.mirror(image), (image.width, 0))
    return out


def surface_row(image: Image.Image) -> int:
    alpha = image.getchannel("A")
    for y in range(image.height):
        row = alpha.crop((0, y, image.width, y + 1))
        if sum(1 for value in row.get_flattened_data() if value > 200) > image.width * 0.98:
            return y
    return 0


def extend_below(image: Image.Image, depth: int) -> Image.Image:
    surface = surface_row(image)
    needed = surface + depth
    if image.height >= needed:
        return image
    band = image.crop((0, image.height - 24, image.width, image.height))
    out = Image.new("RGBA", (image.width, needed), (0, 0, 0, 0))
    out.alpha_composite(image, (0, 0))
    y = image.height
    while y < needed:
        out.alpha_composite(band, (0, y))
        y += band.height
    return out


def layer(spec: dict) -> float:
    folder = ASSETS / "background"
    folder.mkdir(parents=True, exist_ok=True)
    image = Image.open(latest(spec["id"])).convert("RGBA")
    if spec["keyed"]:
        image = key_out(image)
        box = image.getchannel("A").getbbox()
        if box is not None:
            image = image.crop((0, box[1], image.width, image.height))
    image = mirrored(image)
    if "height" in spec:
        factor = spec["height"] * SCALE / image.height
    else:
        factor = spec["width"] * SCALE / image.width
    image = image.resize(
        (round(image.width * factor), round(image.height * factor)), Image.Resampling.LANCZOS
    )
    if "below" in spec:
        image = extend_below(image, spec["below"] * SCALE)
    image.save(folder / spec["file"], optimize=True)
    return surface_row(image) / SCALE


def main() -> int:
    manifest = json.loads((ART / "manifest.json").read_text())
    counts = {job["id"]: job["frames"] for job in json.loads((ART / "jobs.json").read_text())}
    only = set(sys.argv[1:])
    for name, spec in manifest["heroes"].items():
        if not only or name in only:
            hero(name, spec, counts)
            print("hero", name)
    for name, spec in manifest["obstacles"].items():
        if not only or name in only:
            print(f"obstacle {name} aspect {obstacle(name, spec, counts):.3f}")
    existing = ASSETS / "background" / "layers.json"
    layers = json.loads(existing.read_text()) if existing.exists() else {}
    layers["scale"] = SCALE
    for spec in manifest["background"]:
        if not only or spec["id"] in only:
            surface = layer(spec)
            layers[spec["name"]] = {
                "file": spec["file"],
                "parallax": spec["parallax"],
                "overhang": surface,
            }
            print("layer", spec["id"], "surface", surface)
    if all(spec["name"] in layers for spec in manifest["background"]):
        existing.write_text(json.dumps(layers, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
