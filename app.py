from datetime import date, datetime
from functools import wraps
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from cache_service import delete_key, get_json, redis_available, set_json
from config import Config
from extensions import db, login_manager
from models import Booking, ExportJob, Notification, Trek, User

OPEN_TREKS_CACHE_KEY = 'treks:open'


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path(app.root_path, 'exports').mkdir(exist_ok=True)
    Path(app.root_path, 'reports').mkdir(exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    register_routes(app)

    with app.app_context():
        db.create_all()
        seed_admin_and_sample_data(app)

    return app


def api_error(message, status=400):
    return jsonify({'ok': False, 'message': message}), status


def role_required(*roles):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user.status != 'active':
                return api_error('Your account is blocked.', 403)
            if current_user.role not in roles:
                return api_error('Access denied.', 403)
            return fn(*args, **kwargs)
        return wrapped
    return decorator


def parse_date(value, field_name):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        raise ValueError(f'{field_name} must be in YYYY-MM-DD format.')


def invalidate_trek_cache():
    delete_key(OPEN_TREKS_CACHE_KEY)


def active_booking_count(trek_id):
    return Booking.query.filter_by(trek_id=trek_id, status='Booked').count()


def register_routes(app):
    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/api/health')
    def health():
        return jsonify({'ok': True, 'redis': redis_available()})

    @app.post('/api/register')
    def register():
        data = request.get_json(silent=True) or {}
        name = str(data.get('name', '')).strip()
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))
        phone = str(data.get('phone', '')).strip()
        if not name or not email or len(password) < 6:
            return api_error('Name, email and a password of at least 6 characters are required.')
        if User.query.filter_by(email=email).first():
            return api_error('Email already registered.')
        user = User(name=name, email=email, role='user', phone=phone, status='active')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return jsonify({'ok': True, 'user': user.to_dict()})

    @app.post('/api/login')
    def login():
        data = request.get_json(silent=True) or {}
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return api_error('Invalid email or password.', 401)
        if user.status != 'active':
            return api_error('Your account is blocked.', 403)
        login_user(user)
        return jsonify({'ok': True, 'user': user.to_dict()})

    @app.post('/api/logout')
    @login_required
    def logout():
        logout_user()
        return jsonify({'ok': True})

    @app.get('/api/me')
    def me():
        return jsonify({'authenticated': current_user.is_authenticated, 'user': current_user.to_dict() if current_user.is_authenticated else None})

    @app.patch('/api/profile')
    @role_required('user', 'staff', 'admin')
    def update_profile():
        data = request.get_json(silent=True) or {}
        name = str(data.get('name', current_user.name)).strip()
        phone = str(data.get('phone', current_user.phone or '')).strip()
        if not name:
            return api_error('Name is required.')
        current_user.name = name
        current_user.phone = phone
        db.session.commit()
        return jsonify({'ok': True, 'user': current_user.to_dict()})

    @app.get('/api/treks')
    def list_treks():
        location = request.args.get('location', '').strip()
        difficulty = request.args.get('difficulty', '').strip()
        duration = request.args.get('duration', type=int)
        include_all = current_user.is_authenticated and current_user.role == 'admin' and request.args.get('all') == '1'

        use_cache = not location and not difficulty and not duration and not include_all
        if use_cache:
            cached = get_json(OPEN_TREKS_CACHE_KEY)
            if cached is not None:
                return jsonify({'ok': True, 'treks': cached, 'source': 'redis'})

        query = Trek.query
        if not include_all:
            query = query.filter_by(status='Open')
        if location:
            query = query.filter(Trek.location.ilike(f'%{location}%'))
        if difficulty:
            query = query.filter_by(difficulty=difficulty)
        if duration:
            query = query.filter(Trek.duration_days <= duration)
        treks = [t.to_dict() for t in query.order_by(Trek.start_date.asc()).all()]
        if use_cache:
            set_json(OPEN_TREKS_CACHE_KEY, treks)
        return jsonify({'ok': True, 'treks': treks, 'source': 'database'})

    @app.get('/api/admin/stats')
    @role_required('admin')
    def admin_stats():
        return jsonify({'ok': True, 'stats': {
            'treks': Trek.query.count(),
            'users': User.query.filter_by(role='user').count(),
            'staff': User.query.filter_by(role='staff').count(),
            'bookings': Booking.query.count(),
            'completed': Trek.query.filter_by(status='Completed').count(),
        }})

    @app.get('/api/admin/users')
    @role_required('admin')
    def admin_users():
        q = request.args.get('q', '').strip()
        query = User.query.filter(User.role.in_(['user', 'staff']))
        if q:
            if q.isdigit():
                query = query.filter((User.id == int(q)) | User.name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%'))
            else:
                query = query.filter(User.name.ilike(f'%{q}%') | User.email.ilike(f'%{q}%'))
        return jsonify({'ok': True, 'users': [u.to_dict() for u in query.order_by(User.role, User.name).all()]})

    @app.post('/api/admin/staff')
    @role_required('admin')
    def create_staff():
        data = request.get_json(silent=True) or {}
        name = str(data.get('name', '')).strip()
        email = str(data.get('email', '')).strip().lower()
        password = str(data.get('password', ''))
        if not name or not email or len(password) < 6:
            return api_error('Name, email and a password of at least 6 characters are required.')
        if User.query.filter_by(email=email).first():
            return api_error('Email already exists.')
        staff = User(name=name, email=email, role='staff', phone=str(data.get('phone', '')).strip(), specialization=str(data.get('specialization', '')).strip(), status='active')
        staff.set_password(password)
        db.session.add(staff)
        db.session.commit()
        return jsonify({'ok': True, 'staff': staff.to_dict()})

    @app.patch('/api/admin/users/<int:user_id>/status')
    @role_required('admin')
    def change_user_status(user_id):
        user = db.session.get(User, user_id)
        if not user or user.role == 'admin':
            return api_error('User not found.', 404)
        status = (request.get_json(silent=True) or {}).get('status')
        if status not in ['active', 'blacklisted']:
            return api_error('Invalid status.')
        user.status = status
        db.session.commit()
        return jsonify({'ok': True, 'user': user.to_dict()})

    @app.post('/api/admin/treks')
    @role_required('admin')
    def create_trek():
        data = request.get_json(silent=True) or {}
        try:
            total_slots = int(data.get('total_slots', 0))
            start_date = parse_date(data.get('start_date'), 'Start date')
            end_date = parse_date(data.get('end_date'), 'End date')
            duration_days = int(data.get('duration_days', 0))
        except (TypeError, ValueError) as exc:
            return api_error(str(exc))
        if not data.get('name') or not data.get('location') or data.get('difficulty') not in ['Easy', 'Moderate', 'Hard']:
            return api_error('Name, location and valid difficulty are required.')
        if total_slots < 1 or duration_days < 1 or end_date < start_date:
            return api_error('Invalid slots, duration or dates.')
        staff_id = data.get('assigned_staff_id') or None
        if staff_id:
            staff = db.session.get(User, int(staff_id))
            if not staff or staff.role != 'staff' or staff.status != 'active':
                return api_error('Assigned staff is invalid.')
        trek = Trek(
            name=str(data['name']).strip(), location=str(data['location']).strip(), difficulty=data['difficulty'],
            duration_days=duration_days, total_slots=total_slots, available_slots=total_slots,
            status=data.get('status', 'Open'), start_date=start_date, end_date=end_date,
            description=str(data.get('description', '')).strip(), assigned_staff_id=int(staff_id) if staff_id else None,
        )
        db.session.add(trek)
        db.session.commit()
        invalidate_trek_cache()
        return jsonify({'ok': True, 'trek': trek.to_dict()})

    @app.patch('/api/admin/treks/<int:trek_id>')
    @role_required('admin')
    def update_trek(trek_id):
        trek = db.session.get(Trek, trek_id)
        if not trek:
            return api_error('Trek not found.', 404)
        data = request.get_json(silent=True) or {}
        try:
            if 'start_date' in data:
                trek.start_date = parse_date(data['start_date'], 'Start date')
            if 'end_date' in data:
                trek.end_date = parse_date(data['end_date'], 'End date')
            if 'duration_days' in data:
                trek.duration_days = int(data['duration_days'])
            if 'total_slots' in data:
                new_total = int(data['total_slots'])
                booked = active_booking_count(trek.id)
                if new_total < booked:
                    return api_error(f'Total slots cannot be less than {booked} active bookings.')
                trek.total_slots = new_total
                trek.available_slots = new_total - booked
        except (TypeError, ValueError) as exc:
            return api_error(str(exc))
        for field in ['name', 'location', 'difficulty', 'status', 'description']:
            if field in data:
                setattr(trek, field, data[field])
        if 'assigned_staff_id' in data:
            staff_id = data['assigned_staff_id'] or None
            if staff_id:
                staff = db.session.get(User, int(staff_id))
                if not staff or staff.role != 'staff' or staff.status != 'active':
                    return api_error('Assigned staff is invalid.')
            trek.assigned_staff_id = int(staff_id) if staff_id else None
        if trek.end_date < trek.start_date:
            return api_error('End date cannot be before start date.')
        db.session.commit()
        invalidate_trek_cache()
        return jsonify({'ok': True, 'trek': trek.to_dict()})

    @app.delete('/api/admin/treks/<int:trek_id>')
    @role_required('admin')
    def delete_trek(trek_id):
        trek = db.session.get(Trek, trek_id)
        if not trek:
            return api_error('Trek not found.', 404)
        db.session.delete(trek)
        db.session.commit()
        invalidate_trek_cache()
        return jsonify({'ok': True})

    @app.get('/api/admin/bookings')
    @role_required('admin')
    def all_bookings():
        return jsonify({'ok': True, 'bookings': [b.to_dict() for b in Booking.query.order_by(Booking.booking_date.desc()).all()]})

    @app.get('/api/staff/treks')
    @role_required('staff')
    def staff_treks():
        treks = Trek.query.filter_by(assigned_staff_id=current_user.id).order_by(Trek.start_date).all()
        result = []
        for trek in treks:
            item = trek.to_dict()
            item['registered_users'] = active_booking_count(trek.id)
            result.append(item)
        return jsonify({'ok': True, 'treks': result})

    @app.patch('/api/staff/treks/<int:trek_id>')
    @role_required('staff')
    def staff_update_trek(trek_id):
        trek = db.session.get(Trek, trek_id)
        if not trek or trek.assigned_staff_id != current_user.id:
            return api_error('You can manage only your assigned treks.', 403)
        data = request.get_json(silent=True) or {}
        if 'status' in data:
            if data['status'] not in ['Open', 'Closed', 'Started', 'Completed']:
                return api_error('Invalid trek status.')
            trek.status = data['status']
            if trek.status == 'Completed':
                Booking.query.filter_by(trek_id=trek.id, status='Booked').update({'status': 'Completed'})
        if 'available_slots' in data:
            try:
                available = int(data['available_slots'])
            except (TypeError, ValueError):
                return api_error('Available slots must be a number.')
            if available < 0 or available > trek.total_slots:
                return api_error('Available slots must be between 0 and total slots.')
            trek.available_slots = available
        db.session.commit()
        invalidate_trek_cache()
        return jsonify({'ok': True, 'trek': trek.to_dict()})

    @app.get('/api/staff/treks/<int:trek_id>/participants')
    @role_required('staff')
    def participants(trek_id):
        trek = db.session.get(Trek, trek_id)
        if not trek or trek.assigned_staff_id != current_user.id:
            return api_error('You can view only your assigned treks.', 403)
        rows = Booking.query.filter_by(trek_id=trek_id).order_by(Booking.booking_date).all()
        return jsonify({'ok': True, 'participants': [b.to_dict() for b in rows]})

    @app.post('/api/bookings/<int:trek_id>')
    @role_required('user')
    def book_trek(trek_id):
        trek = db.session.get(Trek, trek_id)
        if not trek:
            return api_error('Trek not found.', 404)
        if trek.status != 'Open':
            return api_error('Only open treks can be booked.')
        if trek.available_slots <= 0:
            return api_error('No slots are available.')
        existing = Booking.query.filter_by(user_id=current_user.id, trek_id=trek.id).first()
        if existing:
            if existing.status == 'Cancelled':
                existing.status = 'Booked'
                existing.booking_date = datetime.utcnow()
            else:
                return api_error('You have already booked this trek.')
        else:
            db.session.add(Booking(user_id=current_user.id, trek_id=trek.id, status='Booked'))
        trek.available_slots -= 1
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return api_error('Duplicate booking is not allowed.')
        invalidate_trek_cache()
        return jsonify({'ok': True, 'message': 'Trek booked successfully.'})

    @app.get('/api/bookings/mine')
    @role_required('user')
    def my_bookings():
        rows = Booking.query.filter_by(user_id=current_user.id).order_by(Booking.booking_date.desc()).all()
        return jsonify({'ok': True, 'bookings': [b.to_dict() for b in rows]})

    @app.post('/api/bookings/<int:booking_id>/cancel')
    @role_required('user')
    def cancel_booking(booking_id):
        booking = db.session.get(Booking, booking_id)
        if not booking or booking.user_id != current_user.id:
            return api_error('Booking not found.', 404)
        if booking.status != 'Booked':
            return api_error('Only booked reservations can be cancelled.')
        booking.status = 'Cancelled'
        booking.trek.available_slots = min(booking.trek.total_slots, booking.trek.available_slots + 1)
        db.session.commit()
        invalidate_trek_cache()
        return jsonify({'ok': True})

    @app.get('/api/notifications')
    @role_required('user', 'staff', 'admin')
    def notifications():
        rows = Notification.query.filter_by(user_id=current_user.id).order_by(Notification.created_at.desc()).limit(30).all()
        return jsonify({'ok': True, 'notifications': [n.to_dict() for n in rows]})

    @app.post('/api/exports')
    @role_required('user')
    def start_export():
        from tasks import export_booking_history
        job = ExportJob(user_id=current_user.id, status='Queued')
        db.session.add(job)
        db.session.commit()
        task = export_booking_history.delay(job.id)
        job.celery_task_id = task.id
        db.session.commit()
        return jsonify({'ok': True, 'job': job.to_dict()}), 202

    @app.get('/api/exports/<int:job_id>')
    @role_required('user')
    def export_status(job_id):
        job = db.session.get(ExportJob, job_id)
        if not job or job.user_id != current_user.id:
            return api_error('Export job not found.', 404)
        return jsonify({'ok': True, 'job': job.to_dict()})

    @app.get('/api/exports/<int:job_id>/download')
    @role_required('user')
    def download_export(job_id):
        job = db.session.get(ExportJob, job_id)
        if not job or job.user_id != current_user.id or job.status != 'Completed' or not job.filename:
            return api_error('Export file is not ready.', 404)
        return send_from_directory(Path(app.root_path) / 'exports', job.filename, as_attachment=True)

    @app.post('/api/admin/run-monthly-report')
    @role_required('admin')
    def run_monthly_report():
        from tasks import generate_monthly_report
        task = generate_monthly_report.delay()
        return jsonify({'ok': True, 'task_id': task.id}), 202


def seed_admin_and_sample_data(app):
    admin = User.query.filter_by(role='admin').first()
    if not admin:
        admin = User(name='TMA Admin', email=app.config['ADMIN_EMAIL'].lower(), role='admin', status='active')
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.add(admin)
        db.session.commit()

    if Trek.query.count() == 0:
        samples = [
            Trek(name='Saputara Sunrise Trek', location='Gujarat', difficulty='Easy', duration_days=2, total_slots=25, available_slots=25, status='Open', start_date=date.today().replace(day=min(28, date.today().day)) if False else date.today(), end_date=date.today(), description='A beginner-friendly trek with scenic sunrise views.'),
        ]
        # Keep sample data optional and valid; no sample trek is inserted to avoid past dates.


app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
