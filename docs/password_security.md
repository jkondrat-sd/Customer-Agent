# Password Reset and Security

## Resetting Your Password

If you've forgotten your password:

1. Go to https://app.flowdesk.com/login
2. Click **Forgot Password?**
3. Enter the email address associated with your account
4. Check your inbox for a password reset email (arrives within 5 minutes)
5. Click the reset link — it expires after 1 hour
6. Enter your new password (minimum 12 characters, must include uppercase, lowercase, number, and special character)
7. Confirm the new password and log in

If you don't receive the reset email:
- Check your spam/junk folder
- Ensure you're using the correct email address
- Contact support@flowdesk.com if the issue persists

## Changing Your Password

To change your password while logged in:
1. Go to **Settings** → **Security** → **Change Password**
2. Enter your current password
3. Enter and confirm your new password
4. Click **Update Password**

## Two-Factor Authentication (2FA)

FlowDesk supports two-factor authentication for enhanced security.

### Setting Up 2FA
1. Go to **Settings** → **Security** → **Two-Factor Authentication**
2. Choose your preferred method:
   - **Authenticator App** (recommended): Scan the QR code with Google Authenticator, Authy, or Microsoft Authenticator
   - **SMS**: Enter your phone number to receive codes via text message
3. Enter the verification code to confirm setup
4. Save your backup codes in a secure location — these can be used if you lose access to your 2FA device

### 2FA Recovery
If you lose access to your 2FA device:
1. Use one of your saved backup codes to log in
2. Once logged in, go to **Settings** → **Security** to reconfigure 2FA
3. If you've lost your backup codes, contact support@flowdesk.com with identity verification (government-issued ID + account email confirmation)

## Session Management

- Sessions expire after 8 hours of inactivity
- You can view all active sessions under **Settings** → **Security** → **Active Sessions**
- Click **Revoke** next to any session to terminate it immediately
- Enterprise admins can enforce session policies (max duration, IP restrictions) for all team members

## Security Best Practices

- Use a unique password for your FlowDesk account — do not reuse passwords from other services
- Enable 2FA on all admin accounts
- Review active sessions weekly
- Report suspicious activity to security@flowdesk.com immediately
- Enterprise customers: enable SSO with enforced 2FA at the IdP level for maximum security
