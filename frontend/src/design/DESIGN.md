# Design System: 高考志愿AI顾问 (Gaobao Advisor)

> Category: Education & AI Service
> Warm paper canvas, Chinese red accent, gold secondary — a modern interpretation of China's imperial-examination heritage for AI-powered college admission advising. Warm, dignified, and trustworthy.

## 1. Visual Theme & Atmosphere

Gaobao Advisor compresses into one sentence: **warm paper canvas, Chinese red accent, restrained gold — serif-led Chinese typography, approachable warmth, never cold or clinical.**

The aesthetic bridges two worlds: the cultural weight of China's 1300-year imperial examination tradition (科举, jǔkē) and the approachable clarity of a modern AI service. The result should feel like an esteemed teacher (恩师) sitting across from you at a scholar's desk — warm, authoritative, but never intimidating.

The page background is warm paper (`#f5f0e8`), never pure white. Text sits on this cream foundation. The primary chromatic move is **Chinese Red** (`#D4312E`) — used for primary CTAs, user message bubbles, active states, key data highlights, and section markers. **Gold** (`#C6922A`) appears as a secondary accent for achievement indicators, recommend badges, decorative section anchors (金榜题名 header), and the school-rank safety denotation.

### Key Characteristics

- Warm paper canvas (`#f5f0e8`) — reminiscent of traditional rice paper (宣纸) and exam booklets
- Primary accent: Chinese Red (`#D4312E`) — sits on ~10–15% of interactive surfaces
- Secondary accent: Gold (`#C6922A`) — covers ≤5% of any surface, used sparingly
- All grays are warm (R ≈ G > B), no cool blue-grays anywhere
- Chinese serif (Noto Serif SC) for headings and display text — evokes classical scholarship
- Clean sans-serif (Noto Sans SC or PingFang SC) for body text — modern and readable
- Warm shadows with a slight amber tint, never hard black drop shadows
- Gradients run warm-to-warm, never purple-to-blue
- Numbers use `font-variant-numeric: tabular-nums` in score displays and comparisons
- Dark mode: warm charcoal background (`#1a1817`), never cold `#111` or pure `#000`

### Visual Metaphors

- **The Scholar's Desk**: Warm paper background, calligraphy-inspired headings, seal-stamp-like badges
- **The Golden List (金榜题名)**: Gold accents mark achievements — school recommendations, score milestones, report highlights
- **The Trusted Advisor**: Red CTAs and user elements create warmth and confidence; the AI speaks in clean white cards

## 2. Color Palette & Roles

### Brand Colors

| Token | Hex | Usage |
|-------|-----|-------|
| **Chinese Red** | `#D4312E` | Primary CTAs, user message bubbles, active tab, error states, key data highlight, attention markers |
| **Red Dark** | `#B8282A` | Hover state for red elements, pressed buttons |
| **Red Light** | `#FDF1F0` | Red-tinted backgrounds, notification badges |
| **Red Accent** | `#E85450` | Lighter red for secondary interactive elements |
| **Gold** | `#C6922A` | Achievement/commendation badges, safety-rating markers, report decorative headers, recommend seals |
| **Gold Light** | `#FBF1E0` | Gold-tinted backgrounds, badge backgrounds |
| **Gold Dark** | `#A37822` | Hover state for gold elements |

### Surface Colors (Light Mode)

| Token | Hex | Usage |
|-------|-----|-------|
| **Paper** | `#f5f0e8` | Page background — the emotional foundation. Warm, never white. |
| **Surface** | `#faf7f0` | Cards, lifted containers, input backgrounds. One shade brighter than paper. |
| **Elevated** | `#ffffff` | Modals, popovers, absolute top-layer containers — only here is white allowed |
| **Sidebar** | `#e8e0d0` | Sidebar background — slightly darker than paper for visual layering |
| **Sidebar Dark** | `#2a2520` | Sidebar dark mode background |

### Text Colors (Light Mode)

| Token | Hex | Usage |
|-------|-----|-------|
| **Ink** | `#1a1817` | Primary text. Warm black — never pure `#000`. |
| **Secondary** | `#55504a` | Secondary text, table headers |
| **Muted** | `#8a847b` | Captions, dates, metadata, placeholders |
| **Disabled** | `#c0b8ad` | Disabled text, non-interactive labels |

### Border Colors (Light Mode)

| Token | Hex | Usage |
|-------|-----|-------|
| **Border** | `#e0d8ca` | Cards, dividers, default borders |
| **Border Light** | `#ece5d8` | Subtle internal borders, row separators |
| **Border Accent** | `#D4312E` | Focus rings, active borders |
| **Border Gold** | `#C6922A` | Featured/special element borders |

### Semantic Colors

| Token | Hex | Usage |
|-------|-----|-------|
| **Success** | `#2A9D3E` | Check marks, completion badges, positive indicators |
| **Warning** | `#E8961E` | Warning banners, cautionary indicators |
| **Error** | `#D4312E` | Error messages, destructive actions |
| **Info** | `#2A7FB8` | Information badges, help tooltips |

### Dark Mode Colors

| Token | Hex | Usage |
|-------|-----|-------|
| **Dark BG** | `#1a1817` | Page background — warm charcoal |
| **Dark Surface** | `#252220` | Cards, containers — one step above background |
| **Dark Elevated** | `#302c28` | Modal, popover backgrounds |
| **Dark Sidebar** | `#141211` | Sidebar background |
| **Dark Ink** | `#e8e4da` | Primary text — warm off-white |
| **Dark Secondary** | `#a8a092` | Secondary text |
| **Dark Muted** | `#6b655b` | Captions, metadata |
| **Dark Border** | `#3a3530` | Card borders, dividers |
| **Dark Border Light** | `#2e2a26` | Subtle separators |
| **Dark Red** | `#E85450` | Chinese Red variant on dark — slightly brighter for readability |
| **Dark Gold** | `#D4A843` | Gold variant on dark — brighter to maintain contrast |

### Gradient System

Sanctioned gradients — all warm-toned, no cold gradients:

```css
/* Page footer/bookend gradient — subtle warm fade */
background: linear-gradient(180deg, #f5f0e8 0%, #ede4d4 100%);

/* Gold acclaim banner — for report "金榜题名" header */
background: linear-gradient(135deg, #C6922A 0%, #D4A843 50%, #C6922A 100%);

/* Dark mode footer */
background: linear-gradient(180deg, #1a1817 0%, #252220 100%);
```

### Forbidden Colors

- `#000000` as text (`#1a1817` warm-black instead)
- `#ffffff` as page background (Paper `#f5f0e8` instead)
- Tailwind `indigo-500` (`#6366f1`) or any blue-purple — the most reliable AI-slop tell
- Cool gray values (`#f8f9fa`, `#e5e7eb`, `#9ca3af`, `#6b7280`, `#374151`) — no `slate-*` or `gray-*` from Tailwind unless explicitly mapped to a warm token
- Two-stop "trust" gradients (purple→blue, blue→cyan)
- Neon or fluorescent colors

## 3. Typography Rules

### Font Stack

```css
/* Chinese (default for this app) */
--font-display: "Noto Serif SC", "Source Han Serif SC", "STSong", "SimSun", Georgia, serif;
--font-body: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
--font-mono: "JetBrains Mono", "Fira Code", "Noto Sans SC", monospace;
```

### When to use which stack

- **Display/Headings**: `--font-display` (serif) — headlines, page titles, section headers, report titles. The serif evokes classical scholarship and the gravitas of the Gaokao.
- **Body/Chat copy**: `--font-body` (sans) — message content, form labels, descriptions, table cells. Clean, readable, modern.
- **Mono/Spec**: `--font-mono` — any code, scores in special contexts, hex values.
- **Emphasis within body**: Use `--font-body` at weight 600 with `--accent` color, never italic.

### Hierarchy

| Role | Family | Size | Weight | Line-Height | Letter-Spacing | Notes |
|------|--------|------|--------|-------------|----------------|-------|
| Hero / 金榜 title | display | 48–56px | 700 | 1.15 | -0.5px | Report cover, landing hero — max once per page |
| Page Title | display | 28–32px | 700 | 1.2 | 0 | Page headers |
| Section Title | display | 22–24px | 600 | 1.25 | 0 | Section headings |
| Card Title | body | 16–18px | 600 | 1.3 | 0 | Card titles, sidebar items |
| Body / Chat | body | 15–16px | 400 | 1.6 | 0 | Message content, paragraphs |
| Body Dense | body | 14px | 400 | 1.45 | 0 | Profile fields, form content |
| Small / Caption | body | 13px | 400 | 1.4 | +0.01em | Labels, dates, timestamps |
| Eyebrow | body | 12px | 600 | 1 | +0.06em **uppercase** | Scene switcher labels, badge text |
| Mono / Data | mono | 13px | 400 | 1.5 | 0 | Scores, academic data |

### Weight Rules

- Display serif uses **500–700 range** — weight 700 for headlines, 600 for subheads
- Body sans uses **400–600 range** — 400 for reading, 500 for emphasized, 600 for labels
- `strong` maps to 600
- No weight 100/200/300 — they look anemic on warm paper
- No italic anywhere — use weight/color for emphasis instead

### Line-Height

- Tight heading: 1.15–1.25 (headlines, page titles)
- Reading body: 1.5–1.6 (chat messages, paragraphs)
- Dense body: 1.4–1.45 (profile fields, data tables)
- UI labels: 1.0–1.3 (buttons, tabs, badges)

### Letter-Spacing

- Body text: `0`
- Labels/buttons: `+0.02em`
- ALL CAPS (eyebrow only): `+0.06em` (mandatory)
- Display 32px+: `-0.3px to -0.5px` (tighter for larger sizes)
- Chinese characters in headings: `0.05em` (slight breathing room)

### Font Loading Strategy

- Preload `Noto Serif SC` at weight 700 (most visible heading weight)
- Load `Noto Sans SC` as variable font for 400–600 range
- Fallback: system Chinese fonts display immediately while web fonts load

### Tabular-Nums

```css
font-variant-numeric: tabular-nums;
```

Mandatory for: score displays, school ranking tables, percentile comparisons, admission probability numbers, any column of numeric data.

## 4. Spacing & Grid

### Spacing Scale

Based on 4px unit:

| Token | px | Usage |
|-------|----|-------|
| `--space-1` | 4px | Micro gaps, icon margins |
| `--space-2` | 8px | Tight spacing, badge padding |
| `--space-3` | 12px | Button padding X, chip padding |
| `--space-4` | 16px | Default gap, card padding X |
| `--space-5` | 20px | Card padding Y |
| `--space-6` | 24px | Section gap, modal padding |
| `--space-8` | 32px | Large section gap |
| `--space-10` | 40px | Page section padding |
| `--space-12` | 48px | Page margins |

### Layout Rules

- Max content width: `960px` (chat area), `1120px` (report page), centered
- Page horizontal padding: `24px` on desktop, `16px` on mobile
- Section gap: `32px` between major sections
- Card padding: `20px 16px` (Y, X)
- Two-column grids collapse to single column below `768px`

### Border Radius Scale

| Token | px | Usage |
|-------|----|-------|
| `--radius-sm` | 4px | Tags, small badges, avatar |
| `--radius-md` | 8px | Buttons, cards, inputs |
| `--radius-lg` | 12px | Large cards, modals, message bubbles |
| `--radius-xl` | 16px | Featured containers, hero areas |
| `--radius-full` | 9999px | Pill buttons, scene switcher tabs, avatars |

### Depth & Elevation

| Level | Light Mode | Dark Mode | Usage |
|-------|-----------|-----------|-------|
| Flat (0) | No shadow | No shadow | Surface text, body content |
| Card (1) | `0 1px 3px rgba(0,0,0,0.06)` | `0 1px 3px rgba(0,0,0,0.2)` | Default cards |
| Raised (2) | `0 4px 12px rgba(0,0,0,0.08)` | `0 4px 12px rgba(0,0,0,0.25)` | Hovered cards, dropdowns |
| Modal (3) | `0 8px 30px rgba(0,0,0,0.12)` | `0 8px 30px rgba(0,0,0,0.35)` | Modals, popovers |

## 5. Component Stylings

### Buttons

```css
/* Primary — Chinese Red */
.btn-primary {
  background: var(--red);                          /* #D4312E */
  color: white;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font: 600 14px/1 var(--font-body);
  letter-spacing: 0.02em;
  transition: background 0.15s, box-shadow 0.15s;
}
.btn-primary:hover { background: var(--red-dark); }  /* #B8282A */
.btn-primary:active { box-shadow: inset 0 2px 4px rgba(0,0,0,0.15); }

/* Secondary — surface with red border */
.btn-secondary {
  background: transparent;
  color: var(--red);
  border: 1.5px solid var(--red);
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font: 600 14px/1 var(--font-body);
}
.btn-secondary:hover { background: var(--red-light); }  /* #FDF1F0 */

/* Ghost — text only */
.btn-ghost {
  background: transparent;
  color: var(--secondary);
  padding: 8px 12px;
  border-radius: var(--radius-md);
  font: 500 14px/1 var(--font-body);
}
.btn-ghost:hover { background: rgba(0,0,0,0.04); }

/* Gold accent — for achievement/special actions */
.btn-gold {
  background: linear-gradient(135deg, var(--gold) 0%, var(--gold-dark) 100%);
  color: white;
  padding: 10px 20px;
  border-radius: var(--radius-md);
  font: 600 14px/1 var(--font-body);
}
```

### Message Bubbles

```css
/* User message — Chinese Red */
.user-bubble {
  background: var(--red);
  color: white;
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-sm) var(--radius-lg);
  padding: 12px 16px;
  max-width: 72%;
  font: 400 15px/1.6 var(--font-body);
  box-shadow: 0 1px 3px rgba(212, 49, 46, 0.15);
}

/* AI message — warm surface */
.ai-bubble {
  background: var(--surface);
  color: var(--ink);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg) var(--radius-lg) var(--radius-lg) var(--radius-sm);
  padding: 12px 16px;
  max-width: 76%;
  font: 400 15px/1.6 var(--font-body);
  box-shadow: var(--shadow-card);
}
```

### Cards

```css
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px 16px;
  box-shadow: var(--shadow-card);
  transition: box-shadow 0.2s;
}
.card:hover { box-shadow: var(--shadow-raised); }

/* Elevated card — for dialog modals, panels */
.card-elevated {
  background: var(--elevated);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-modal);
}
```

### Form Inputs

```css
.input {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-md);
  padding: 10px 14px;
  font: 400 14px/1.4 var(--font-body);
  color: var(--ink);
  transition: border-color 0.15s;
}
.input:focus {
  border-color: var(--red);
  box-shadow: 0 0 0 3px rgba(212, 49, 46, 0.12);
  outline: none;
}
.input::placeholder { color: var(--muted); }
```

### Chat Input

```css
.chat-input-wrapper {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-xl);
  padding: 8px 12px;
}
.chat-input-wrapper:focus-within {
  border-color: var(--red);
  box-shadow: 0 0 0 3px rgba(212, 49, 46, 0.12);
}
```

### Scene / Tab Switcher

```css
.scene-tab {
  padding: 6px 16px;
  border-radius: var(--radius-full);
  font: 600 13px/1 var(--font-body);
  letter-spacing: 0.02em;
  transition: all 0.15s;
}
.scene-tab.active {
  background: var(--red);
  color: white;
}
.scene-tab.inactive {
  background: transparent;
  color: var(--muted);
}
.scene-tab.inactive:hover {
  background: rgba(212, 49, 46, 0.06);
  color: var(--red);
}
```

### Badges & Tags

```css
/* Standard badge */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-sm);
  font: 500 12px/1.3 var(--font-body);
  letter-spacing: 0.02em;
}

/* Red badge */
.badge-red { background: var(--red-light); color: var(--red); }

/* Gold badge — for featured/achievement */
.badge-gold { background: var(--gold-light); color: var(--gold-dark); }

/* Green badge — for completed/completion */
.badge-green { background: #e8f5e9; color: #1b5e20; }

/* Gray badge */
.badge-gray { background: var(--border); color: var(--muted); }

/* School-rank badges */
.badge-rush { background: #FDF1F0; color: #D4312E; }     /* 冲 */
.badge-stable { background: var(--gold-light); color: #A37822; }  /* 稳 */
.badge-safe { background: #e8f5e9; color: #2A9D3E; }     /* 保 */
```

### Progress Bar

```css
.progress-bar {
  height: 6px;
  border-radius: var(--radius-full);
  background: var(--border);
  overflow: hidden;
}
.progress-fill {
  height: 100%;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--gold) 0%, var(--red) 100%);
  transition: width 0.4s ease;
}
```

### Feedback Buttons

```css
.feedback-btn {
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  color: var(--muted);
  font-size: 14px;
  transition: all 0.15s;
}
.feedback-btn:hover { background: var(--border); }
.feedback-btn.active-helpful { color: #2A9D3E; background: #e8f5e9; }
.feedback-btn.active-unhelpful { color: var(--red); background: var(--red-light); }
```

### Sidebar

```css
.sidebar {
  background: var(--sidebar);     /* light: #e8e0d0, dark: #2a2520 */
  color: var(--ink);              /* text color */
  width: 260px;
  border-right: 1px solid var(--border);
}

.sidebar-item {
  padding: 10px 16px;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background 0.1s;
}
.sidebar-item.active {
  background: var(--red-light);
  color: var(--red);
  font-weight: 600;
}
.sidebar-item:hover:not(.active) {
  background: rgba(0,0,0,0.04);
}
```

### Soul Question Card

```css
.soul-question-card {
  background: var(--surface);
  border: 1px solid var(--gold);
  border-radius: var(--radius-lg);
  padding: 20px;
  box-shadow: 0 2px 8px rgba(198, 146, 42, 0.08);
}
.soul-question-label {
  font: 500 12px/1 var(--font-body);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--gold-dark);
  margin-bottom: 8px;
}
```

### Report Section

```css
.report-section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  margin-bottom: 16px;
}
.report-section h2 {
  font: 600 20px/1.25 var(--font-display);
  color: var(--ink);
  padding-bottom: 12px;
  border-bottom: 2px solid var(--gold);
  margin-bottom: 16px;
}
/* 金榜 header */
.report-header {
  background: linear-gradient(135deg, #C6922A 0%, #D4A843 50%, #C6922A 100%);
  color: white;
  padding: 40px 24px;
  border-radius: var(--radius-xl);
  text-align: center;
  margin-bottom: 24px;
}
.report-header h1 {
  font: 700 42px/1.2 var(--font-display);
  letter-spacing: 0.15em;
  margin-bottom: 8px;
}
```

### School Suggestion Cards

```css
.school-card {
  border-left: 4px solid;
  border-radius: var(--radius-md);
  padding: 14px 16px;
  margin-bottom: 8px;
  background: var(--surface);
}
/* Rush/冲 */
.school-card.rush { border-left-color: var(--red); }
.school-card.rush .tag { background: #FDF1F0; color: var(--red); }

/* Stable/稳 */
.school-card.stable { border-left-color: var(--gold); }
.school-card.stable .tag { background: var(--gold-light); color: var(--gold-dark); }

/* Safe/保 */
.school-card.safe { border-left-color: var(--success); }
.school-card.safe .tag { background: #e8f5e9; color: #1b5e20; }
```

### Voice Modal

```css
.voice-modal {
  background: linear-gradient(135deg, #1a1817 0%, #252220 50%, #302c28 100%);
  color: #e8e4da;
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-modal);
}

.voice-ripple {
  border: 2px solid var(--red);
  border-radius: 50%;
  animation: ripple-pulse 1.5s ease-out infinite;
}

.voice-active-indicator {
  color: var(--red);
}

.voice-control-btn {
  background: rgba(255,255,255,0.08);
  border-radius: 50%;
  padding: 12px;
  transition: background 0.15s;
}
.voice-control-btn:hover { background: rgba(255,255,255,0.15); }
.voice-control-btn.danger { background: var(--red); }
.voice-control-btn.danger:hover { background: var(--red-dark); }
```

## 6. Layout & Composition

### Page Layouts

#### Chat Page (Main)
```
┌─────────┬─────────────────────────────────┬──────────┐
│ Sidebar │  Header (scene switcher)        │ Right    │
│ 260px   ├─────────────────────────────────┤ Panel    │
│         │  Chat Area (scrollable)         │ 280px    │
│         │                                 │ (profile │
│         │                                 │  slots)  │
│         ├─────────────────────────────────┤          │
│         │  Message Input Bar              │          │
└─────────┴─────────────────────────────────┴──────────┘
```

#### Profile Page
```
┌─────────────────────────────────────────────────────┐
│     Header: 用户画像 + 进度条                         │
├─────────────────────────────────────────────────────┤
│     Soul Question Card (if any)                      │
├──────────────────┬──────────────────────────────────┤
│  Province *      │  Score *                          │
├──────────────────┼──────────────────────────────────┤
│  Subject *       │  Interest *                       │
├──────────────────┼──────────────────────────────────┤
│  Region          │  Family                           │
├──────────────────┼──────────────────────────────────┤
│  Goal            │                                   │
├──────────────────┴──────────────────────────────────┤
│  ← Back to Chat              Next Question →        │
└─────────────────────────────────────────────────────┘
```

#### Report Page
```
┌─────────────────────────────────────────────────────┐
│        金榜题名 (Gold Gradient Header)               │
├─────────────────────────────────────────────────────┤
│    考生信息 (info grid: name, province, score...)    │
├─────────────────────────────────────────────────────┤
│    分析摘要                                          │
├─────────────────────────────────────────────────────┤
│    院校推荐                                          │
│    ┌ 冲 ─────────────────────────────────┐          │
│    ┌ 稳 ─────────────────────────────────┐          │
│    ┌ 保 ─────────────────────────────────┐          │
├─────────────────────────────────────────────────────┤
│    风险提示 + 建议行动                                 │
├─────────────────────────────────────────────────────┤
│    Export Buttons                                    │
└─────────────────────────────────────────────────────┘
```

### Responsive Breakpoints

| Name | Width | Key Changes |
|------|-------|-------------|
| Mobile | < 768px | Single column sidebar as drawer, right panel hidden, card padding reduces |
| Tablet | 768–1024px | 2-column grids hold, sidebar collapses to icon-only |
| Desktop | ≥ 1024px | Full 3-column layout |

### Touch Targets

- All interactive elements minimum 44×44px
- Sidebar items: generous internal padding
- Feedback buttons: 36px minimum height with clear tap zone

## 7. Motion & Interaction

### Duration Tokens

```css
--motion-instant: 100ms;
--motion-fast: 150ms;
--motion-normal: 250ms;
--motion-slow: 400ms;
```

### Easing

```css
--ease-smooth: cubic-bezier(0.23, 1, 0.32, 1);   /* Default for UI transitions */
--ease-enter: cubic-bezier(0, 0, 0.2, 1);         /* Enter — slightly overshoot */
--ease-exit: cubic-bezier(0.4, 0, 1, 1);          /* Exit — decisive */
```

### Micro-interactions

- **Message bubble enter**: fade-up from 4px with opacity — 250ms ease-smooth
- **Sidebar item hover**: background color shift — 100ms
- **Button hover**: background + subtle shadow — 150ms
- **Feedback toggle**: color change + slight scale (0.95→1) — 150ms
- **Scene tab switch**: background crossfade — 200ms
- **Modal open**: fade-in + scale(0.96→1) — 250ms ease-enter
- **Modal close**: fade-out + scale(1→0.97) — 150ms ease-exit
- **Dropdown expand**: grid-template-rows 0fr→1fr with opacity — 250ms
- **Voice ripple pulse**: keyframe animation 1.5s loop

### Transition Patterns

```css
/* Page enter */
.page-enter-active { animation: page-enter 250ms var(--ease-enter); }
@keyframes page-enter {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

/* Fade in */
.fade-in { animation: fade-in 200ms var(--ease-smooth); }
@keyframes fade-in {
  from { opacity: 0; }
  to   { opacity: 1; }
}
```

## 8. Voice & Tone

### Character

- **Role**: An esteemed Gaokao advisor — knowledgeable, warm, and straightforward
- **Tone**: Warm and authoritative (温暖可信), never casual or overly technical
- **Formality**: Respectful but approachable — like a good teacher, not a bureaucrat

### Microcopy Principles

- Use second person ("您" for respect, "你" for younger students in informal contexts)
- Keep messages clear and action-oriented
- Celebrate achievements with warmth ("恭喜!" "这个分数很不错!")
- Use Chinese educational idioms sparingly — 金榜题名, 鱼跃龙门, but only when earned
- Error messages are apologetic and helpful, never technical
- Placeholder text is instructive, not empty

### Do's

- "根据您的分数和选科，我们分析出以下适合的院校..."
- "您还差 3 个信息就能获得完整的志愿分析报告"
- "这个分数段，冲刺 211 院校的成功率很高！"

### Don'ts

- "Error: Something went wrong" (technical, cold)
- "Please fill in required fields" (robotic)
- "You scored 524. Here are options" (flat, no warmth)
- No marketing exaggeration ("best ever", "guaranteed admission")

## 9. Anti-Patterns & Forbidden Patterns

### P0 — Must Fix (Auto-Linted)

1. **Tailwind indigo (blue-600, `#6366f1`, etc.) as accent** — the most reliable AI-slop tell. Our accent is Chinese Red.
2. **Two-stop "trust" gradients** (purple→blue, blue→cyan). All gradients must be warm-toned.
3. **Emoji as feature icons** — no `🎓` `💡` `✨` `🚀` inside headings, buttons, or feature lists. Use Lucide icons instead.
4. **Sans-serif on headings when serif is specified** — display headings use Noto Serif SC.
5. **Rounded card with colored left-border** (the canonical AI dashboard tile) — school cards are an exception (冲/稳/保), but regular cards must not use left-border accents.
6. **Invented metrics** ("10x better", "99.9% accurate") — be honest and specific.
7. **Filler copy** — no lorem ipsum, "Feature One/Two/Three", or placeholder text.

### P1 — Should Fix

- Default hero → features → pricing → FAQ → CTA template flow
- External placeholder image CDNs (unsplash.com, placehold.co, picsum.photos)
- More than ~12 raw hex values outside the CSS variables
- `var(--red)` used 6+ times in one view — extract to component-level tokens
- Pure white (`#ffffff`) backgrounds outside modals and elevated containers

### P2 — Nice to Fix

- Decorative blob/wave SVG backgrounds
- Perfect symmetric layout with no visual tension — add asymmetry deliberately
- Sections without semantic HTML landmarks
- Overuse of the gold accent (>3 distinct gold elements per page)

### Design-Specific Forbidden Patterns

- **No cold UI**: No pure `#000` text, no `#fff` background (except modals), no cool grays
- **No emoji icons**: All emoji in UI must be replaced with Lucide icons
- **No thick drop shadows**: Max shadow is `0 8px 30px rgba(0,0,0,0.12)`
- **No glassmorphism** (`backdrop-filter: blur` on elements)
- **No neumorphism**
- **No second accent color**: Only red + gold. No green accent, no blue accent.
- **No horizontal scroll**: All layouts should be responsive within viewport
- **No justified text**: Text-align must be left or center only

## Appendix: Quick Reference

### CSS Variables Summary

```css
:root {
  /* Brand */
  --red: #D4312E;
  --red-dark: #B8282A;
  --red-light: #FDF1F0;
  --gold: #C6922A;
  --gold-light: #FBF1E0;
  --gold-dark: #A37822;

  /* Surfaces */
  --paper: #f5f0e8;
  --surface: #faf7f0;
  --elevated: #ffffff;
  --sidebar: #e8e0d0;

  /* Text */
  --ink: #1a1817;
  --secondary: #55504a;
  --muted: #8a847b;

  /* Borders */
  --border: #e0d8ca;
  --border-light: #ece5d8;

  /* Semantic */
  --success: #2A9D3E;
  --warning: #E8961E;
  --error: #D4312E;
  --info: #2A7FB8;

  /* Typography */
  --font-display: "Noto Serif SC", "Source Han Serif SC", "STSong", "SimSun", Georgia, serif;
  --font-body: "Noto Sans SC", "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Helvetica, Arial, sans-serif;
  --font-mono: "JetBrains Mono", "Fira Code", "Noto Sans SC", monospace;

  /* Spacing */
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
  --space-10: 40px;
  --space-12: 48px;

  /* Radius */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 16px;
  --radius-full: 9999px;

  /* Shadows */
  --shadow-card: 0 1px 3px rgba(0,0,0,0.06);
  --shadow-raised: 0 4px 12px rgba(0,0,0,0.08);
  --shadow-modal: 0 8px 30px rgba(0,0,0,0.12);

  /* Motion */
  --motion-fast: 150ms;
  --motion-normal: 250ms;
  --ease-smooth: cubic-bezier(0.23, 1, 0.32, 1);
}
```

### Deep Mode Overrides

```css
@media (prefers-color-scheme: dark) {
  :root {
    --paper: #1a1817;
    --surface: #252220;
    --elevated: #302c28;
    --sidebar: #141211;
    --ink: #e8e4da;
    --secondary: #a8a092;
    --muted: #6b655b;
    --border: #3a3530;
    --border-light: #2e2a26;
    --red: #E85450;
    --gold: #D4A843;
  }
}
```