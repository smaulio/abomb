"""Copy the shapes from art/abomb-family.svg into index.html and favicon.svg.

Run from the repo root after saving the artwork:

    python art/apply_art.py

The SVG needs three layers (groups) with the ids cloud, shadow and family,
each containing one or more <path> elements. Everything else in the file,
such as the reference layer, is ignored.
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


def fail(msg):
    sys.exit(f"apply_art: {msg}")


def layer(root, name):
    """Return (d, fill_rule) for the named layer, merged into one path."""
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
    rule = "evenodd" if any(p.get("fill-rule") == "evenodd" for p in paths) else None
    if len(paths) > 1:
        print(f'apply_art: note: "{name}" has {len(paths)} separate paths; merging them. Pathfinder > Unite gives cleaner results.')
        rule = None  # separate pieces may overlap; even-odd would punch holes where they do
    d = " ".join(" ".join(p.get("d").split()) for p in paths)
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
    vb = (root.get("viewBox") or "").replace(",", " ").split()
    if [float(v) for v in vb] != [0, 0, 181, 153]:
        fail(f'viewBox is "{root.get("viewBox")}", expected "0 0 181 153". Keep the artboard at 181 x 153 with its origin unchanged.')

    cloud, cloud_rule = layer(root, "cloud")
    shadow, shadow_rule = layer(root, "shadow")
    family, family_rule = layer(root, "family")

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
    print("apply_art: updated index.html and favicon.svg")


main()
