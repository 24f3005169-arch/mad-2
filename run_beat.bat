@echo off
celery -A celery_worker.celery beat --loglevel=info
pause
