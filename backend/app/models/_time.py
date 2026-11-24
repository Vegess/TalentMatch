import datetime


def utcnow() -> datetime.datetime:
    """Naive UTC timestamp (works the same on SQLite and Postgres)."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)
