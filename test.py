import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders

# Email Credentials
EMAIL_ADDRESS = ""
EMAIL_PASSWORD = ""  # Use an App Password

# Recipient
TO_EMAIL = "iqbalarshaan1a1@gmail.com"

# Email Content
subject = "Hello! Here's your PDF"
body = "Please find the attached PDF document."

# Create Email Message
msg = MIMEMultipart()
msg["From"] = EMAIL_ADDRESS
msg["To"] = TO_EMAIL
msg["Subject"] = subject
msg.attach(MIMEText(body, "plain"))

# Attach PDF File
filename = "An_Intelligent_LLM-Powered_Personalized_Assistant_for_Digital_Banking_Using_LangGraph_and_Chain_of_Thoughts.pdf"  # Change to your PDF file name
filepath = f"E:\\major project\\project files\\An_Intelligent_LLM-Powered_Personalized_Assistant_for_Digital_Banking_Using_LangGraph_and_Chain_of_Thoughts.pdf"  # Change to the actual file path

try:
    with open(filepath, "rb") as attachment:
        part = MIMEBase("application", "octet-stream")
        part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", f"attachment; filename={filename}")
        msg.attach(part)

    # Send Email
    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.sendmail(EMAIL_ADDRESS, TO_EMAIL, msg.as_string())
        print("Email with PDF sent successfully!")

except Exception as e:
    print(f"Error: {e}")
