# SENTINEL-X — Design System & UX Architecture

Phase: design only. No React/TypeScript/Tailwind/backend wiring in this document — tokens, component specs, and five annotated screen layouts, all consistent with one shell.

---

## 0. Product reasoning (why this, not a generic dashboard)

SENTINEL-X is operated by a person watching camera feeds for a full shift, triaging AI-flagged incidents under time pressure. That's the real job — closer to air-traffic-control or trading-floor software than to a B2B SaaS admin panel. Three consequences follow through every decision below:

1. **Color is alarm, not branding.** Severity colors are earned by real detections. They never appear decoratively on chrome, nav, or empty states.
2. **Numbers must align.** All confidence scores, timestamps, coordinates, and IDs render in a monospace figure face, right-aligned in tables, so a tired operator can scan a column instead of reading every row.
3. **Density beats whitespace.** This is a tool used for hours at a stretch, not a landing page. Generous marketing padding is wrong here on purpose.

Visual ancestors: VMS software (Genetec/Milestone), Bloomberg terminal, mission-control consoles — not Notion/Linear-style SaaS. That means graphite surfaces (not pure black), hairline borders (not soft drop-shadow cards), square-ish panels (not 12px-radius tiles), and motion that only ever answers a real event.

---

## 1. Color System

Cold graphite base — deliberately not the warm-cream/terracotta cliché, and not pure-black-plus-neon either. Backgrounds step up in four flat tones; there is no gradient anywhere in the system.

| Token | Hex | Use |
|---|---|---|
| `surface-0` | `#0B0F13` | True background — only visible behind video players and the camera grid letterbox |
| `surface-1` | `#12161B` | App shell background |
| `surface-2` | `#181D24` | Panels, cards, table backgrounds |
| `surface-3` | `#222832` | Raised/hover state, input fields, active nav item |
| `border` | `#262D36` | Default hairline border (1px, never blurred) |
| `border-strong` | `#39424E` | Dividers that separate major regions |
| `text-primary` | `#E7EAED` | Headings, primary values |
| `text-secondary` | `#99A3AD` | Labels, secondary metadata |
| `text-tertiary` | `#64707C` | Disabled, placeholder, timestamps of low importance |
| `accent` | `#4FA6D9` | Operational blue — selection, links, "live," focus ring. Never used for alarm. |
| `accent-dim` | `#2B5570` | Accent at rest / pressed state |

**Severity scale** — the only saturated colors in the system, reserved exclusively for AI/operator-assigned severity. Desaturated enough to avoid "neon," saturated enough to be unambiguous at a glance:

| Token | Hex | Meaning |
|---|---|---|
| `sev-critical` | `#E0453A` | Immediate response required (e.g. Assault, Robbery, Shooting ≥ threshold) |
| `sev-high` | `#E08A3E` | High-confidence anomaly, action pending |
| `sev-moderate` | `#D9BD3F` | Anomaly detected, lower confidence or lower-severity class |
| `sev-low` | `#4FA6D9` | Flagged for review, non-urgent |
| `sev-clear` | `#49A87A` | Normal / resolved / no anomaly |
| `sev-offline` | `#64707C` | Camera/model offline or unknown |

Each severity token has a corresponding 12%-opacity background wash (`sev-critical-wash` etc.) used only behind badges and row highlights — never as a full-panel background.

**Accessibility note:** text-on-surface and badge-text-on-wash pairs are chosen for ≥4.5:1 contrast at body size; full WCAG verification would need manual testing with a contrast checker and screen reader, which hasn't been done at this design stage.

---

## 2. Typography

Two families, strictly separated by role — this is the one deliberately distinctive choice, and it's functional, not decorative: operators need numeric columns to align.

- **UI / body / headings:** Inter (400, 500, 600). A tool's chrome shouldn't make a brand statement; Inter stays out of the way at small sizes, which is what 90% of this interface is.
- **Data / numeric / identifiers:** IBM Plex Mono (400, 500), tabular figures only. Used for: confidence percentages, timestamps, camera IDs, coordinates, incident IDs, durations, file sizes. Never used for prose.

No tracked-out all-caps labels anywhere. Section labels are sentence case, small, and colored `text-secondary` — they describe content, they don't decorate it.

| Style | Family | Size / Line | Weight | Use |
|---|---|---|---|---|
| Display | Inter | 28px / 34px | 600 | Page-level title only (one per screen, in topbar) |
| H1 | Inter | 20px / 26px | 600 | Panel titles |
| H2 | Inter | 15px / 20px | 600 | Card/section titles |
| Body | Inter | 13px / 19px | 400 | Default text |
| Body-sm | Inter | 12px / 16px | 400 | Secondary metadata |
| Label | Inter | 11px / 14px | 500 | Field labels, table headers — sentence case |
| Data-lg | IBM Plex Mono | 22px / 26px | 500 | Hero numeric readouts (e.g. confidence %) |
| Data | IBM Plex Mono | 13px / 18px | 400 | Table cells, timestamps, IDs |
| Data-sm | IBM Plex Mono | 11px / 14px | 400 | Dense table data, overlay HUD text |

---

## 3. Spacing

8px base unit, one scale used everywhere: `4, 8, 12, 16, 24, 32, 48, 64`.

Panel internal padding: 16px standard, 12px for dense tables/grids. Gap between sibling panels: 16px. Gap between major regions (nav/topbar/workspace/status strip): defined by fixed chrome heights, not spacing tokens.

---

## 4. Grid

Desktop-first, fixed-chrome shell (not a scrolling page) at ≥1280px:

```
┌────┬──────────────────────────────────────────────────────────┐
│    │ topbar — 56px fixed                                       │
│ 64 ├──────────────────────────────────────────────────────────┤
│ px │                                                            │
│nav │  workspace — fluid, 12-col grid, 16px gutter               │
│rail│  (per-screen composition, see §screens)                   │
│    │                                                            │
│    ├──────────────────────────────────────────────────────────┤
│    │ status strip — 32px fixed                                 │
└────┴──────────────────────────────────────────────────────────┘
```

Responsive behavior: below 1280px the nav rail stays fixed (icons are small enough to never need collapsing), the workspace grid drops from 12 to 6 columns, and multi-panel screens (Command Center, Incident Detail) stack secondary panels below primary ones rather than side-by-side. Below 860px (tablet), the camera grid in Live Operations drops to 2 columns and side panels become a bottom sheet. This system is not designed for phone-width operational use — a 12-hour shift tool is desktop/large-tablet by nature — but no layout breaks below 480px; it degrades to a single scrolling column.

---

## 5. Border Radius

Minimal and consistent — this is a control room, not a consumer app. No soft "SaaS card" rounding.

| Token | Value | Use |
|---|---|---|
| `radius-sm` | 2px | Badges, inputs, buttons |
| `radius-md` | 3px | Panels, cards, modals |
| `radius-none` | 0px | Tables, video player frame, grid cells |

---

## 6. Elevation

No blurred drop-shadows anywhere — elevation is communicated by a flat background-tone step plus a 1px border, matching real console hardware rather than a simulated paper stack.

| Level | Background | Border |
|---|---|---|
| Base | `surface-1` | — |
| Panel | `surface-2` | `border` |
| Raised (hover, active input) | `surface-3` | `border-strong` |
| Overlay (modal, dropdown) | `surface-2` | `border-strong` + a single 1px `0 0 0 1px rgba(0,0,0,.4)` ring to separate from backdrop — no blur |
| Backdrop (behind modal) | `rgba(11,15,19,.72)` flat scrim | — |

---

## 7. Navigation

Narrow icon rail, 64px, fixed left, present on all five screens — not a labeled sidebar. Five destinations is small enough that icon-only (with a tooltip on hover, and a persistent active-state underline + wash) is faster to scan than text once learned, and it reclaims width for data.

```
┌────┐
│ ▣  │  ← org mark (static, top)
├────┤
│ ◉  │  Command Center
│ ▦  │  Live Operations
│ ⚠  │  Incidents          (badge: live count, sev-colored)
│ ▶  │  Video Investigation
│ ▢  │  Evidence
├────┤
│    │  (flex spacer)
├────┤
│ ⚙  │  System / model health
│ ◐  │  Operator avatar
└────┘
```

Topbar (56px, spans remaining width): left = breadcrumb-style page title (Display style) + contextual subtitle; center = global command/search input (see §20); right = environment tag (e.g. `PRODUCTION`), live clock in Data style (HH:MM:SS, updates per second, `text-secondary`), operator name.

Status strip (32px, bottom, fixed, spans full width): model pipeline health (I3D / Stage 1 / Stage 2 — three small dot indicators, green/amber/red), inference queue depth, API connection state, build/version tag. This is a control-room convention: operators must always be able to see, without navigating, whether the AI pipeline itself is healthy — independent of whatever incident they're currently looking at.

---

## 8. Buttons

Flat, bordered, no gradients, no shadow. Three variants only — restraint here matters more than coverage.

- **Primary:** `accent` background, `surface-0` text, no border. Reserved for the one correct next action on a screen (e.g. "Acknowledge incident").
- **Secondary:** `surface-3` background, `border-strong` border, `text-primary` text. Default for most actions.
- **Ghost:** transparent, `text-secondary` text, border appears on hover only. Used in dense toolbars where a bordered button per action would be visually loud.
- **Destructive:** `sev-critical` text on transparent, `sev-critical` border on hover. Used for dismiss/delete only, never for "normal" negative actions like Cancel (Cancel is Ghost).

Sizes: 32px (default), 28px (dense toolbar/table row actions), 40px (rare, modal primary action). Icon-only buttons are square at the same heights, radius-sm.

States: hover = +1 surface step; active/pressed = `accent-dim` for primary; focus-visible = 2px `accent` outline offset 1px (never removed, never a subtle box-shadow substitute — this is a keyboard-navigable operational tool).

---

## 9. Inputs

Flat `surface-3` fields, 1px `border`, radius-sm, 32px height default. Label above (Label style, `text-secondary`), never floating/inline — floating labels cost legibility for a marginal space saving this product doesn't need. Focus = `border-strong` → `accent` border + no glow. Error state = `sev-critical` border + inline message below in `sev-critical`, Body-sm.

Search/filter inputs include a leading icon slot and, where relevant, inline filter chips (removable, `surface-3` pill, radius-sm — small deliberate exception to the general "no soft chips" rule because filter chips are a widely understood, functional pattern, not decoration).

---

## 10. Tables

The primary data surface of this product — incident lists, evidence lists, camera lists. Dense by default:

- Row height 36px (dense) or 44px (default, used for Incidents).
- Header row: Label style, `text-secondary`, bottom border `border-strong`, sticky on scroll.
- Numeric columns (confidence, timestamp, ID, duration): IBM Plex Mono, right-aligned.
- Text columns (incident type, camera name): Inter, left-aligned.
- Row hover: `surface-3`. Row click target = entire row where the row opens a detail view.
- Severity column: a 3px solid left-edge bar in the row's severity color, plus a small text badge (§12) — redundant encoding (color + text + position) so the information survives for colorblind users and in bad lighting.
- Zebra striping: not used — a hairline row divider (`border`) is enough at this density and striping would compete with the severity bar.

---

## 11. Cards / Panels

Square-cornered (`radius-md`), `surface-2` background, 1px `border`, 16px padding, header row (H2 title + optional right-aligned action/filter) separated from body by a `border` hairline. No shadow. No decorative icon-in-colored-circle headers — a pattern this system explicitly avoids as the "SaaS card kit" tell.

Panels never nest more than one level deep (a card inside a card is a sign the layout needs a different structure, not a double border).

---

## 12. Status Badges

Small, rectangular (`radius-sm`), 4px/8px padding, Label-style text. Structure: a 6px solid dot + label, on a 12%-opacity wash of the status color, with 1px border at 35% opacity of the same color. The dot is the redundant non-color-dependent signal (shape + position), label is the text-dependent one.

Used for: incident status (`new`, `acknowledged`, `investigating`, `resolved`, `false positive`), camera status (`online`, `offline`, `degraded`), model status (`ready`, `loading`, `error`).

---

## 13. Severity Indicators

Beyond the table's left-edge bar, severity appears as a standalone component in Incident Detail and Command Center summaries: a horizontal 5-segment bar (clear → low → moderate → high → critical) with the current level filled solid in its color and the rest at 20% opacity — gives an at-a-glance sense of "how bad, out of how bad it could be," not just a label.

---

## 14. Confidence Indicators

Confidence (anomaly probability, action-class confidence) is never shown as a decorative circular progress ring — that pattern reads as dashboard filler and doesn't aid a fast decision. Instead:

- **Primary readout:** the number itself, Data-lg, IBM Plex Mono, e.g. `97.8%`, with a Label-style caption below (`anomaly probability`).
- **Comparative bar:** a single horizontal bar, `surface-3` track, filled in the relevant severity color to the confidence percentage — used when showing multiple action-class candidates stacked (Abuse 57.2%, Assault 12.3%, Fighting 8.9%...), so relative confidence across classes is scannable as a shape, with the exact number right-aligned in mono type at the end of each bar.
- Confidence below a configurable threshold (e.g. <40%) renders the bar in `text-tertiary` grey rather than a severity color — low confidence is not itself a severity signal, and using a severity color there would be a meaningless-chart violation.

---

## 15. Video Player

Frame: `surface-0` background (true black-adjacent, so letterboxing doesn't read as a design background bleeding through), `radius-none`, 1px `border-strong`.

Controls bar (bottom overlay, `surface-2` at 92% opacity — the one deliberate near-transparent surface in the system, justified because it must sit over video without a hard cut): play/pause, scrub bar with detection markers (see §16) baked into the track, timestamp readout (Data style, current / total), frame-step buttons, playback speed, fullscreen toggle, extract-frame action (camera icon → saves to Evidence).

Detection overlay (when AI analysis is shown over live/recorded frame): a thin `sev-{level}` bounding indicator — a corner-bracket style frame (four short corner lines, not a full rectangle outline) is used instead of a solid box so it doesn't obscure the subject; label chip top-left of the bracket with class + confidence in Data-sm mono.

---

## 16. Timeline

Horizontal, used in Video Investigation (scoped to one video's duration) and Incident Detail (scoped to an incident's event sequence).

- Track: 1px `border-strong` baseline on `surface-2`.
- Detection markers: small upward ticks in severity color at their timestamp; hovering reveals a tooltip (class, confidence, timestamp in mono).
- Current playhead: `accent` vertical line with a small flag at top.
- Dense video timelines additionally render a low-height "activity density" strip above the tick marks — a muted-grey filled area showing where in the video the model's internal attention/anomaly score was elevated, giving a scannable shape rather than a flat line of evenly spaced ticks. This maps directly to real backend output (the MIL attention weights already computed per window) rather than being a decorative sparkline.

---

## 17. Charts

Used only where they map to real fields already returned by the backend — explicitly not decorative:

- **Severity distribution (Command Center):** horizontal stacked bar, one segment per severity level, counts in mono at each segment end. Not a donut/pie — a stacked bar reads faster for "how much of each" at this width and avoids the generic-dashboard donut-chart tell.
- **Action-class candidates (Incident Detail):** the confidence comparative bars from §14, sorted descending — this is itself the chart, not a separate component.
- **Detections-over-time (Command Center):** a simple stepped area, muted single color, no gridlines beyond a baseline and a light 25/50/75% reference tick on the axis — not a smoothed/gradient-filled line, which would look decorative rather than read as real counts.

No 3D, no gratuitous color-per-category where two categories would do, no gauge/speedometer widgets.

---

## 18. Alerts

Two forms:

- **Toast (transient, top-right of workspace, below topbar):** new incident notification. `surface-2`, 3px severity-colored left edge, auto-dismiss after 8s unless hovered, max 3 stacked. This is the one place sanctioned motion for a non-interactive event happens: slide-in from the right, 160ms, no bounce.
- **Inline banner (persistent, within a panel):** system-level conditions — "Stage 2 model degraded," "Camera 14 offline for 6 minutes." `surface-3` background, severity-colored left edge + icon, stays until the condition clears or is dismissed by an operator action, never auto-dismisses (a system condition shouldn't disappear just because 8 seconds passed).

---

## 19. Modals

Reserved for actions that need focus and confirmation — not used for general content display (Incident Detail is a full view, not a modal, because operators need to keep spatial context). `surface-2`, `radius-md`, `border-strong`, flat scrim backdrop (§6), max-width 560px for confirmation dialogs, 880px for richer content (e.g. "assign incident" with operator picker). Entrance: 120ms opacity + 4px translate-up, no bounce, respects `prefers-reduced-motion` (falls back to opacity-only).

---

## 20. Command / Search Interface

Global search lives in the topbar center, not a separate overlay-triggered command palette — this product's search target (find an incident, camera, or evidence item) is frequent enough to deserve permanent placement rather than a `Cmd+K` layer, which would add a step to the single most common cross-screen action.

Behavior: typing filters a lightweight dropdown grouped by type (Incidents / Cameras / Evidence), each row showing the item's severity/status badge + mono timestamp or ID, keyboard-navigable (↑↓ + Enter), Esc closes. `Cmd/Ctrl+K` is additionally bound to focus this same field rather than opening a different UI — one search surface, two entry points.

---

## Screen inventory

See [SCREENS.md](SCREENS.md) for the five annotated layouts: Command Center, Live Operations, Incident Detail, Video Investigation, Evidence — all built from the primitives above, sharing the same nav rail, topbar, and status strip.
