import json
import sys
from pathlib import Path

from gen_image import ART, RAW, generate

ROOT = Path(__file__).resolve().parents[1]
MAX_FAILURES = 2


def latest(asset_id: str) -> Path | None:
    versions = sorted(RAW.glob(f"{asset_id}_v*.png"), key=lambda p: int(p.stem.rsplit("_v", 1)[1]))
    return versions[-1] if versions else None


def main() -> int:
    wanted = set(sys.argv[1:])
    jobs = json.loads((ART / "jobs.json").read_text())
    failures = 0
    for job in jobs:
        if wanted and job["id"] not in wanted:
            continue
        if not wanted and latest(job["id"]) is not None:
            continue
        reference = job["reference"]
        path = (
            latest(reference.split(":", 1)[1])
            if reference.startswith("latest:")
            else ROOT / reference
        )
        if path is None or not path.exists():
            print(job["id"], "SKIPPED missing reference", reference, flush=True)
            continue
        try:
            print(
                job["id"], "->", generate(job["id"], job["prompt"], path, job["role"]), flush=True
            )
            failures = 0
        except SystemExit as error:
            failures += 1
            print(job["id"], "FAILED", error, flush=True)
            if failures >= MAX_FAILURES:
                print("stopping after", failures, "consecutive failures", flush=True)
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
