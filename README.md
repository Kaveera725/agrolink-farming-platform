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
```

---

## 4. Run the Application

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

## 5. Application Structure & Roles

AgroLink features two main user roles:
- **Farmer**: Manage crops, list products for sale, view market prices and incoming orders.
- **Buyer**: Browse marketplace listings, place crop orders, view order status and price trends.

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
- `/dashboard/` - User dashboard (Farmer or Buyer)
- `/marketplace/` - Crop marketplace listings
- `/prices/` - Live market benchmark prices and best deals
- `/prices/bids` - Best price comparison
- `/orders/` - Order history & tracking

---

## 6. Common Troubleshooting

| Issue | Cause | Solution |
| :--- | :--- | :--- |
| **`psql: error: connection to server at "localhost" failed`** | PostgreSQL Windows service is not running | Run `Start-Service postgresql*` in PowerShell as Administrator or start it from `services.msc`. |
| **`password authentication failed for user "agrolink_db_user"`** | User doesn't exist or incorrect password | Update `DATABASE_URL` in `.env` with your `postgres` username and password, or run the `CREATE USER` snippet from Section 2. |
| **`Script execution is disabled on this system`** | PowerShell execution policy restrictions | Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` before activating the virtualenv. |
| **Missing tables or relations** | Database backup wasn't imported into `agrolink_db` | Verify database name is `agrolink_db` and rerun the SQL dump import. |

---

## 7. Version Control & Development

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
