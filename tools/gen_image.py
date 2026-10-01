import os
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "art"
RAW = ART / "raw"
LOG = ART / "prompts.md"
MODEL = os.environ.get("CODEX_MODEL", "gpt-5.6-sol")


def valid_png(path: Path) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as image:
            image.load()
            return image.width >= 512 and image.height >= 256
    except Exception:
        return False


def generate(
    asset_id: str, prompt: str, reference: Path | None = None, role: str = "character"
) -> Path:
    RAW.mkdir(parents=True, exist_ok=True)
    version = 1
    while (RAW / f"{asset_id}_v{version}.png").exists():
        version += 1
    target = RAW / f"{asset_id}_v{version}.png"
    workdir = Path(tempfile.mkdtemp(prefix="codex_image_"))
    output = workdir / "image.png"
    if reference is not None:
        shutil.copy(reference, workdir / "reference.png")
    if reference is None:
        guidance = ""
    elif role == "character":
        guidance = (
            " using the attached image as the style and character reference (same character design)"
        )
    else:
        guidance = " using the attached image only as the art style reference (draw the new subject described below, not the character in the image)"
    instruction = (
        "Use the built-in image_gen tool (not the CLI/API fallback). "
        "Generating exactly this one image is pre-confirmed by the user: do not ask for confirmation, "
        "do not ask questions, do not plan, just do it. Generate exactly one image"
        + guidance
        + f' with this prompt:\n"""\n{prompt}\n"""\n'
        f"Then copy the generated PNG to {output}. Make exactly one image_gen call. If it fails, do not retry, do not "
        "change or rephrase the prompt, do not try alternatives: reply with the exact error text and stop. "
        "Do nothing else. Reply only with the final file path or the exact error."
    )
    command = [
        "codex",
        "exec",
        "--skip-git-repo-check",
        "-m",
        MODEL,
        "-C",
        str(workdir),
        "-s",
        "workspace-write",
    ]
    if reference is not None:
        command += ["-i", str(workdir / "reference.png")]
    command += ["--", instruction]
    error = ""
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, timeout=900, stdin=subprocess.DEVNULL
        )
        error = result.stdout[-3000:] + "\n" + result.stderr[-3000:]
    except (subprocess.TimeoutExpired, FileNotFoundError) as exception:
        error = str(exception)
    if valid_png(output):
        shutil.copy(output, target)
    shutil.rmtree(workdir, ignore_errors=True)
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    with LOG.open("a") as log:
        log.write(f"\n## {asset_id} v{version} ({stamp})\n\n")
        if reference is not None:
            log.write(f"Reference: `{reference.relative_to(ROOT)}`\n\n")
        log.write(
            f"File: `{target.relative_to(ROOT)}`{'' if target.exists() else ' (MISSING)'}\n\n"
        )
        log.write(f"```\n{prompt}\n```\n")
    if not target.exists():
        sys.stderr.write(error)
        raise SystemExit(f"no image for {asset_id}")
    return target


def main() -> int:
    asset_id, prompt_file = sys.argv[1], Path(sys.argv[2])
    reference = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    print(generate(asset_id, prompt_file.read_text().strip(), reference))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
