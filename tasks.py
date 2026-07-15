import csv
from datetime import date, datetime, timedelta
from pathlib import Path

from celery_worker import celery
from extensions import db
from mail_service import send_html_email
from models import Booking, ExportJob, Notification, Trek, User


@celery.task(name='tasks.export_booking_history')
def export_booking_history(job_id):
    job = db.session.get(ExportJob, job_id)
    if not job:
        return {'ok': False, 'message': 'Job not found'}
    try:
        job.status = 'Processing'
        db.session.commit()
        rows = Booking.query.filter_by(user_id=job.user_id).order_by(Booking.booking_date.desc()).all()
        filename = f'booking_history_user_{job.user_id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        path = Path(celery_worker_root()) / 'exports' / filename
        path.parent.mkdir(exist_ok=True)
        with path.open('w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow(['User ID', 'Trek Name', 'Location', 'Booking Status', 'Booking Date', 'Start Date', 'End Date'])
            for booking in rows:
                writer.writerow([
                    booking.user_id, booking.trek.name, booking.trek.location, booking.status,
                    booking.booking_date.strftime('%Y-%m-%d %H:%M'), booking.trek.start_date, booking.trek.end_date,
                ])
        job.status = 'Completed'
        job.filename = filename
        job.completed_at = datetime.utcnow()
        db.session.add(Notification(user_id=job.user_id, message='Your booking-history CSV export is ready to download.'))
        db.session.commit()
        return {'ok': True, 'filename': filename}
    except Exception as exc:
        db.session.rollback()
        job = db.session.get(ExportJob, job_id)
        if job:
            job.status = 'Failed'
            db.session.commit()
        raise exc


@celery.task(name='tasks.send_daily_reminders')
def send_daily_reminders():
    today = date.today()
    limit = today + timedelta(days=2)
    bookings = (
        Booking.query.join(Trek)
        .filter(Booking.status == 'Booked', Trek.start_date >= today, Trek.start_date <= limit)
        .all()
    )
    count = 0
    for booking in bookings:
        message = (
            f'Reminder: {booking.trek.name} starts on {booking.trek.start_date}. '
            f'Please carry your ID, water bottle and required trekking gear.'
        )
        db.session.add(Notification(user_id=booking.user_id, message=message))
        send_html_email(booking.user.email, f'Upcoming trek: {booking.trek.name}', f'<p>Hello {booking.user.name},</p><p>{message}</p>')
        count += 1
    db.session.commit()
    return {'ok': True, 'reminders_sent': count}


@celery.task(name='tasks.generate_monthly_report')
def generate_monthly_report():
    today = date.today()
    first_this_month = today.replace(day=1)
    previous_month_end = first_this_month - timedelta(days=1)
    start = previous_month_end.replace(day=1)
    end = previous_month_end

    completed_treks = Trek.query.filter(Trek.status == 'Completed', Trek.end_date >= start, Trek.end_date <= end).all()
    completed_bookings = (
        Booking.query.join(Trek)
        .filter(Booking.status == 'Completed', Trek.end_date >= start, Trek.end_date <= end)
        .all()
    )
    popularity = {}
    for booking in completed_bookings:
        popularity[booking.trek.name] = popularity.get(booking.trek.name, 0) + 1
    popular = max(popularity, key=popularity.get) if popularity else 'No completed bookings'

    html = f'''<!doctype html>
    <html><body style="font-family:Arial,sans-serif">
      <h2>TMA Monthly Activity Report — {start.strftime('%B %Y')}</h2>
      <p><strong>Treks conducted:</strong> {len(completed_treks)}</p>
      <p><strong>User participations:</strong> {len(completed_bookings)}</p>
      <p><strong>Most popular trek:</strong> {popular}</p>
      <h3>Completed treks</h3>
      <ul>{''.join(f'<li>{t.name} — {t.location}</li>' for t in completed_treks) or '<li>None</li>'}</ul>
    </body></html>'''
    filename = f'monthly_report_{start.strftime("%Y_%m")}.html'
    path = Path(celery_worker_root()) / 'reports' / filename
    path.parent.mkdir(exist_ok=True)
    path.write_text(html, encoding='utf-8')

    admin = User.query.filter_by(role='admin').first()
    if admin:
        send_html_email(admin.email, f'TMA Monthly Report - {start.strftime("%B %Y")}', html)
        db.session.add(Notification(user_id=admin.id, message=f'Monthly report for {start.strftime("%B %Y")} has been generated.'))
        db.session.commit()
    return {'ok': True, 'filename': filename}


def celery_worker_root():
    return Path(__file__).resolve().parent
