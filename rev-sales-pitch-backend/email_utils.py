import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os


def send_summary_email(to_email: str, from_email: str, summary_text: str):
    """
    Sends an email with the session summary using Gmail's SMTP server.
    """

    # Prepare the message
    message = MIMEMultipart()
    message["From"] = from_email
    message["To"] = to_email
    message["Subject"] = "Your RevPitch Conversation Summary"

    body = f"Hi there,\n\nHere's a summary of your conversation:\n\n{summary_text}\n\nCheers,\nTeam RevPitch"
    message.attach(MIMEText(body, "plain"))

    # Send the email
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(from_email, os.environ["EMAIL_PASSWORD"])
            server.sendmail(from_email, to_email, message.as_string())
            print(f"Summary email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}. Error: {e}")
