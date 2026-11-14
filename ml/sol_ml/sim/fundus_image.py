"""Synthetic fundus (retina) photos for the demo: SIMULATED images, not photos of a person.

    png_bytes = fundus_image.render(seed=1, swelling=0.0)     # 0 = normal disc, 1 = clearly swollen (blurred, larger)

The picture follows the anatomy a fundus camera shows: a round orange-red field on black, a darker macula, a bright
optic disc, and vessels branching out of the disc. `swelling` blurs the disc margin, enlarges the disc and hides the
vessels where they cross the margin, which is what optic disc oedema looks like.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

SIZE = 512


def render(seed: int = 0, swelling: float = 0.0) -> bytes:
    rng = np.random.default_rng(seed)
    yy, xx = np.indices((SIZE, SIZE), dtype=float)
    c = SIZE / 2
    field = np.hypot(yy - c, xx - c) < SIZE * 0.46

    # background retina: orange-red with gentle vignetting and texture
    vignette = 1 - 0.35 * (np.hypot(yy - c, xx - c) / (SIZE * 0.46)) ** 2
    texture = ndi.gaussian_filter(rng.normal(0, 1, (SIZE, SIZE)), 6) * 0.03
    r = (0.78 * vignette + texture)
    g = (0.36 * vignette + texture * 0.6)
    b = (0.16 * vignette + texture * 0.3)

    # macula: darker spot to the right of centre
    mx, my = c + SIZE * 0.12, c + rng.normal(0, 4)
    mac = np.exp(-((xx - mx) ** 2 + (yy - my) ** 2) / (2 * (SIZE * 0.06) ** 2))
    r -= 0.18 * mac; g -= 0.10 * mac; b -= 0.05 * mac

    # vessels: dark red curves leaving the disc, drawn before the disc so the disc covers their roots
    dx, dy = c - SIZE * 0.17 + rng.normal(0, 3), c + rng.normal(0, 3)
    vessels = np.zeros((SIZE, SIZE))
    for k in range(9):
        angle = rng.uniform(0, 2 * np.pi)
        x, y, width = dx, dy, rng.uniform(2.0, 3.6)
        for _ in range(170):
            angle += rng.normal(0, 0.06)
            x += 2.0 * np.cos(angle); y += 2.0 * np.sin(angle)
            if not (0 <= x < SIZE and 0 <= y < SIZE):
                break
            vessels[int(y), int(x)] = width
            width = max(width * 0.996, 1.0)
    vessels = ndi.grey_dilation(vessels, size=(3, 3))
    vessels = ndi.gaussian_filter((vessels > 0).astype(float), 1.0)
    dist = np.hypot(yy - dy, xx - dx)
    radius = SIZE * 0.055 * (1 + 0.45 * swelling)
    hidden = np.clip(1 - swelling * np.exp(-((dist - radius) ** 2) / (2 * (radius * 0.6) ** 2)), 0, 1)   # swelling hides vessels at the margin
    v = vessels * hidden
    r -= 0.30 * v; g -= 0.20 * v; b -= 0.08 * v

    # optic disc: bright yellow-white; swelling blurs the margin
    edge = 1.5 + 9.0 * swelling
    disc = 1 / (1 + np.exp((dist - radius) / edge))
    r = r * (1 - disc) + 0.98 * disc
    g = g * (1 - disc) + 0.86 * disc
    b = b * (1 - disc) + 0.55 * disc

    rgb = np.stack([r, g, b], axis=-1)
    rgb = np.clip(rgb + rng.normal(0, 0.008, rgb.shape), 0, 1) * field[..., None]
    out = io.BytesIO()
    Image.fromarray((rgb * 255).astype(np.uint8)).save(out, format="PNG", optimize=True)
    return out.getvalue()
