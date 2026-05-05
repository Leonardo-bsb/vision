"""Batch processing entrypoint for image rectification."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable


def iter_images(input_dir: Path) -> Iterable[Path]:
    """Yield common image files recursively."""
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}
    for path in input_dir.rglob("*"):
        if path.is_file() and path.suffix.lower() in exts:
            yield path


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch rectification scaffold")
    parser.add_argument("--input", required=True, type=Path, help="Input folder")
    parser.add_argument("--output", required=True, type=Path, help="Output folder")
    args = parser.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)

    count = 0
    for image_path in iter_images(args.input):
        rel = image_path.relative_to(args.input)
        output_path = args.output / rel
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Placeholder: load image, rectify with your chosen pipeline, then write output.
        output_path.write_bytes(image_path.read_bytes())
        count += 1

    print(f"Scaffold copied {count} files. Replace copy step with real rectification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
