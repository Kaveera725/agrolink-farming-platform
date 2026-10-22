# AgroLink - Project Execution Guide (RUN.md)

Quick, ordered step-by-step instructions to run the AgroLink application on your local machine.

---

## Prerequisites Checklist
- [x] Python 3.10+ installed
- [x] PostgreSQL service running
- [x] Virtual environment created (`venv`)
- [x] Dependencies installed (`pip install -r requirements.txt`)
- [x] `.env` configuration file present

---

## Step-by-Step Running Order

### Step 1: Open Terminal in Project Directory
Open PowerShell or your preferred terminal in the project root:
```powershell
cd "c:\Users\anush\OneDrive\Desktop\Projects for money\AgroLink"
```

---

### Step 2: Ensure PostgreSQL Service is Running
Check that the PostgreSQL service (`postgresql-x64-18` or your version) is active:
```powershell
Get-Service postgresql*
```
> *If the status is `Stopped`, start it with:*
> ```powershell
> Start-Service postgresql*
> ```

---

### Step 3: Activate the Virtual Environment
Activate the project's Python virtual environment:
```powershell
.\venv\Scripts\Activate.ps1
```
> *If PowerShell blocks script execution, run this once in your current session:*
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> ```

---

### Step 4: Verify or Apply Database Migrations
Ensure the database schema is up-to-date with all tables, constraints, and newly added columns (`farm_name`, `bio`):
```powershell
flask db upgrade
```

---

### Step 5: (Optional) Seed Market Benchmark Prices
If starting with a fresh database or missing market benchmark data, run:
```powershell
flask seed-prices
```

---

### Step 6: Start the Flask Application
Run the development server:
```powershell
python app.py
```
*(Alternatively: `flask run`)*

You will see output confirming the server is live:
```text
 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000
Press CTRL+C to quit
```

---

### Step 7: Open the Application in Your Browser
Open your browser and navigate to:
👉 **[http://127.0.0.1:5000](http://127.0.0.1:5000)**

---

## Default Demo Accounts

You can log in immediately using these pre-configured demo credentials:

| Role | Name | Email | Password |
| :--- | :--- | :--- | :--- |
| **Farmer** | Nimal Perera | `nimal@agrolink.lk` | `password123` |
| **Farmer** | Sunil Fernando | `sunil@agrolink.lk` | `password123` |
| **Buyer** | Kamani Silva | `kamani@agrolink.lk` | `password123` |

---

## Essential Application Routes

- **Home Page**: `http://127.0.0.1:5000/`
- **Marketplace**: `http://127.0.0.1:5000/marketplace/`
- **Market Prices**: `http://127.0.0.1:5000/prices/`
- **User Dashboard**: `http://127.0.0.1:5000/dashboard/`
- **My Profile**: `http://127.0.0.1:5000/profile`
- **Edit Profile**: `http://127.0.0.1:5000/profile/edit`
- **Change Password**: `http://127.0.0.1:5000/profile/password`
- **Order History**: `http://127.0.0.1:5000/orders/`

---

## Stopping the Application
To stop the server in terminal:
- Press `Ctrl + C`
- Deactivate the virtual environment:
  ```powershell
  deactivate
  ```
