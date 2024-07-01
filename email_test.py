import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Email configuration
email_from = "ariennation@gmail.com"
email_to = "ariennation@gmail.com"  # You can test by sending an email to yourself
email_to = "arien.seghetti@ironbow.com" # You can test by sending an email to yourself
email_subject = "Test Email from Python Script"
email_body = "This is a test email sent from a Python script."

# Gmail SMTP server configuration
smtp_server = "smtp.gmail.com"
smtp_port = 587
email_password = "your-email-password"  # Replace with your Gmail app password

# Create email message
msg = MIMEMultipart()
msg['From'] = email_from
msg['To'] = email_to
msg['Subject'] = email_subject
msg.attach(MIMEText(email_body, 'plain'))

try:
    # Connect to Gmail SMTP server
    server = smtplib.SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(email_from, email_password)
    text = msg.as_string()
    server.sendmail(email_from, email_to, text)
    server.quit()
    print("Email sent successfully")
except Exception as e:
    print(f"Failed to send email: {e}")
