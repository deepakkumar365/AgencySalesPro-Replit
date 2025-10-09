"""
Email Service Module for Agency Sales Pro
Handles all email sending functionality using SMTP
"""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Email service for sending emails via SMTP"""
    
    def __init__(self):
        """Initialize email service with configuration from environment variables"""
        self.smtp_host = os.environ.get('SMTP_HOST', 'smtp.gmail.com')
        self.smtp_port = int(os.environ.get('SMTP_PORT', '587'))
        self.smtp_username = os.environ.get('SMTP_USERNAME', '')
        self.smtp_password = os.environ.get('SMTP_PASSWORD', '')
        self.smtp_from_email = os.environ.get('SMTP_FROM_EMAIL', self.smtp_username)
        self.smtp_from_name = os.environ.get('SMTP_FROM_NAME', 'Agency Sales Pro')
        self.smtp_use_tls = os.environ.get('SMTP_USE_TLS', 'true').lower() == 'true'
        self.enabled = os.environ.get('EMAIL_ENABLED', 'false').lower() == 'true'
        
    def send_email(self, to_email, subject, body_html, body_text=None):
        """
        Send an email
        
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            body_html (str): HTML body content
            body_text (str, optional): Plain text body content (fallback)
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        if not self.enabled:
            logger.warning(f"Email service disabled. Would have sent email to {to_email} with subject: {subject}")
            return False
            
        if not self.smtp_username or not self.smtp_password:
            logger.error("SMTP credentials not configured. Cannot send email.")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.smtp_from_name} <{self.smtp_from_email}>"
            msg['To'] = to_email
            msg['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S +0000')
            
            # Attach plain text version (if provided)
            if body_text:
                part1 = MIMEText(body_text, 'plain')
                msg.attach(part1)
            
            # Attach HTML version
            part2 = MIMEText(body_html, 'html')
            msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.smtp_use_tls:
                    server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {str(e)}")
            return False
    
    def send_otp_email(self, to_email, otp, user_name=None):
        """
        Send OTP email for password reset
        
        Args:
            to_email (str): Recipient email address
            otp (str): One-time password
            user_name (str, optional): User's name for personalization
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        subject = "Password Reset OTP - Agency Sales Pro"
        
        # HTML body
        body_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background-color: #007bff; color: white; padding: 20px; text-align: center; }}
                .content {{ background-color: #f9f9f9; padding: 30px; border: 1px solid #ddd; }}
                .otp-box {{ background-color: #fff; border: 2px solid #007bff; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; margin: 20px 0; }}
                .footer {{ text-align: center; padding: 20px; font-size: 12px; color: #666; }}
                .warning {{ color: #dc3545; font-weight: bold; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Password Reset Request</h1>
                </div>
                <div class="content">
                    <p>Hello{' ' + user_name if user_name else ''},</p>
                    <p>You have requested to reset your password for your Agency Sales Pro account.</p>
                    <p>Your One-Time Password (OTP) is:</p>
                    <div class="otp-box">{otp}</div>
                    <p>This OTP is valid for <strong>10 minutes</strong>.</p>
                    <p class="warning">⚠️ If you did not request this password reset, please ignore this email and ensure your account is secure.</p>
                    <p>For security reasons, never share this OTP with anyone.</p>
                </div>
                <div class="footer">
                    <p>&copy; {datetime.utcnow().year} Agency Sales Pro. All rights reserved.</p>
                    <p>This is an automated email. Please do not reply.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Plain text version
        body_text = f"""
        Password Reset Request - Agency Sales Pro
        
        Hello{' ' + user_name if user_name else ''},
        
        You have requested to reset your password for your Agency Sales Pro account.
        
        Your One-Time Password (OTP) is: {otp}
        
        This OTP is valid for 10 minutes.
        
        If you did not request this password reset, please ignore this email and ensure your account is secure.
        
        For security reasons, never share this OTP with anyone.
        
        © {datetime.utcnow().year} Agency Sales Pro. All rights reserved.
        This is an automated email. Please do not reply.
        """
        
        return self.send_email(to_email, subject, body_html, body_text)


# Global email service instance
email_service = EmailService()