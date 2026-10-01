import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art"
STYLE_REF = "art/raw/footballer_run_01_v1.png"


def blocks() -> dict[str, str]:
    found = re.findall(r"```\n(.*?)\n```", (ART / "style.md").read_text(), re.S)
    return {text.split(":", 1)[0]: text for text in found}


SHEET = (
    "ANIMATION SHEET: one horizontal row of exactly {count} animation frames of the same {subject} for a 2D "
    "side-scrolling game, read left to right. Every frame shows the whole {subject} at exactly the same size and "
    "scale, with the same design and colors, evenly spaced with a wide empty magenta gap between frames so that no "
    "frames touch or overlap. The frames form one smooth continuous motion: {motion} Wide landscape image."
)
SHEET_REQUIREMENTS = (
    "REQUIREMENTS: solid pure #FF00FF magenta background filling the whole image, no shadow on the background, no "
    "ground line, no text, no numbers, no frame borders, no watermark, side view facing right."
)

HERO_BASE = {
    "run": (
        6,
        "a smooth looping run cycle in 6 phases: 1 contact with the front heel touching down, 2 down with a "
        "slight squash, 3 passing with the back leg tucking under the body, 4 push-off rising up, 5 airborne "
        "stride with both feet off the ground, 6 reaching forward before the next contact; arms swing opposite "
        "to the legs and the cape flows back.",
    ),
    "jump": (
        5,
        "1 crouch squash before takeoff, 2 takeoff stretching up with arms raised, 3 rising with knees "
        "tucked and a big smile, 4 apex floating happily, 5 falling with legs reaching down to land.",
    ),
    "idle": (
        4,
        "a gentle looping idle animation, standing in a proud superhero pose with hands on hips, 4 phases "
        "with subtle breathing up and down, a blink in phase 3, the cape gently waving.",
    ),
}
HERO_REACTIONS = {
    "flytrap": "1 running upright, 2 shocked jump backwards with arms up and big eyes, 3 tumbling through the air "
    "spinning, 4 sitting on the floor dizzy with little stars around the head.",
    "pitcher": "1 running upright, 2 lifted upside down with legs kicking in surprise, 3 dangling upside down "
    "covered in green goo, 4 sitting sticky and sad dripping with green goo.",
    "rose": "1 running upright, 2 jumping up with an ouch face after a thorn poke, 3 hopping on one leg holding the "
    "foot, 4 sitting and rubbing the foot with a tear.",
    "stump": "1 running upright, 2 tripping forward with arms thrown out, 3 flying forward horizontally, 4 lying "
    "face down flat on the floor.",
    "cactus": "1 running upright, 2 jumping straight up holding the bottom with little spikes stuck in it, 3 "
    "leaping high with tears flying, 4 sitting and sniffling while pulling out a spike.",
    "rock": "1 running upright, 2 bonking the head with a squashed face, 3 stumbling backwards holding the head, 4 "
    "sitting dazed with little stars and birds circling the head.",
}
OBSTACLE_IDLE = {
    "flytrap": "the jaws slowly opening and closing while the head sways on the stem.",
    "pitcher": "the lid bobbing up and down and a drop of drool dripping.",
    "rose": "the petals breathing open and closed while the head sways and the stem bends.",
    "stump": "sleepy breathing, the eyes slowly blinking and the sprout waving.",
    "cactus": "the arms twitching, a grumpy blink and the flower pulsing.",
    "rock": "the crystals twinkling, a stern blink and the moss swaying.",
}
OBSTACLE_REACTION = {
    "flytrap": "1 jaws wide open, 2 jaws snapping shut hard, 3 chewing with puffed cheeks, 4 spitting with the jaws wide open.",
    "pitcher": "1 lid flipping open, 2 sucking air in with a swirl in the mouth, 3 lid closing with a burp, 4 a satisfied grin.",
    "rose": "1 petals opening wide, 2 whipping the thorny stem forward, 3 the stem swinging back, 4 a proud pose.",
    "stump": "1 sleepy, 2 startled wide open eyes, 3 wobbling from the impact, 4 an annoyed frown.",
    "cactus": "1 grumpy, 2 spikes bristling out, 3 shaking angrily, 4 a smug grin.",
    "rock": "1 stern, 2 small crack lines and a shocked face, 3 wobbling from the impact, 4 the crystals glowing brightly.",
}
BACKGROUNDS = {
    "sky": "a very wide seamless panorama of a bright cartoon sky with a few soft fluffy clouds and pale distant rolling "
    "mountains along the bottom, soft pastel colors, low contrast, calm and simple so it does not distract. "
    "The left and right edges must match seamlessly. No characters, no text. Wide landscape image.",
    "hills": "a very wide seamless panorama of soft rolling cartoon green hills with a few round trees and bushes, "
    "soft pastel colors, low contrast, calm. The whole area above the hills is solid pure #FF00FF magenta. "
    "The left and right edges must match seamlessly. No characters, no text. Wide landscape image.",
    "ground": "a very wide seamless horizontal strip of cartoon ground seen from the side: a flat bumpy grass edge on "
    "top and rich brown soil with a few small pebbles below, soft colors. The whole area above the grass is "
    "solid pure #FF00FF magenta. The left and right edges must match seamlessly. No text. Wide landscape image.",
}
HEROES = {"footballer": "FOOTBALL KID", "princess": "PRINCESS KID"}
KINDS = {
    "flytrap": "FLYTRAP",
    "pitcher": "PITCHER",
    "rose": "ROSE",
    "stump": "STUMP",
    "cactus": "CACTUS",
    "rock": "ROCK",
}


def sheet(style: dict[str, str], subject_block: str, subject: str, count: int, motion: str) -> str:
    return "\n\n".join(
        [
            style["STYLE"],
            style[subject_block],
            style["COLOR SAFETY"],
            SHEET.format(count=count, subject=subject, motion=motion),
            SHEET_REQUIREMENTS,
        ]
    )


def jobs() -> list[dict]:
    style = blocks()
    result = []
    for hero, block in HEROES.items():
        for animation, (count, motion) in HERO_BASE.items():
            if hero == "princess" and animation == "run":
                reference, role = STYLE_REF, "style"
            elif hero == "princess":
                reference, role = "latest:princess_run", "character"
            else:
                reference, role = STYLE_REF, "character"
            result.append(
                {
                    "id": f"{hero}_{animation}",
                    "frames": count,
                    "reference": reference,
                    "role": role,
                    "prompt": sheet(style, block, "character", count, motion),
                }
            )
    for kind, block in KINDS.items():
        result.append(
            {
                "id": f"{kind}_idle",
                "frames": 4,
                "reference": STYLE_REF,
                "role": "style",
                "prompt": sheet(
                    style,
                    block,
                    "plant or object",
                    4,
                    f"a gentle looping idle animation in 4 phases, {OBSTACLE_IDLE[kind]}",
                ),
            }
        )
    for kind, block in KINDS.items():
        result.append(
            {
                "id": f"{kind}_react",
                "frames": 4,
                "reference": f"latest:{kind}_idle",
                "role": "character",
                "prompt": sheet(
                    style,
                    block,
                    "plant or object",
                    4,
                    f"its reaction when a running kid hero crashes into it, 4 phases: {OBSTACLE_REACTION[kind]} Only the obstacle is drawn, no hero.",
                ),
            }
        )
    for hero, block in HEROES.items():
        for kind, motion in HERO_REACTIONS.items():
            result.append(
                {
                    "id": f"{hero}_hit_{kind}",
                    "frames": 4,
                    "reference": f"latest:{hero}_run",
                    "role": "character",
                    "prompt": sheet(
                        style,
                        block,
                        "character",
                        4,
                        f"the hero crashing into a {KINDS[kind].lower()} obstacle, 4 phases: {motion} The obstacle itself is not drawn, only the hero.",
                    ),
                }
            )
    for name, text in BACKGROUNDS.items():
        result.append(
            {
                "id": f"bg_{name}",
                "frames": 1,
                "reference": STYLE_REF,
                "role": "style",
                "prompt": "\n\n".join([style["STYLE"], text]),
            }
        )
    return result


if __name__ == "__main__":
    (ART / "jobs.json").write_text(json.dumps(jobs(), indent=2) + "\n")
    print(len(jobs()), "jobs")
