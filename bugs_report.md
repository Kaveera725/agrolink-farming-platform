# AgroLink — Code Audit & Bugs Report

**Auditor:** Senior QA Engineer & Code Auditor  
**Date:** October 2026  
**Workspace:** `AgroLink`  
**Application Type:** Flask (Python 3) & PostgreSQL Web Application  
**Audit Scope:** Full codebase scan, runtime route invocation, static analysis, security review, and UI inspection  

---

## Executive Summary

A comprehensive code audit and quality assurance evaluation was performed across the AgroLink platform. While the core CRUD operations for crop logging, produce listing, and order submission function cleanly under nominal conditions, the codebase harbors **critical runtime crash risks**, **major security vulnerabilities**, **logic errors in data aggregation**, and **architectural routing conflicts**.

### Summary by Severity

| Severity | Count | Summary Impact |
| :--- | :---: | :--- |
| **Critical** | 3 | Immediate server crashes (HTTP 500), complete vulnerability to CSRF forgery, and inventory overselling race conditions. |
| **High** | 5 | Shadowed API endpoints, broken market deal lookups, deceptive bidding workflows, open redirect vulnerabilities, and state corruption on order cancellation. |
| **Medium** | 5 | Insecure HTML DOM structure, image overwrites, missing input sanitization/validation, vulnerable dependencies, and predictable fallback secret keys. |
| **Low** | 5 | Dead code functions, missing asset directories, multi-worker startup collisions, circular import risks, and missing query pagination. |
| **Total** | **18** | **18 Distinct Issues Identified** |

---

## Detailed Bug Findings

### BUG-001: Runtime 500 Crash on Market Prices Page Due to Undefined `deal.product`
- **Severity:** Critical
- **Category:** Runtime error / UI
- **Location:** [`templates/prices/index.html:L34,40,48,56,136`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/prices/index.html#L34-58)
- **Problem:** The route controller returns a flat dictionary for each item in `best_deals`, but the template attempts to access attributes through a nested `product` object that does not exist.
- **Evidence:**
  In [`blueprints/prices/routes.py:L79-87`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/prices/routes.py#L79-87), items in `best_deals` are appended as:
  ```python
  best_deals.append({
      "product_name": product.name,
      "category": product.category,
      "seller": best_seller.farmer.name,
      "price": best_seller.price_per_kg,
      "market_price": market.selling_price,
      "saving": round(market.selling_price - best_seller.price_per_kg, 2),
      "product_id": best_seller.id
  })
  ```
  In [`templates/prices/index.html:L34,48,56`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/prices/index.html#L34-56):
  ```jinja2
  <h3 class="font-bold text-gray-800">{{ deal.product.name }}</h3>
  <p class="text-xl font-bold text-green-600">LKR {{ "{:,.0f}".format(deal.farmer_price) }}</p>
  <a href="{{ url_for('marketplace.product_detail', product_id=deal.product.id) }}">
  ```
  Runtime execution traceback when a product qualifies as a best deal:
  ```text
  File "templates/prices/index.html", line 34, in block 'content'
    <h3 class="font-bold text-gray-800">{{ deal.product.name }}</h3>
  jinja2.exceptions.UndefinedError: 'dict object' has no attribute 'product'
  ```
- **Impact:** As soon as any farmer lists a product with a matching market name whose price is below the market selling price (the exact core purpose of the Best Deals feature), visiting the Market Prices page throws an unhandled HTTP 500 error for all users.
- **Suggested fix:** Update [`templates/prices/index.html`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/prices/index.html) to reference `deal.product_name`, `deal.category`, `deal.price`, and `product_id=deal.product_id` instead of `deal.product.*`.

---

### BUG-002: Complete Absence of CSRF Protection Across All Forms
- **Severity:** Critical
- **Category:** Security
- **Location:** [`app.py`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/app.py) & all template forms in [`templates/`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/)
- **Problem:** Although `Flask-WTF` is listed in `requirements.txt`, `CSRFProtect` is never initialized in `app.py`, and no HTML `<form>` contains a CSRF token.
- **Evidence:**
  In [`app.py:L19-22`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/app.py#L19-22):
  ```python
  # Init extensions
  db.init_app(app)
  login_manager.init_app(app)
  # CSRFProtect is never imported or initialized
  ```
  Inspect [`templates/orders/place_order.html`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/orders/place_order.html), [`templates/auth/login.html`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/auth/login.html), [`templates/marketplace/product_form.html`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/marketplace/product_form.html): none contain `{{ csrf_token() }}` or `<input type="hidden" name="csrf_token">`.
- **Impact:** The application is entirely vulnerable to Cross-Site Request Forgery (CSRF). Any malicious website visited by an authenticated farmer or buyer can execute unauthorized actions (placing orders, cancelling orders, deleting crop records, or unlisting products) silently in the background.
- **Suggested fix:** Initialize `CSRFProtect(app)` in [`app.py`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/app.py) and embed `{{ csrf_token() }}` hidden inputs in all POST forms.

---

### BUG-003: Inventory Overselling Race Condition in Order Placement
- **Severity:** Critical
- **Category:** Logic / Database
- **Location:** [`blueprints/orders/routes.py:L27-57`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/orders/routes.py#L27-57)
- **Problem:** Produce stock validation and deduction occur in application memory without pessimistic database row locking or atomic SQL decrement statements.
- **Evidence:**
  ```python
  product = Product.query.filter_by(id=product_id, is_available=True).first_or_404()
  ...
  if quantity_kg > product.quantity_kg:
      flash(f'Only {product.quantity_kg} kg available.', 'error')
      return render_template('orders/place_order.html', product=product)
  ...
  product.quantity_kg -= quantity_kg
  if product.quantity_kg <= 0:
      product.is_available = False
  db.session.add(order)
  db.session.commit()
  ```
- **Impact:** When two buyers simultaneously place orders for remaining stock of the same produce item, both transactions read the original `product.quantity_kg`. If remaining stock is 10 kg and each orders 10 kg, both orders pass validation. The second commit either triggers a database check constraint failure (`CONSTRAINT products_quantity_kg_check CHECK (quantity_kg >= 0)`) resulting in an unhandled HTTP 500 error, or oversells the farmer's produce.
- **Suggested fix:** Apply pessimistic locking with `Product.query.filter_by(...).with_for_update().first_or_404()` inside an explicit database transaction block.

---

### BUG-004: Shadowed Root Route and Prefix Collision on `prices_bp`
- **Severity:** High
- **Category:** API / Architecture
- **Location:** [`blueprints/prices/routes.py:L5,45`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/prices/routes.py#L5), [`blueprints/main/routes.py:L3-7`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/main/routes.py#L3-7), [`app.py:L40-41`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/app.py#L40-41)
- **Problem:** `prices_bp` is registered with `url_prefix='/'` and defines route `/`. `main_bp` also defines route `/`. Because `prices_bp` is registered first, it shadows `main_bp.home`, rendering it unreachable. Furthermore, accessing `/prices/` returns an HTTP 404 error.
- **Evidence:**
  In `app.py`:
  ```python
  app.register_blueprint(prices_bp)  # Registered with url_prefix='/'
  app.register_blueprint(main_bp)    # Defines @main_bp.route('/')
  ```
  Runtime verification:
  - `GET /` $\rightarrow$ Resolves to `prices.index` (200 OK)
  - `GET /prices/` $\rightarrow$ Returns 404 NOT FOUND
  - `main.home` (`return "AgroLink API is running 🚀"`) $\rightarrow$ Unreachable dead endpoint
  - Contradicts [`README.md:L173-182`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/README.md#L173-182) which claims `/` is the landing page and `/prices/` is live prices.
- **Impact:** Missing home landing page, broken URL routing hierarchy, and dead route in `main_bp`.
- **Suggested fix:** Set `prices_bp = Blueprint('prices', __name__, url_prefix='/prices')` and dedicate `main_bp` to the homepage or landing page at `/`.

---

### BUG-005: Broken Lookup and Negative Savings in "Cheapest Sellers" Table
- **Severity:** High
- **Category:** Logic / UI
- **Location:** [`blueprints/prices/routes.py:L58-63`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/prices/routes.py#L58-63) & [`templates/prices/index.html:L172-215`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/prices/index.html#L172-215)
- **Problem:** `seller_map` groups products by lowercase *product name*, but the template iterates over it assuming the keys are *categories*, and attempts to look up `grouped[cat]` using the product name.
- **Evidence:**
  In `blueprints/prices/routes.py`:
  ```python
  seller_map = {}
  for product in products:
      key = product.name.lower()  # Grouped by product name (e.g. 'fresh ginger')
      if key not in seller_map:
          seller_map[key] = []
      seller_map[key].append(product)
  ```
  In `templates/prices/index.html`:
  ```jinja2
  {% for cat, products in seller_map.items() %}
    <h3 class="text-xl font-bold mb-3">{{ cat }}</h3> <!-- Renders product name instead of category -->
    {% set market = grouped[cat]|selectattr("crop_name", "equalto", p.name)|list %}
    <!-- grouped is keyed by Category ('Vegetables', 'Spices'), so grouped['fresh ginger'] is None -->
    {% set market_price = market[0].selling_price if market else 0 %}
    <td class="p-3 text-right">LKR {{ "{:,.0f}".format(market_price) }}</td> <!-- Prints LKR 0 -->
    <td class="p-3 text-right">-{{ "{:,.0f}".format(market_price - p.price_per_kg) }}</td> <!-- Prints --420 -->
  ```
  Rendered HTML output observed during audit:
  ```html
  <h3 class="text-xl font-bold mb-3">fresh ginger</h3>
  <td class="p-3 text-right">LKR 0</td>
  <td class="p-3 text-right text-red-500">--420</td>
  ```
- **Impact:** The "Cheapest Sellers" section displays product names as category headers, displays market price as `LKR 0`, and displays negative savings with double hyphens (e.g., `--420`), confusing buyers and displaying nonsensical financial figures.
- **Suggested fix:** Group `seller_map` by product category in `routes.py`, or modify the template to look up market benchmark rates directly from `market_dict.get(p.name.lower())`.

---

### BUG-006: Fake Bidding Engine Misleading to Buy-Now Order Form
- **Severity:** High
- **Category:** Logic / UI
- **Location:** [`blueprints/prices/routes.py:L113-139`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/prices/routes.py#L113-139) & [`templates/prices/bids.html:L97-100`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/prices/bids.html#L97-100)
- **Problem:** The screen promises a "Live Farmer Bidding Market", but the "Place Bid" button simply directs the user to fixed-price product purchasing.
- **Evidence:**
  In [`templates/prices/bids.html:L97-100`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/prices/bids.html#L97-100):
  ```html
  <!-- BID -->
  <a href="{{ url_for('orders.place_order', product_id=product.id) }}"
     class="bg-green-600 text-white px-3 py-2 rounded-lg text-sm">
    Place Bid
  </a>
  ```
  The database schema has no `bids` table, no counter-offer columns, and no auction model.
- **Impact:** Misleads users and academic evaluators into expecting an auction/bidding engine, whereas the functionality is merely a duplicated view of the marketplace sorted by price.
- **Suggested fix:** Either implement a true bidding system (bid placement, acceptance/rejection by farmer, bid expiration), or rebrand the screen accurately as "Price Comparison & Best Rates".

---

### BUG-007: Open Redirect Vulnerability via `next` Parameter on Login
- **Severity:** High
- **Category:** Security
- **Location:** [`blueprints/auth/routes.py:L56-58`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/auth/routes.py#L56-58)
- **Problem:** The login handler reads the `next` query parameter and issues a redirection without validating whether the URL belongs to the application domain.
- **Evidence:**
  ```python
  next_page = request.args.get('next')
  flash(f'Welcome back, {user.name}!', 'success')
  return redirect(next_page or url_for('dashboard.index'))
  ```
- **Impact:** Attackers can construct phishing URLs (e.g., `http://agrolink/auth/login?next=https://attacker-stealer.com`) that redirect legitimate users to malicious external domains immediately upon login.
- **Suggested fix:** Use `urllib.parse.urlsplit` to verify that `next_page` has no netloc (relative path only), e.g., `if next_page and not urlsplit(next_page).netloc: return redirect(next_page)`.

---

### BUG-008: Cancelled Orders Re-List Farmer-Deleted Products to Marketplace
- **Severity:** High
- **Category:** Logic / Database
- **Location:** [`blueprints/orders/routes.py:L99-102`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/orders/routes.py#L99-102)
- **Problem:** When a buyer cancels an order, the code automatically resets `order.product.is_available = True`, even if the farmer had previously unlisted or deleted the product.
- **Evidence:**
  ```python
  order.status = 'cancelled'
  order.product.quantity_kg += order.quantity_kg
  order.product.is_available = True
  db.session.commit()
  ```
  Compare with [`blueprints/marketplace/routes.py:L116-118`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/marketplace/routes.py#L116-118) where deletion is soft:
  ```python
  product.is_available = False
  db.session.commit()
  ```
- **Impact:** If a farmer withdraws a product from the marketplace and a buyer subsequently cancels a prior order, the cancelled product is unexpectedly published back onto the active public marketplace against the farmer's will.
- **Suggested fix:** Introduce an explicit `is_deleted` column on `Product` to distinguish between products that are out of stock (`quantity_kg == 0`) and products permanently unlisted by the farmer.

---

### BUG-009: Invalid HTML Structure with Nested Anchor Tags in Marketplace Cards
- **Severity:** Medium
- **Category:** UI / Frontend
- **Location:** [`templates/marketplace/index.html:L82-153`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/marketplace/index.html#L82-153)
- **Problem:** The entire product card is wrapped inside an `<a>` element, while containing nested `<a>` elements for WhatsApp and phone dialing.
- **Evidence:**
  ```html
  <a href="{{ url_for('marketplace.product_detail', product_id=product.id) }}"
     class="bg-white rounded-xl shadow hover:shadow-lg transition block overflow-hidden">
     ...
     <a href="https://wa.me/{{ product.farmer.phone }}" class="block ...">💬 WhatsApp Farmer</a>
     <a href="tel:{{ product.farmer.phone }}" class="block ...">📞 Call Farmer</a>
     ...
  </a>
  ```
- **Impact:** Direct violation of W3C HTML5 specification (anchors cannot contain interactive elements or descendant anchors). Modern browsers handle this by prematurely closing the outer tag or swallowing click events, leading to unpredictable navigation and broken button behavior.
- **Suggested fix:** Change the product card wrapper from `<a>` to a `<div>`, and place a distinct "View Details" link alongside the WhatsApp and Call buttons.

---

### BUG-010: Product Editing Overwrites Custom Images with Static Unsplash Default
- **Severity:** Medium
- **Category:** Logic
- **Location:** [`blueprints/marketplace/routes.py:L106`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/marketplace/routes.py#L106)
- **Problem:** Updating a product unconditionally overwrites its `image_url` with the default category stock image from `PRODUCT_IMAGES`.
- **Evidence:**
  ```python
  product.image_url = PRODUCT_IMAGES.get(product.category, PRODUCT_IMAGES['Other'])
  db.session.commit()
  ```
- **Impact:** Any custom image URL assigned to a product (either manually or through future file uploads) is wiped out whenever the farmer edits the title, description, quantity, or price.
- **Suggested fix:** Only assign a default image if `product.image_url` is empty or if the category has changed.

---

### BUG-011: Zero Server-Side Password Complexity and Email Format Validation
- **Severity:** Medium
- **Category:** Security / Auth
- **Location:** [`blueprints/auth/routes.py:L16-34`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/auth/routes.py#L16-34)
- **Problem:** Backend registration accepts any non-empty password without length or complexity checks, and does not validate email address syntax.
- **Evidence:**
  ```python
  if not name or not email or not password:
      flash('All fields are required.', 'error')
      return render_template('auth/register.html')
  if password != confirm:
      flash('Passwords do not match.', 'error')
      return render_template('auth/register.html')
  ```
  No validation occurs for email formatting or minimum password length. In the live database, users with emails `shoun@sdnf` and `shoun@fas` were registered without issue.
- **Impact:** Users can register with single-character passwords (bypassing HTML5 `minlength="6"` via direct POST) or malformed emails, causing communication failures and account security degradation.
- **Suggested fix:** Utilize `email-validator` (already present in `requirements.txt`) and enforce a minimum 8-character password constraint in Python.

---

### BUG-012: Known Security Vulnerabilities in Outdated Werkzeug Dependency
- **Severity:** Medium
- **Category:** Dependency / Security
- **Location:** [`requirements.txt:L9`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/requirements.txt#L9)
- **Problem:** Project pins `Werkzeug==3.0.1`, which is subject to published security advisories.
- **Evidence:**
  - **CVE-2024-34069:** High severity vulnerability in Werkzeug's multipart parser leading to unlimited CPU/memory consumption (DoS).
  - **CVE-2024-49766 / CVE-2024-49767:** Windows UNC path handling vulnerabilities in safe_join.
- **Impact:** Exploitation can crash the Flask backend service or cause path traversal issues on Windows environments.
- **Suggested fix:** Update `Werkzeug>=3.0.6` in [`requirements.txt`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/requirements.txt).

---

### BUG-013: Hardcoded Weak Secret Key Fallback in Application Factory
- **Severity:** Medium
- **Category:** Security
- **Location:** [`app.py:L12`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/app.py#L12) & [`.env.example:L3`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/.env.example#L3)
- **Problem:** If the `SECRET_KEY` environment variable is omitted or misconfigured, the application silently falls back to a trivial hardcoded string.
- **Evidence:**
  ```python
  app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-fallback-key')
  ```
- **Impact:** In production deployments where `.env` is missing or improperly mapped, session cookies can be tampered with or forged using the known fallback key.
- **Suggested fix:** Raise a runtime configuration error if `SECRET_KEY` is not explicitly provided outside of development mode.

---

### BUG-014: Uncalled Dead Code Function `get_price_suggestion`
- **Severity:** Low
- **Category:** Logic / Dead Code
- **Location:** [`blueprints/prices/routes.py:L99-111`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/prices/routes.py#L99-111)
- **Problem:** A function calculating recommended listing prices is defined in the prices blueprint but is never imported, invoked, or exposed.
- **Evidence:**
  ```python
  def get_price_suggestion(product_name):
      market = MarketPrice.query.filter_by(crop_name=product_name).first()
      if not market:
          return None
      suggested = round((market.buying_price + market.selling_price) / 2, 2)
      return {
          "min_price": market.buying_price,
          "max_price": market.selling_price,
          "suggested_price": suggested
      }
  ```
- **Impact:** Clutters route files with unused code; farmers receive no automated price suggestions when creating new produce listings.
- **Suggested fix:** Connect this function to an AJAX endpoint or pass suggested pricing into [`templates/marketplace/product_form.html`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/templates/marketplace/product_form.html) to assist farmers when setting prices.

---

### BUG-015: Missing `static/` Directory Despite Route Registration
- **Severity:** Low
- **Category:** Runtime / Static Assets
- **Location:** Project root / `app.py`
- **Problem:** Flask automatically configures a static asset endpoint (`/static/<filename>`), but no `static/` directory exists in the workspace.
- **Evidence:**
  `app.url_map` displays `static -> /static/<path:filename>`, but listing the workspace root demonstrates no `static/` folder exists.
- **Impact:** Any future references to local favicon (`favicon.ico`), local CSS, or JavaScript assets will trigger HTTP 404 errors.
- **Suggested fix:** Create a standard `static/` folder with subdirectories for `css/`, `js/`, and `images/`.

---

### BUG-016: Startup Race Condition Running `db.create_all()` in WSGI Environments
- **Severity:** Low
- **Category:** Database / Startup
- **Location:** [`app.py:L44-48`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/app.py#L44-48)
- **Problem:** `db.create_all()` and price seeding are executed inside `create_app()` without checking whether tables or migrations already exist.
- **Evidence:**
  ```python
  with app.app_context():
      db.create_all()
      from blueprints.prices.routes import seed_market_prices
      seed_market_prices()
  ```
- **Impact:** Running under multi-worker WSGI servers (Gunicorn, uWSGI) causes multiple workers to execute DDL statements and seed checks simultaneously upon server restart, risking deadlock or database constraint collisions.
- **Suggested fix:** Move schema creation and seeding into a dedicated CLI command (`flask init-db` or `flask seed`).

---

### BUG-017: Circular Import Design Pattern in `models.py`
- **Severity:** Low
- **Category:** Architecture
- **Location:** [`models.py:L1`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/models.py#L1)
- **Problem:** `models.py` imports `db` and `login_manager` from `app.py` instead of the decoupled `extensions.py` module.
- **Evidence:**
  In [`models.py:L1`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/models.py#L1):
  ```python
  from app import db, login_manager
  ```
  In [`extensions.py`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/extensions.py):
  ```python
  from flask_sqlalchemy import SQLAlchemy
  from flask_login import LoginManager
  db = SQLAlchemy()
  login_manager = LoginManager()
  ```
- **Impact:** Fragile import structure that breaks unit tests, standalone scripts, or Alembic migrations when importing `models.py` without invoking `create_app()`.
- **Suggested fix:** Update [`models.py:L1`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/models.py#L1) to `from extensions import db, login_manager`.

---

### BUG-018: Complete Lack of Query Pagination Leading to Unbounded Memory Usage
- **Severity:** Low
- **Category:** Performance / Database
- **Location:** [`blueprints/marketplace/routes.py:L35`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/marketplace/routes.py#L35), [`blueprints/dashboard/routes.py:L40`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/dashboard/routes.py#L40), [`blueprints/orders/routes.py:L13`](file:///c:/Users/anush/OneDrive/Desktop/Projects%20for%20money/AgroLink/blueprints/orders/routes.py#L13)
- **Problem:** Database queries for products, crops, and orders fetch all rows unconditionally with `.all()`.
- **Evidence:**
  `products = query.order_by(Product.price_per_kg.asc()).all()`
  `crops = Crop.query.filter_by(farmer_id=current_user.id).order_by(Crop.created_at.desc()).all()`
- **Impact:** As data volume scales beyond thousands of records, page load times degrade significantly and server memory consumption spikes.
- **Suggested fix:** Use Flask-SQLAlchemy's built-in `.paginate(page=page, per_page=20)` method.

---

## Strategic Remediation Plan

### 1. Top 5 Blockers (Must Fix First)
1. **BUG-001 (Market Prices 500 Crash):** Fix the dictionary key mismatch in `templates/prices/index.html` to prevent server crashes when qualifying deals exist.
2. **BUG-002 (Missing CSRF Protection):** Initialize `Flask-WTF` CSRF protection across the app to secure all form submissions against malicious cross-site forgery.
3. **BUG-004 (Shadowed Route Collision):** Relocate `prices_bp` to `url_prefix='/prices'` and restore the main application homepage at `/`.
4. **BUG-003 (Order Inventory Race Condition):** Implement database transaction row locking when placing orders to prevent produce overselling and check-constraint crashes.
5. **BUG-005 (Cheapest Sellers Grouping & Calculations):** Correct the product vs. category grouping logic to eliminate `LKR 0` and `--420` financial display errors.

---

### 2. Recommended Fix Order

```
┌────────────────────────────────────────────────────────────────────────┐
│ Phase 1: Crash & Security Hardening (P0)                               │
│ 1. Fix BUG-001: Resolve dict key mismatch in prices/index.html         │
│ 2. Fix BUG-002: Enable Flask-WTF CSRFProtect and add form tokens       │
│ 3. Fix BUG-004: Remap prices_bp to /prices and fix root route conflict │
│ 4. Fix BUG-007: Sanitize next redirect parameter in auth routes        │
├────────────────────────────────────────────────────────────────────────┤
│ Phase 2: Transactional & Business Logic Integrity (P1)                 │
│ 5. Fix BUG-003: Add pessimistic row locking on order stock decrement   │
│ 6. Fix BUG-005: Correct grouping and savings in Cheapest Sellers table │
│ 7. Fix BUG-008: Separate out-of-stock from soft-deleted products       │
│ 8. Fix BUG-010: Retain custom image URLs during product edits          │
├────────────────────────────────────────────────────────────────────────┤
│ Phase 3: Validation, Frontend & Cleanup (P2)                           │
│ 9. Fix BUG-009: Flatten nested <a> tags in marketplace cards           │
│ 10. Fix BUG-011: Enforce server-side password & email validation       │
│ 11. Fix BUG-006: Rebrand or implement true bidding functionality       │
│ 12. Fix BUG-017 & BUG-016: Clean model imports & decouple DB seeding   │
│ 13. Fix BUG-012: Upgrade Werkzeug dependency                           │
└────────────────────────────────────────────────────────────────────────┘
```

---

### 3. Estimated Effort by Issue Group

| Issue Group | Associated Bugs | Estimated Effort | Description |
| :--- | :--- | :---: | :--- |
| **Crash & Blueprint Routing** | BUG-001, BUG-004, BUG-005 | **Small** (~1–2 hours) | Template key corrections, blueprint prefix realignment, and grouping dict fixes. |
| **Security & Authentication** | BUG-002, BUG-007, BUG-011, BUG-012, BUG-013 | **Medium** (~2–4 hours) | CSRF initialization across 7 templates, input validation, redirect checks, and dependency bumps. |
| **Transaction & Order Logic** | BUG-003, BUG-008, BUG-010 | **Medium** (~2–3 hours) | Pessimistic locking (`with_for_update`), transaction management, and soft-delete state modeling. |
| **UI Semantics & Bidding** | BUG-006, BUG-009, BUG-014, BUG-015, BUG-018 | **Medium** (~3–5 hours) | DOM restructuring of product cards, bidding engine redesign or rebranding, and query pagination. |
| **Total Estimated Effort** | All 18 Bugs | **~8–14 hours** | Comprehensive stabilization for production readiness. |
