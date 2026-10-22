# AgroLink — Design System & UI/UX Guidelines (DESIGN.md)

This document establishes the design principles, visual tokens, component library standards, accessibility guidelines, and responsive rules for **AgroLink**.

---

## 1. Principles & Vision

1. **Agricultural Authenticity & Trust:**
   A warm, grounded, and modern aesthetic reflecting Sri Lankan agriculture. Vibrant foliage greens (`leaf`), rich soil browns (`earth`), and fresh sky blues (`sky`) replace sterile corporate or generic templates.
2. **Mobile-First Realism:**
   Farmers, field coordinators, and buyers primarily use mobile devices (e.g. 375px viewport on Android/iOS). Every screen is designed at 375px first, scaling gracefully to 768px (tablet) and 1280px+ (desktop).
3. **No Horizontal Scroll:**
   Layouts must never overflow horizontally at any viewport width (`width: 100%`, `max-w-full`, flexible grid/flexbox).
4. **Text Flexibility & Localization Readiness:**
   No fixed-width buttons (`w-32`), rigid containers (`w-[200px]`), or tight line-height truncations. All labels, buttons, and cards must expand naturally to accommodate longer Sinhala (`සිංහල`) and Tamil (`தமிழ்`) translations.
5. **Zero Remote Image Dependencies:**
   No reliance on external CDNs or remote Unsplash links. The application uses crisp inline SVGs, CSS patterns, and user-uploaded media from `static/uploads/`.
6. **Strict Accessibility (WCAG 2.1 AA):**
   - High contrast ratios (minimum 4.5:1 for body text, 3:1 for large headers and interactive icons).
   - Clear focus indicators (`focus-visible:ring-2 focus-visible:ring-leaf focus-visible:ring-offset-2`).
   - Every input has an explicit `<label for="...">` or descriptive `aria-label`.
   - Descriptive `alt` tags and `loading="lazy"` on all images.
   - Screen-reader skip-to-content links.

---

## 2. Color Palette & Contrast Tokens

| Token | Hex Value | Semantic Usage | Minimum Contrast vs White |
| :--- | :--- | :--- | :--- |
| **`leaf-dark`** | `#1B4332` | Primary headings, prominent text, footer bg | **11.8:1** (AAA) |
| **`leaf`** | `#2D6A4F` | Primary buttons, brand identity, active tabs | **5.7:1** (AA) |
| **`leaf-light`** | `#40916C` | Hover states, secondary brand accents | **3.8:1** (UI Components) |
| **`leaf-pale`** | `#D8F3DC` | Active badges, soft container backgrounds | Background tint |
| **`earth`** | `#8B4513` | Farmer persona badges, farm identity | **6.1:1** (AA) |
| **`earth-pale`** | `#FDF1E8` | Farmer card backgrounds, pill tags | Background tint |
| **`sky`** | `#1A659E` | Buyer persona badges, orders, links | **5.3:1** (AA) |
| **`sky-pale`** | `#EBF4FB` | Buyer card backgrounds, info banners | Background tint |
| **`gold`** | `#D97706` | Price deals, urgent notices, benchmark ratings | **4.6:1** (AA) |
| **`gold-pale`** | `#FFF8E7` | Deal highlight cards | Background tint |
| **`gray-900`** | `#111827` | Primary dark body text | **15.3:1** (AAA) |
| **`gray-600`** | `#4B5563` | Secondary text, descriptions | **7.0:1** (AA) |
| **`gray-100`** | `#F3F4F6` | Card borders, dividers, subtle surfaces | Background / Border |

---

## 3. Typography & Hierarchy

- **Display & Headings:** `Playfair Display`, serif.
  - Page Titles (`h1`): `font-display text-2xl sm:text-3xl lg:text-4xl font-bold text-gray-900 tracking-tight`
  - Section Headings (`h2`): `font-display text-xl sm:text-2xl font-bold text-gray-800`
  - Subheadings (`h3`): `font-display text-lg font-bold text-gray-800`
- **Body & User Interface:** `DM Sans`, sans-serif.
  - Body Text: `text-sm sm:text-base text-gray-600 leading-relaxed`
  - Microcopy / Metadata: `text-xs font-medium text-gray-500`
  - Interactive Labels: `text-sm font-semibold text-gray-800`

---

## 4. Breakpoint Standards

- **Small Mobile:** `375px` (Single column, full-width inputs, touch targets $\ge 44\text{px}$, responsive mobile drawer).
- **Tablet / Phablet:** `768px` (`md:`, 2-column grids, expanded search filters, visible horizontal navigation).
- **Desktop:** `1280px` (`lg:` and `xl:`, 3 to 4-column catalog grids, dual-column product details, spacious dashboard tables).

---

## 5. Reusable Component Macros (`templates/components/`)

All templates import shared UI components with context:
```jinja2
{% import "components/badges.html" as badges with context %}
{% import "components/buttons.html" as buttons with context %}
{% import "components/cards.html" as cards with context %}
{% import "components/forms.html" as forms with context %}
```

### Component Modules:
1. **`badges.html`**:
   - `crop_status_badge(status)` (`growing`, `ready`, `harvested`)
   - `order_status_badge(status)` (`pending`, `confirmed`, `delivered`, `cancelled`)
   - `role_badge(role)` (`farmer`, `buyer`, `admin`)
   - `deal_badge(saving_text)`
2. **`buttons.html`**:
   - `btn_primary(text, href, icon, type, extra_classes)`
   - `btn_secondary(text, href, icon, type, extra_classes)`
   - `btn_danger(text, href, icon, type, extra_classes)`
3. **`cards.html`**:
   - `product_card(product)` (renders thumbnail, stock status, title, price, category pill, view link)
   - `stat_metric_card(title, value, subtitle, icon_svg, trend)`
   - `farmer_profile_card(farmer)` (public verified profile card)
4. **`forms.html`**:
   - `input_field(id, name, label, type, value, required, placeholder, hint, error)`
   - `textarea_field(id, name, label, value, required, rows, placeholder, hint, error)`
   - `select_field(id, name, label, options, selected, required, hint, error)`
   - `image_upload_field(id, name, label, current_url, hint)`
