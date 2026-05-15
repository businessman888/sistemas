"""Conversão entre segundos e formato legível de timestamp."""


def seconds_to_timestamp(total_seconds: int | float) -> str:
    """Converte segundos numéricos para formato HH:MM:SS ou MM:SS."""
    total_seconds = int(total_seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def timestamp_to_seconds(timestamp: str) -> int:
    """Converte HH:MM:SS ou MM:SS para total de segundos."""
    parts = timestamp.split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return int(parts[0])
