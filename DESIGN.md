# AgroLink — Design System & Component Reference (DESIGN.md)

> **Living document.** All UI work references this file.
> Last updated: October 2026 | Design system version: 2.0

---

## Table of Contents

1. [Design Principles](#1-design-principles)
2. [Color System](#2-color-system)
3. [Typography](#3-typography)
4. [Spacing & Grid](#4-spacing--grid)
5. [Shape & Shadow](#5-shape--shadow)
6. [Motion](#6-motion)
7. [Buttons](#7-buttons)
8. [Form Fields](#8-form-fields)
9. [Icons](#9-icons)
10. [Badges](#10-badges)
11. [UI Components](#11-ui-components)
12. [Component Catalogue](#12-component-catalogue)
13. [Do / Don't](#13-do--dont)
14. [Accessibility Rules](#14-accessibility-rules)
15. [How to Add New Components](#15-how-to-add-new-components)

---

## 1. Design Principles

| # | Principle | What it means |
|---|-----------|---------------|
| 1 | **Agricultural authenticity** | Warm greens, earthy browns, fresh sky blues — not generic SaaS pastels. |
| 2 | **Mobile-first, always** | Design at 375px first. Every tap target ≥ 44 × 44px. |
| 3 | **Never horizontal-scroll** | `overflow-x: hidden` on body; all layouts use flexbox/grid with `min-w-0`. |
| 4 | **Text-flexible** | No hard widths on buttons or containers. Sinhala/Tamil must render cleanly. |
| 5 | **WCAG 2.1 AA minimum** | 4.5:1 for normal text, 3:1 for large text and UI components. |
| 6 | **Zero emoji icons** | All icons are crisp Lucide-style SVGs via the `icon()` macro. |
| 7 | **Zero native `confirm()`** | Use `window.AgroConfirm()` or `data-confirm` attribute pattern. |
| 8 | **One primary per section** | Never two `btn-primary` elements in the same visual grouping. |

---

## 2. Color System

All tokens live in `base.html` → `tailwind.config → theme.extend.colors`.

### Brand Colors

| Token | Hex | Contrast on white | Usage |
|-------|-----|-------------------|-------|
| `leaf` / DEFAULT | `#2D6A4F` | **5.7:1** ✓ AA | Primary buttons, active states, brand |
| `leaf-dark` / 700 | `#1B4332` | **11.8:1** ✓ AAA | Hover states, footer bg, headings |
| `leaf-light` / 500 | `#40916C` | **3.8:1** ✓ UI | Icons, borders, large text **only** |
| `leaf-pale` / 100 | `#D8F3DC` | Background only | Tinted cards, active pills, hover BG |
| `leaf-50` | `#F0FAF4` | Background only | Page section alternates |

> ⚠️ **`leaf-light` is 3.8:1 — never use it for small body text. Use `leaf` or `leaf-dark`.**

### Semantic Colors

| Role | Default token | Hex | Pale | Notes |
|------|--------------|-----|------|-------|
| Farmer persona | `earth` | `#A0522D` (5.5:1) | `earth-pale #FDF1E8` | Farmer role chips, farm identity |
| Buyer / Info | `sky` | `#1A659E` (5.3:1) | `sky-pale #EBF4FB` | Buyer chips, info banners, phone CTA |
| Price / Deal | `gold` | `#F4A226` | `gold-pale #FFF8E7` | **BG only**; always pair with `gold-text #3B2A00` |
| Danger / Error | `danger` | `#B42318` (5.8:1) | `danger-pale #FEF3F2` | Delete actions, form errors |

> ⚠️ **Gold rule**: Never use `gold` as text color on white. Gold is a background. Pair with `text-gold-text` (`#3B2A00`).

### Neutrals (green-tinted)

| Token | Hex | Role |
|-------|-----|------|
| `canvas` | `#F7FAF5` | Page background |
| `surface` | `#FFFFFF` | Card/panel background |
| `bdr` | `#E2E8E0` | Borders and dividers |
| `ink` | `#1F2A24` | Primary heading and body text (15.8:1) |
| `inksoft` | `#3D4F44` | Secondary text (8.3:1) |
| `muted` | `#567361` | Placeholder text, metadata, icons (4.6:1) |

All three text tokens pass **4.5:1** on both `surface` (#FFF) and `canvas` (#F7FAF5).

---

## 3. Typography

### Fonts

| Family | Variable | Google Fonts | Use for |
|--------|----------|--------------|---------|
| **Poppins** | `font-display`, `font-sans` (universal) | `display=swap` | All headings, body, navigation, numbers, UI |

Fallback stack includes `"Noto Sans Sinhala"` and `"Noto Sans Tamil"` for localization.

### Scale

| Element | Size / Weight | Line height | Class |
|---------|--------------|-------------|-------|
| `h1` | `clamp(1.75rem, 4vw, 2.75rem)` / 700 | 1.2 | `font-display font-bold text-ink` |
| `h2` | `clamp(1.5rem, 3vw, 2rem)` / 700 | 1.25 | `font-display font-bold text-ink` |
| `h3` | `1.25rem` / 700 | 1.35 | `font-display font-bold text-ink` |
| `h4` | `1rem` / 600 | 1.4 | `font-sans font-semibold text-ink` |
| Body | `1rem` / 400 | 1.6 | `text-inksoft` |
| Small | `0.875rem` / 400 | 1.55 | `text-sm text-inksoft` |
| Micro / Meta | `0.75rem` / 500 | — | `text-xs text-muted` |
| Price | `1.375rem` / 700 | 1.2 | `.price-value` |

### Prices

Always format as: **`LKR 1,250.00`** using `tabular-nums` and `Poppins bold`.
```html
<span class="price-value">LKR 1,250.00</span>
<span class="price-unit">/ kg</span>
```

---

## 4. Spacing & Grid

- **Base unit:** 4px (Tailwind default)
- **Container:** `max-w-[80rem]` (1280px) with `px-4 sm:px-6 lg:px-8`
- **Use `.container-app`** class for all page-level containers
- **Section vertical spacing:** `.section-gap` (`py-10 sm:py-14 lg:py-20`)

### Breakpoints

| Name | Width | Usage |
|------|-------|-------|
| `sm` | 640px | Cards start to go multi-column |
| `md` | 768px | Desktop nav visible, 2-col grids |
| `lg` | 1024px | 3–4 col grids, expanded sidebar |
| `xl` | 1280px | Max container width |

---

## 5. Shape & Shadow

### Border Radii

| Token | CSS | Use for |
|-------|-----|---------|
| `rounded-lg` | 12px | **Buttons, inputs** |
| `rounded-xl` | 16px | **Cards, dropdowns** |
| `rounded-2xl` | 20px | **Modals, large panels** |
| `rounded-full` | 9999px | **Pills, avatars** |

### Shadow Levels (green-tinted)

```css
shadow-xs:  0 1px 2px rgba(27,67,50,0.06)           /* Nav, subtle chrome */
shadow-sm:  0 1px 3px rgba(27,67,50,0.08)           /* Default cards */
shadow-md:  0 4px 6px  rgba(27,67,50,0.08)          /* Hovered cards */
shadow-lg:  0 10px 15px rgba(27,67,50,0.08)         /* Dropdowns, popovers */
shadow-xl:  0 20px 25px rgba(27,67,50,0.08)         /* Modals */
shadow-2xl: 0 25px 50px rgba(27,67,50,0.14)         /* Hero elements */
```

---

## 6. Motion

- **Default transition:** `150ms ease-out` for hover/active states
- **Color/shadow transitions:** `200ms ease-out`
- **Scale on active:** `active:scale-[0.98]`
- **Respect reduced motion:** All animations disabled via `@media (prefers-reduced-motion: reduce)`

---

## 7. Buttons

```jinja2
{% from 'components/buttons.html' import button, link_button, icon_button %}
```

### Sizes

| Size | Height | Font size | Padding | Use for |
|------|--------|-----------|---------|---------|
| `sm` | 36px | 14px/600 | px-14px | Dense tables (always wrap in `btn-sm-touch` on mobile for 44px hit area) |
| `md` (default) | 44px | 15px/600 | px-20px | Standard interactive actions |
| `lg` | 52px | 16px/600 | px-28px | Hero CTAs, primary mobile form actions |

### Variants

| Variant | Appearance | When to use |
|---------|------------|-------------|
| `primary` | Solid `leaf` green | **Primary action** — one per section max |
| `secondary` | White + leaf border | Secondary alternative to primary |
| `soft` | Leaf-pale bg, leaf-dark text | Tertiary in card footers, filter pills |
| `ghost` | Transparent, leaf text | Icon-only actions, nav items |
| `danger` | Solid red | Destructive — delete, cancel |
| `danger-soft` | Red-pale bg, red text | Softer destructive for inline table rows |
| `accent` | Gold bg, dark text | **Price/deal CTAs only** — not general use |
| `link` | Text only, underlined | Inline text links |

### Usage Examples

```jinja2
{# Primary CTA #}
{{ button('Publish Listing', type='submit', variant='primary', size='lg', icon_name='check') }}

{# Secondary navigation #}
{{ link_button('Cancel', href=url_for('dashboard.index'), variant='secondary') }}

{# Danger action — requires confirm dialog #}
{{ button('Delete Listing', variant='danger', size='sm',
          data_attrs={'data-confirm': 'Delete this listing?', 'data-confirm-danger': ''}) }}

{# Icon-only button (always 44px touch target) #}
{{ icon_button('edit', 'Edit listing', variant='soft') }}
```

### Loading State (global)

Add `data-loading-text="Saving…"` to any `<form>` tag. On submit, the button auto-disables and shows a spinner.

```html
<form method="post" data-loading-text="Publishing…">
  ...
  <button type="submit" class="btn-primary btn-lg w-full">Publish</button>
</form>
```

---

## 8. Form Fields

```jinja2
{% from 'components/forms.html' import field, password_field, textarea_field,
        select_field, checkbox, radio_card, switch, file_field, quantity_stepper %}
```

### Rules

- Every input has `height: 48px` and `font-size: 16px` (prevents iOS auto-zoom)
- `label` is always rendered above the input with `for` matching `id`
- `required` fields show a red `*` and `(required)` for screen readers
- `optional` fields show an "Optional" hint when not required
- Error state: `border-danger` + icon + `aria-invalid="true"` + `aria-describedby`
- Focus state: `ring-2 ring-leaf` (always leaf, never gray)
- Password fields include show/hide toggle button

### Key Macros

| Macro | Use for |
|-------|---------|
| `field(...)` | All `<input>` types including prefix/suffix slots (`LKR`, `kg`) |
| `password_field(...)` | Password with show/hide toggle |
| `textarea_field(...)` | Multi-line text |
| `select_field(...)` | Dropdown with custom arrow |
| `checkbox(...)` | Single checkbox with 44px touch area |
| `radio_card(...)` | Role-picker style large radio pills |
| `switch(...)` | Toggle for binary settings |
| `file_field(...)` | Image upload with live preview |
| `quantity_stepper(...)` | `−` / value / `+` stepper (48px targets) |

---

## 9. Icons

```jinja2
{% from 'components/icons.html' import icon %}
{{ icon('leaf', size=20, cls='text-leaf') }}
```

- **Grid:** 24px viewBox, Lucide-style, 1.75px stroke-width, `currentColor`
- **`aria-hidden="true"`** on all icons (text labels provide meaning)
- **Never use emoji** as UI icons — always use `icon()` macro
- **45+ icons available:** see `templates/components/icons.html` for the full list

---

## 10. Badges

```jinja2
{% from 'components/badges.html' import badge, order_status_badge, crop_status_badge,
        role_badge, stock_badge, payment_badge, deal_badge %}
```

**All badges include an icon** (never color alone — WCAG 1.4.1).

| Group | Macro | Variants |
|-------|-------|----------|
| Order | `order_status_badge(status)` | pending, confirmed, delivered, cancelled, rejected |
| Crop | `crop_status_badge(status)` | growing, ready, harvested |
| Role | `role_badge(role)` | farmer, buyer, admin |
| Stock | `stock_badge(qty)` | in stock, low stock, out of stock |
| Payment | `payment_badge(status)` | paid, unpaid, failed, refunded |
| Deal | `deal_badge(text)` | gold with trending-down icon |
| Generic | `badge(text, variant)` | success, warning, danger, info, neutral, earth, sky, gold, purple |

Use `size='sm'` for compact badge contexts (table cells).

---

## 11. UI Components

```jinja2
{% from 'components/ui.html' import alert, empty_state, page_header, skeleton,
        avatar, price_breakdown, timeline, map_container, tabs, pagination, stat_card %}
```

| Component | Purpose |
|-----------|---------|
| `alert(message, variant, title, dismissible)` | Inline status banners (not flash) |
| `empty_state(title, description, icon_name, action_url, action_text)` | Zero-data views |
| `page_header(title, subtitle, breadcrumbs, back_url)` | Standardized page headers |
| `skeleton(width, height, rounded)` | Loading placeholder shimmer |
| `avatar(name, image_url, size)` | User avatar with initial fallback |
| `price_breakdown(rows, total_label, total_value)` | Label/value rows + total |
| `timeline(steps)` | Order/process progress stepper |
| `map_container(id, ratio)` | Styled frame for Google Maps |
| `tabs(items)` | Segmented control / tab navigation |
| `pagination(current, total, base_url)` | Accessible page controls |
| `stat_card(title, value, subtitle, icon_name, trend)` | Dashboard metric tile |

---

## 12. Component Catalogue

### Files in `templates/components/`

| File | Contents |
|------|----------|
| `icons.html` | `icon(name, size, cls)` — 45+ Lucide SVG icons |
| `buttons.html` | `button()`, `link_button()`, `icon_button()`, backward-compat aliases |
| `forms.html` | All form field macros + `quantity_stepper()` |
| `badges.html` | All badge macros |
| `ui.html` | `alert`, `empty_state`, `page_header`, `skeleton`, `avatar`, `price_breakdown`, `timeline`, `map_container`, `tabs`, `pagination`, `stat_card` |
| `cards.html` | `product_card()`, `stat_metric_card()`, `farmer_profile_card()` |

### Import Pattern

Always import **with context** so macros have access to `url_for`, `current_user`, etc.:

```jinja2
{% from 'components/icons.html'   import icon with context %}
{% from 'components/buttons.html' import button, link_button with context %}
{% from 'components/forms.html'   import field, select_field with context %}
{% from 'components/badges.html'  import order_status_badge, role_badge with context %}
{% from 'components/ui.html'      import empty_state, page_header with context %}
{% from 'components/cards.html'   import product_card with context %}
```

---

## 13. Do / Don't

### Colors

| ✅ Do | ❌ Don't |
|-------|----------|
| Use `text-leaf` or `text-leaf-dark` for body text | Use `text-leaf-light` for small body text (3.8:1) |
| Use `bg-gold` with `text-gold-text` | Use gold as text color on white |
| Use `text-muted` for placeholders and metadata | Use `text-gray-400` (fails AA at 2.28:1) |
| Use `text-danger-700` for form errors | Use `text-red-500` (3.99:1 — fails AA) |

### Buttons

| ✅ Do | ❌ Don't |
|-------|----------|
| One `btn-primary` per section | Two primary buttons side by side |
| Use `btn-accent` only for price CTAs | Use `btn-accent` for general actions |
| Use `data-confirm` for destructive actions | Use native `confirm()` |
| Add `data-loading-text` to forms | Let buttons be clicked multiple times |

### Icons

| ✅ Do | ❌ Don't |
|-------|----------|
| `{{ icon('leaf', size=20, cls='text-leaf') }}` | Use 🌾 🛒 📦 or any raw emoji as icons |
| `aria-hidden="true"` on decorative icons | Put meaningful text inside `<svg>` |

### Forms

| ✅ Do | ❌ Don't |
|-------|----------|
| Use `field()` macro with explicit label | Use `placeholder` as the only label |
| Show error icon + text message | Use color alone to indicate errors |
| `font-size: 16px` on inputs | Use smaller font (causes iOS zoom) |

---

## 14. Accessibility Rules

1. **Contrast:** All body text ≥ 4.5:1; large text and UI components ≥ 3:1
2. **Focus rings:** `focus-visible:ring-2 focus-visible:ring-leaf focus-visible:ring-offset-2` on all interactive elements
3. **Touch targets:** Minimum 44 × 44px (use `btn-sm-touch` wrapper for sm buttons on mobile)
4. **Labels:** Every `<input>`, `<select>`, `<textarea>` must have an associated `<label for="id">`
5. **Modals:** Use `role="dialog" aria-modal="true"` + focus trap + `Escape` to close + `body: overflow: hidden`
6. **Icons:** `aria-hidden="true"` on decorative SVGs; provide visible label or `aria-label` for icon-only buttons
7. **Buttons vs Links:** Use `<button>` for JS actions, `<a href>` for navigation
8. **Color-only:** Never use color as the sole indicator — always pair with icon, shape, or text
9. **Live regions:** Flash alerts use `aria-live="polite"`, errors use `role="alert"`
10. **Skip link:** Always present in `base.html` as the first focusable element

---

## 15. How to Add New Components

1. Create or edit a file in `templates/components/`.
2. Write a Jinja2 `{% macro %}` with:
   - Clear parameter names with defaults
   - `aria-*` attributes
   - Tokens from the design system (no hardcoded hex colors)
3. Add usage example to the **styleguide** at `/_styleguide` (template: `templates/styleguide/index.html`).
4. Document it in this file under Section 12.
5. Test at 375px and 1280px in the browser.

---

## Styleguide

Access the full interactive component catalogue at:

```
http://127.0.0.1:5000/_styleguide
```

> Only available when `FLASK_DEBUG=1` / `app.debug = True`.
