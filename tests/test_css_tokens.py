"""Design-token discipline for site/style.css, and contrast of the colour tokens.

Rules:
- Numbers, hex colours and colour functions appear only in custom-property
  (token) definitions; everywhere else only 0, 1, 1fr and 100% are allowed.
- Media queries carry no numbers: the layout is intrinsic, not breakpoint-based.
- Every var(--x) is defined, and every defined token is used.
- No inline styles from HTML or JS, which would bypass the tokens.
- Every text colour meets WCAG AA (4.5:1) on each background it is used on,
  in both the light and the dark theme.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSS = re.sub(r"/\*.*?\*/", "", (ROOT / "site" / "style.css").read_text(), flags=re.S)
HTML = (ROOT / "site" / "index.html").read_text()
JS = (ROOT / "site" / "app.js").read_text()

DECLARATION = re.compile(r"(--[\w-]+|[a-z-]+)\s*:\s*([^;{}]+?)\s*(?=;|})")
NUMBER = re.compile(r"(?<![\w#.-])-?\d*\.?\d+[a-z%]*")
# Identities, not design decisions: nothing, one share (flex 1, grid 1fr), all of it.
ALLOWED_NUMBERS = {"0", "1", "1fr", "100%"}
COLOR_LITERAL = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(rgb|rgba|hsl|hsla|oklch|oklab|lab|lch)\(")
AA = 4.5


def declarations(css):
    return [(prop, value) for prop, value in DECLARATION.findall(css)]


def token_block(css, dark):
    """The token declarations of the light :root, or of the dark-scheme override."""
    if dark:
        block = re.search(r"@media \(prefers-color-scheme: dark\)\s*{\s*:root\s*{(.*?)}\s*}", css, re.S)
    else:
        block = re.search(r"^:root\s*{(.*?)^}", css, re.S | re.M)
    assert block, "token block not found"
    return dict(DECLARATION.findall(block.group(1)))


def hex_rgb(value):
    value = value.strip().lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def luminance(rgb):
    def channel(c):
        c = c / 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((luminance(a), luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def mix(fg, bg, pct):
    """color-mix(in srgb, fg pct, bg): linear blend of the encoded channels."""
    t = pct / 100
    return tuple(round(f * t + b * (1 - t)) for f, b in zip(fg, bg))


class TokenDiscipline(unittest.TestCase):
    def test_numbers_and_colours_only_in_token_definitions(self):
        offenders = []
        for prop, value in declarations(CSS):
            if prop.startswith("--"):
                continue
            bare = re.sub(r"var\(--[\w-]+\)", "", value)
            numbers = [n for n in NUMBER.findall(bare) if n not in ALLOWED_NUMBERS]
            if numbers or COLOR_LITERAL.search(bare):
                offenders.append(f"{prop}: {value}")
        self.assertEqual(offenders, [])

    def test_media_queries_have_no_breakpoints(self):
        for condition in re.findall(r"@(?:media|container)([^{]*)", CSS):
            self.assertNotRegex(condition, r"\d", condition)

    def test_every_used_token_is_defined_and_every_defined_token_used(self):
        defined = {prop for prop, _ in declarations(CSS) if prop.startswith("--")}
        used = set(re.findall(r"var\((--[\w-]+)", CSS))
        self.assertEqual(sorted(used - defined), [], "used but never defined")
        self.assertEqual(sorted(defined - used), [], "defined but never used")

    def test_every_grid_declares_shrinkable_columns(self):
        # An implicit grid column is sized to its widest child's max-content, so one
        # wide child (a scrolling tab strip, a long file name) widens the whole page.
        for selector, body in re.findall(r"([^{}]+){([^{}]*)}", CSS):
            if re.search(r"display:\s*grid", body):
                self.assertIn("grid-template-columns", body, selector.strip())

    def test_no_inline_styles(self):
        self.assertNotRegex(HTML, r"\sstyle\s*=")
        self.assertNotRegex(JS, r"\.style\b|[\"']style[\"']")
        self.assertIsNone(COLOR_LITERAL.search(JS))


class Contrast(unittest.TestCase):
    # (text token, background token or ("mix", colour token, tint token, base token))
    PAIRS = [
        ("--c-text", "--c-bg"), ("--c-text", "--c-surface"), ("--c-text", "--c-surface-sunken"),
        ("--c-text-muted", "--c-bg"), ("--c-text-muted", "--c-surface"), ("--c-text-muted", "--c-surface-sunken"),
        ("--c-accent", "--c-bg"), ("--c-accent", "--c-surface"), ("--c-accent", "--c-accent-soft"),
        ("--c-accent-hover", "--c-surface"),
        ("--c-on-accent", "--c-accent"), ("--c-on-accent", "--c-accent-hover"),
        ("--c-bad", "--c-bg"),
        *[(c, ("mix", c, "--tint", "--c-surface")) for c in ("--c-ok", "--c-warn", "--c-info", "--c-bad", "--c-neutral")],
    ]

    def check(self, dark):
        tokens = {**token_block(CSS, dark=False), **(token_block(CSS, dark=True) if dark else {})}
        failures = []
        for fg, bg in self.PAIRS:
            fg_rgb = hex_rgb(tokens[fg])
            if isinstance(bg, tuple):
                _, colour, tint, base = bg
                bg_rgb = mix(hex_rgb(tokens[colour]), hex_rgb(tokens[base]), float(tokens[tint].rstrip("%")))
                bg_name = f"{colour} {tokens[tint]} on {base}"
            else:
                bg_rgb, bg_name = hex_rgb(tokens[bg]), bg
            ratio = contrast(fg_rgb, bg_rgb)
            if ratio < AA:
                failures.append(f"{fg} on {bg_name}: {ratio:.2f}")
        self.assertEqual(failures, [], "dark" if dark else "light")

    def test_light_theme_meets_aa(self):
        self.check(dark=False)

    def test_dark_theme_meets_aa(self):
        self.check(dark=True)


if __name__ == "__main__":
    unittest.main()
