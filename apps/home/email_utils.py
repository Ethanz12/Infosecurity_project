from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import logging

logger = logging.getLogger(__name__)

def send_2fa_code_email(user, code, ip_address=None):
    """Send 2FA code via email"""
    
    subject = 'SecureGov - Your Login Verification Code'
    
    # HTML email content
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background-color: #0A2342; color: white; padding: 20px; text-align: center; }}
            .content {{ background-color: #f8f9fa; padding: 30px; border-radius: 5px; margin-top: 20px; }}
            .code-box {{ background-color: white; border: 2px dashed #0A2342; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 8px; margin: 20px 0; }}
            .warning {{ background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0; }}
            .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 30px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔐 SecureGov Login Verification</h1>
            </div>
            
            <div class="content">
                <p>Hello <strong>{user.username}</strong>,</p>
                
                <p>You are attempting to log in to SecureGov. Please use the verification code below to complete your login:</p>
                
                <div class="code-box">
                    {code}
                </div>
                
                <p><strong>This code will expire in 5 minutes.</strong></p>
                
                {f'<p>Login attempt from IP: <code>{ip_address}</code></p>' if ip_address else ''}
                
                <div class="warning">
                    ⚠️ <strong>Security Notice:</strong> If you did not attempt to log in, please ignore this email and consider changing your password immediately.
                </div>
                
                <p>For security reasons, do not share this code with anyone.</p>
            </div>
            
            <div class="footer">
                <p>This is an automated message from SecureGov. Please do not reply to this email.</p>
                <p>&copy; 2026 SecureGov. All rights reserved.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    # Plain text version (fallback)
    plain_message = f"""
    SecureGov - Login Verification Code
    
    Hello {user.username},
    
    You are attempting to log in to SecureGov.
    
    Your verification code is: {code}
    
    This code will expire in 5 minutes.
    
    {f'Login attempt from IP: {ip_address}' if ip_address else ''}
    
    If you did not attempt to log in, please ignore this email and consider changing your password.
    
    Do not share this code with anyone.
    
    ---
    This is an automated message from SecureGov.
    """
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"2FA code sent to {user.email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send 2FA email to {user.email}: {e}")
        return False