from datetime import datetime, timezone, timedelta

try:
    from zoneinfo import ZoneInfo
    JAKARTA_TZ = ZoneInfo("Asia/Jakarta")
except Exception:
    JAKARTA_TZ = timezone(timedelta(hours=7), name="WIB")

INDONESIAN_MONTHS = [
    "",
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember"
]


def utc_now() -> datetime:
    """Return current UTC datetime with timezone info."""
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """Return current UTC datetime as ISO 8601 string."""
    return utc_now().isoformat()


def parse_utc_iso(iso_str: str) -> datetime:
    """Parse an ISO string to a timezone-aware UTC datetime."""
    if not iso_str:
        return utc_now()
    clean_str = iso_str.replace("Z", "+00:00")
    dt = datetime.fromisoformat(clean_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_wib(dt_or_iso: datetime | str | None) -> str:
    """Format UTC datetime or ISO string to Indonesian WIB format."""
    if dt_or_iso is None:
        return "-"
    if isinstance(dt_or_iso, str):
        try:
            dt = parse_utc_iso(dt_or_iso)
        except Exception:
            return dt_or_iso
    else:
        dt = dt_or_iso
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

    wib_dt = dt.astimezone(JAKARTA_TZ)
    month_name = INDONESIAN_MONTHS[wib_dt.month]
    time_str = wib_dt.strftime('%H:%M:%S')
    return f"{wib_dt.day} {month_name} {wib_dt.year}, {time_str} WIB"


def format_wib_short(dt_or_iso: datetime | str | None) -> str:
    """Short format for table displays."""
    if dt_or_iso is None:
        return "-"
    if isinstance(dt_or_iso, str):
        try:
            dt = parse_utc_iso(dt_or_iso)
        except Exception:
            return dt_or_iso
    else:
        dt = dt_or_iso
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

    wib_dt = dt.astimezone(JAKARTA_TZ)
    short_months = [
        "", "Jan", "Feb", "Mar", "Apr", "Mei", "Jun",
        "Jul", "Agu", "Sep", "Okt", "Nov", "Des"
    ]
    formatted_date = f"{wib_dt.day} {short_months[wib_dt.month]} {wib_dt.year}"
    return f"{formatted_date}, {wib_dt.strftime('%H:%M')}"
