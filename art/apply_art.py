"""Copy the shapes from art/abomb-family.svg into index.html and favicon.svg.

Run from the repo root after saving the artwork:

    python art/apply_art.py

The SVG needs three layers (groups) with the ids cloud, shadow and family,
each containing one or more <path> elements. The artwork may be drawn at any
scale: the "reference" layer's 181 x 153 image marks where the page's
181 x 153 frame sits, and every path is mapped back into page units from it.
(Without a reference image, the viewBox is assumed to be that frame, scaled.)
Everything else in the file is ignored.
"""
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ART = ROOT / "art" / "abomb-family.svg"
PAGE = ROOT / "index.html"
FAVICON = ROOT / "favicon.svg"
SVG_NS = "{http://www.w3.org/2000/svg}"
SHAPES = {"circle", "ellipse", "rect", "polygon", "polyline", "line"}
FRAME_W, FRAME_H = 181.0, 153.0
NUMBER = re.compile(r"[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
PARAMS = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7, "Z": 0}


def fail(msg):
    sys.exit(f"apply_art: {msg}")


# ---------------------------------------------------------------- path data

def tokenize(d):
    """Yield commands and numbers; arc flags may be packed without separators."""
    i, cmd, argn = 0, None, 0
    while i < len(d):
        ch = d[i]
        if ch in " \t\r\n,":
            i += 1
        elif ch.upper() in PARAMS:
            cmd, argn = ch, 0
            yield ch
            i += 1
        elif cmd and cmd.upper() == "A" and argn % 7 in (3, 4):
            yield float(ch)  # large-arc / sweep flag: a single 0 or 1
            argn += 1
            i += 1
        else:
            m = NUMBER.match(d, i)
            if not m:
                fail(f"can't read path data near: {d[i:i + 20]!r}")
            yield float(m.group())
            argn += 1
            i = m.end()


def to_absolute(d):
    """Parse path data into absolute (CMD, [numbers]) segments; H/V become L."""
    out, cmd, cx, cy, sx, sy = [], None, 0.0, 0.0, 0.0, 0.0
    toks = list(tokenize(d))
    i = 0
    while i < len(toks):
        if isinstance(toks[i], str):
            cmd = toks[i]
            i += 1
            if cmd in "Zz":
                out.append(("Z", []))
                cx, cy = sx, sy
                continue
        n = PARAMS[cmd.upper()]
        args = toks[i:i + n]
        i += n
        rel = cmd.islower()
        C = cmd.upper()
        if C == "H":
            C, args = "L", [args[0] + (cx if rel else 0), cy]
        elif C == "V":
            C, args = "L", [cx, args[0] + (cy if rel else 0)]
        elif C == "A":
            if rel:
                args = args[:5] + [args[5] + cx, args[6] + cy]
        elif rel:
            args = [v + (cx if k % 2 == 0 else cy) for k, v in enumerate(args)]
        out.append((C, args))
        cx, cy = args[-2], args[-1]
        if C == "M":
            sx, sy = cx, cy
            cmd = "l" if rel else "L"  # extra pairs after M are line-tos
    return out


def fmt(v):
    s = f"{v:.3f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def map_path(d, k, ox, oy):
    """Absolute path data with every point mapped by p -> (p - origin) / k."""
    parts = []
    for C, a in to_absolute(d):
        if C == "Z":
            parts.append("Z")
        elif C == "A":
            rx, ry, rot, large, sweep, x, y = a
            parts.append(f"A{fmt(rx / k)},{fmt(ry / k)} {fmt(rot)} {int(large)} {int(sweep)} "
                         f"{fmt((x - ox) / k)},{fmt((y - oy) / k)}")
        else:
            pts = [fmt((v - (ox if j % 2 == 0 else oy)) / k) for j, v in enumerate(a)]
            parts.append(C + " ".join(f"{pts[j]},{pts[j + 1]}" for j in range(0, len(pts), 2)))
    return "".join(parts)


# ---------------------------------------------------------------- the file

def frame_mapping(root):
    """(scale, origin x, origin y) of the 181 x 153 page frame inside the artwork."""
    for el in root.iter(SVG_NS + "image"):
        if float(el.get("width", 0)) == FRAME_W and float(el.get("height", 0)) == FRAME_H:
            t = el.get("transform", "")
            nums = [float(v) for v in NUMBER.findall(t)]
            if not t:
                return 1.0, float(el.get("x", 0)), float(el.get("y", 0))
            if t.startswith("matrix") and len(nums) == 6 and nums[1] == nums[2] == 0 and nums[0] == nums[3]:
                return nums[0], nums[4], nums[5]
            m = re.fullmatch(r"\s*translate\(([^)]*)\)\s*scale\(([^)]*)\)\s*", t)
            if m:
                tx, ty = ([float(v) for v in NUMBER.findall(m.group(1))] + [0])[:2]
                sc = [float(v) for v in NUMBER.findall(m.group(2))]
                if len(sc) == 1 or sc[0] == sc[1]:
                    return sc[0], tx, ty
            m = re.fullmatch(r"\s*scale\(([^)]*)\)\s*", t)
            if m:
                sc = [float(v) for v in NUMBER.findall(m.group(1))]
                if len(sc) == 1 or sc[0] == sc[1]:
                    return sc[0], 0.0, 0.0
            fail(f'the reference image has a transform I can\'t read ("{t}"). Keep it unrotated and evenly scaled.')
    vb = [float(v) for v in NUMBER.findall(root.get("viewBox") or "")]
    if len(vb) != 4:
        fail("no viewBox and no reference image to work out the artwork's scale.")
    k = vb[2] / FRAME_W
    if abs(vb[3] / FRAME_H - k) > 0.01 * k:
        fail(f"viewBox {vb} isn't a scaled {FRAME_W:g} x {FRAME_H:g} frame, and there's no reference image to go by.")
    return k, vb[0], vb[1]


def class_rules(root):
    """fill-rule per CSS class, from Illustrator's internal <style> block."""
    rules = {}
    for style in root.iter(SVG_NS + "style"):
        for names, body in re.findall(r"([^{}]+)\{([^}]*)\}", style.text or ""):
            m = re.search(r"fill-rule\s*:\s*(\w+)", body)
            if m:
                for name in names.split(","):
                    rules[name.strip().lstrip(".")] = m.group(1)
    return rules


def fill_rule(el, rules):
    if el.get("fill-rule"):
        return el.get("fill-rule")
    m = re.search(r"fill-rule\s*:\s*(\w+)", el.get("style", ""))
    if m:
        return m.group(1)
    for cls in (el.get("class") or "").split():
        if cls in rules:
            return rules[cls]
    return None


def layer(root, name, mapping, rules):
    """Return (d, fill_rule) for the named layer in page units, merged into one path."""
    group = next((el for el in root.iter() if el.get("id") == name), None)
    if group is None:
        fail(f'no layer named "{name}". In Illustrator, export with Object IDs: Layer Names.')
    paths = []
    for el in group.iter():
        tag = el.tag.replace(SVG_NS, "")
        if el.get("transform"):
            fail(f'"{name}" contains a transform. Select the layer\'s art and use Object > Transform > Reset Bounding Box, or ungroup it, then export again.')
        if tag in SHAPES:
            fail(f'"{name}" contains a separate {tag} shape. Select everything on that layer and click Pathfinder > Unite, then export again.')
        if tag == "path":
            paths.append(el)
    if not paths:
        fail(f'layer "{name}" has no paths.')
    rule = "evenodd" if any(fill_rule(p, rules) == "evenodd" for p in paths) else None
    if len(paths) > 1:
        print(f'apply_art: note: "{name}" has {len(paths)} separate paths; merging them. Pathfinder > Unite gives cleaner results.')
        rule = None  # separate pieces may overlap; even-odd would punch holes where they do
    d = "".join(map_path(p.get("d"), *mapping) for p in paths)
    return d, rule


def attr(rule):
    return f' fill-rule="{rule}"' if rule else ""


def replace_once(html, pattern, new, what):
    html, n = re.subn(pattern, lambda _: new, html, count=1, flags=re.S)
    if n != 1:
        fail(f"couldn't find the {what} path in index.html.")
    return html


def main():
    root = ET.parse(ART).getroot()
    mapping = frame_mapping(root)
    rules = class_rules(root)

    cloud, cloud_rule = layer(root, "cloud", mapping, rules)
    shadow, shadow_rule = layer(root, "shadow", mapping, rules)
    family, family_rule = layer(root, "family", mapping, rules)

    html = PAGE.read_text(encoding="utf-8")
    html = replace_once(html, r'(?<=<g class="billow">)\s*<path [^>]*/>',
                        f'\n        <path fill="var(--ink)"{attr(cloud_rule)} d="{cloud}"/>', "cloud")
    html = replace_once(html, r'(?<=<g class="shadows">)\s*<path [^>]*/>',
                        f'\n        <path fill="var(--shadow)"{attr(shadow_rule)} d="{shadow}"/>', "shadow")
    html = replace_once(html, r'<path class="family"[^>]*/>',
                        f'<path class="family"{attr(family_rule)} d="{family}"/>', "family")
    PAGE.write_text(html, encoding="utf-8", newline="\n")

    FAVICON.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="8 2 165 112">'
        '<rect x="8" y="2" width="165" height="112" rx="14" fill="#000"/>'
        f'<path fill="#e2f34b"{attr(cloud_rule)} d="{cloud}"/>'
        f'<path fill="#000"{attr(family_rule)} d="{family}"/></svg>',
        encoding="utf-8", newline="\n")
    k = mapping[0]
    print(f"apply_art: updated index.html and favicon.svg (artwork at {k:g}x scale)")


if __name__ == "__main__":
    main()
