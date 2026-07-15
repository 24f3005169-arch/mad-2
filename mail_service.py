import smtplib
from email.mime.text import MIMEText
from pathlib import Path
from flask import current_app


def send_html_email(to_email, subject, html_body):
    host = current_app.config.get('SMTP_HOST')
    if not host:
        outbox = Path(current_app.root_path) / 'reports' / 'mail_outbox.log'
        outbox.parent.mkdir(exist_ok=True)
        with outbox.open('a', encoding='utf-8') as f:
            f.write(f"\nTO: {to_email}\nSUBJECT: {subject}\n{html_body}\n{'-'*70}\n")
        return False

    msg = MIMEText(html_body, 'html', 'utf-8')
    msg['Subject'] = subject
    msg['From'] = current_app.config['SMTP_FROM']
    msg['To'] = to_email
    with smtplib.SMTP(host, current_app.config['SMTP_PORT']) as server:
        if current_app.config['SMTP_USE_TLS']:
            server.starttls()
        if current_app.config['SMTP_USER']:
            server.login(current_app.config['SMTP_USER'], current_app.config['SMTP_PASSWORD'])
        server.send_message(msg)
    return True
