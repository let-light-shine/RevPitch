# email_utils.py
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging

def send_email(to_email: str, subject: str, body: str, attachment_path: str = None):
    """
    Send email using SMTP
    """
    try:
        # Email configuration from environment variables
        from_email = os.getenv("FROM_EMAIL")
        email_password = os.getenv("EMAIL_PASSWORD")
        
        if not from_email or not email_password:
            raise ValueError("Email credentials not found in environment variables")
        
        # Create message
        msg = MIMEMultipart()
        msg['From'] = from_email
        msg['To'] = to_email
        msg['Subject'] = subject
        
        # Add body to email
        msg.attach(MIMEText(body, 'plain'))
        
        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {os.path.basename(attachment_path)}'
                )
                msg.attach(part)
        
        # Gmail SMTP configuration
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(from_email, email_password)
        
        # Send email
        text = msg.as_string()
        server.sendmail(from_email, to_email, text)
        server.quit()
        
        logging.info(f"Email sent successfully to {to_email}")
        return True
        
    except Exception as e:
        logging.error(f"Failed to send email to {to_email}: {str(e)}")
        raise e

def send_summary_email(to_email: str, campaign_summary: dict):
    """
    Send campaign summary email
    """
    subject = f"Campaign Summary - {campaign_summary.get('sector', 'Unknown Sector')}"
    
    body = f"""
Campaign Summary Report

Sector: {campaign_summary.get('sector', 'N/A')}
Total Emails: {campaign_summary.get('total_emails', 0)}
Successful Sends: {campaign_summary.get('successful_sends', 0)}
Failed Sends: {campaign_summary.get('failed_sends', 0)}
Success Rate: {campaign_summary.get('success_rate', 0):.1f}%

Campaign completed at: {campaign_summary.get('completion_time', 'N/A')}

---
This is an automated summary from RevReach Agent.
"""
    
    return send_email(to_email, subject, body)

def validate_email_format(email: str) -> bool:
    """
    Basic email format validation
    """
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None