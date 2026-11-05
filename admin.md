# AgroLink Administration & Platform Governance Guide

Comprehensive documentation for platform operators, system administrators, and security auditors of the AgroLink Agricultural Trading Platform.

---

## 1. Overview & Account Provisioning

Administrative access is restricted to authenticated users assigned the `admin` role. The administrative portal operates under a strict principle of least privilege, complete auditability, and compliance with the **Sri Lanka Personal Data Protection Act (PDPA No. 9 of 2022)** and core **GDPR** data governance standards.

### Creating an Administrator
To provision a new administrator account, execute the interactive CLI command within your virtual environment:

```powershell
.\venv\Scripts\python.exe -m flask create-admin
```

The command will interactively prompt for:
- **Admin Email:** Normalized and validated against email delivery standards.
- **Admin Name:** Full legal or operational name.
- **WhatsApp / Phone:** Optional Sri Lankan contact number.
- **Admin Password:** Masked prompt enforcing the enterprise password policy (minimum 10 characters, upper/lower/digit/special, rejecting common passwords or email/name matching).

> **Security Mandate:** Administrator credentials are never logged, stored in source code, or committed to documentation in plaintext.

### Accessing the Control Center
Once authenticated, navigate to:
```text
http://127.0.0.1:5000/admin/
```
*(A purple **ADMIN** indicator appears in the global navigation bar exclusively for accounts with the `admin` role).*

---

## 2. Navigation & Functional Organization

The admin navigation is structured into eight operational domains with real-time badge counts:

1. **Overview:**
   - **Dashboard:** Executive KPI cards, date range filtering, revenue trends, Chart.js visualizations, and the "Needs Attention" triage panel.
   - **Farmers Map (`/admin/map`):** Interactive Google Maps geographic intelligence plotting verified farm clusters, district coverage, active produce availability, and fallback data tables.
2. **People:**
   - **Users Directory (`/admin/users`):** Full account lifecycle management, role filtering, deactivation, password resets, and admin notes.
   - **Verification (`/admin/verifications`):** Farmer accreditation queue reviewing land coordinates and granting verified badges.
   - **Data Requests (`/admin/data-requests`):** Sri Lanka PDPA 2022 compliance queue for portable JSON data export and account anonymization.
3. **Marketplace:**
   - **Produce Listings (`/admin/listings`):** Real-time inventory surveillance, moderation controls, and hide/restore capabilities.
   - **Listing Reports (`/admin/listing-reports`):** Buyer report queue handling dispute resolution for misleading pricing, prohibited items, or counterfeit media.
   - **Crops & Harvests (`/admin/crops`):** Read-only visibility into farmer field production cycles, harvest schedules, and upcoming agricultural supply.
4. **Orders:**
   - **Orders Registry (`/admin/orders`):** Order inspection, fulfillment tracking (Pickup vs. Door-to-Door Delivery), delivery pricing snapshots, and administrative dispute cancellation.
5. **Pricing:**
   - **Market Prices (`/admin/prices`):** Colombo benchmark wholesale and retail commodity pricing, historical change tracking, and stale price alerts.
   - **Bulk CSV Import (`/admin/prices/import`):** Dry-run validated, formula-injection-safe bulk price updating with 30% typo guard confirmation.
6. **Reports:**
   - **Reports & Analytics (`/admin/reports`):** Queryable reporting hub (Sales, Users, Orders, Produce, Benchmark Prices, Audit Trail) with streaming CSV exports (UTF-8 BOM) and print-friendly browser views.
7. **Settings:**
   - **Platform Settings (`/admin/settings`):** Live configuration of delivery base fees, per-km rates, delivery radii, low-stock thresholds, and stale-price intervals.
8. **System:**
   - **Status & Telemetry (`/admin/system`):** Database connectivity, schema migration verification, upload directory health, failed login counts, and Google Routes API live probes.
   - **Activity Audit Log (`/admin/activity`):** Non-tamperable append-only audit trail logging every administrative state change.

*(Reserved sidebar slots for Payments and WhatsApp logs remain hidden until their respective subsystems are activated).*

---

## 3. Operational Safeguards & Security Hardening

The administrative layer enforces multi-layered defensive constraints:

- **Strict Access Matrix:** Every admin route is guarded by `@roles_required('admin')`. Unauthenticated visitors are redirected to `/auth/login`, while buyers or farmers attempting to access administrative endpoints receive an immediate `403 Forbidden` challenge.
- **CSRF Enforcement:** All administrative POST actions require valid CSRF tokens. Submissions missing tokens are rejected with `400 Bad Request`.
- **Last Admin Protection:** The system prevents the deactivation, role demotion, or deletion of the last remaining active administrator to prevent operational lockout.
- **Self-Protection Guard:** An administrator cannot deactivate or demote their own account.
- **Forced Password Changes:** When an administrator issues a temporary password reset, `must_change_password` is set to `True`. The target user is restricted and redirected to change their password upon their next login.
- **Session Version Revocation:** Modifying critical user state or password resets increments `user.session_version`, instantly invalidating all existing browser sessions across other devices.
- **Zero Secret Leakage:** Telemetry screens, logs, and export routines never return connection strings, password hashes, or raw Google Maps / external service API keys.

---

## 4. Moderation & Governance Workflows

### Farmer Verification Queue (`/admin/verifications`)
Farmers can apply for verified accreditation from their profile. Administrators review:
- Registered farm/estate name and farmer bio.
- Geolocation coordinates and district positioning within Sri Lanka.
- Historical active listing count and fulfillment track record.
- **Outcomes:** Approval stamps `is_verified = True`, sets `verified_at` and `verified_by`, and activates the green verified seal across marketplace listings. Rejection requires a descriptive explanation. Verification can be revoked at any time.

### Listing Reports & Content Moderation (`/admin/listing-reports`)
Buyers can report suspicious or invalid listings.
- Reports record the specific infraction (`misleading_price`, `wrong_or_fake_photo`, `prohibited_item`, `spam`, `other`) and buyer notes.
- Administrators can inspect the reported listing, communicate with the farmer, hide the listing from public view, or dismiss unfounded reports with resolution notes.

---

## 5. Platform Settings & Pricing Intelligence

Configured in `services/settings.py` and editable via `/admin/settings`:

| Key | Default | Validation Range | Business Purpose |
|---|---|---|---|
| `delivery_base_fee` | 350.00 LKR | 0 – 100,000 | Baseline fixed fee for delivery within base radius |
| `delivery_base_km` | 10.0 km | 1 – 500 | Radius covered by baseline delivery fee |
| `delivery_extra_per_km` | 45.00 LKR | 0 – 5,000 | Incremental per-kilometer surcharge beyond base radius |
| `max_delivery_km` | 150.0 km | 1 – 1,000 | Maximum permissible delivery distance before requiring pickup |
| `low_stock_kg` | 25.0 kg | 0 – 10,000 | Inventory threshold triggering low-stock admin triage alerts |
| `stale_price_days` | 7 days | 1 – 90 | Interval after which unadjusted market prices trigger alerts |

### Market Price Auditing & Bulk Import
- Every change to a commodity price writes an immutable row into `market_price_history` recording old/new values, administrator ID, timestamp, and source (`manual` or `import`).
- **Typo Guard:** Price changes exceeding ±30% trigger an explicit confirmation checkpoint.
- **Formula Injection Defense:** Bulk CSV upload cells starting with `=`, `+`, `-`, or `@` are sanitized before dry-run evaluation.
- Changes update the in-memory cache instantly (`clear_settings_cache()`). Placed orders preserve their historical fee snapshot.

---

## 6. Personal Data Tools (Sri Lanka PDPA 2022 / GDPR)

AgroLink adheres to Sections 13 and 14 of the **Sri Lanka Personal Data Protection Act (PDPA No. 9 of 2022)**:

### Data Portability (Export)
- Users can request their data from `/profile`.
- Administrators download a clean, machine-readable JSON archive at `/admin/data-requests/<id>/export`.
- **Contents:** User account details, contact information, geographic coordinates, produce listings, and complete order history.
- **Safety:** Explicitly excludes password hashes, session identifiers, and internal security tokens.
- Audited with user ID only.

### Right to Erasure (Account Anonymization)
- Irreversible account anonymization executed via `/admin/data-requests/<id>/anonymize`.
- **Pre-condition Guard:** Blocked if the user has any `pending` or `confirmed` orders. All transactions must be completed or cancelled first.
- **Confirmation Guard:** Requires typing the user's exact email address plus an administrative reason.
- **Execution:**
  - Name replaced with `Deleted user #<id>`.
  - Email replaced with `deleted_user<id>@deleted.agrolink.lk`.
  - Phone, WhatsApp, address text, bio, farm name, and geolocation coordinates set to `NULL`.
  - Profile image files deleted from disk via `delete_uploaded_image()`.
  - Account deactivated (`is_active = False`) and sessions invalidated.
  - Active farmer listings deactivated (`is_available = False`, `is_deleted = True`).
  - Historical orders and financial totals preserved anonymously for statutory accounting.
  - Audit log records only neutral event indicators—old personal data is never written into audit details.

### Public Privacy Notice
Public privacy notice accessible at `/privacy`, linked across global footers and registration checkpoints.

---

## 7. Metrics & Report Definitions

Standard financial definitions enforced across dashboard widgets and downloadable reports:

- **Order Value:** Cumulative value of all orders excluding `cancelled` and `rejected` statuses.
- **Completed Value:** Cumulative value of delivered orders (`status = 'delivered'`).
- **Average Order Value (AOV):** `Order Value / Non-cancelled Order Count`.
- **Completion Rate:** `(Delivered Orders / Total Orders) * 100`.
- **Cancellation Rate:** `((Cancelled + Rejected Orders) / Total Orders) * 100`.

Reports feature streaming CSV generation with UTF-8 BOM encoding (`\xef\xbb\xbf`) for Microsoft Excel compatibility, as well as print-friendly views with report title, date range, generator ID, and timestamp.

---

## 8. System Status & Diagnostics (`/admin/system`)

Real-time infrastructure health monitoring:
- **Database Connectivity:** Direct ping and PostgreSQL dialect/version check.
- **Schema Migration Status:** Compares current database `alembic_version` against repository head revision (`0014_data_requests`).
- **Environment Telemetry:** Flask environment inspection with automated warning flags if debug mode is active in production.
- **Storage Health:** Checks write permissions for `/static/uploads` and computes total storage volume in megabytes.
- **Failed Login Tracking:** Telemetry counter querying failed authentication attempts in the preceding 24 hours.
- **Google Maps Integration:** Reports configuration presence (`Present` / `Missing`) for Browser Key, Map ID, and Server Key without exposing raw values.
- **Routes API Probe:** Rate-limited (maximum 5 probes per hour) diagnostic tool executing a real Colombo Fort to Kandy Clock Tower route calculation, reporting roundtrip latency in milliseconds.

---

## 9. Immutable Activity Audit Log (`/admin/activity`)

The `admin_audit_log` records:
- **Timestamp & Operator:** Server timestamp and administrator ID.
- **Action & Target:** Action name (e.g. `user_anonymized`, `test_routes_api`, `price_updated`), target entity, and target ID.
- **Network Metadata:** Remote IP address and user-agent string.
- **Append-Only Database Trigger:** PostgreSQL trigger `prevent_admin_audit_log_tamper` blocks any `UPDATE` or `DELETE` statements on the audit table at the engine level, guaranteeing non-repudiation.
