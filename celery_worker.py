from celery import Celery, Task
from celery.schedules import crontab
from app import create_app

flask_app = create_app()


def make_celery(app):
    celery_app = Celery(
        app.import_name,
        broker=app.config['CELERY_BROKER_URL'],
        backend=app.config['CELERY_RESULT_BACKEND'],
    )
    celery_app.conf.update(
        timezone='Asia/Kolkata',
        enable_utc=False,
        beat_schedule={
            'daily-trek-reminders': {
                'task': 'tasks.send_daily_reminders',
                'schedule': crontab(hour=8, minute=0),
            },
            'monthly-admin-report': {
                'task': 'tasks.generate_monthly_report',
                'schedule': crontab(day_of_month=1, hour=9, minute=0),
            },
        },
    )

    class FlaskTask(Task):
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app.Task = FlaskTask
    return celery_app


celery = make_celery(flask_app)

import tasks  # noqa: E402,F401
