# AgroLink Admin Role

## Current Admin Account

The current administrator signs in with:

- **Email:** `admin@agrolink.lk`
- **Password:** `admin123`
- **Role:** `admin`
- **Status:** Active

Admin accounts should be created or managed through the Flask CLI command:

```powershell
flask create-admin
```

## Admin Panel

After signing in, open:

```text
http://127.0.0.1:5000/admin/
```

The admin link is visible in the navigation only to users whose role is `admin`.

## Permissions

The admin role can:

- View the operational dashboard.
- View totals for users, listings, orders, order value, and delivery fees.
- View users grouped by role: farmer, buyer, and admin.
- Search users by name or email.
- Filter users by role and active/inactive status.
- Open a user's profile, listings, and orders.
- Deactivate or reactivate users.
- View all product listings, including deleted or hidden listings.
- Search listings by product name or farmer name.
- Hide or unhide listings for moderation.
- View the farmer associated with each listing.
- View all orders.
- Filter orders by status and date range.
- Open an order's complete price, delivery, buyer, farmer, and fulfilment breakdown.
- Create, update, and delete market prices.
- Maintain crop name, category, buying price, selling price, unit, and market location.
- Export users, orders, and sales summaries as CSV files.
- Filter report data by date range.
- View the administrative activity log.

## Dashboard Information

The dashboard includes:

- Total users.
- Farmer, buyer, and admin counts.
- Active listings.
- Total orders.
- Total order value.
- Total delivery fees.
- Orders grouped by status.
- Recent orders.
- Recent registrations.
- A Chart.js chart showing orders per day for the last 30 days.

## Market Price Validation

Market price records must satisfy these rules:

- Crop name is required.
- Category is required.
- Buying price must be greater than zero.
- Selling price must be greater than or equal to the buying price.
- Unit defaults to `per kg` when omitted.
- Market location defaults to `Colombo` when omitted.

Market prices are maintained through the admin panel rather than automatic hardcoded startup seeding.

## Security Rules

- Every admin route is protected by `@roles_required('admin')`.
- Unauthenticated visitors are sent to the login page.
- Farmers and buyers receive a 403 Access denied page when opening admin routes.
- An admin cannot deactivate their own account.
- Deactivated users cannot log in because inactive accounts are rejected by the user loader.
- Admin actions are stored in the `admin_audit_log` table.
- Audit entries record the admin, action, target, details, and timestamp.

## Activity Logged

The following actions are recorded in the activity log:

- User activation or deactivation.
- Listing hide or unhide actions.
- Market price creation or update.
- Market price deletion.
- CSV report exports.

Open the activity log at:

```text
http://127.0.0.1:5000/admin/activity
```

## Database Setup

Apply all migrations before using the admin panel:

```powershell
flask db upgrade
```

The admin audit table is created by migration `0009_add_admin_audit_log`.
