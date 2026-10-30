import secrets
import string

COMMON_PASSWORDS = {
    'admin123', 'password123', '12345678', '123456789', '1234567890',
    'admin', 'password', 'administrator', 'qwerty123', 'admin@123',
    'letmein123', 'welcome123', 'secret123', 'password1234', 'admin1234',
    'changeme', 'iloveyou', 'sunshine', 'princess', 'football'
}


def validate_admin_password(password, email=None, name=None):
    """
    Admin password policy:
    - Min 10 characters
    - Not equal to the email or name
    - Not in a small built-in list of common passwords
    """
    if not password:
        return False, "Admin password is required."

    pwd_lower = password.strip().lower()

    if pwd_lower in COMMON_PASSWORDS:
        return False, "Password is too common and easily guessable. Please choose a more complex password."

    if email:
        email_clean = email.strip().lower()
        email_user = email_clean.split('@')[0]
        if pwd_lower in (email_clean, email_user):
            return False, "Password cannot be equal to your email address."

    if name:
        name_clean = name.strip().lower()
        if pwd_lower == name_clean:
            return False, "Password cannot be equal to your name."
        for part in name_clean.split():
            if len(part) >= 3 and pwd_lower == part:
                return False, "Password cannot be equal to your name."

    if len(password) < 10:
        return False, "Admin password must be at least 10 characters long."

    return True, None


def generate_temp_password(length=14):
    """
    Generate a cryptographically secure random temporary password.
    Contains uppercase, lowercase, digits, and safe special characters.
    """
    chars = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = ''.join(secrets.choice(chars) for _ in range(length))
        # Ensure at least one uppercase, lowercase, digit, and symbol
        if (any(c.islower() for c in pwd) and
            any(c.isupper() for c in pwd) and
            any(c.isdigit() for c in pwd) and
            any(c in "!@#$%^&*" for c in pwd)):
            return pwd


def sanitize_csv_cell(val):
    """
    Prevent CSV formula injection:
    Any cell starting with =, +, -, @, tab (\t), or carriage return (\r) gets a leading apostrophe.
    """
    if val is None:
        return ''
    s = str(val)
    if s and s[0] in ('=', '+', '-', '@', '\t', '\r'):
        return "'" + s
    return s
