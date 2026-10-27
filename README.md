# AgroLink - Farming Marketplace & Management Platform

A Flask and PostgreSQL based platform connecting farmers and buyers for direct crop trading, marketplace listings, price tracking, and order management.

---

## Prerequisites

Before starting, ensure you have the following installed on your machine:
- **Python 3.10+** ([python.org](https://www.python.org/downloads/))
- **PostgreSQL 14+** (with `psql` or **pgAdmin 4**) ([postgresql.org](https://www.postgresql.org/download/))
- **Git**

---

## 1. Environment Setup

### 1.1 Open Terminal in Project Root
Open PowerShell or your preferred terminal in the project directory:
```powershell
cd "c:\Users\anush\OneDrive\Desktop\Projects for money\AgroLink"
```

### 1.2 Create & Activate Python Virtual Environment
```powershell
# Create virtual environment
python -m venv venv

# Activate virtual environment (Windows PowerShell)
.\venv\Scripts\Activate.ps1

# (If PowerShell blocks script execution, run this first in the current session):
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

*(On macOS/Linux: `source venv/bin/activate`)*

### 1.3 Install Required Dependencies
```powershell
pip install -r requirements.txt
```

---

## 2. Database Setup (Importing `agrolink_database_backup_file.sql`)

You have two simple ways to set up and restore the database: **Method A (Command Line - Recommended)** or **Method B (pgAdmin GUI)**.

### Method A: Command Line (`psql`) - Recommended

The `agrolink_database_backup_file.sql` script is pre-configured with statements to create the `agrolink_db` database, connect to it, build the schema, and insert sample data.

1. **Verify PostgreSQL Service is Running:**
   ```powershell
   Get-Service postgresql*
   ```
   If it is stopped, start it from Windows Services or run:
   ```powershell
   Start-Service postgresql*
   ```

2. **Restore Database from SQL Backup:**
   Run `psql` using your PostgreSQL superuser (`postgres`):
   ```powershell
   psql -U postgres -f agrolink_database_backup_file.sql
   ```
   *(Enter your `postgres` password when prompted. The script will create `agrolink_db` and populate all tables, relationships, and sample data).*

3. **(Optional) Create the Dedicated Application User:**
   If you want to use the default user specified in the `.env` file (`agrolink_db_user`), open the PostgreSQL shell:
   ```powershell
   psql -U postgres -d agrolink_db
   ```
   Then execute:
   ```sql
   CREATE USER agrolink_db_user WITH PASSWORD 'agrolink_db_user_password';
   GRANT ALL PRIVILEGES ON DATABASE agrolink_db TO agrolink_db_user;
   GRANT ALL ON ALL TABLES IN SCHEMA public TO agrolink_db_user;
   GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO agrolink_db_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO agrolink_db_user;
   ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO agrolink_db_user;
   \q
   ```

---

### Method B: Using pgAdmin 4 (GUI)

If you prefer using the pgAdmin graphical interface:

1. Open **pgAdmin 4** and connect to your local PostgreSQL server.
2. In the left browser tree, right-click **Databases** $\rightarrow$ **Create** $\rightarrow$ **Database...**.
3. Set **Database** name to: `agrolink_db` and click **Save**.
4. Right-click the newly created `agrolink_db` database $\rightarrow$ select **Query Tool**.
5. Click the **Open File** icon (folder icon in the toolbar), browse to `agrolink_database_backup_file.sql`, and open it.
6. Click the **Execute / Run** button (Play icon or `F5`).
   *(Note: The `\connect` meta-command has been commented out in `agrolink_database_backup_file.sql` so pgAdmin runs standard SQL smoothly without syntax errors).*
7. Once completed, refresh the database tables under `Schemas` $\rightarrow$ `public` $\rightarrow$ `Tables` to verify:
   - `crops`
   - `market_prices`
   - `orders`
   - `products`
   - `users`

---

## 3. Configure `.env` File

Create or verify your `.env` file in the project root directory.

If it does not exist, copy from `.env.example`:
```powershell
Copy-Item .env.example .env
```

Ensure `.env` matches your local database credentials:

### If using the dedicated user:
```ini
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=agrolink-super-secret-key-2024
DATABASE_URL=postgresql://agrolink_db_user:agrolink_db_user_password@localhost:5432/agrolink_db
```

### If connecting directly with your `postgres` superuser:
Replace `<YOUR_POSTGRES_PASSWORD>` with your actual local PostgreSQL password:
```ini
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=agrolink-super-secret-key-2024
DATABASE_URL=postgresql://postgres:<YOUR_POSTGRES_PASSWORD>@localhost:5432/agrolink_db

# Google Maps Platform Credentials (safe browser key, server key, and map ID)
GOOGLE_MAPS_BROWSER_KEY=
GOOGLE_MAPS_SERVER_KEY=
GOOGLE_MAPS_MAP_ID=
```

---

## 4. Google Maps Setup

AgroLink features a decoupled, secure Google Maps foundation designed for Sri Lankan agricultural logistics.

### 4.1 Google Cloud Project & Billing
1. Navigate to the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new Google Cloud Project (e.g. `agrolink-platform`).
3. Link an active **Billing Account** to the project (Google Maps Platform requires an active billing account linked to the project, even within the free monthly tier).

### 4.2 Enable the 4 Required APIs
In the Google Cloud Console, open **APIs & Services** $\rightarrow$ **Library** and enable:
1. **Maps JavaScript API**: Used for client-side interactive map rendering, vector maps, and Advanced Markers.
2. **Places API (New)**: Powers location autocomplete searches restricted to Sri Lanka (`lk`).
3. **Geocoding API**: Reverse geocoding (coordinates to street addresses) and forward address resolution.
4. **Distance Matrix API**: Server-side farm-to-buyer distance calculations and route estimation.

### 4.3 Configure the 2 API Keys & Security Restrictions
To strictly protect your credentials and quota, configure two separate API keys under **APIs & Services** $\rightarrow$ **Credentials**:

#### Key 1: Browser Key (`GOOGLE_MAPS_BROWSER_KEY`)
- **Purpose**: Client-facing frontend JavaScript and templates.
- **Application Restriction**: Select **Websites (HTTP referrers)** and add:
  - `http://localhost:5000/*`
  - `http://127.0.0.1:5000/*`
  - `https://your-production-domain.com/*`
- **API Restriction**: Restrict key to:
  - `Maps JavaScript API`
  - `Places API (New)`

#### Key 2: Server Key (`GOOGLE_MAPS_SERVER_KEY`)
- **Purpose**: Backend server-to-server operations ONLY (`services/maps.py`).
- **Security Rule**: NEVER exposed to Jinja templates, frontend JavaScript, or API responses.
- **Application Restriction**: Select **IP addresses** (set your backend server IP addresses; leave unrestricted or IP-bound in development).
- **API Restriction**: Restrict key to:
  - `Geocoding API`
  - `Distance Matrix API`

### 4.4 Create a Map ID (`GOOGLE_MAPS_MAP_ID`)
Modern Google Maps `AdvancedMarkerElement` requires a registered Map ID:
1. Go to **Google Maps Platform** $\rightarrow$ **Map Management**.
2. Click **Create Map ID**.
3. Name: `AgroLink Map`.
4. Map type: **JavaScript** $\rightarrow$ **Vector** (or Raster).
5. Copy the generated Map ID string into `GOOGLE_MAPS_MAP_ID` in your `.env`.

### 4.5 Set Environment Variables
Add the credentials to your `.env` file (never commit real keys to git):
```ini
GOOGLE_MAPS_BROWSER_KEY=your_restricted_browser_key_here
GOOGLE_MAPS_SERVER_KEY=your_restricted_server_key_here
GOOGLE_MAPS_MAP_ID=your_map_id_here
```

### 4.6 How to Test: Developer Diagnostics Bench (`/_maps_test`)
A dedicated diagnostics bench is available in development mode (`app.debug = True`):

1. Start the development server (`python app.py`).
2. Navigate to:
   ```
   http://127.0.0.1:5000/_maps_test
   ```
3. **Verify Interactive Features**:
   - Status badges confirm key and Map ID presence without printing the raw secrets.
   - Interactive map is centered on Sri Lanka (`7.8731, 80.7718`).
   - Pin is an `AdvancedMarkerElement` that can be dragged across Sri Lanka.
   - Places search is scoped to Sri Lanka (`country: 'lk'`).
   - "Use my location" centers map to current device GPS coordinates.
   - Live read-out displays coordinates, address, and in-country boundary validation.
4. **Verify Failure Diagnostics & Fallback**:
   - Use the built-in simulator to test and verify clear failure messages for:
     - `RefererNotAllowedMapError` (website restriction mismatch)
     - `ApiNotActivatedMapError` (missing enabled API in Google Cloud)
     - `BillingNotEnabledMapError` (unlinked billing account)
     - `InvalidKeyMapError` (invalid key)
     - `missing key` (missing `GOOGLE_MAPS_BROWSER_KEY`)
     - `missing map id` (missing `GOOGLE_MAPS_MAP_ID`)
   - Notice banner: *"Map is unavailable, enter your location manually"* appears whenever maps are disabled or loading fails.
   - Form fields (Latitude, Longitude, Address) remain fully editable and functional.

### 4.7 CLI Diagnostics: `flask maps-check`
Run the self-diagnostic CLI command at any time to verify key configurations without printing secrets:
```powershell
flask maps-check
```
It verifies:
- Presence and character length of `GOOGLE_MAPS_BROWSER_KEY`, `GOOGLE_MAPS_MAP_ID`, and `GOOGLE_MAPS_SERVER_KEY`.
- Identifies obvious placeholders (e.g. `your_api_key_here`, `paste_your_key`, etc.).
- Performs a live, single server-side call to Google Geocoding API for "Kandy, Sri Lanka".
- Displays the exact HTTP referrer entries required for your browser key.

### 4.8 Troubleshooting Common Google Maps Errors

| Error Code / Symptom | Probable Cause | Recommended Fix |
| :--- | :--- | :--- |
| `RefererNotAllowedMapError` | Browser key HTTP referrer restrictions do not match current host. | In Google Cloud Console $\rightarrow$ Credentials $\rightarrow$ Browser Key, add `http://localhost:5000/*` and `http://127.0.0.1:5000/*`. |
| `ApiNotActivatedMapError` | One or more required APIs are disabled in your Google Cloud project. | Enable Maps JavaScript API, Places API (New), and Geocoding API in Google Cloud Console. |
| `BillingNotEnabledMapError` | Google Cloud project lacks an active linked billing account. | Link an active billing account in Google Cloud Console. (Includes free monthly tier usage). |
| `InvalidKeyMapError` / `gm_authFailure` | Key is mistyped, deleted, or invalid. | Verify and re-copy the API key from Google Cloud Console into `.env`. |
| `REQUEST_DENIED` (Geocoding API) | Server key is invalid or Geocoding API is not enabled for that key. | Check `GOOGLE_MAPS_SERVER_KEY` in `.env` and verify API restrictions in Google Cloud Console. |
| Geolocation Permission Denied | Browser or OS location permission was declined. | Allow location access in browser site settings or enter location using the search bar / manual fields. |
| Geolocation Timeout / Unavailable | GPS sensor unavailable or signal lost. | Re-try device location button or enter coordinates manually. |
| Map Unavailable / Offline | Network error, ad-blocker, or missing credentials. | AgroLink automatically unhides manual latitude/longitude/address inputs so user flows are never blocked. |

---

## 5. Delivery Pricing & Routing System

AgroLink provides transparent, tiered delivery pricing calculated from actual driving distances across Sri Lanka, backed by Google Routes API with an automatic direct-distance fallback.

### Core Delivery Rules
1. **Farmer Requirement**: A farmer must have a saved location pin on their profile to enable delivery on their product listings (`offers_delivery`). If no pin is set, enabling delivery is blocked with a guidance link to edit their profile.
2. **Geographical Constraints**: Delivery addresses and pins must fall within Sri Lanka territory (`lat: 5.8 to 9.9`, `lng: 79.6 to 82.0`) and cannot exceed `MAX_DELIVERY_KM` (300 km).
3. **Privacy by Design**:
   - Guests and third parties see only the farmer's district.
   - Exact buyer coordinates and delivery address are disclosed **only** to the farmer who owns the ordered product, and **only** for delivery fulfillment.
   - For pickup orders, buyer coordinates and address are strictly omitted.
4. **Order Status Workflow**:
   - Status transitions strictly enforce: `pending` → `confirmed` → `delivered`, or `cancelled` / `rejected`.
   - Farmer rejection requires a reason (≥ 5 characters) and immediately restores produce stock.
   - Buyer cancellation is allowed only while the order remains `pending` and immediately restores produce stock.

### Configuration Constants (`config.py`)
All parameters are configurable via constants in [`config.py`](file:///c:/Users/anush/OneDrive/Desktop/Projects/AgroLink/config.py) or environment variables:
| Constant | Default Value | Description |
| :--- | :--- | :--- |
| `DELIVERY_BASE_FEE` | `Decimal("5000")` | Base flat fee in LKR for up to 50 km. |
| `DELIVERY_BASE_KM` | `Decimal("50")` | Base threshold distance in kilometers. |
| `DELIVERY_EXTRA_PER_KM` | `Decimal("60")` | Incremental rate in LKR for each additional kilometer over base. |
| `MAX_DELIVERY_KM` | `Decimal("300")` | Maximum allowable delivery distance in kilometers. |
| `ROUTE_FALLBACK_FACTOR` | `Decimal("1.3")` | Winding factor applied to Haversine direct distance during API fallback. |
| `ROUTES_API_TIMEOUT_SECONDS` | `5` | Request timeout before falling back to local estimation. |

### Fee Calculation & Examples
- If **Distance ≤ 50 km**:  
  Fee = `LKR 5,000.00`
- If **Distance > 50 km**:  
  Extra km = `ceil(Distance - 50)`  
  Fee = `5,000 + (Extra km * 60)`

#### Calculation Examples (with 15 kg @ LKR 300 = LKR 4,500.00 produce):
- **Example 1 (< 50 km)**: Colombo to Mount Lavinia (11.12 km driving distance via Routes API)  
  - Delivery Fee: **LKR 5,000.00**  
  - Grand Total: **LKR 9,500.00**
- **Example 2 (~51.4 km)**: Colombo to Kalutara (51.42 km driving distance via estimated mode)  
  - Extra distance: 51.42 - 50 = 1.42 km → ceil(1.42) = 2 km  
  - Extra fee: 2 * 60 = LKR 120.00  
  - Delivery Fee: 5,000 + 120 = **LKR 5,120.00**  
  - Grand Total: **LKR 9,620.00**
- **Example 3 (~75.2 km)**: Colombo to Aluthgama (75.24 km driving distance via estimated mode)  
  - Extra distance: 75.24 - 50 = 25.24 km → ceil(25.24) = 26 km  
  - Extra fee: 26 * 60 = LKR 1,560.00  
  - Delivery Fee: 5,000 + 1,560 = **LKR 6,560.00**  
  - Grand Total: **LKR 11,060.00**

### Fallback & Resilience Behavior
- **Google Routes API**: Requested server-side using field mask `routes.distanceMeters`.
- **LRU Distance Cache**: Distances are cached in an in-memory thread-safe LRU cache (TTL: 24h, rounded to 4 decimals / ~11m) to optimize latency and eliminate redundant API costs.
- **Graceful Fallback**: If the Routes API times out (> 5s), returns a non-200 status code, or `GOOGLE_MAPS_SERVER_KEY` is not configured, the system computes:
  Estimated km = `round(Haversine(origin, destination) * 1.3, 2)`
  The fee is computed normally with `distance_source = 'estimated'`. The user flow is never interrupted with a 500 error.

---

## 6. Database Migrations & CLI Management

AgroLink uses **Flask-Migrate** (Alembic) for structured schema migrations and CLI commands for administrative maintenance.

### Apply Migrations
To bring the database schema up to the latest revision (tables, enum types, columns):
```powershell
flask db upgrade
```

### Seed Market Benchmark Prices
Market prices are decoupled from application startup. To populate initial reference prices:
```powershell
flask seed-prices
```

### Create an Administrator User
Create an admin account interactively without storing passwords in code or scripts:
```powershell
flask create-admin
```
*(Prompts securely for Admin Email, Name, WhatsApp/Phone, and Password).*

---

## 7. Run the Application

With your virtual environment activated and database running:

```powershell
python app.py
```

You should see output similar to:
```text
 * Serving Flask app 'app'
 * Debug mode: off
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 8. Application Structure & Roles

AgroLink features three primary user roles:
- **Farmer**: Manage crops, list products for sale, view market prices and incoming orders.
- **Buyer**: Browse marketplace listings, place crop orders, view order status and price trends.
- **Admin**: System management and administrative access.

### Demo / Default Accounts:
| Role | Name | Email | Password |
| :--- | :--- | :--- | :--- |
| **Farmer** | Nimal Perera | `nimal@agrolink.lk` | `password123` |
| **Farmer** | Sunil Fernando | `sunil@agrolink.lk` | `password123` |
| **Buyer** | Kamani Silva | `kamani@agrolink.lk` | `password123` |

### Key Routes:
- `/` - Landing home page
- `/auth/login` - User login
- `/auth/register` - New user registration (choose Farmer or Buyer)
- `/profile` - User profile view (personal & farm info, contact details, map placeholder)
- `/profile/edit` - Edit profile information & credentials
- `/profile/password` - Change account password securely
- `/dashboard/` - User dashboard (Farmer or Buyer)
- `/marketplace/` - Crop marketplace listings
- `/prices/` - Live market benchmark prices and best deals
- `/prices/bids` - Best price comparison
- `/orders/` - Order history & tracking

---

## 9. Common Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **`psql: error: connection to server at "localhost" failed`** | PostgreSQL Windows service is not running | Run `Start-Service postgresql*` in PowerShell as Administrator or start it from `services.msc`. |
| **`password authentication failed for user "agrolink_db_user"`** | User doesn't exist or incorrect password | Update `DATABASE_URL` in `.env` with your `postgres` username and password, or run the `CREATE USER` snippet from Section 2. |
| **`Script execution is disabled on this system`** | PowerShell execution policy restrictions | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` before activating the virtualenv. |
| **Missing tables or relations** | Database backup wasn't imported into `agrolink_db` | Verify database name is `agrolink_db` and rerun the SQL dump import. |

---

## 10. Version Control & Development

```powershell
# Check modified files
git status

# Stage changes
git add .

# Commit
git commit -m "Your descriptive commit message"

# Push to your repository
git push
```
