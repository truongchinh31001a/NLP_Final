from datetime import datetime, timedelta, timezone


def next_review_at(
    mastery_probability: float,
    confidence: float,
    now: datetime | None = None,
) -> str:
    anchor = now or datetime.now(timezone.utc)
    confidence_bonus = 1 if confidence >= 0.75 else 0

    if mastery_probability < 0.4:
        delta = timedelta(hours=12)
    elif mastery_probability < 0.65:
        delta = timedelta(days=1 + confidence_bonus)
    elif mastery_probability < 0.85:
        delta = timedelta(days=3 + confidence_bonus)
    else:
        delta = timedelta(days=7 + confidence_bonus)

    return (anchor + delta).replace(microsecond=0).isoformat()

