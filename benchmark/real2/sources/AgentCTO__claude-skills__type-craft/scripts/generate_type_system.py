#!/usr/bin/env python3
"""
Typography System Generator

Generates a complete, production-ready CSS custom properties block for a
typographic design system based on user-selected parameters.

Usage:
    generate_type_system.py [OPTIONS]

Options:
    --ratio NAME_OR_NUMBER  Type scale ratio (default: major-third)
    --base-size PX          Base font size in px (default: 16)
    --spacing SYSTEM        Spacing system: 8px-grid, fibonacci, golden-ratio (default: 8px-grid)
    --fonts PRESET          Font stack: system, inter, playfair-montserrat,
                            montserrat-merriweather, poppins-lora, source-family,
                            roboto-family, custom (default: system)
    --heading-font STACK    Custom heading font stack (requires --fonts custom)
    --body-font STACK       Custom body font stack (requires --fonts custom)
    --color-mode MODE       Color mode: light, dark (default: light)
    --fluid                 Generate clamp()-based fluid type scale
    --steps MIN,MAX         Type scale step range (default: -2,5)
    --json                  Output structured JSON instead of CSS

Examples:
    generate_type_system.py
    generate_type_system.py --ratio perfect-fourth --fluid
    generate_type_system.py --ratio 1.333 --fonts playfair-montserrat --color-mode dark
    generate_type_system.py --spacing fibonacci --steps -1,6
    generate_type_system.py --fonts custom --heading-font "Playfair Display, serif" --body-font "Inter, sans-serif"
    generate_type_system.py --json

Ratios derived from musical intervals (Klink 2000, typescale.com).
Spacing systems based on Material Design 8px grid, Fibonacci sequence,
and golden ratio (phi = 1.618).
"""

import argparse
import json
import math
import sys

# --- Named Ratios ---

RATIOS = {
    "minor-second":    1.067,
    "major-second":    1.125,
    "minor-third":     1.2,
    "major-third":     1.25,
    "perfect-fourth":  1.333,
    "augmented-fourth": 1.414,
    "perfect-fifth":   1.5,
    "golden-ratio":    1.618,
}

RATIO_DESCRIPTIONS = {
    "minor-second":    "Barely perceptible steps — dense dashboards, data-heavy UIs",
    "major-second":    "Subtle, controlled — mobile apps, e-commerce, compact layouts",
    "minor-third":     "Moderate, clear — documentation, blogs, all-purpose default",
    "major-third":     "Balanced, elegant — most websites (recommended default)",
    "perfect-fourth":  "Distinct hierarchy — editorial, mixed content types",
    "augmented-fourth": "Dramatic (sqrt 2) — landing pages, promotional material",
    "perfect-fifth":   "High contrast — banners, advertisements, attention-grabbing",
    "golden-ratio":    "Maximum drama — luxury brands, hero headings, creative sites",
}

# --- Font Stacks ---

FONT_STACKS = {
    "system": {
        "heading": "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
        "body":    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
        "mono":    "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace",
        "label":   "System stack (zero network requests)",
    },
    "inter": {
        "heading": "Inter, Roboto, 'Helvetica Neue', Arial, sans-serif",
        "body":    "Inter, Roboto, 'Helvetica Neue', Arial, sans-serif",
        "mono":    "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace",
        "label":   "Inter — clean neo-grotesque for UI-focused designs",
    },
    "playfair-montserrat": {
        "heading": "'Playfair Display', Georgia, 'Times New Roman', serif",
        "body":    "Montserrat, 'Helvetica Neue', Arial, sans-serif",
        "mono":    "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace",
        "label":   "Playfair Display + Montserrat — editorial elegance",
    },
    "montserrat-merriweather": {
        "heading": "Montserrat, 'Helvetica Neue', Arial, sans-serif",
        "body":    "Merriweather, Georgia, 'Times New Roman', serif",
        "mono":    "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace",
        "label":   "Montserrat + Merriweather — geometric heading + reading comfort",
    },
    "poppins-lora": {
        "heading": "Poppins, 'Helvetica Neue', Arial, sans-serif",
        "body":    "Lora, Georgia, 'Times New Roman', serif",
        "mono":    "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace",
        "label":   "Poppins + Lora — contemporary + warm",
    },
    "source-family": {
        "heading": "'Source Sans 3', 'Source Sans Pro', 'Helvetica Neue', Arial, sans-serif",
        "body":    "'Source Serif 4', 'Source Serif Pro', Georgia, serif",
        "mono":    "'Source Code Pro', ui-monospace, Menlo, Consolas, monospace",
        "label":   "Source family (Adobe) — designed as a matching set",
    },
    "roboto-family": {
        "heading": "'Roboto Slab', Georgia, serif",
        "body":    "Roboto, 'Helvetica Neue', Arial, sans-serif",
        "mono":    "'Roboto Mono', ui-monospace, Menlo, Consolas, monospace",
        "label":   "Roboto family (Google) — cohesive Material family",
    },
}

# --- Color Palettes ---

COLOR_MODES = {
    "light": {
        "text-primary":   "#1a1a2e",   # ~16:1 on white
        "text-secondary": "#4a4a68",   # ~7.4:1 — AAA
        "text-muted":     "#6b6b8a",   # ~4.8:1 — AA
        "bg-primary":     "#ffffff",
        "bg-surface":     "#f8f9fa",
    },
    "dark": {
        "text-primary":   "#f0f0f5",   # ~15.4:1 on dark bg
        "text-secondary": "#b0b0c8",   # ~7.2:1 — AAA
        "text-muted":     "#8888a8",   # ~4.6:1 — AA
        "bg-primary":     "#0f0f1a",
        "bg-surface":     "#1a1a2e",
    },
}

# --- Spacing Systems ---

FIBONACCI = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89]

PHI = 1.618


def generate_type_scale(base_size: float, ratio: float, step_min: int, step_max: int) -> list:
    """Generate type scale steps as (step, px_size, rem_size) tuples."""
    steps = []
    for step in range(step_min, step_max + 1):
        px = base_size * (ratio ** step)
        rem = px / 16.0
        steps.append((step, round(px, 2), round(rem, 4)))
    return steps


def generate_fluid_scale(base_size: float, ratio: float, step_min: int, step_max: int,
                         min_vw: float = 360, max_vw: float = 1240) -> list:
    """Generate fluid type scale using clamp() with rem+vw formula."""
    mobile_ratio = max(1.067, ratio - 0.067)  # slightly tighter on mobile
    steps = []
    for step in range(step_min, step_max + 1):
        mobile_px = base_size * (mobile_ratio ** step)
        desktop_px = base_size * (ratio ** step)
        # For negative steps, a tighter mobile ratio produces LARGER values,
        # so always use the smaller value as min and larger as max.
        min_px = min(mobile_px, desktop_px)
        max_px = max(mobile_px, desktop_px)
        min_rem = min_px / 16.0
        max_rem = max_px / 16.0
        # Calculate preferred value: rem_base + vw_component
        # Solve: min_rem = rem_base + vw_component * (min_vw / 100)
        #        max_rem = rem_base + vw_component * (max_vw / 100)
        vw_diff = (max_vw - min_vw) / 100.0
        if vw_diff > 0:
            vw_component = (max_rem - min_rem) / vw_diff
            rem_base = min_rem - vw_component * (min_vw / 100.0)
        else:
            vw_component = 0
            rem_base = min_rem

        clamp_str = f"clamp({min_rem:.4f}rem, {rem_base:.4f}rem + {vw_component:.4f}vw, {max_rem:.4f}rem)"
        steps.append((step, clamp_str, round(min_px, 2), round(max_px, 2)))
    return steps


def step_to_name(step: int) -> str:
    """Map a type scale step number to a CSS custom property name."""
    names = {
        -3: "text-3xs",
        -2: "text-2xs",
        -1: "text-xs",
        0:  "text-base",
        1:  "text-lg",
        2:  "text-xl",
        3:  "text-2xl",
        4:  "text-3xl",
        5:  "text-4xl",
        6:  "text-5xl",
        7:  "text-6xl",
    }
    return names.get(step, f"text-step-{step}")


def step_to_use(step: int) -> str:
    """Map a type scale step to its typical use."""
    uses = {
        -3: "Fine print",
        -2: "Fine print",
        -1: "Captions, labels",
        0:  "Body text",
        1:  "Large body / H6",
        2:  "H5",
        3:  "H4",
        4:  "H3",
        5:  "H2",
        6:  "H1",
        7:  "Display / Hero",
    }
    return uses.get(step, "")


def generate_spacing_8px() -> list:
    """Generate 8px grid spacing tokens."""
    return [
        ("space-3xs", 0.25,   4),
        ("space-2xs", 0.5,    8),
        ("space-xs",  0.75,  12),
        ("space-s",   1.0,   16),
        ("space-m",   1.5,   24),
        ("space-l",   2.0,   32),
        ("space-xl",  3.0,   48),
        ("space-2xl", 4.0,   64),
        ("space-3xl", 6.0,   96),
    ]


def generate_spacing_fibonacci() -> list:
    """Generate Fibonacci-based spacing tokens."""
    names = ["space-3xs", "space-2xs", "space-xs", "space-sm", "space-md",
             "space-lg", "space-xl", "space-2xl", "space-3xl", "space-4xl"]
    tokens = []
    for i, (name, fib) in enumerate(zip(names, FIBONACCI)):
        rem = fib / 16.0
        tokens.append((name, round(rem, 4), fib))
    return tokens


def generate_spacing_golden() -> list:
    """Generate golden ratio spacing tokens."""
    tokens = []
    names = ["space-3xs", "space-2xs", "space-xs", "space-sm", "space-md",
             "space-lg", "space-xl", "space-2xl", "space-3xl"]
    base = 1.0  # 1rem = 16px
    # Generate: base / phi^3, base / phi^2, base / phi, base, base * phi, ...
    values = []
    for exp in range(-4, 5):
        values.append(base * (PHI ** exp))
    for name, rem in zip(names, values):
        px = round(rem * 16, 1)
        tokens.append((name, round(rem, 4), px))
    return tokens


def format_css(config: dict) -> str:
    """Format the complete type system as CSS custom properties."""
    lines = [":root {"]

    # Fonts
    fonts = config["fonts"]
    lines.append("  /* === FONTS === */")
    lines.append(f"  --font-heading: {fonts['heading']};")
    lines.append(f"  --font-body: {fonts['body']};")
    lines.append(f"  --font-mono: {fonts['mono']};")
    lines.append("")

    # Type scale
    ratio_name = config.get("ratio_name", "")
    ratio_val = config["ratio"]
    label = f" ({ratio_name})" if ratio_name else ""
    lines.append(f"  /* === TYPE SCALE — ratio: {ratio_val}{label} === */")

    if config["fluid"]:
        for step, clamp_str, min_px, max_px in config["type_scale"]:
            name = step_to_name(step)
            use = step_to_use(step)
            comment = f"  /* {min_px}px → {max_px}px — {use} */" if use else f"  /* {min_px}px → {max_px}px */"
            lines.append(comment)
            lines.append(f"  --{name}: {clamp_str};")
    else:
        for step, px, rem in config["type_scale"]:
            name = step_to_name(step)
            use = step_to_use(step)
            comment = f"  /* {px}px — {use} */" if use else f"  /* {px}px */"
            lines.append(comment)
            lines.append(f"  --{name}: {rem}rem;")
    lines.append("")

    # Line heights
    lines.append("  /* === LINE HEIGHTS === */")
    lines.append("  --leading-tight:   1.1;")
    lines.append("  --leading-snug:    1.3;")
    lines.append("  --leading-normal:  1.5;")
    lines.append("  --leading-relaxed: 1.65;")
    lines.append("  --leading-loose:   1.8;")
    lines.append("")

    # Tracking
    lines.append("  /* === TRACKING (letter-spacing) === */")
    lines.append("  --tracking-tight:  -0.01em;")
    lines.append("  --tracking-normal:  0;")
    lines.append("  --tracking-wide:    0.025em;")
    lines.append("  --tracking-wider:   0.05em;")
    lines.append("  --tracking-widest:  0.1em;")
    lines.append("")

    # Weights
    lines.append("  /* === WEIGHTS === */")
    lines.append("  --weight-normal:    400;")
    lines.append("  --weight-medium:    500;")
    lines.append("  --weight-semibold:  600;")
    lines.append("  --weight-bold:      700;")
    lines.append("")

    # Measure
    lines.append("  /* === MEASURE (line length) === */")
    lines.append("  --measure-narrow: 45ch;")
    lines.append("  --measure-base:   65ch;")
    lines.append("  --measure-wide:   80ch;")
    lines.append("")

    # Spacing
    spacing_label = config["spacing_system"]
    lines.append(f"  /* === SPACING ({spacing_label}) === */")
    for name, rem, px in config["spacing"]:
        px_display = int(px) if px == int(px) else px
        lines.append(f"  --{name}: {rem}rem;  /* {px_display}px */")
    lines.append("")

    # Layout
    lines.append("  /* === LAYOUT === */")
    lines.append("  --content-width: 1.618fr;  /* golden ratio */")
    lines.append("  --sidebar-width: 1fr;")
    lines.append("  --container-max: 1200px;")
    lines.append("")

    # Colors
    mode = config["color_mode"]
    colors = config["colors"]
    lines.append(f"  /* === COLORS ({mode} mode, contrast-safe) === */")
    for key, val in colors.items():
        lines.append(f"  --{key}: {val};")

    lines.append("}")
    lines.append("")

    # Base styles
    lines.append("/* === BASE STYLES === */")
    lines.append("body {")
    lines.append("  font-family: var(--font-body);")
    lines.append("  font-size: var(--text-base);")
    lines.append("  line-height: var(--leading-normal);")
    lines.append("  font-weight: var(--weight-normal);")
    lines.append("  color: var(--text-primary);")
    lines.append("  background: var(--bg-primary);")
    lines.append("}")
    lines.append("")

    # Headings
    lines.append("h1, h2, h3, h4, h5, h6 {")
    lines.append("  font-family: var(--font-heading);")
    lines.append("  font-weight: var(--weight-bold);")
    lines.append("  letter-spacing: var(--tracking-tight);")
    lines.append("  color: var(--text-primary);")
    lines.append("}")
    lines.append("h1 { font-size: var(--text-4xl); line-height: var(--leading-tight); max-width: 20ch; }")
    lines.append("h2 { font-size: var(--text-3xl); line-height: 1.15; max-width: 25ch; }")
    lines.append("h3 { font-size: var(--text-2xl); line-height: 1.2; max-width: 30ch; }")
    lines.append("h4 { font-size: var(--text-xl);  line-height: var(--leading-snug); max-width: 35ch; }")
    lines.append("")

    # Prose
    lines.append("p { max-width: var(--measure-base); margin-bottom: var(--space-s); }")
    lines.append(".lead { font-size: var(--text-lg); line-height: var(--leading-relaxed); }")
    lines.append("small { font-size: var(--text-xs); line-height: var(--leading-loose); }")
    lines.append("")

    # Flow utility
    lines.append("/* === VERTICAL RHYTHM (flow utility) === */")
    lines.append(".flow > * + *  { margin-top: var(--space-s); }")
    lines.append(".flow > h2 + * { margin-top: var(--space-xs); }")
    lines.append(".flow > * + h2 { margin-top: var(--space-xl); }")
    lines.append(".flow > * + h3 { margin-top: var(--space-l); }")

    return "\n".join(lines)


def format_markdown_table(config: dict) -> str:
    """Format a summary markdown table of the type scale."""
    lines = ["**Type scale summary:**", ""]

    if config["fluid"]:
        lines.append("| Step | Name | Min | Max | Use |")
        lines.append("|------|------|-----|-----|-----|")
        for step, _, min_px, max_px in config["type_scale"]:
            name = step_to_name(step)
            use = step_to_use(step)
            lines.append(f"| {step} | --{name} | {min_px}px | {max_px}px | {use} |")
    else:
        lines.append("| Step | Name | Size | Rem | Use |")
        lines.append("|------|------|------|-----|-----|")
        for step, px, rem in config["type_scale"]:
            name = step_to_name(step)
            use = step_to_use(step)
            lines.append(f"| {step} | --{name} | {px}px | {rem}rem | {use} |")

    return "\n".join(lines)


def build_config(args) -> dict:
    """Build configuration dict from parsed arguments."""
    # Resolve ratio
    ratio_name = ""
    try:
        ratio = float(args.ratio)
    except ValueError:
        ratio_name = args.ratio.lower()
        if ratio_name not in RATIOS:
            print(f"Unknown ratio: {args.ratio}", file=sys.stderr)
            print(f"Available: {', '.join(RATIOS.keys())}", file=sys.stderr)
            sys.exit(1)
        ratio = RATIOS[ratio_name]

    # Resolve fonts
    if args.fonts == "custom":
        if not args.heading_font or not args.body_font:
            print("--fonts custom requires both --heading-font and --body-font", file=sys.stderr)
            sys.exit(1)
        fonts = {
            "heading": args.heading_font,
            "body":    args.body_font,
            "mono":    "ui-monospace, 'Cascadia Code', 'Source Code Pro', Menlo, Consolas, monospace",
            "label":   "Custom fonts",
        }
    elif args.fonts in FONT_STACKS:
        fonts = FONT_STACKS[args.fonts]
    else:
        print(f"Unknown font preset: {args.fonts}", file=sys.stderr)
        print(f"Available: {', '.join(FONT_STACKS.keys())}, custom", file=sys.stderr)
        sys.exit(1)

    # Parse step range
    try:
        parts = args.steps.split(",")
        step_min, step_max = int(parts[0]), int(parts[1])
    except (ValueError, IndexError):
        print(f"Invalid steps format: {args.steps} (expected MIN,MAX e.g. -2,5)", file=sys.stderr)
        sys.exit(1)

    # Generate type scale
    if args.fluid:
        type_scale = generate_fluid_scale(args.base_size, ratio, step_min, step_max)
    else:
        type_scale = generate_type_scale(args.base_size, ratio, step_min, step_max)

    # Generate spacing
    spacing_generators = {
        "8px-grid":     generate_spacing_8px,
        "fibonacci":    generate_spacing_fibonacci,
        "golden-ratio": generate_spacing_golden,
    }
    if args.spacing not in spacing_generators:
        print(f"Unknown spacing system: {args.spacing}", file=sys.stderr)
        print(f"Available: {', '.join(spacing_generators.keys())}", file=sys.stderr)
        sys.exit(1)
    spacing = spacing_generators[args.spacing]()

    # Colors
    if args.color_mode not in COLOR_MODES:
        print(f"Unknown color mode: {args.color_mode}", file=sys.stderr)
        sys.exit(1)
    colors = COLOR_MODES[args.color_mode]

    return {
        "ratio": ratio,
        "ratio_name": ratio_name,
        "base_size": args.base_size,
        "fonts": fonts,
        "type_scale": type_scale,
        "fluid": args.fluid,
        "spacing_system": args.spacing,
        "spacing": spacing,
        "color_mode": args.color_mode,
        "colors": colors,
        "steps": (step_min, step_max),
    }


def format_json(config: dict) -> str:
    """Format the configuration as structured JSON."""
    output = {
        "ratio": config["ratio"],
        "ratio_name": config["ratio_name"],
        "base_size_px": config["base_size"],
        "fluid": config["fluid"],
        "fonts": {
            "heading": config["fonts"]["heading"],
            "body": config["fonts"]["body"],
            "mono": config["fonts"]["mono"],
            "description": config["fonts"]["label"],
        },
        "type_scale": [],
        "spacing_system": config["spacing_system"],
        "spacing": [],
        "color_mode": config["color_mode"],
        "colors": config["colors"],
    }

    if config["fluid"]:
        for step, clamp_str, min_px, max_px in config["type_scale"]:
            output["type_scale"].append({
                "step": step,
                "name": step_to_name(step),
                "clamp": clamp_str,
                "min_px": min_px,
                "max_px": max_px,
                "use": step_to_use(step),
            })
    else:
        for step, px, rem in config["type_scale"]:
            output["type_scale"].append({
                "step": step,
                "name": step_to_name(step),
                "px": px,
                "rem": rem,
                "use": step_to_use(step),
            })

    for name, rem, px in config["spacing"]:
        output["spacing"].append({"name": name, "rem": rem, "px": px})

    return json.dumps(output, indent=2)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a production-ready CSS typography system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Ratios: " + ", ".join(f"{k} ({v})" for k, v in RATIOS.items()),
    )
    parser.add_argument("--ratio", default="major-third",
                        help="Type scale ratio name or number (default: major-third)")
    parser.add_argument("--base-size", type=float, default=16,
                        help="Base font size in px (default: 16)")
    parser.add_argument("--spacing", default="8px-grid",
                        choices=["8px-grid", "fibonacci", "golden-ratio"],
                        help="Spacing system (default: 8px-grid)")
    parser.add_argument("--fonts", default="system",
                        help="Font stack preset (default: system)")
    parser.add_argument("--heading-font", default=None,
                        help="Custom heading font stack (requires --fonts custom)")
    parser.add_argument("--body-font", default=None,
                        help="Custom body font stack (requires --fonts custom)")
    parser.add_argument("--color-mode", default="light", choices=["light", "dark"],
                        help="Color mode (default: light)")
    parser.add_argument("--fluid", action="store_true",
                        help="Generate clamp()-based fluid type scale")
    parser.add_argument("--steps", default="-2,5",
                        help="Type scale step range as MIN,MAX (default: -2,5)")
    parser.add_argument("--json", action="store_true", dest="json_output",
                        help="Output structured JSON instead of CSS")

    args = parser.parse_args()
    config = build_config(args)

    if args.json_output:
        print(format_json(config))
    else:
        print(format_css(config))
        print()
        print(format_markdown_table(config))


if __name__ == "__main__":
    main()
