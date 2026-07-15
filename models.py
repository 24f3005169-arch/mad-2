from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')  # admin/staff/user
    phone = db.Column(db.String(20))
    status = db.Column(db.String(20), nullable=False, default='active')  # active/blacklisted
    specialization = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    assigned_treks = db.relationship('Trek', back_populates='assigned_staff', foreign_keys='Trek.assigned_staff_id')
    bookings = db.relationship('Booking', back_populates='user', cascade='all, delete-orphan')
    notifications = db.relationship('Notification', back_populates='user', cascade='all, delete-orphan')
    export_jobs = db.relationship('ExportJob', back_populates='user', cascade='all, delete-orphan')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'role': self.role,
            'phone': self.phone or '',
            'status': self.status,
            'specialization': self.specialization or '',
            'created_at': self.created_at.isoformat(),
        }


class Trek(db.Model):
    __tablename__ = 'treks'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    location = db.Column(db.String(150), nullable=False)
    difficulty = db.Column(db.String(20), nullable=False)
    duration_days = db.Column(db.Integer, nullable=False)
    total_slots = db.Column(db.Integer, nullable=False)
    available_slots = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Pending')
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    description = db.Column(db.Text, default='')
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    assigned_staff = db.relationship('User', back_populates='assigned_treks', foreign_keys=[assigned_staff_id])
    bookings = db.relationship('Booking', back_populates='trek', cascade='all, delete-orphan')

    def to_dict(self, include_bookings=False):
        data = {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'difficulty': self.difficulty,
            'duration_days': self.duration_days,
            'total_slots': self.total_slots,
            'available_slots': self.available_slots,
            'status': self.status,
            'start_date': self.start_date.isoformat(),
            'end_date': self.end_date.isoformat(),
            'description': self.description or '',
            'assigned_staff_id': self.assigned_staff_id,
            'assigned_staff_name': self.assigned_staff.name if self.assigned_staff else None,
        }
        if include_bookings:
            data['bookings'] = [b.to_dict() for b in self.bookings]
        return data


class Booking(db.Model):
    __tablename__ = 'bookings'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    trek_id = db.Column(db.Integer, db.ForeignKey('treks.id'), nullable=False)
    booking_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    status = db.Column(db.String(20), nullable=False, default='Booked')
    payment_status = db.Column(db.String(20), nullable=False, default='Pending')

    user = db.relationship('User', back_populates='bookings')
    trek = db.relationship('Trek', back_populates='bookings')

    __table_args__ = (db.UniqueConstraint('user_id', 'trek_id', name='uq_user_trek_booking'),)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user.name if self.user else '',
            'trek_id': self.trek_id,
            'trek_name': self.trek.name if self.trek else '',
            'location': self.trek.location if self.trek else '',
            'start_date': self.trek.start_date.isoformat() if self.trek else '',
            'end_date': self.trek.end_date.isoformat() if self.trek else '',
            'booking_date': self.booking_date.isoformat(),
            'status': self.status,
            'payment_status': self.payment_status,
        }


class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    is_read = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    user = db.relationship('User', back_populates='notifications')

    def to_dict(self):
        return {
            'id': self.id,
            'message': self.message,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat(),
        }


class ExportJob(db.Model):
    __tablename__ = 'export_jobs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    celery_task_id = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default='Queued')
    filename = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)

    user = db.relationship('User', back_populates='export_jobs')

    def to_dict(self):
        return {
            'id': self.id,
            'status': self.status,
            'filename': self.filename,
            'created_at': self.created_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
        }
