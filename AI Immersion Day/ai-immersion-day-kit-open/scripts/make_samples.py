"""Generates the bundled sample sketches, sample LEGO build photos and the printable sketch template.
Run:  python scripts/make_samples.py
Sample PNGs carry their 'true' spec in PNG metadata so mock mode can behave like a perfect model."""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from PIL.PngImagePlugin import PngInfo

ROOT = Path(__file__).resolve().parents[1]
COL = {
    "red": (205, 25, 40), "crimson": (125, 30, 45), "blue": (30, 50, 120), "white": (250, 250, 248), "black": (25, 25, 25),
    "silver": (180, 186, 192), "lime green": (150, 225, 40), "purple": (95, 45, 140), "pink": (232, 90, 130), "orange": (232, 112, 42),
}


def font(size):
    for f in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"]:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default()


def wobble_line(d, pts, rnd, width=3, fill=(30, 30, 30), passes=2, amp=2.5):
    for _ in range(passes):
        jp = [(x + rnd.uniform(-amp, amp), y + rnd.uniform(-amp, amp)) for x, y in pts]
        d.line(jp, fill=fill, width=width, joint="curve")


def fill_poly(d, pts, colour, rnd, quality):
    if quality == "high":
        d.polygon(pts, fill=colour)
    else:  # scribbled hatch fill - like a quick marker sketch
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        mask = Image.new("L", (1000, 600), 0)
        ImageDraw.Draw(mask).polygon(pts, fill=255)
        layer = Image.new("RGB", (1000, 600), colour)
        hatch = Image.new("L", (1000, 600), 0)
        hd = ImageDraw.Draw(hatch)
        for x in range(int(min(xs)) - 200, int(max(xs)), 9):
            hd.line([(x, max(ys)), (x + 160 + rnd.randint(-10, 10), min(ys))], fill=255, width=6)
        from PIL import ImageChops

        m = ImageChops.multiply(mask, hatch)
        d._image.paste(layer, (0, 0), m)


def draw_wheel(d, cx, cy, style, rnd):
    r = 70 if style == "off-road" else 60
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(30, 30, 30))
    if style == "off-road":
        for i in range(16):
            import math

            a = i * math.pi / 8
            d.rectangle([cx + (r - 4) * math.cos(a) - 6, cy + (r - 4) * math.sin(a) - 6, cx + (r - 4) * math.cos(a) + 6, cy + (r - 4) * math.sin(a) + 6], fill=(10, 10, 10))
    rr = 30 if style == "off-road" else 40
    d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=(185, 190, 195))
    import math

    if style == "5-spoke":
        for i in range(5):
            a = i * 2 * math.pi / 5
            d.line([(cx, cy), (cx + rr * math.cos(a), cy + rr * math.sin(a))], fill=(70, 70, 70), width=9)
    elif style == "multi-spoke":
        for i in range(14):
            a = i * 2 * math.pi / 14
            d.line([(cx, cy), (cx + rr * math.cos(a), cy + rr * math.sin(a))], fill=(80, 80, 80), width=3)
    elif style == "turbine":
        for i in range(8):
            a = i * 2 * math.pi / 8
            d.arc([cx - rr, cy - rr, cx + rr, cy + rr], math.degrees(a), math.degrees(a) + 40, fill=(60, 60, 60), width=6)
            d.line([(cx, cy), (cx + rr * 0.8 * math.cos(a + 0.5), cy + rr * 0.8 * math.sin(a + 0.5))], fill=(60, 60, 60), width=4)
    d.ellipse([cx - 8, cy - 8, cx + 8, cy + 8], fill=(50, 50, 50))


def draw_car(spec, quality="high", seed=1, label=""):
    rnd = random.Random(seed)
    im = Image.new("RGB", (1000, 600), (252, 251, 246))
    d = ImageDraw.Draw(im)
    body_c, door_c, mir_c = COL[spec["body"]], COL[spec["door"]], COL[spec["mirror"]]
    body = [(90, 395), (88, 322), (140, 297), (380, 270), (790, 262), (905, 290), (912, 395)]
    cabin = [(380, 272), (472, 192), (680, 188), (790, 265)]
    fill_poly(d, body + [], body_c, rnd, quality)
    fill_poly(d, cabin, body_c, rnd, quality)
    d.polygon([(405, 266), (480, 204), (668, 201), (758, 262)], fill=(185, 220, 240))
    d.line([(570, 202), (570, 266)], fill=body_c if quality == "high" else (40, 40, 40), width=10)
    # door
    door = [(470, 275), (470, 385), (650, 385), (650, 272)]
    fill_poly(d, door, door_c, rnd, quality)
    wobble_line(d, door + [door[0]], rnd, width=3)
    d.line([(600, 300), (630, 300)], fill=(40, 40, 40), width=5)
    # mirror
    if spec.get("mirror_visible", True):
        m = [(438, 262), (474, 247), (478, 270)]
        d.polygon(m, fill=mir_c)
        wobble_line(d, m + [m[0]], rnd, width=2)
    # bonnet
    bd = spec["bonnet"]
    if bd == "scoop":
        sc = [(225, 287), (250, 258), (318, 254), (335, 279)]
        d.polygon(sc, fill=body_c)
        wobble_line(d, sc, rnd, width=3)
        d.polygon([(250, 262), (262, 270), (262, 282), (250, 286)], fill=(20, 20, 20))
    elif bd == "vents":
        for i in range(4):
            d.line([(220 + i * 28, 283 - i * 2), (240 + i * 28, 280 - i * 2)], fill=(20, 20, 20), width=6)
    elif bd == "stripes":
        for off in (-7, 7):
            d.line([(110, 312 + off), (380, 270 + off), (470, 200 + off // 2), (680, 196 + off // 2)], fill=(250, 250, 250), width=8)
    elif bd == "power dome":
        d.arc([180, 255, 370, 315], 190, 350, fill=(20, 20, 20), width=4)
    # outline + arches
    wobble_line(d, body + [body[0]], rnd, width=4)
    wobble_line(d, cabin, rnd, width=4)
    for cx in (250, 760):
        d.pieslice([cx - 78, 317, cx + 78, 473], 180, 360, fill=(252, 251, 246))
        draw_wheel(d, cx, 395, spec["wheels"], rnd)
    d.ellipse([92, 318, 120, 338], fill=(255, 220, 90))
    d.rectangle([892, 300, 910, 322], fill=(220, 20, 20))
    wobble_line(d, [(40, 462), (960, 462)], rnd, width=2, fill=(120, 120, 120))
    if quality == "low":  # stray scribbles and smudges
        for _ in range(12):
            x, y = rnd.randint(50, 950), rnd.randint(50, 560)
            d.line([(x, y), (x + rnd.randint(-60, 60), y + rnd.randint(-30, 30))], fill=(110, 110, 110), width=2)
    d.text((40, 30), label, fill=(60, 60, 60), font=font(26))
    return im


SKETCHES = [
    # file, body, door, mirror, bonnet, wheels, quality, label, body_style
    ("sketch_01.png", "red", "red", "black", "scoop", "5-spoke", "high", "Team Apex - 'Firebird'", "coupe"),
    ("sketch_02.png", "red", "red", "black", "scoop", "5-spoke", "low", "Team Apex - quick version", "coupe"),
    ("sketch_03.png", "blue", "white", "silver", "power dome", "multi-spoke", "high", "Team Torque - 'Night Run'", "saloon"),
    ("sketch_04.png", "red", "black", "black", "vents", "5-spoke", "high", "Team Piston - 'Venom'", "coupe"),
    ("sketch_05.png", "lime green", "purple", "pink", "stripes", "off-road", "high", "Team Gearbox - 'Joker'", "coupe"),
    ("sketch_06.png", "blue", "blue", "silver", "power dome", "multi-spoke", "low", "Team Torque - v2", "saloon"),
    ("sketch_07.png", "white", "white", "black", "flat", "turbine", "high", "Team Volt - 'Ghost'", "hatchback"),
    ("sketch_08.png", "red", "red", "red", "scoop", "5-spoke", "high", "Team Clutch - 'Inferno'", "coupe"),
]


def make_sketches():
    out = ROOT / "data" / "sample_sketches"
    out.mkdir(parents=True, exist_ok=True)
    for i, (fn, b, dr, m, bn, w, q, label, style) in enumerate(SKETCHES):
        im = draw_car({"body": b, "door": dr, "mirror": m, "bonnet": bn, "wheels": w}, q, seed=i + 7, label=label)
        truth = {
            "body_colour": b, "door_colour": dr, "mirror_colour": m, "bonnet_design": bn, "tyre_style": w, "body_style": style,
            "quality_score": {"high": 8, "low": 4}[q] + (1 if i in (0, 2) else 0) - (1 if i == 4 else 0),
        }
        meta = PngInfo()
        meta.add_text("spec", json.dumps(truth))
        im.save(out / fn, pnginfo=meta)
    print(f"wrote {len(SKETCHES)} sketches to {out}")


def lego_car(body, door_l, mirrors, bonnet_scoop=True, seed=0):
    rnd = random.Random(seed)
    im = Image.new("RGB", (1000, 600), (248, 248, 248))
    d = ImageDraw.Draw(im)
    B, Dc = COL[body], COL[door_l]

    def brick(x, y, w, h, c, studs=True):
        d.rectangle([x, y, x + w, y + h], fill=c, outline=tuple(max(0, v - 50) for v in c), width=3)
        if studs:
            for sx in range(x + 12, x + w - 10, 40):
                d.rectangle([sx, y - 10, sx + 22, y], fill=c, outline=tuple(max(0, v - 50) for v in c), width=2)

    d.rectangle([120, 380, 880, 410], fill=(60, 60, 60))  # chassis
    brick(120, 300, 320, 80, B)
    brick(440, 300, 200, 80, Dc)
    brick(640, 300, 240, 80, B)
    brick(140, 270, 260, 30, B)  # bonnet plate
    if bonnet_scoop:
        d.polygon([(220, 270), (250, 238), (320, 238), (340, 270)], fill=B, outline=(90, 10, 20))
        d.rectangle([255, 246, 300, 262], fill=(20, 20, 20))
    d.polygon([(400, 300), (470, 210), (560, 210), (560, 300)], fill=(200, 230, 245), outline=(120, 140, 150))  # windscreen
    brick(560, 220, 300, 80, B)
    for i, mc in enumerate(mirrors):
        if mc:
            d.polygon([(410 + i * 8, 262), (448 + i * 8, 248), (448 + i * 8, 278)], fill=COL[mc], outline=(0, 0, 0))
    for cx in (260, 750):
        d.ellipse([cx - 62, 360, cx + 62, 484], fill=(25, 25, 25))
        d.ellipse([cx - 32, 390, cx + 32, 454], fill=(175, 180, 185))
        for k in range(5):
            import math

            a = k * 2 * math.pi / 5
            d.line([(cx, 422), (cx + 30 * math.cos(a), 422 + 30 * math.sin(a))], fill=(90, 90, 90), width=7)
    d.rectangle([120, 312, 140, 334], fill=(255, 245, 200))
    d.rectangle([862, 312, 880, 334], fill=(230, 30, 30))
    return im


def make_builds():
    out = ROOT / "data" / "sample_builds"
    out.mkdir(parents=True, exist_ok=True)
    good = lego_car("red", "red", ["black", "black"], True, 1)
    obs_good = {"body_colour": "red", "door_colour": "red", "mirror_count": 2, "mirror_colour": "black", "bonnet_feature": "scoop",
                "wheel_count": 4, "wheel_style": "5-spoke", "windscreen_present": True, "lights_present": True, "symmetry_ok": True}
    bad = lego_car("red", "blue", ["black", None], True, 2)
    obs_bad = dict(obs_good, door_colour="blue (one door)", mirror_count=1, symmetry_ok=False)
    for im, obs, fn in ((good, obs_good, "build_team_apex_good.png"), (bad, obs_bad, "build_team_piston_defects.png")):
        meta = PngInfo()
        meta.add_text("spec", json.dumps({"observations": obs}))
        im.save(out / fn, pnginfo=meta)
    print(f"wrote sample builds to {out}")


def make_template():
    W, H = 2480, 1754  # A4 landscape @ 300 dpi
    im = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(im)
    d.text((120, 90), "AI IMMERSION DAY  -  DREAM CAR SKETCH", fill=(20, 20, 20), font=font(78))
    d.text((120, 200), "Team: ____________________     Designer: ____________________     Car name: ____________________", fill=(60, 60, 60), font=font(44))
    sx, sy, ox, oy = 2.1, 2.1, 190, 360
    def S(pts):
        return [(ox + x * sx, oy + y * sy) for x, y in pts]
    grey = (205, 205, 205)
    for seg in ([(90, 395), (88, 322), (140, 297), (380, 270), (790, 262), (905, 290), (912, 395)], [(380, 272), (472, 192), (680, 188), (790, 265)]):
        pts = S(seg)
        for a, b in zip(pts, pts[1:]):
            # dashed line
            n = 18
            for k in range(0, n, 2):
                d.line([(a[0] + (b[0] - a[0]) * k / n, a[1] + (b[1] - a[1]) * k / n), (a[0] + (b[0] - a[0]) * (k + 1) / n, a[1] + (b[1] - a[1]) * (k + 1) / n)], fill=grey, width=6)
    for cx in (250, 760):
        x, y = ox + cx * sx, oy + 395 * sy
        d.ellipse([x - 130, y - 130, x + 130, y + 130], outline=grey, width=6)
    tips = "Use your markers to show:  (1) BODY colour  (2) DOOR colour  (3) MIRROR colour  (4) BONNET design (scoop / vents / dome / stripes / flat)  (5) WHEEL style"
    d.text((120, 1580), tips, fill=(40, 40, 40), font=font(38))
    out = ROOT / "props"
    out.mkdir(exist_ok=True)
    im.save(out / "sketch_template_A4.png")
    print("wrote props/sketch_template_A4.png")


if __name__ == "__main__":
    make_sketches()
    make_builds()
    make_template()
