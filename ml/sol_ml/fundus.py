"""Fundus (retina) photo check with classical image processing: no trained or pretrained model.

    from sol_ml import fundus
    m = fundus.measure(image_bytes)                 # works on ANY image; says when it is not a usable fundus photo
    result = fundus.compare(m, baseline_measurements)

Why: in weightlessness fluid shifts toward the head and some astronauts develop Spaceflight-Associated Neuro-ocular
Syndrome (SANS): the optic disc swells, its margin blurs, and choroidal folds appear. The standard clinical grade
(Frisén) is read from how blurred the disc margin is. This module measures that blur and compares it with the
astronaut's own pre-flight photo, the same personal-baseline idea as the rest of the engine.

Every number has a plain meaning:
  quality      field coverage (share of the frame inside the round fundus field), brightness, contrast, sharpness
               (variance of the Laplacian) and red dominance (a fundus photo is mostly orange-red)
  optic disc   located as the brightest blob after heavy smoothing; radius from where brightness falls to half
               way between the disc and its surroundings
  margin       mean brightness gradient on a ring at the disc edge, divided by the disc-to-background contrast
               (sharp edge = high, swollen blurred edge = low)
  vessels      black top-hat of the green channel (dark thin structures) on a ring just outside the disc; swelling
               hides the vessels as they cross the margin
This is an image measurement, not a diagnosis. The flight surgeon reviews every photo.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

SIZE = 512                      # every photo is analysed at 512 px on its long side
MARGIN_WATCH, MARGIN_ACT = 0.75, 0.55       # margin sharpness relative to the baseline photo
DISC_GROWTH_ACT = 1.35                      # disc area relative to the baseline photo
VESSEL_WATCH = 0.70                         # vessel visibility at the margin relative to the baseline


def load(data: bytes) -> np.ndarray:
    """Any image file -> RGB float array in 0..1, long side SIZE px."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((SIZE, SIZE))
    return np.asarray(img, dtype=float) / 255.0


def _field_mask(rgb: np.ndarray) -> np.ndarray:
    """The round fundus field: pixels clearly brighter than the black surround."""
    red = rgb[..., 0]
    mask = ndi.gaussian_filter(red, 3) > max(0.08, 0.25 * np.percentile(red, 95))
    mask = ndi.binary_opening(mask, iterations=3)
    labels, n = ndi.label(mask)
    if n == 0:
        return mask
    sizes = ndi.sum(mask, labels, range(1, n + 1))
    return labels == (int(np.argmax(sizes)) + 1)


def measure(data: bytes) -> dict:
    """Measurements of one photo. Never raises on a valid image file; a poor or non-fundus photo is reported as such."""
    rgb = load(data)
    h, w, _ = rgb.shape
    mask = _field_mask(rgb)
    coverage = float(mask.mean())
    inside = rgb[mask] if mask.any() else rgb.reshape(-1, 3)
    brightness = float(inside.mean())
    green = rgb[..., 1]
    contrast = float(green[mask].std()) if mask.any() else float(green.std())
    lap = ndi.laplace(ndi.gaussian_filter(green, 1.0))
    sharpness = float(lap[mask].var() * 1e4) if mask.any() else float(lap.var() * 1e4)
    red_share = float(inside[:, 0].mean() / max(inside.sum(axis=1).mean(), 1e-6))

    problems = []
    if coverage < 0.25:
        problems.append("the round retina field is not visible")
    if red_share < 0.40:
        problems.append("the colours do not look like a retina photo")
    if brightness < 0.12:
        problems.append("the photo is too dark")
    if sharpness < 0.6:
        problems.append("the photo is blurred")
    usable = not problems

    # optic disc: the brightest smooth blob inside the field (luminance, weighted toward red and green)
    lum = 0.5 * rgb[..., 0] + 0.5 * rgb[..., 1]
    smooth = ndi.gaussian_filter(np.where(mask, lum, 0.0), sigma=max(h, w) / 40)
    cy, cx = np.unravel_index(int(np.argmax(smooth)), smooth.shape)
    yy, xx = np.indices(lum.shape)
    dist = np.hypot(yy - cy, xx - cx)
    rmax = int(max(h, w) * 0.25)
    radial = ndi.mean(ndi.gaussian_filter(lum, 1.5), labels=np.minimum(dist, rmax).astype(int), index=np.arange(rmax))
    radial = np.nan_to_num(np.asarray(radial, float))
    peak, background = float(radial[:3].mean()), float(np.median(radial[int(rmax * 0.6):]))
    half = background + 0.5 * (peak - background)
    below = np.flatnonzero(radial < half)
    radius = float(below[0]) if len(below) else float(rmax / 4)
    radius = max(radius, 4.0)

    # margin sharpness: brightness gradient on a ring at the disc edge, scaled by the disc contrast
    grad = np.hypot(ndi.sobel(ndi.gaussian_filter(lum, 1.0), 0), ndi.sobel(ndi.gaussian_filter(lum, 1.0), 1)) / 8.0
    ring = (dist > radius * 0.8) & (dist < radius * 1.2) & mask
    disc_contrast = max(peak - background, 1e-3)
    margin = float(grad[ring].mean() / disc_contrast * radius) if ring.any() else 0.0

    # vessels crossing the margin: dark thin structures (black top-hat on green) on a ring just outside the disc
    tophat = ndi.grey_closing(green, size=(9, 9)) - green
    vessel_ring = (dist > radius * 1.1) & (dist < radius * 1.8) & mask
    vessels = float((tophat[vessel_ring] > 0.03).mean()) if vessel_ring.any() else 0.0

    return {
        "usable": usable, "problems": problems,
        "quality": {"field_coverage": round(coverage, 3), "brightness": round(brightness, 3), "contrast": round(contrast, 3),
                    "sharpness": round(sharpness, 2), "red_share": round(red_share, 3)},
        "disc": {"center": [int(cx), int(cy)], "radius_px": round(radius, 1), "area_px": round(float(np.pi * radius ** 2), 0),
                 "margin_sharpness": round(margin, 3), "vessel_visibility": round(vessels, 3)},
        "size_px": [int(w), int(h)],
    }


def compare(current: dict, baseline: dict | None) -> dict:
    """Level and one-sentence reason from a photo compared with the astronaut's own baseline photo."""
    if not current["usable"]:
        return {"level": "YELLOW", "kind": "retake",
                "reason": "The eye photo could not be read (" + "; ".join(current["problems"]) + "). Retake it with the fundus camera.",
                "ratios": None}
    if baseline is None or not baseline.get("usable"):
        return {"level": "GREEN", "kind": "baseline",
                "reason": "This photo is stored as your baseline; later photos are compared with it.", "ratios": None}
    cur, base = current["disc"], baseline["disc"]
    ratios = {"margin_sharpness": round(cur["margin_sharpness"] / max(base["margin_sharpness"], 1e-6), 3),
              "disc_area": round(cur["area_px"] / max(base["area_px"], 1e-6), 3),
              "vessel_visibility": round(cur["vessel_visibility"] / max(base["vessel_visibility"], 1e-6), 3)}
    blur_pct = round((1 - ratios["margin_sharpness"]) * 100)
    if ratios["margin_sharpness"] < MARGIN_ACT or ratios["disc_area"] > DISC_GROWTH_ACT:
        return {"level": "RED", "kind": "optic_disc_change", "ratios": ratios,
                "reason": f"The optic disc margin is {blur_pct}% less sharp than in your baseline photo and the disc looks "
                          f"{round((ratios['disc_area'] - 1) * 100)}% larger: possible optic disc swelling. The photo has been sent to your flight surgeon."}
    if ratios["margin_sharpness"] < MARGIN_WATCH or ratios["vessel_visibility"] < VESSEL_WATCH:
        return {"level": "YELLOW", "kind": "optic_disc_change", "ratios": ratios,
                "reason": f"The optic disc margin is {blur_pct}% less sharp than in your baseline photo: an early sign to watch. "
                          f"The photo goes to your flight surgeon in today's report."}
    return {"level": "GREEN", "kind": "unchanged", "ratios": ratios,
            "reason": "Your optic disc looks the same as in your baseline photo."}
