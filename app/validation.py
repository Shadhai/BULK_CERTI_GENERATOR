import re
from datetime import date, datetime, timedelta

MAX_NAME_LEN = 120
MAX_COURSE_LEN = 200
MAX_EMAIL_LEN = 320

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _clean(value: str) -> str:
    return _CONTROL_RE.sub("", value).strip()


def _parse_issue_date(raw) -> tuple[date | None, str | None]:
    """Return (parsed_date, error). Absent input is valid -> (None, None)."""
    if raw in (None, ""):
        return None, None
    if isinstance(raw, datetime):
        return raw.date(), None
    if isinstance(raw, date):
        return raw, None
    if isinstance(raw, str):
        raw = raw.strip()
        try:
            if "T" in raw:
                return datetime.fromisoformat(raw).date(), None
            return date.fromisoformat(raw), None
        except ValueError:
            return None, "issue_date is not a valid ISO date"
    return None, "issue_date must be a string in ISO format"


def validate_recipient(row: dict, index: int) -> tuple[dict | None, str | None]:
    """
    Row-level validation.

    Returns ``(clean_fields, None)`` on success, ``(None, reason)`` on failure.
    ``index`` is included purely for debugging symmetry with the caller.
    """
    if not isinstance(row, dict):
        return None, "recipient must be a JSON object"

    raw_name = row.get("name", row.get("recipient_name"))
    raw_email = row.get("email", row.get("recipient_email"))
    raw_course = row.get("course_name", row.get("course"))
    raw_date = row.get("issue_date")

    if not isinstance(raw_name, str) or not raw_name.strip():
        return None, "name is required"

    name = _clean(raw_name)
    if not name:
        return None, "name is required"
    if len(name) > MAX_NAME_LEN:
        return None, f"name exceeds {MAX_NAME_LEN} characters"

    email: str | None = None
    if raw_email not in (None, ""):
        if not isinstance(raw_email, str):
            return None, "email must be a string"
        email = _clean(raw_email)
        if len(email) > MAX_EMAIL_LEN:
            return None, f"email exceeds {MAX_EMAIL_LEN} characters"
        if not _EMAIL_RE.match(email):
            return None, "email is not a valid address"

    course: str | None = None
    if raw_course not in (None, ""):
        if not isinstance(raw_course, str):
            return None, "course_name must be a string"
        course = _clean(raw_course)
        if len(course) > MAX_COURSE_LEN:
            return None, f"course_name exceeds {MAX_COURSE_LEN} characters"

    issue, err = _parse_issue_date(raw_date)
    if err:
        return None, err

    if issue is not None:
        if issue.year < 1900:
            return None, "issue_date is too far in the past"
        # Bounded window: prevents absurd inputs from slipping through.
        if issue > (datetime.utcnow().date() + timedelta(days=365)):
            return None, "issue_date is too far in the future"

    return (
        {
            "recipient_name": name,
            "recipient_email": email,
            "course_name": course,
            "issue_date": issue,
        },
        None,
    )