import os
import smtplib
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

def send_summary_email(to_email: str, from_email: str, summary: str):
    msg = EmailMessage()
    msg.set_content(summary)
    msg["Subject"] = "DevRev Campaign Summary"
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(from_email, os.environ["EMAIL_PASSWORD"])
        smtp.send_message(msg)

def send_email(to_email: str, subject: str, body: str):
    msg = MIMEMultipart()
    from_email = os.environ['FROM_EMAIL']
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(from_email, os.environ['EMAIL_PASSWORD'])
    server.send_message(msg)
    server.quit()
