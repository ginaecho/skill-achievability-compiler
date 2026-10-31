---
name: type-craft
description: >
  Builds mathematically-grounded CSS typography and layout systems for web
  projects. Generates type scales, spacing tokens, font pairings, and
  accessible color schemes as production-ready CSS custom properties.
  Use when the user wants to "set up typography for my site",
  "create a type system", "help me pick fonts", "generate CSS variables
  for typography", "make my site look more professional", "set up a
  fluid type scale", or any web typography, spacing, or layout task.
license: MIT
---

# Type Craft

A structured, human-in-the-loop workflow for building professional typography and layout systems for web projects. Every value traces back to mathematical relationships (modular scales, golden ratio, Fibonacci sequence) that produce visually harmonious results.

Before starting, load [references/typography-guide.md](references/typography-guide.md) -- a comprehensive design reference covering type scales, golden ratio layouts, typographic best practices, accessibility requirements, fluid typography, optical alignment, and a complete production-ready CSS system. Reference it throughout the workflow.

## Workflow Overview

```
Discovery → Scale → Fonts → Spacing/Layout → Generate CSS → Accessibility → Deliver
    |                                              |
    └──────────── Refine ──────────────────────────┘
```

Follow steps 1-7 in order. The user may loop back from step 5 to refine choices.

## Step 1: Discovery

Ask the user about their project. Gather these essentials:

- **Project type** -- Marketing site, documentation, blog, dashboard, e-commerce, landing page, web app?
- **Content density** -- Text-heavy (docs, blog), mixed (marketing), data-heavy (dashboard), minimal (landing)?
- **Brand personality** -- Elegant, technical, playful, minimal, bold, luxurious?
- **Audience** -- Developers, general consumers, enterprise, creative professionals?
- **Constraints** -- Existing framework (Tailwind, Bootstrap)? Existing fonts? Dark mode needed? Performance budget (system fonts only)?

Keep discovery concise: 3-5 questions max in one message.

After discovery, identify the recommended type scale ratio range using the **Ratios and when to use them** table in typography-guide.md:

| Project Type | Recommended Ratio |
|---|---|
| Dense dashboards, data UIs | Minor Second (1.067) or Major Second (1.125) |
| Mobile apps, e-commerce | Major Second (1.125) or Minor Third (1.2) |
| Documentation, blogs | Minor Third (1.2) |
| General websites (default) | Major Third (1.25) |
| Editorial, mixed content | Perfect Fourth (1.333) |
| Landing pages, promotional | Augmented Fourth (1.414) |
| Banners, hero-heavy sites | Perfect Fifth (1.5) |
| Luxury brands, creative | Golden Ratio (1.618) |

## Step 2: Scale Selection

Based on discovery, recommend a type scale ratio with reasoning. Present the computed sizes by running the generator:

```bash
scripts/generate_type_system.py --ratio major-third --json
```

Show the user the step-by-step scale (step, pixel size, rem value, typical use) and explain why the ratio fits their project. If the user wants fluid (responsive) type, add `--fluid`:

```bash
scripts/generate_type_system.py --ratio major-third --fluid --json
```

Expected output: A JSON object with the type scale array showing each step's name, size, and recommended use.

Let the user confirm or request a different ratio before proceeding.

## Step 3: Font Selection

Recommend font pairings based on the project personality identified in Step 1. Present 2-3 options from these categories.

**System stacks (zero network cost, best performance):**
- Sans-serif: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, ...`
- Neo-Grotesque: `Inter, Roboto, 'Helvetica Neue', ...`
- Best for: dashboards, web apps, performance-critical projects

**Google Font pairings (see the **Font pairing** section in typography-guide.md):**
- Playfair Display + Montserrat -- editorial elegance
- Montserrat + Merriweather -- geometric + reading comfort
- Poppins + Lora -- contemporary + warm
- Best for: marketing sites, blogs, brand-heavy projects

**Superfamilies (designed as matching sets):**
- Source family (Sans/Serif/Code) by Adobe
- Roboto family (Sans/Slab/Mono) by Google
- Best for: projects needing serif, sans, and mono in one cohesive system

Available presets for the generator: `system`, `inter`, `playfair-montserrat`, `montserrat-merriweather`, `poppins-lora`, `source-family`, `roboto-family`, or `custom` with `--heading-font` and `--body-font`.

## Step 4: Spacing and Layout

Choose a spacing system based on the project needs. Refer to the **Layout Grids** and **Golden Ratio and Fibonacci** sections in typography-guide.md.

**Spacing systems:**

| System | Character | Best For |
|---|---|---|
| 8px grid | Even, predictable steps | Most projects (default), Material Design |
| Fibonacci | Accelerating steps (tight small, expansive large) | Organic, editorial layouts |
| Golden ratio | Phi-based proportions | Luxury, high-end designs |

**Layout patterns:**
- **12-column grid** -- Standard, maximum flexibility (divisible by 1, 2, 3, 4, 6)
- **Golden ratio split** -- `1.618fr 1fr` (~61.8% / ~38.2%) for content + sidebar
- **Fibonacci columns** -- `5fr 8fr` (2-col), `2fr 3fr 5fr` (3-col)

**Apply Gestalt proximity rules** (from the **Gestalt proximity** section in typography-guide.md):
- Internal spacing must always be less than external spacing
- Heading margin-top should be 2-3x larger than heading margin-bottom
- Card padding must be less than the gap between cards

## Step 5: Generate CSS

Run the generator with all chosen parameters:

```bash
scripts/generate_type_system.py --ratio major-third --fonts system --spacing 8px-grid --color-mode light --fluid
```

For custom fonts:
```bash
scripts/generate_type_system.py --ratio 1.25 --fonts custom --heading-font "'Playfair Display', serif" --body-font "Inter, sans-serif" --fluid
```

Expected output: A complete `:root { ... }` CSS block with custom properties for type scale, line heights, tracking, weights, measure, spacing tokens, layout proportions, and colors, followed by base styles for body, headings, prose, and the flow utility.

Present the output to the user. If they want adjustments, re-run with different parameters.

## Step 6: Accessibility Check

Review the generated system against WCAG requirements. Consult the **Accessibility** section in typography-guide.md.

**Verify these minimums:**

| Check | Requirement | How to Verify |
|---|---|---|
| Body font size | At least 16px (1rem) | Confirm `--text-base` is 1rem or larger |
| Body line height | At least 1.5 | Confirm `--leading-normal` is 1.5 |
| Text contrast (AA) | 4.5:1 for body, 3:1 for large text | Check generated color values |
| Line length | Max 75ch | Confirm `--measure-wide` is 80ch or less |
| Fluid type zoom | clamp() includes rem component | Confirm no pure-vw preferred values |
| Font weight | 400+ for body text | Confirm `--weight-normal` is 400 |

**Flag any issues** and suggest fixes. Common problems:
- Dark mode colors failing contrast -- adjust `--text-muted` to a lighter shade
- Heading sizes too large on mobile when not using `--fluid` -- recommend switching to fluid
- Line height too tight on small text -- verify captions use `--leading-loose` (1.8)

## Step 7: Deliver

Present the final CSS system with integration guidance:

1. **Where to put it** -- Create a `typography.css` or add to the project's existing CSS custom properties file. For Tailwind projects, extend the theme config. For CSS-in-JS, convert to a theme object.

2. **How to use the flow utility** -- Explain the `.flow > * + *` pattern for automatic vertical rhythm.

3. **Google Font loading** (if applicable) -- Provide the `<link>` tag or `@import` for chosen fonts. Recommend `font-display: swap` and preconnect hints:
   ```html
   <link rel="preconnect" href="https://fonts.googleapis.com">
   <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
   ```

4. **Responsive notes** -- If fluid type is used, explain that the scale adjusts automatically between ~360px and ~1240px viewports. If static, suggest breakpoint overrides.

Offer to create the CSS file directly in the user's project directory.

## Examples

### Example 1: Marketing site

User says: "Set up typography for my Next.js marketing site"

Actions:
1. Ask about brand personality, audience, performance preferences
2. Recommend Perfect Fourth (1.333) for strong editorial hierarchy
3. Suggest Playfair Display + Montserrat for elegance
4. Use 8px grid spacing, golden ratio layout
5. Generate with `--ratio perfect-fourth --fonts playfair-montserrat --fluid --color-mode light`
6. Verify WCAG AA contrast, check fluid zoom behavior
7. Create `styles/typography.css` in the project

Result: A complete fluid type system with serif headings, sans body, and golden-ratio content/sidebar split.

### Example 2: Documentation site

User says: "I need a type scale for our docs site, it's very text-heavy"

Actions:
1. Identify: text-heavy, technical audience, readability priority
2. Recommend Minor Third (1.2) for compact, clear hierarchy
3. Suggest system fonts (zero load time) or Source family (sans + serif + mono)
4. Use 8px grid spacing, 65ch max line width
5. Generate with `--ratio minor-third --fonts system --fluid`
6. Verify line length, line height, contrast
7. Deliver with emphasis on the `--measure-base: 65ch` constraint

Result: A tight, readable scale optimized for long-form technical content.

### Example 3: Dashboard

User says: "Help me with typography for a fintech dashboard, needs dark mode"

Actions:
1. Identify: data-dense, professional audience, dark mode required
2. Recommend Major Second (1.125) for subtle steps that don't overwhelm data
3. Suggest Inter (designed for UI) or system stack
4. Use 8px grid spacing (Material Design alignment)
5. Generate with `--ratio major-second --fonts inter --spacing 8px-grid --color-mode dark`
6. Verify dark mode contrast ratios (especially `--text-muted`)
7. Deliver with notes on data table typography and monospace for numbers

Result: A compact dark-mode scale with subtle hierarchy suited to data-dense interfaces.

## Troubleshooting

### Error: Fluid type not scaling on resize

Cause: The `clamp()` preferred value uses pure `vw` units without a `rem` component, which also breaks browser zoom (WCAG 1.4.4 failure).

Solution: Always use the `--fluid` flag which generates `rem + vw` formulas. Never write `clamp(1rem, 2vw, 2rem)` -- use `clamp(1rem, 0.95rem + 0.25vw, 1.125rem)` instead.

### Error: Fonts not loading / FOUT flash

Cause: Missing preconnect hints or no `font-display` strategy.

Solution: Add preconnect links in `<head>` before the font stylesheet. Use `font-display: swap` to show system fallback immediately while the web font loads. The generated system includes system font fallbacks in every stack for this reason.

### Error: Spacing looks inconsistent across components

Cause: Mixing multiple spacing systems (e.g., 8px grid in some places, arbitrary values in others).

Solution: Use only the generated `--space-*` tokens for all padding, margin, and gap values. The flow utility (`.flow > * + *`) handles vertical rhythm automatically. Never use hardcoded pixel values for spacing.

### Error: Headings appear disconnected from their content

Cause: Equal spacing above and below headings violates Gestalt proximity.

Solution: Heading margin-top should be 2-3x margin-bottom. The generated flow utility handles this: `h2` gets `--space-xl` above and `--space-xs` below. See the **Gestalt proximity** section in typography-guide.md.
