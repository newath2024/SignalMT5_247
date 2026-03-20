import datetime as dt


def get_session_quality():
    utc_hour = dt.datetime.now(dt.timezone.utc).hour
    if 6 <= utc_hour < 10 or 12 <= utc_hour < 16:
        return 1.0, "London/New York active"
    if 5 <= utc_hour < 6 or 10 <= utc_hour < 12 or 16 <= utc_hour < 18:
        return 0.75, "Session transition"
    return 0.45, "Off-peak session"
