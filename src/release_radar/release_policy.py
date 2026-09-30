from datetime import date

from .models import ReleaseAnalysis


def release_state(release_date: str, release_status: str, today: date | None = None) -> str:
    """A mesma regra governa a publicacao e o estado exibido no painel."""
    if release_status == "released":
        return "released"
    try:
        day = date.fromisoformat(release_date)
    except ValueError:
        day = None
    today = today or date.today()
    if day is not None and day <= today:
        return "released"
    if release_status == "upcoming" or (day is not None and day > today):
        return "upcoming"
    return "unconfirmed"


def already_released(analysis: ReleaseAnalysis, today: date | None = None) -> bool:
    return release_state(analysis.release_date, analysis.release_status, today) == "released"


def confirmed_upcoming(analysis: ReleaseAnalysis, today: date | None = None) -> bool:
    return release_state(analysis.release_date, analysis.release_status, today) == "upcoming"
