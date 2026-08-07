import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.core.config import settings

def send_verification_email(email_to: str, code: str) -> None:
    """Gửi email xác thực tài khoản qua SMTP.
    Hỗ trợ gửi HTML và tự động cấu hình TLS / SSL.
    Nếu chưa cấu hình SMTP, in mã xác thực ra console cho dev testing.
    """
    if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
        print(f"[SMTP WARNING] SMTP is not configured in .env. Mock verification code for {email_to} is {code}")
        return

    message = MIMEMultipart("alternative")
    message["Subject"] = f"Mã xác thực tài khoản Portal Gimasys: {code}"
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = email_to

    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
        <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
          <h2 style="color: #1a73e8; text-align: center;">Kích hoạt tài khoản Portal</h2>
          <p>Xin chào,</p>
          <p>Cảm ơn bạn đã đăng ký tài khoản tại <strong>Gimasys Intern Portal</strong>. Vui lòng sử dụng mã xác thực dưới đây để kích hoạt tài khoản của bạn:</p>
          <div style="text-align: center; margin: 30px 0;">
            <span style="font-size: 24px; font-weight: bold; letter-spacing: 5px; color: #fff; background-color: #1a73e8; padding: 10px 20px; border-radius: 5px; font-family: monospace;">{code}</span>
          </div>
          <p>Mã này có hiệu lực trong vòng 15 phút. Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email.</p>
          <hr style="border: 0; border-top: 1px solid #eee;" />
          <p style="font-size: 11px; color: #777; text-align: center;">© 2025 Công ty Cổ phần Công nghệ Gimasys. Bảo mật thông tin nội bộ.</p>
        </div>
      </body>
    </html>
    """
    part = MIMEText(html_content, "html", "utf-8")
    message.attach(part)

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT)
            if settings.SMTP_TLS:
                server.starttls()
        
        server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM or settings.SMTP_USER, email_to, message.as_string())
        server.quit()
        print(f"[SMTP] Verification email successfully sent to {email_to}")
    except Exception as e:
        print(f"[SMTP ERROR] Failed to send verification email to {email_to}: {str(e)}")
        raise RuntimeError(f"Gửi email xác thực thất bại: {str(e)}")
