# Typography and Layout Design Guide

Mathematical design systems — the golden ratio, Fibonacci sequence, and musical scale ratios — distilled into concrete CSS values and rules that produce visually harmonious websites. Every spacing token, font size, and layout proportion traces back to proven mathematical relationships. The guide covers type scales, layout grids, accessibility requirements, and responsive patterns, with copy-paste-ready CSS throughout.

---

## Type Scales

A modular type scale starts from a **base size (16px / 1rem)** and multiplies or divides by a consistent ratio to produce every font size. This single ratio generates a complete, harmonious hierarchy. The ratio you choose sets the personality of the entire design.

### Ratios and when to use them

| Ratio Name | Value | Character | Best For |
|---|---|---|---|
| Minor Second | 1.067 | Barely perceptible steps | Dense dashboards, data-heavy UIs |
| Major Second | 1.125 | Subtle, controlled | Mobile apps, e-commerce, compact layouts |
| Minor Third | 1.2 | Moderate, clear | Documentation, blogs, all-purpose safe default |
| **Major Third** | **1.25** | Balanced, elegant | **Most websites — the recommended default** |
| Perfect Fourth | 1.333 | Distinct hierarchy | Editorial, mixed content types |
| Augmented Fourth | 1.414 | Dramatic (sqrt 2) | Landing pages, promotional material |
| Perfect Fifth | 1.5 | High contrast | Banners, advertisements, attention-grabbing |
| Golden Ratio | 1.618 | Maximum drama | Luxury brands, hero headings, creative sites |

These ratios originate from music theory — the intervals that sound consonant also produce visual proportions that look harmonious. **Use 1.2-1.25 for mobile, 1.25-1.333 for desktop, and 1.414-1.618 only for display/marketing contexts.**

### Computed type scales from 16px base

**Major Third (1.25) — recommended default:**

| Step | Size | Rem | Use |
|---|---|---|---|
| -2 | 10.24px | 0.64rem | Fine print |
| -1 | 12.8px | 0.8rem | Captions, labels |
| 0 | 16px | 1rem | Body text |
| 1 | 20px | 1.25rem | H5 / Large body |
| 2 | 25px | 1.563rem | H4 |
| 3 | 31.25px | 1.953rem | H3 |
| 4 | 39.06px | 2.441rem | H2 |
| 5 | 48.83px | 3.052rem | H1 |

**Perfect Fourth (1.333) — strong hierarchy:**

| Step | Size | Rem | Use |
|---|---|---|---|
| -1 | 12px | 0.75rem | Captions |
| 0 | 16px | 1rem | Body |
| 1 | 21.33px | 1.333rem | H5 |
| 2 | 28.43px | 1.777rem | H4 |
| 3 | 37.9px | 2.369rem | H3 |
| 4 | 50.52px | 3.157rem | H2 |
| 5 | 67.34px | 4.209rem | H1 |

**Minor Third (1.2) — compact, content-heavy:**

| Step | Size | Rem | Use |
|---|---|---|---|
| -1 | 13.33px | 0.833rem | Captions |
| 0 | 16px | 1rem | Body |
| 1 | 19.2px | 1.2rem | H5 |
| 2 | 23.04px | 1.44rem | H4 |
| 3 | 27.65px | 1.728rem | H3 |
| 4 | 33.18px | 2.074rem | H2 |
| 5 | 39.81px | 2.488rem | H1 |

### CSS custom properties for any ratio

Change `--ratio` once and the entire scale recalculates:

```css
:root {
  --ratio: 1.25;
  --s-2: calc(var(--s-1) / var(--ratio));
  --s-1: calc(var(--s0) / var(--ratio));
  --s0: 1rem;
  --s1: calc(var(--s0) * var(--ratio));
  --s2: calc(var(--s1) * var(--ratio));
  --s3: calc(var(--s2) * var(--ratio));
  --s4: calc(var(--s3) * var(--ratio));
  --s5: calc(var(--s4) * var(--ratio));
}

body  { font-size: var(--s0); }
small { font-size: var(--s-1); }
h4    { font-size: var(--s2); }
h3    { font-size: var(--s3); }
h2    { font-size: var(--s4); }
h1    { font-size: var(--s5); }
```

---

## Golden Ratio and Fibonacci

The golden ratio (phi = **1.618**) and the Fibonacci sequence (1, 1, 2, 3, 5, 8, 13, 21, 34, 55, 89) are mathematically linked — the ratio of consecutive Fibonacci numbers converges to phi. In practice, **5:8 is a convenient approximation** of the golden ratio (5 / 8 = 0.625 ~ 0.618).

### Golden ratio layout proportions

The golden ratio divides any container into **61.8%** and **38.2%**:

| Container | Content Area | Sidebar |
|---|---|---|
| 960px | 593px | 367px |
| 1200px | 741px | 459px |
| 1440px | 890px | 550px |

```css
/* Golden ratio two-column layout */
.layout {
  display: grid;
  grid-template-columns: 1.618fr 1fr; /* ~61.8% / ~38.2% */
  gap: 2rem;
}

/* Flexbox alternative */
.content { flex: 1.618; }
.sidebar { flex: 1; }
```

For vertical spacing, multiply each level by phi: **8px -> 13px -> 21px -> 34px -> 55px -> 89px**. This naturally produces the Fibonacci sequence, connecting both systems.

### Golden ratio for typography spacing

The golden ratio links font size to line height directly: **font-size x 1.618 = line-height**. At 16px body text, this gives a 25.9px (~26px) line height, or simply `line-height: 1.618`. For heading-to-body relationships, each heading level = previous level x 1.618.

```css
:root {
  --phi: 1.618;
  --base-size: 1rem;
  --text-sm: calc(var(--base-size) / var(--phi));    /* 0.618rem */
  --text-base: var(--base-size);                      /* 1rem */
  --text-lg: calc(var(--base-size) * var(--phi));     /* 1.618rem */
  --text-xl: calc(var(--text-lg) * var(--phi));       /* 2.618rem */
  --text-2xl: calc(var(--text-xl) * var(--phi));      /* 4.236rem */

  --space-base: 1rem;
  --space-lg: calc(var(--space-base) * var(--phi));   /* 1.618rem */
  --space-xl: calc(var(--space-lg) * var(--phi));     /* 2.618rem */
  --space-sm: calc(var(--space-base) / var(--phi));   /* 0.618rem */

  --content-width: 61.8%;
  --sidebar-width: 38.2%;
}
```

### Fibonacci spacing scale

Fibonacci numbers create a spacing system where each step feels naturally proportioned to the previous one. Unlike linear scales (4, 8, 12, 16...), Fibonacci spacing accelerates gracefully — tight at small sizes and expansive at large ones.

```css
:root {
  --space-3xs: 0.0625rem;  /* 1px */
  --space-2xs: 0.125rem;   /* 2px */
  --space-xs:  0.1875rem;  /* 3px */
  --space-sm:  0.3125rem;  /* 5px */
  --space-md:  0.5rem;     /* 8px */
  --space-lg:  0.8125rem;  /* 13px */
  --space-xl:  1.3125rem;  /* 21px */
  --space-2xl: 2.125rem;   /* 34px */
  --space-3xl: 3.4375rem;  /* 55px */
  --space-4xl: 5.5625rem;  /* 89px */
}
```

### Fibonacci grid layouts

```css
.fibonacci-2col { display: grid; grid-template-columns: 5fr 8fr; }
.fibonacci-3col { display: grid; grid-template-columns: 2fr 3fr 5fr; }
.fibonacci-4col { display: grid; grid-template-columns: 1fr 1fr 2fr 3fr; }
```

---

## Typographic Rules

### Line length: the 65-character rule

The optimal line length is **45-75 characters per line**, with **66 characters as the ideal** (per Robert Bringhurst's *Elements of Typographic Style*). Lines that are too wide cause readers to lose their place when returning to the left margin. Lines that are too narrow break reading flow.

```css
p              { max-width: 65ch; }
h1, h2         { max-width: 20ch; }
h3, h4         { max-width: 35ch; }
blockquote     { max-width: 55ch; }
figcaption     { max-width: 45ch; }
.text-container { width: min(95vw, 65ch); margin-inline: auto; }
```

### Line height varies with font size and line length

**Always use unitless line-height values** (e.g., `1.5` not `1.5em`). Unitless values are inherited as a multiplier of each element's own font-size, preventing overflow bugs in headings.

| Context | Line Height | Why |
|---|---|---|
| Body text | **1.5-1.6** | WCAG minimum is 1.5; sweet spot for readability |
| Headings (large) | **1.1-1.3** | Large text needs less leading |
| Display/hero text | **1.0-1.1** | Tight leading for visual impact |
| Small text/captions | **1.6-1.8** | Small text needs more breathing room |
| All-caps text | **1.0-1.2** | No descenders fill the space |
| Code/monospace | **1.4-1.5** | Moderate for scanning |

**Longer lines need more line height.** Body text at 75 characters works with 1.6; at 45 characters, 1.4 is sufficient.

```css
body  { font-size: 1rem;    line-height: 1.5; }
h1    { font-size: 2.5rem;  line-height: 1.1; }
h2    { font-size: 2rem;    line-height: 1.2; }
h3    { font-size: 1.5rem;  line-height: 1.3; }
small { font-size: 0.875rem; line-height: 1.7; }
```

### Vertical rhythm through consistent spacing

Vertical rhythm means all spacing is based on multiples of a single baseline unit. With 16px font and 1.5 line-height, the baseline unit is **24px (1.5rem)**. Every margin, padding, and gap should be a multiple (or half) of this value.

```css
:root { --baseline: 1.5rem; }

.flow > * + * { margin-top: var(--baseline); }
.flow > h2 + * { margin-top: calc(var(--baseline) * 0.5); }
.flow > * + h2 { margin-top: calc(var(--baseline) * 2); }
.flow > * + h3 { margin-top: calc(var(--baseline) * 1.5); }
```

The **"flow" utility pattern** (from Every Layout) applies consistent spacing at the parent level using the lobotomized owl selector (`> * + *`), eliminating per-element margin declarations.

### Font pairing: contrast in style, similarity in proportion

Use **2-3 fonts maximum** per page. Pair fonts with different classifications (serif + sans-serif) but similar x-heights. One font leads; the other supports.

**Reliable Google Font pairings:**

- **Playfair Display** (serif heading) + **Montserrat** (sans body) — editorial elegance
- **Montserrat** (sans heading) + **Merriweather** (serif body) — geometric + reading comfort
- **Poppins** (sans heading) + **Lora** (serif body) — contemporary + warm
- **Source Sans 3** (sans heading) + **Source Serif 4** (serif body) — designed as a pair by Adobe
- **Roboto Slab** (slab heading) + **Roboto** (sans body) — cohesive Material family

**Superfamilies** (designed to work together) eliminate pairing guesswork: IBM Plex (Sans/Serif/Mono), Source family (Sans/Serif/Code), Noto (Sans/Serif), Roboto family.

### Modern system font stacks (zero network requests)

```css
/* Sans-serif system stack */
font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI',
  Roboto, 'Helvetica Neue', Arial, sans-serif;

/* Serif system stack */
font-family: Iowan Old Style, Apple Garamond, Baskerville,
  'Times New Roman', Droid Serif, Times, serif;

/* Monospace system stack */
font-family: ui-monospace, 'Cascadia Code', 'Source Code Pro',
  Menlo, Consolas, monospace;

/* Modern approach (modernfontstacks.com) */
/* Neo-Grotesque */
font-family: Inter, Roboto, 'Helvetica Neue', 'Arial Nova', Arial, sans-serif;
/* Transitional Serif */
font-family: Charter, 'Bitstream Charter', 'Sitka Text', Cambria, serif;
/* Geometric Humanist */
font-family: Avenir, Montserrat, Corbel, 'URW Gothic', source-sans-pro, sans-serif;
```

---

## Layout Grids

### The 8px grid: Material Design's foundation

All dimensions, padding, and margins use **multiples of 8px**. This creates consistent visual rhythm across every component. Use 4px for fine adjustments (icon gaps, label spacing).

```css
:root {
  --grid-1:  0.25rem;  /*  4px — fine control */
  --grid-2:  0.5rem;   /*  8px — tight spacing */
  --grid-3:  1rem;     /* 16px — standard padding */
  --grid-4:  1.5rem;   /* 24px — card padding */
  --grid-5:  2rem;     /* 32px — section sub-spacing */
  --grid-6:  2.5rem;   /* 40px — major gaps */
  --grid-7:  3rem;     /* 48px — hero padding */
  --grid-8:  4rem;     /* 64px — section gaps */
  --grid-9:  5rem;     /* 80px — page section margins */
  --grid-10: 6rem;     /* 96px — between major sections */
}
```

The standard **12-column grid** divides a container into 12 equal parts. Twelve is ideal because it's divisible by 1, 2, 3, 4, and 6, enabling flexible column combinations.

```css
.container {
  max-width: 1200px;
  margin: 0 auto;
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 1.5rem;
}
```

### Rule of thirds and eye-tracking patterns

Divide the viewport into a 3x3 grid. Place key elements at intersection points. Eye-tracking data shows attention distribution: **top-left intersection gets 41%** of viewer attention, top-right 20%, bottom-left 25%, bottom-right 14%.

For text-heavy pages, users follow the **F-pattern**: horizontal scan across the top, a shorter scan below, then vertical scanning down the left edge. For minimal-content pages like landing pages, the **Z-pattern** applies: top-left to top-right to bottom-left to bottom-right.

Design implications: place the most important content — headline, value proposition — at top-left. Place the primary CTA where the eye naturally rests at the end of the scan pattern.

### Gestalt proximity: the most important spacing principle

**Elements closer together are perceived as a related group.** This is the single most important rule for spacing decisions in CSS. The practical implementation is straightforward: **internal spacing must always be less than external spacing.**

- Related items within a group: **8-16px** apart
- Separate groups: **24-48px** apart
- Heading margin-top (separating from previous section) should be **2-3x larger** than heading margin-bottom (connecting to its content)

```css
/* Headings pull toward their content, push away from previous section */
h2 { margin-top: 3rem; margin-bottom: 0.75rem; }
h3 { margin-top: 2rem; margin-bottom: 0.5rem; }

/* Card internal padding < gap between cards */
.card { padding: 1rem; }
.card-grid { gap: 1.5rem; }

/* Form groups: tight within, loose between */
.form-group label { margin-bottom: 0.25rem; }
.form-group input + input { margin-top: 0.75rem; }
.form-group + .form-group { margin-top: 1.5rem; }
```

### Visual hierarchy through size, weight, color, and space

Size is the strongest hierarchy signal. Pair it with **three levels of text color contrast** to create clear information hierarchy:

```css
:root {
  --text-primary:   #1a1a2e;  /* High contrast ~16:1 — headings, body */
  --text-secondary: #4a4a68;  /* Medium ~7.4:1 (AAA) — secondary info */
  --text-muted:     #6b6b8a;  /* Moderate ~4.8:1 (AA) — captions, metadata */
}
```

Generous whitespace around an element increases its perceived importance. More spacing = more emphasis. This is **active whitespace** — intentionally placed to direct attention, as opposed to passive whitespace (line-height, default margins) that simply improves readability.

---

## Accessibility

### WCAG 2.1 contrast minimums

| Level | Normal Text (below 18px) | Large Text (18px+ or 14px bold+) |
|---|---|---|
| AA (minimum) | **4.5:1** | **3:1** |
| AAA (enhanced) | **7:1** | **4.5:1** |
| Non-text UI components | **3:1** | — |

**"Large text"** = 24px (18pt) or larger at any weight, or 18.66px (14pt) bold or larger.

### WCAG 1.4.12 text spacing requirements (Level AA)

Content must remain functional when users apply these overrides:

- Line height: at least **1.5x font size**
- Paragraph spacing: at least **2x font size**
- Letter spacing: at least **0.12x font size**
- Word spacing: at least **0.16x font size**

```css
/* Accessible base typography */
body {
  font-size: 1rem;         /* 16px minimum for body */
  line-height: 1.5;        /* WCAG 1.4.12 minimum */
  letter-spacing: 0.01em;
  word-spacing: 0.01em;
}
```

**Never set body text below 16px.** Use relative units (rem, em) rather than fixed px so text can be resized to 200% without content loss (WCAG 1.4.4). Font weights below 400 (thin, light) should only be used for large display text — anti-aliasing makes thin fonts appear lighter than their measured contrast ratio.

---

## Fluid Typography

The `clamp()` function creates typography that scales smoothly between viewport sizes without breakpoints. The formula is `clamp(minimum, preferred, maximum)`, where the preferred value combines a rem base with a viewport-width component.

**Critical accessibility rule:** Always include a `rem` component in the preferred value. Pure `vw` units break browser zoom and fail WCAG 1.4.4.

### Practical fluid type values

```css
:root {
  /* Fluid type scale (scales from ~360px to ~1240px viewport) */
  --text-xs:   clamp(0.75rem,  0.72rem + 0.15vw, 0.875rem);
  --text-sm:   clamp(0.875rem, 0.85rem + 0.13vw, 1rem);
  --text-base: clamp(1rem,     0.95rem + 0.25vw, 1.125rem);
  --text-lg:   clamp(1.125rem, 1.05rem + 0.375vw, 1.3125rem);
  --text-xl:   clamp(1.25rem,  1.1rem + 0.75vw, 1.625rem);
  --text-2xl:  clamp(1.5rem,   1.25rem + 1.25vw, 2.125rem);
  --text-3xl:  clamp(1.875rem, 1.5rem + 1.875vw, 2.75rem);
  --text-4xl:  clamp(2.25rem,  1.7rem + 2.75vw, 3.5rem);

  /* Fluid spacing scale */
  --space-xs:  clamp(0.75rem,  0.7rem + 0.25vw, 0.875rem);
  --space-s:   clamp(1rem,     0.95rem + 0.25vw, 1.125rem);
  --space-m:   clamp(1.5rem,   1.4rem + 0.5vw, 1.75rem);
  --space-l:   clamp(2rem,     1.85rem + 0.75vw, 2.5rem);
  --space-xl:  clamp(3rem,     2.75rem + 1.25vw, 3.75rem);
  --space-2xl: clamp(4rem,     3.5rem + 2.5vw, 5.625rem);
}
```

### Utopia-style fluid type scale (industry standard)

The Utopia approach uses a smaller ratio on mobile (1.2) and a larger ratio on desktop (1.25-1.333), with fluid interpolation between them:

```css
:root {
  --step--2: clamp(0.7813rem, 0.7747rem + 0.0341vw, 0.8rem);
  --step--1: clamp(0.9375rem, 0.9158rem + 0.1136vw, 1rem);
  --step-0:  clamp(1.125rem,  1.0795rem + 0.2273vw, 1.25rem);
  --step-1:  clamp(1.35rem,   1.2717rem + 0.3864vw, 1.5625rem);
  --step-2:  clamp(1.62rem,   1.4918rem + 0.6057vw, 1.9531rem);
  --step-3:  clamp(1.944rem,  1.7494rem + 0.9044vw, 2.4414rem);
  --step-4:  clamp(2.3328rem, 2.0514rem + 1.3072vw, 3.0518rem);
  --step-5:  clamp(2.7994rem, 2.4066rem + 1.8461vw, 3.8147rem);
}
```

### Container queries for component-level typography

```css
.card-container { container-type: inline-size; }
@container (min-width: 400px) {
  .card h2 { font-size: var(--text-2xl); }
}
@container (max-width: 399px) {
  .card h2 { font-size: var(--text-xl); }
}
```

---

## Optical Alignment

Mathematical centering doesn't always look centered to the human eye. Several common situations require optical correction.

**Play button triangles** must shift right 3-5px within circular containers because the visual center of mass of a triangle sits at its centroid, not the center of its bounding box. **Round letters** (C, G, O, S) extend 1-2px past the baseline in professional typefaces to appear aligned with flat-bottomed letters. **All-caps button text** needs bottom padding reduced by ~2px because uppercase letters have no descenders, making the text appear to sit too high.

```css
/* Icon-text vertical alignment fix */
.icon-text {
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}
.icon-text svg {
  flex-shrink: 0;
  transform: translateY(-1px); /* optical correction */
}

/* Hanging punctuation for pull quotes */
blockquote {
  hanging-punctuation: first last;
  text-indent: -0.45em; /* fallback */
}
```

**Whitespace in buttons** should follow the **1.5-2x horizontal-to-vertical padding ratio**: `padding: 0.75rem 1.5rem`. As font size increases, surrounding whitespace must increase proportionally. Headings need more space above (separating from the previous section) than below (connecting to their content) — a **2:1 ratio** works well.

---

## Production CSS

This complete system combines modular type scale, fluid sizing, spacing tokens, and accessibility compliance into a single set of custom properties. Change `--ratio` and `--font-body` to transform the entire design.

```css
:root {
  /* === FONTS === */
  --font-sans: Inter, Roboto, 'Helvetica Neue', Arial, sans-serif;
  --font-serif: Merriweather, Georgia, 'Times New Roman', serif;
  --font-mono: ui-monospace, 'Cascadia Code', 'Source Code Pro',
    Menlo, Consolas, monospace;
  --font-body: var(--font-sans);
  --font-heading: var(--font-sans);

  /* === TYPE SCALE (Major Third 1.25) === */
  --text-xs:   clamp(0.75rem,  0.72rem + 0.15vw, 0.875rem);
  --text-sm:   clamp(0.875rem, 0.85rem + 0.13vw, 1rem);
  --text-base: clamp(1rem,     0.95rem + 0.25vw, 1.125rem);
  --text-lg:   clamp(1.125rem, 1.05rem + 0.375vw, 1.3125rem);
  --text-xl:   clamp(1.25rem,  1.1rem + 0.75vw, 1.625rem);
  --text-2xl:  clamp(1.5rem,   1.25rem + 1.25vw, 2.125rem);
  --text-3xl:  clamp(1.875rem, 1.5rem + 1.875vw, 2.75rem);
  --text-4xl:  clamp(2.25rem,  1.7rem + 2.75vw, 3.5rem);

  /* === LINE HEIGHTS === */
  --leading-tight:   1.1;
  --leading-snug:    1.3;
  --leading-normal:  1.5;
  --leading-relaxed: 1.65;
  --leading-loose:   1.8;

  /* === TRACKING === */
  --tracking-tight:  -0.01em;
  --tracking-normal:  0;
  --tracking-wide:    0.025em;
  --tracking-wider:   0.05em;
  --tracking-widest:  0.1em;

  /* === WEIGHTS === */
  --weight-normal:    400;
  --weight-medium:    500;
  --weight-semibold:  600;
  --weight-bold:      700;

  /* === MEASURE (LINE LENGTH) === */
  --measure-narrow: 45ch;
  --measure-base:   65ch;
  --measure-wide:   80ch;

  /* === SPACING (8px grid) === */
  --space-3xs: 0.25rem;   /*  4px */
  --space-2xs: 0.5rem;    /*  8px */
  --space-xs:  0.75rem;   /* 12px */
  --space-s:   1rem;      /* 16px */
  --space-m:   1.5rem;    /* 24px */
  --space-l:   2rem;      /* 32px */
  --space-xl:  3rem;      /* 48px */
  --space-2xl: 4rem;      /* 64px */
  --space-3xl: 6rem;      /* 96px */

  /* === LAYOUT === */
  --content-width: 1.618fr;
  --sidebar-width: 1fr;
  --container-max: 1200px;

  /* === COLORS (contrast-safe) === */
  --text-primary:   #1a1a2e;  /* ~16:1 on white */
  --text-secondary: #4a4a68;  /* ~7.4:1 — AAA */
  --text-muted:     #6b6b8a;  /* ~4.8:1 — AA */
  --bg-primary:     #ffffff;
  --bg-surface:     #f8f9fa;
}

/* === BASE === */
body {
  font-family: var(--font-body);
  font-size: var(--text-base);
  line-height: var(--leading-normal);
  font-weight: var(--weight-normal);
  color: var(--text-primary);
  background: var(--bg-primary);
}

/* === HEADINGS === */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-heading);
  font-weight: var(--weight-bold);
  letter-spacing: var(--tracking-tight);
  color: var(--text-primary);
}
h1 { font-size: var(--text-4xl); line-height: var(--leading-tight); max-width: 20ch; }
h2 { font-size: var(--text-3xl); line-height: 1.15; max-width: 25ch; }
h3 { font-size: var(--text-2xl); line-height: 1.2; max-width: 30ch; }
h4 { font-size: var(--text-xl);  line-height: var(--leading-snug); max-width: 35ch; }

/* === PROSE === */
p { max-width: var(--measure-base); margin-bottom: var(--space-s); }
.lead { font-size: var(--text-lg); line-height: var(--leading-relaxed); }
small { font-size: var(--text-sm); line-height: var(--leading-loose); }

/* === VERTICAL RHYTHM (flow utility) === */
.flow > * + *  { margin-top: var(--space-s); }
.flow > h2 + * { margin-top: var(--space-xs); }
.flow > * + h2 { margin-top: var(--space-xl); }
.flow > * + h3 { margin-top: var(--space-l); }

/* === LAYOUT === */
.container {
  max-width: var(--container-max);
  margin-inline: auto;
  padding-inline: var(--space-m);
}
.golden-layout {
  display: grid;
  grid-template-columns: var(--content-width) var(--sidebar-width);
  gap: var(--space-l);
}
```

---

## Rules Summary

The mathematical systems in this guide are not separate philosophies — they are facets of a single coherent design logic. The golden ratio generates the Fibonacci sequence, which produces the spacing tokens, which align with the 8px grid, which enforces vertical rhythm. Every decision reinforces every other.

### Five non-negotiable rules

1. Body text is always at least 16px with 1.5 line-height
2. Line length never exceeds 75 characters
3. Contrast meets WCAG AA (4.5:1 for body text)
4. Headings connect to their content through proximity (more space above than below)
5. All spacing derives from a consistent scale rather than arbitrary values

### Decision heuristics

**The most impactful single choice** is the type scale ratio. Start with the Major Third (1.25) for general websites, Minor Third (1.2) for dense content, and Perfect Fourth (1.333) for editorial or marketing pages.

Pair this with the 8px spacing grid and the flow utility pattern, and the design will have professional visual rhythm with zero guesswork.

Use `clamp()` with a rem+vw formula for every font size to get responsive typography that respects user zoom settings.

When in doubt about any spacing value, refer to the Fibonacci sequence — its numbers (8, 13, 21, 34, 55) are almost always the right answer.
