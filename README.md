# SummitFlow — Trekking Management Application V2

A simple MAD-II project built with Flask APIs, Vue 3 (CDN), Bootstrap, SQLite, Redis and Celery.

## Included requirements

- Unified user model with `admin`, `staff`, and `user` roles
- One pre-created Admin; no Admin registration
- User self-registration; Staff accounts created by Admin
- Admin trek CRUD, staff assignment, user/staff blocking, bookings and statistics
- Staff assigned-trek view, slot/status updates and participant list
- User trek search/filter, booking, cancellation, profile, history and notifications
- Duplicate-booking and overbooking prevention
- Redis cache for open-trek API responses with expiry and invalidation
- Celery daily reminders
- Celery monthly HTML report for Admin
- Celery user-triggered booking-history CSV export
- SQLite tables created programmatically

## 1. Extract and open the project

```powershell
cd C:\Users\parth\tma_mad2_simple
```

## 2. Create a virtual environment (recommended)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 3. Start Redis

With Docker Desktop:

```powershell
docker run --name tma-redis -p 6379:6379 -d redis:7-alpine
```

To reuse it later:

```powershell
docker start tma-redis
```

Verify:

```powershell
docker exec -it tma-redis redis-cli ping
```

Expected: `PONG`

## 4. Start Flask

```powershell
python app.py
```

Open `http://127.0.0.1:5000`.

## 5. Start Celery worker

Open a second PowerShell in the same folder and activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
celery -A celery_worker.celery worker --loglevel=info --pool=solo
```

## 6. Start Celery Beat

Open a third PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
celery -A celery_worker.celery beat --loglevel=info
```

## Admin login

- Email: `admin@tma.com`
- Password: `admin123`

Change these through environment variables before submission.

## Demo sequence

1. Login as Admin and create a Staff account.
2. Create an Open trek and assign the Staff member.
3. Register a Trekker account.
4. Book the trek and inspect booking history.
5. Login as Staff and update assigned trek status/slots.
6. Start Redis and show `/api/health` returning `"redis": true`.
7. Start Celery worker, then trigger CSV export from the user dashboard.
8. Trigger the monthly report from Admin → Reports.

## Email behavior

Add SMTP settings in environment variables for real email. Without SMTP configuration, email output is saved to:

```text
reports/mail_outbox.log
```

This keeps the local demo fully usable without requiring an external email account.
