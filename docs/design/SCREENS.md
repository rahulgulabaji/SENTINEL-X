# SENTINEL-X — Five Core Screens

All five share the fixed shell from [DESIGN_SYSTEM.md](DESIGN_SYSTEM.md) §7: 64px icon rail, 56px topbar, 32px status strip. Only the workspace region (between topbar and status strip) differs per screen. ASCII wireframes below show structure and hierarchy, not pixel-exact layout.

---

## 1. Command Center

**Job:** answer "what needs my attention right now" in one glance, then route to the right incident/camera/evidence. This is the landing screen, not a vanity metrics page — every panel maps to a real decision an operator makes next.

```
┌────┬───────────────────────────────────────────────────────────────────┐
│    │ Command Center                            [search]   PRODUCTION 09:41:03  J.OKAFOR │
│ ▣  ├───────────────────────────────────────────────────────────────────┤
│ ◉● │ ┌─ Active incidents (4) ──────────────┐ ┌─ System health ────────┐ │
│ ▦  │ │ ⬤ CRITICAL  Robbery      Cam 14  2m │ │ I3D       ● ready       │ │
│ ⚠3 │ │ ⬤ HIGH      Fighting     Cam 03  8m │ │ Stage 1   ● ready       │ │
│ ▶  │ │ ⬤ MODERATE  Loitering    Cam 22 14m │ │ Stage 2   ● ready       │ │
│ ▢  │ │ ⬤ LOW       Unattended   Cam 09 31m │ │ Queue depth      0      │ │
│    │ │ view all incidents →                │ │ Avg inference   36.5s   │ │
│    │ └──────────────────────────────────────┘ └─────────────────────────┘ │
│    │ ┌─ Severity distribution (24h) ───────────────────────────────────┐ │
│ ⚙  │ │ ███ critical 2  ██████ high 5  █████████ moderate 9  ████ low 4 │ │
│ ◐  │ └────────────────────────────────────────────────────────────────┘ │
│    │ ┌─ Active cameras ──────┐ ┌─ Recent AI analyses ──────────────────┐ │
│    │ │ 24 online  2 offline  │ │ Cam 14  Abuse      97.8%   00:36 ago  │ │
│    │ │ ▦▦▦▦▦▦▦▦▦▦▦▦ (grid    │ │ Cam 03  Fighting   84.1%   08:12 ago  │ │
│    │ │  status mini-map →)   │ │ Cam 22  Normal      4.2%   09:50 ago  │ │
│    │ └────────────────────────┘ │ view all analyses →                 │ │
│    │                            └────────────────────────────────────────┘ │
│    │ ┌─ Recent evidence ──────┐ ┌─ Detections, last 24h ────────────────┐ │
│    │ │ [thumb][thumb][thumb]  │ │     ▂▃▂▅▇▃▂▁▂▃▄▇▆▃▂▁▂▃  (stepped area) │ │
│    │ │ 3 clips · 2 stills     │ │ 00:00        12:00              23:59 │ │
│    │ └────────────────────────┘ └────────────────────────────────────────┘ │
├────┴───────────────────────────────────────────────────────────────────┤
│ ● I3D  ● Stage 1  ● Stage 2    Queue: 0    API: connected    v0.1.0     │
└───────────────────────────────────────────────────────────────────────┘
```

**Composition notes:**
- Top-left panel (Active incidents) is the largest and highest-priority panel — severity-sorted, not time-sorted, because triage order matters more than recency. Each row uses the full redundant encoding from §12/§10: colored dot + text severity label + relative timestamp in mono.
- System health sits top-right, same visual weight as incidents, because "is the AI even working" is a precondition for trusting everything else on the screen — this is the model/inference status requirement made structurally prominent, not buried in a footer.
- Severity distribution is the one chart that's a stacked bar (§17), not a donut — scannable proportion, with counts in mono at each segment.
- Active cameras panel shows a count + a tiny status mini-map (a compressed grid of colored dots, one per camera, green/red/amber) rather than duplicating the full Live Operations grid — this panel's job is "is anything down," and it routes to Live Operations for anything deeper.
- Recent AI analyses is a dense mono-numeric list (confidence right-aligned) — this is the panel that most directly surfaces real backend output (the exact fields from the verified test: anomaly probability, likely action).
- Bottom row (evidence thumbnails, detections-over-time) is lower priority, smaller panels — deliberately not given equal visual weight to incidents/health, avoiding the "everything is a card of equal size" SaaS-kit trait.
- Status strip repeats the model health at a glance even while scrolled/deep in another panel's hover state — redundant with the System health panel on purpose, since it's always visible regardless of screen.

---

## 2. Live Operations

**Job:** monitor many camera feeds at once, spot anomalies as they're flagged, jump to fullscreen on any feed. This screen is viewing-dense by nature — more grid, less panel chrome than any other screen.

```
┌────┬───────────────────────────────────────────────────────────────────┐
│    │ Live Operations          [search]  [grid: 4×4 ▾] [filter: all ▾]  │
│ ▣  ├───────────────────────────────────────────────────────────────────┤
│ ◉  │ ┌──────────┬──────────┬──────────┬──────────┐                     │
│ ▦● │ │ CAM 01    │ CAM 02    │ CAM 03  ⚠│ CAM 04    │                     │
│ ⚠3 │ │ ● LIVE    │ ● LIVE    │ ⌐  HIGH ¬│ ● LIVE    │                     │
│ ▶  │ │  (feed)   │  (feed)   │  Fighting│  (feed)   │                     │
│ ▢  │ │           │           │  84.1%  │           │                     │
│    │ │           │           │ ⌐      ¬│           │                     │
│    │ ├──────────┼──────────┼──────────┼──────────┤                     │
│ ⚙  │ │ CAM 05    │ CAM 06    │ CAM 07    │ CAM 08    │                     │
│ ◐  │ │ ○ OFFLINE │ ● LIVE    │ ● LIVE    │ ● LIVE    │                     │
│    │ │  (grey,   │  (feed)   │  (feed)   │  (feed)   │                     │
│    │ │  last     │           │           │           │                     │
│    │ │  frame)   │           │           │           │                     │
│    │ ├──────────┼──────────┼──────────┼──────────┤                     │
│    │ │  ... (continues to fill grid, 4×4 default, configurable 2×2–6×6) │
│    │ └──────────┴──────────┴──────────┴──────────┘                     │
├────┴───────────────────────────────────────────────────────────────────┤
│ ● I3D  ● Stage 1  ● Stage 2    24 online / 2 offline    API: connected  │
└───────────────────────────────────────────────────────────────────────┘
```

**Composition notes:**
- Each tile: camera label (top-left, Data-sm mono, e.g. `CAM 03`), live/offline status dot (top-left, next to label — same dot+label pattern as badges), severity corner-brackets (§15) only rendered on tiles with an active detection, confidence readout bottom-left of the bracket when present.
- Offline tiles show the last captured frame desaturated to ~40% + the `sev-offline` badge, not a blank grey box — operators need to know *what* went dark, not just that something did.
- Grid density is user-configurable (2×2 up to 6×6) via the toolbar control — default 4×4 balances feed size against camera count for a typical install.
- Clicking a tile opens fullscreen single-camera view: same corner-bracket overlay at larger scale, plus a right-side slide-in panel (320px) showing that camera's live detection log (timestamped list, newest first, mono timestamps) and a "create incident" primary button if an unacknowledged detection exists. Escape or a close control returns to grid — no navigation away from Live Operations, preserving the operator's monitoring context.
- No animation on normal feed tiles. The only sanctioned motion here is the live-dot pulse (slow, 2s cycle, opacity 100%→60%) and the corner-bracket appearing instantly (no fade) the moment a detection event arrives — speed of signal matters more than polish for a real-time alert.

---

## 3. Incident Detail

**Job:** give a complete, confident picture of one incident — what happened, how sure the system is, what else it might have been, and what evidence supports it — so an operator can act (acknowledge, escalate, dismiss as false positive) without needing to open five other screens.

```
┌────┬───────────────────────────────────────────────────────────────────┐
│    │ Incident #INC-2026-0614           [Acknowledge] [Escalate] [···]  │
│ ▣  ├───────────────────────────────────────────────────────────────────┤
│ ◉  │ ┌─ Summary ──────────────────────────┐ ┌─ Severity ─────────────┐ │
│ ▦  │ │ ⬤ CRITICAL · investigating          │ │ clear─low─mod─HIGH─crit │ │
│ ⚠● │ │ Camera 14 · Loading Dock B           │ │ ██████████████████████ │ │
│ ▶  │ │ 2026-10-06  09:38:52                 │ │        (filled to crit)│ │
│ ▢  │ │ Opened 2m ago · unassigned           │ └─────────────────────────┘ │
│    │ └──────────────────────────────────────┘                           │
│    │ ┌─ Video evidence ───────────────────────┐ ┌─ AI detection ────────┐ │
│ ⚙  │ │ ┌──────────────────────────────────┐  │ │ Anomaly probability    │ │
│ ◐  │ │ │                                    │  │ │      97.8%             │ │
│    │ │ │        (video player, §15)         │  │ │ (Data-lg, mono)        │ │
│    │ │ │     with detection bracket          │  │ │                        │ │
│    │ │ └──────────────────────────────────┘  │ │ Likely action           │ │
│    │ │ ▂▃▇▅▂  [timeline w/ markers, §16]       │ │   ABUSE                │ │
│    │ │ 00:00  ◀ ❙❙ ▶  00:00:52 / 00:01:40    │ │   confidence 57.2%      │ │
│    │ └──────────────────────────────────────┘ │ ┌────────────────────┐ │ │
│    │                                           │ │Alternative candidates│ │ │
│    │                                           │ │Assault    ███░░ 12.3%│ │ │
│    │                                           │ │Fighting   ██░░░  8.9%│ │ │
│    │                                           │ │Vandalism  █░░░░  7.7%│ │ │
│    │                                           │ └────────────────────┘ │ │
│    │                                           │ Model: action_classifier_v2│
│    │                                           └────────────────────────┘ │
│    │ ┌─ Event timeline ───────────────────────────────────────────────┐ │
│    │ │ 09:38:52  Detected        anomaly flagged, Stage 1              │ │
│    │ │ 09:38:54  Classified      Abuse, 57.2%, Stage 2                 │ │
│    │ │ 09:39:01  Incident opened automatically                        │ │
│    │ │ 09:40:50  (now) unassigned, awaiting acknowledgement            │ │
│    │ └──────────────────────────────────────────────────────────────────┘ │
│    │ ┌─ Related evidence ──────────────────────────────────────────────┐ │
│    │ │ [clip 00:52] [still 00:34] [still 00:41]              + extract │ │
│    │ └──────────────────────────────────────────────────────────────────┘ │
├────┴───────────────────────────────────────────────────────────────────┤
│ ● I3D  ● Stage 1  ● Stage 2    Queue: 0    API: connected    v0.1.0     │
└───────────────────────────────────────────────────────────────────────┘
```

**Composition notes:**
- Top action row uses Primary (Acknowledge), Secondary (Escalate), Ghost-overflow (···: reassign, mark false positive, export) — exactly the button hierarchy from §8, with the single correct next action (Acknowledge) as the only primary-colored control on the page.
- Severity bar (§13) sits beside the summary, same visual weight, because severity is as central to this view as the who/where/when.
- AI detection panel is the direct surface for the verified backend output: anomaly probability as Data-lg hero number (not a gauge), likely action as a short label, confidence + alternative candidates as the comparative bars from §14 — this panel is where the brief's "AI detection, likely action, confidence, alternative candidates" requirement lives, built from fields the backend already returns (`anomaly_probability`, `likely_action`, `action_confidence`, `action_candidates`).
- Event timeline is a simple chronological log, mono timestamps left column, plain-language event description right column — distinct from the video timeline (§16), which is time-within-the-clip; this one is time-across-the-incident's-lifecycle.
- Related evidence strip is intentionally small/secondary here — its full treatment lives in the Evidence screen; here it's just enough to confirm what's attached and jump to it.

---

## 4. Video Investigation

**Job:** deep, frame-accurate review of one piece of footage — scrubbing, inspecting individual detection events, filtering the timeline, and pulling stills/clips into Evidence. This is the "zoom in and verify" screen, used after Incident Detail when an operator needs to actually scrutinize the footage rather than just read the AI's summary.

```
┌────┬───────────────────────────────────────────────────────────────────┐
│    │ Video Investigation — Cam 14, 2026-10-06 09:38           [⤓ export]│
│ ▣  ├───────────────────────────────────────────────────────────────────┤
│ ◉  │ ┌────────────────────────────────────────────┐ ┌─ Filters ──────┐ │
│ ▦  │ │                                              │ │ Show markers:  │ │
│ ⚠  │ │                                              │ │ ☑ Stage 1      │ │
│ ▶● │ │         (video player, large, §15)           │ │ ☑ Stage 2      │ │
│ ▢  │ │          corner-bracket on subject            │ │ ☐ below 40%    │ │
│    │ │                                              │ │   confidence   │ │
│    │ └──────────────────────────────────────────────┘ └────────────────┘ │
│    │ ┌─ Activity + detections ────────────────────────────────────────┐ │
│ ⚙  │ │ attention ▂▃▂▅▇▇▆▅▃▂▁▁▂▃▅▆▇▆▃▂▁  (density strip, §16)            │ │
│ ◐  │ │        │        │          │                                    │ │
│    │ │ markers ▲        ▲          ▲▲   (severity-colored ticks)        │ │
│    │ │ 00:00   00:20    00:40     01:00     01:20          01:40        │ │
│    │ │                     ◆ playhead                                   │ │
│    │ └──────────────────────────────────────────────────────────────────┘ │
│    │ ◀◀  ◀  ❙❙  ▶  ▶▶   0.5x 1x 2x    00:00:52 / 00:01:40   [⬛ extract] │
│    │ ┌─ Frame / event inspector ───────────────────────────────────────┐ │
│    │ │ Window 14 of 32 · frames 52.0–60.0s                              │ │
│    │ │ I3D feature extracted ✓   Stage 1: anomaly 97.8%   Stage 2: Abuse 57.2%│
│    │ │ attention weight (this window): 0.14 of 1.00 total              │ │
│    │ └──────────────────────────────────────────────────────────────────┘ │
├────┴───────────────────────────────────────────────────────────────────┤
│ ● I3D  ● Stage 1  ● Stage 2    Queue: 0    API: connected    v0.1.0     │
└───────────────────────────────────────────────────────────────────────┘
```

**Composition notes:**
- Player is the largest element on screen by far — this view exists to look closely at footage, so chrome stays minimal around it.
- Filters panel lets an operator hide low-confidence markers or isolate Stage 1 vs Stage 2 events on a long clip — directly useful on a video with many windows, not decoration.
- The activity+detections strip combines the density strip and tick markers from §16 into one taller region here (vs. the compact version in Incident Detail) because frame-accurate investigation is this screen's whole purpose.
- Frame/event inspector is new to this screen and maps directly to the real pipeline internals documented in PROJECT_INVENTORY.md — temporal windows, per-window attention weight — giving an operator (or, realistically, a developer/analyst validating the model) a way to inspect *why* the model flagged a moment, not just that it did. This is deliberately technical/dense, appropriate for an investigation screen specifically, not for Command Center.
- Extract control (camera-icon button, also in the player control bar per §15) saves the current frame or a scrub-selected clip range directly to Evidence, tagged with the source incident if one exists.

---

## 5. Evidence

**Job:** a searchable library of everything extracted from incidents — clips and stills — with enough metadata to find a specific piece later (for a report, for law enforcement handoff, for review). This is the only screen that behaves like a traditional library/browser rather than a live monitoring view.

```
┌────┬───────────────────────────────────────────────────────────────────┐
│    │ Evidence                    [search evidence…]      [+ 142 items] │
│ ▣  ├───────────────────────────────────────────────────────────────────┤
│ ◉  │ ┌─ Filters ──────┐ ┌────────────────────────────────────────────┐ │
│ ▦  │ │ Type            │ │ [thumb]      [thumb]      [thumb]      [thumb]│
│ ⚠  │ │ ☑ Clips  ☑ Stills│ │ INC-0614     INC-0609     INC-0601     INC-0598│
│ ▶  │ │                 │ │ Abuse 97.8%  Fighting 84% Normal 4.2%  Theft 61%│
│ ▢● │ │ Severity        │ │ Cam 14       Cam 03       Cam 22       Cam 07  │
│    │ │ ☑ critical       │ │ 2m ago       8m ago       14m ago      31m ago │
│    │ │ ☑ high          │ ├────────────────────────────────────────────┤ │
│    │ │ ☐ moderate      │ │ [thumb]      [thumb]      [thumb]      [thumb]│
│ ⚙  │ │ ☐ low           │ │   ... (grid continues, 4-up, scrolling)       │
│ ◐  │ │                 │ └────────────────────────────────────────────┘ │
│    │ │ Date range       │                                                │
│    │ │ [last 7 days ▾] │                                                │
│    │ │                 │                                                │
│    │ │ Camera           │                                                │
│    │ │ [all cameras ▾] │                                                │
│    │ └──────────────────┘                                                │
├────┴───────────────────────────────────────────────────────────────────┤
│ ● I3D  ● Stage 1  ● Stage 2    Queue: 0    API: connected    v0.1.0     │
└───────────────────────────────────────────────────────────────────────┘
```

**Composition notes:**
- Left filter panel is persistent (not a dropdown-triggered overlay) because evidence search is this screen's primary task, not a secondary refinement — same reasoning as the always-visible global search in the topbar, applied locally.
- Grid cards show exactly four pieces of metadata, consistently positioned: incident ID (mono), classification + confidence (text + mono %), camera (text), relative timestamp (mono) — same information density pattern as the Recent AI analyses list on Command Center, just in a thumbnail grid instead of a table, for visual scanning of footage rather than numeric scanning.
- Clicking a card opens a preview overlay (modal, §19, 880px variant): larger thumbnail/video, full metadata table, "open source incident" and "open in Video Investigation" links, download/export action. Preview is a modal here (not a full navigation) because the operator's expectation on a library screen is "glance and return to the grid," unlike Incident Detail which deserves a full view.
- No infinite-scroll-with-no-feedback — a persistent item count in the topbar (`142 items`, updates live with filters) tells the operator how large the filtered set is before they scroll.

---

## Cross-screen consistency checklist

- Same shell (rail/topbar/status strip) on all five — confirmed above.
- Same severity vocabulary and colors (critical/high/moderate/low/clear) used identically in Command Center, Live Operations, Incident Detail, and Evidence filters.
- Same confidence-bar component (§14) appears in Incident Detail (alternative candidates) and could extend identically to any future screen showing model output — one component, one place it's defined.
- Same video player chrome (§15) appears in Incident Detail and Video Investigation, differing only in size/surrounding panels, not in control behavior.
- Same table/list row pattern (severity bar + badge + mono timestamp, right-aligned numerics) appears in Command Center's incident list, Live Operations' detection log, and would back Incident list and Evidence list views.
- Status strip is identical, same three dots, same position, on every screen — the one element an operator can rely on to look unchanged no matter where they are in the product.
