# rev-sales-pitch-backend/email_utils.py

import os
import smtplib
from email.message import EmailMessage

# Sends the end-of-campaign summary to your own inbox
def send_summary_email(to_email: str, from_email: str, summary: str):
    msg = EmailMessage()
    msg.set_content(summary)
    msg["Subject"] = "DevRev Campaign Summary"
    msg["From"] = from_email
    msg["To"] = to_email

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(from_email, os.environ["EMAIL_PASSWORD"])
        smtp.send_message(msg)

# Sends a single cold email to a lead
def send_email(recipient: str, subject: str, body: str):
    from_email = os.environ["FROM_EMAIL"]
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = recipient

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(from_email, os.environ["EMAIL_PASSWORD"])
        smtp.send_message(msg)
