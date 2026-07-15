@echo off
celery -A celery_worker.celery worker --loglevel=info --pool=solo
pause
