#!/usr/bin/env python3

import argparse
import os
import subprocess
import sys
from pathlib import Path


def render_preview(pdf_path, output_path, pages=(0, 1, 2), density=150, gap=20):
    pdf_path = Path(pdf_path)

    if not pdf_path.exists():
        print(f"Error: {pdf_path} not found", file=sys.stderr)
        sys.exit(1)

    cmd = ["magick"]

    for page in pages:
        cmd.extend([
            "(",
            "-density", str(density),
            f"{pdf_path}[{page}]",
            "-colorspace", "sRGB",
            "-background", "white",
            "-alpha", "remove",
            "-bordercolor", "#e0e0e0",
            "-border", "1",
            "(", "+clone",
                "-background", "black",
                "-shadow", "60x4+2+2",
            ")",
            "+swap",
            "-background", "white",
            "-layers", "merge",
            "+repage",
            ")",
        ])

    cmd.extend([
        "+smush", str(gap),
        "-background", "white",
        "-flatten",
        str(output_path),
    ])

    subprocess.run(cmd, check=True)

    print(f"Saved {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Render PDF preview images")

    parser.add_argument(
        "--build-dir",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "../out/build"),
        help="Directory containing built PDFs",
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default=os.path.join(os.path.dirname(__file__), "../docs/images"),
        help="Output directory for preview PNGs",
    )

    parser.add_argument(
        "--density",
        type=int,
        default=150,
        help="Render density in DPI",
    )

    args = parser.parse_args()

    build_dir = Path(args.build_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    previews = [
        ("project_euler_offline.pdf", "preview_compact.webp"),
        ("project_euler_offline_spaced.pdf", "preview_spaced.webp"),
    ]

    for pdf_name, output_name in previews:
        pdf_path = build_dir / pdf_name

        if not pdf_path.exists():
            print(f"Skipping {pdf_name}: not found", file=sys.stderr)
            continue

        render_preview(
            pdf_path,
            output_dir / output_name,
            density=args.density,
        )


if __name__ == "__main__":
    main()
