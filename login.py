from __future__ import annotations

import os
from typing import Dict, Sequence, Tuple

ALLOWED_USN_PREFIXES: Sequence[str] = ("4pa23", "4pa24")
ALLOWED_EMAIL_DOMAIN = "@pace.edu.in"


def _read_secret(name: str, default: str) -> str:
    env_value = os.getenv(name, "").strip()
    if env_value:
        return env_value

    try:
        import streamlit as st

        secret_value = st.secrets.get(name)
        if secret_value:
            return str(secret_value).strip()

        admin_section = st.secrets.get("admin")
        if admin_section is not None and hasattr(admin_section, "get"):
            nested_value = admin_section.get(name.lower())
            if nested_value:
                return str(nested_value).strip()
    except Exception:
        pass

    return default


ADMIN_EMAIL = _read_secret("ADMIN_EMAIL", "faculty@college.edu").lower()
ADMIN_PASSWORD = _read_secret("ADMIN_PASSWORD", "admin123")


def get_admin_config_warning() -> str:
    if ADMIN_EMAIL == "faculty@college.edu" and ADMIN_PASSWORD == "admin123":
        return (
            "Admin credentials are using the built-in defaults. "
            "Set ADMIN_EMAIL and ADMIN_PASSWORD in Streamlit secrets before sharing the app publicly."
        )
    return ""


def validate_student_login(
    *,
    name: str,
    usn: str,
    email: str,
    allowed_prefixes: Sequence[str] = ALLOWED_USN_PREFIXES,
    allowed_email_domain: str = ALLOWED_EMAIL_DOMAIN,
) -> Tuple[bool, str, Dict[str, str]]:
    normalized_name = name.strip()
    normalized_usn = usn.strip().lower()
    normalized_email = email.strip().lower()

    if not normalized_name or not normalized_usn or not normalized_email:
        return False, "Please fill in name, USN, and college email.", {}

    if not any(normalized_usn.startswith(prefix) for prefix in allowed_prefixes):
        return False, f"USN must start with {' or '.join(allowed_prefixes)}.", {}

    if allowed_email_domain not in normalized_email:
        return False, f"Email must contain {allowed_email_domain}.", {}

    return True, "", {
        "name": normalized_name,
        "usn": normalized_usn,
        "email": normalized_email,
    }


def validate_admin_login(
    *,
    email: str,
    password: str,
    admin_email: str = ADMIN_EMAIL,
    admin_password: str = ADMIN_PASSWORD,
) -> Tuple[bool, str]:
    normalized_email = email.strip().lower()
    if normalized_email != admin_email or password != admin_password:
        return False, "Invalid admin credentials."
    return True, ""
