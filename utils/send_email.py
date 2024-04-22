import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
import logging

# Setting up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_secret(key):
    """Fetch secrets from streamlit secrets."""
    return st.secrets.get(key)

def create_email_body(subject, data):
    """Create the email body based on the subject and data."""
    if subject.startswith(("Error", "SMP")) or isinstance(data, str):
        return str(data)
    
    return f"""
        <html>
        <head>
            Please find {subject}.
        </head>
        <body>
            {data.to_html()}
        </body>
        </html>
    """

def send_email(receiver, subject, data):
    """Send an email to the given receiver with the given subject and data."""
    # Create email message
    mimemsg = MIMEMultipart()
    mimemsg['From'] = fetch_secret("OFFICE_USN")
    mimemsg['To'] = receiver
    mimemsg['Subject'] = subject
    
    # Attach the body
    body = create_email_body(subject, data)
    mimemsg.attach(MIMEText(body, 'html'))

    # Establish connection and send the email
    try:
        connection = smtplib.SMTP(host='smtp.office365.com', port=587)
        connection.starttls()
        connection.login(fetch_secret("OFFICE_USN"), fetch_secret("OFFICE_PSW"))
        connection.send_message(mimemsg)
        connection.quit()
        logging.info(f"Email sent successfully to {receiver} with subject: {subject}")
    except Exception as e:
        logging.error(f"Failed to send email to {receiver} with subject: {subject}. Error: {e}")

