#!/usr/bin/env python3
"""
Turn a large PSD collage into a hoverable web page.

Outputs three files next to viewer.html:
  collage.jpg   — flattened, downscaled preview the user sees
  regions.png   — invisible ID map, same size; pixel color encodes layer id
  captions.json — { "1": "layer name", "2": "...", ... }  (edit freely)

Usage:
  pip install psd-tools pillow numpy
  python psd_to_hover.py path/to/collage.psd --max-dim 1600 --alpha-threshold 16
"""

import argparse, json, sys
from pathlib import Path

import numpy as np
from PIL import Image
from psd_tools import PSDImage


def iter_leaf_layers(group):
    for layer in group:
        if layer.is_group():
            yield from iter_leaf_layers(layer)
        else:
            yield layer


def encode_id(i: int) -> tuple[int, int, int, int]:
    # 24-bit id split across RGB so we can support >255 layers.
    return (i & 0xFF, (i >> 8) & 0xFF, (i >> 16) & 0xFF, 255)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd", type=Path)
    ap.add_argument("--out", type=Path, default=Path(__file__).parent)
    ap.add_argument("--max-dim", type=int, default=1600,
                    help="Longest side of output images in pixels.")
    ap.add_argument("--alpha-threshold", type=int, default=16,
                    help="A layer 'owns' a pixel if its alpha is at least this (0-255).")
    ap.add_argument("--jpeg-quality", type=int, default=85)
    ap.add_argument("--include-hidden", action="store_true",
                    help="Include layers hidden in the PSD.")
    args = ap.parse_args()

    print(f"Loading {args.psd} …", flush=True)
    psd = PSDImage.open(args.psd)
    W, H = psd.width, psd.height
    scale = min(1.0, args.max_dim / max(W, H))
    tW, tH = max(1, round(W * scale)), max(1, round(H * scale))
    print(f"Source {W}x{H}  →  output {tW}x{tH}  (scale {scale:.3f})", flush=True)

    # Flattened preview
    print("Compositing preview …", flush=True)
    flat = psd.composite().convert("RGB")
    if (flat.width, flat.height) != (tW, tH):
        flat = flat.resize((tW, tH), Image.LANCZOS)
    flat.save(args.out / "collage.jpg", quality=args.jpeg_quality, optimize=True)

    # Build ID map — later layers (drawn on top in PSD order) win.
    print("Building region map …", flush=True)
    id_map = np.zeros((tH, tW), dtype=np.uint32)  # 0 = background
    captions: dict[int, str] = {}

    layers = list(iter_leaf_layers(psd))
    next_id = 1
    for layer in layers:
        if not args.include_hidden and not layer.visible:
            continue
        name = (layer.name or "").strip()
        if not name:
            continue

        bbox = layer.bbox  # (left, top, right, bottom) in PSD coords, may be empty
        if bbox[2] <= bbox[0] or bbox[3] <= bbox[1]:
            continue

        try:
            layer_img = layer.composite()
        except Exception as e:
            print(f"  skip {name!r}: {e}", file=sys.stderr)
            continue
        if layer_img is None:
            continue
        layer_img = layer_img.convert("RGBA")

        # Place onto full-canvas alpha
        alpha_full = Image.new("L", (W, H), 0)
        alpha_full.paste(layer_img.split()[-1], (bbox[0], bbox[1]))
        if (alpha_full.width, alpha_full.height) != (tW, tH):
            alpha_full = alpha_full.resize((tW, tH), Image.LANCZOS)
        a = np.asarray(alpha_full, dtype=np.uint8)

        mask = a >= args.alpha_threshold
        if not mask.any():
            continue

        id_map[mask] = next_id
        captions[next_id] = name
        print(f"  #{next_id:>3}  {name}", flush=True)
        next_id += 1

    # Encode id_map as RGBA PNG
    rgba = np.zeros((tH, tW, 4), dtype=np.uint8)
    rgba[..., 0] = (id_map & 0xFF).astype(np.uint8)
    rgba[..., 1] = ((id_map >> 8) & 0xFF).astype(np.uint8)
    rgba[..., 2] = ((id_map >> 16) & 0xFF).astype(np.uint8)
    rgba[..., 3] = 255
    Image.fromarray(rgba, "RGBA").save(args.out / "regions.png", optimize=True)

    (args.out / "captions.json").write_text(
        json.dumps({str(k): v for k, v in captions.items()}, indent=2, ensure_ascii=False)
    )

    print(f"\nDone. {next_id - 1} regions.")
    print(f"  {args.out / 'collage.jpg'}")
    print(f"  {args.out / 'regions.png'}")
    print(f"  {args.out / 'captions.json'}")
    print("Open viewer.html in a browser (serve the folder, e.g. `python -m http.server`).")


if __name__ == "__main__":
    main()
