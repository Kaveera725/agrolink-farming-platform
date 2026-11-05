# AgroLink Demonstration & Walkthrough Guide

Step-by-step instructions for demonstrating the AgroLink Agricultural Trading Platform, from initial seeding to complete administrative governance.

---

## 1. Quick Start & Environment Verification

### Prerequisites
- Python 3.10+ activated in virtual environment (`.\venv\Scripts\Activate.ps1`)
- PostgreSQL database service active (`agrolink_db`)
- All database migrations applied:
  ```powershell
  flask db upgrade
  ```

### Generate Isolated Demo Data
Populate realistic demo records (~300 users, ~200 listings, ~800 orders across Sri Lankan districts):
```powershell
flask seed-admin-demo
```
*(All demo records are tagged with `@demo.agrolink.lk` and can be reset at any time with `flask seed-admin-demo --clear`).*

### Provision Administrator
Provision an administrator account interactively:
```powershell
flask create-admin
```
*(Enter email, name, and a password with 10+ characters adhering to the enterprise password policy).*

---

## 2. Farmer & Buyer User Journeys

### Buyer Journey:
1. **Browse Produce (`/marketplace/`):** Filter by category (e.g. Vegetables, Grains) and district.
2. **Review Reference Rates (`/prices/`):** Verify Colombo wholesale and retail benchmark prices.
3. **Place Order (`/orders/place/<id>`):**
   - Select **Home Delivery** or **Farm Pickup**.
   - For delivery, enter an address in Sri Lanka. The platform queries Google Routes API to compute road driving distance and distance-tiered delivery fees.
4. **Inspect Order Status (`/orders/`):** Real-time fulfillment progress (`pending` $\rightarrow$ `confirmed` $\rightarrow$ `delivered`).
5. **Direct Farmer Contact:** Click WhatsApp links to initiate direct end-to-end communication via `wa.me`.

### Farmer Journey:
1. **Crop Management (`/dashboard/crops`):** Record field cultivation cycles, planting dates, and harvest forecasts.
2. **Publish Produce Listing (`/marketplace/new`):** Set price per kilogram, available stock, and upload produce photography.
3. **Apply for Verification (`/profile`):** Submit farm name and coordinates to request verified accreditation.
4. **Fulfill Orders (`/dashboard/`):** Confirm orders, mark deliveries, or cancel invalid requests with automated inventory restoration.

---

## 3. The Administrative Control Center (`/admin/`)

Sign in with your administrator account and navigate to:
```text
http://127.0.0.1:5000/admin/
```

### 3.1 Executive Dashboard
- **Date Range Filters:** Toggle between Last 7, 30, 90 days, or custom ranges; parameters persist in URL query strings.
- **KPI Metrics:** Total Users, Active Listings, Order Value (excluding cancelled/rejected), Completed Value (delivered orders), and AOV.
- **Chart Visualizations:** Orders per day, revenue per day, fulfillment split (Delivery vs Pickup), and orders by status.
- **Needs Attention Panel:** One-click links for pending verifications, open listing reports, stale prices, and low-stock listings.

### 3.2 Farmers Map Intelligence (`/admin/map`)
- Interactive Google Maps interface plotting registered farmers across Sri Lanka.
- Filter pins by district, verified status, or active listings.
- Click pins to inspect farm names, active listings, and direct user profile links.
- Graceful table fallback for environments without Google Maps browser keys.

### 3.3 User Management & Operational Safeguards (`/admin/users`)
- Search users by name or email; filter by role (`farmer`, `buyer`, `admin`) and status (`active`, `deactivated`).
- **Self-Protection Guard:** Admins cannot deactivate or demote their own account.
- **Last Admin Guard:** System blocks deactivation or demotion of the final active admin.
- **Password Reset Flow:** Resetting a user's password sets `must_change_password = True` and increments `session_version`, invalidating existing sessions.

### 3.4 Farmer Verification Queue (`/admin/verifications`)
- Inspect farmer applications, bio, location coordinates, and historical performance.
- Approve to grant the green **✓ Verified Farmer** seal or reject with a descriptive explanation.
- Verification can be revoked at any time from user detail screens.

### 3.5 Content Moderation & Listing Reports (`/admin/listing-reports`)
- Review buyer dispute reports for misleading prices, fake photos, or prohibited items.
- Administrators can hide suspicious listings from the public marketplace or resolve reports with administrative notes.

### 3.6 Benchmark Prices, Typo Guard & CSV Import (`/admin/prices`)
- Manage Colombo benchmark commodity buying and selling prices.
- **Price History:** View Chart.js price movement trends over the last 90 days.
- **Typo Guard:** Price changes exceeding ±30% display a warning requiring explicit checkbox confirmation.
- **Bulk CSV Import (`/admin/prices/import`):**
  - Download standard CSV template.
  - Upload CSV with formula injection sanitization.
  - Interactive dry-run preview marking records as New, Update, Unchanged, or Invalid.
  - Atomic commit writing individual history rows (`source='import'`).

### 3.7 Queryable Reports Hub (`/admin/reports`)
- Query 6 dedicated report types: Sales Summary (by day, category, farmer), Users, Orders, Produce Listings, Market Prices with History, and Audit Log.
- Export streaming CSVs with UTF-8 BOM (`\xef\xbb\xbf`) for Microsoft Excel compatibility.
- Open print-friendly browser views formatted with report title, date range, generator ID, and timestamp.

### 3.8 Personal Data Tools — Sri Lanka PDPA 2022 (`/admin/data-requests`)
- **Data Export (Portability):** Generates a clean, portable JSON archive of the user's account, listings, and orders (excluding password hashes and secrets).
- **Account Anonymization (Right to Erasure):**
  - Blocked if the user has active orders in progress.
  - Requires typing the user's exact email address to confirm plus an administrative reason.
  - Overwrites all personal identifiers with neutral placeholders (`Deleted user #<id>`, `deleted_user<id>@deleted.agrolink.lk`).
  - Deletes profile photos from disk, deactivates account, and retains order financials anonymously for accounting compliance.
- **Public Privacy Notice (`/privacy`):** Transparent explanation of data rights under Sri Lanka PDPA 2022.

### 3.9 System Status & Integration Diagnostics (`/admin/system`)
- **Database Connectivity:** Direct PostgreSQL ping and version verification.
- **Schema Migrations:** Verifies active database revision matches repository head (`0014_data_requests`).
- **Environment Telemetry:** Alerts if debug mode is active in production.
- **Upload Storage Health:** Confirms `/static/uploads` write permissions and computes disk utilization in MB.
- **Failed Login Telemetry:** Reports failed login count over the last 24 hours.
- **Integration Diagnostics:** Reports configuration status (`Present` / `Missing`) for Google Maps keys and external providers without leaking secret values.
- **Routes API Probe:** Rate-limited probe (max 5/hour) calculating a live Colombo Fort to Kandy Clock Tower driving route and reporting roundtrip latency in ms.

### 3.10 Immutable Activity Audit Log (`/admin/activity`)
- Every administrative action is logged with operator ID, action type, target entity, and timestamp.
- Backed by PostgreSQL append-only database triggers (`prevent_admin_audit_log_tamper`) preventing modification or deletion of audit entries.

