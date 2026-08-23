from __future__ import annotations

import re


def _section_start(text: str, marker: str) -> int | None:
    pattern = re.compile(
        rf"(?im)^[^\S\r\n]*(?:[-*•]\s*)?(?:<[^>\n]+>)*[^\w@\r\n]{{0,16}}[^\S\r\n]*{re.escape(marker)}\b"
    )
    match = pattern.search(text)
    if match:
        return match.start()
    return None


def split_horoscope_by_participant(text: str, participants: list[str]) -> list[str]:
    clean_text = text.strip()
    if not clean_text:
        return []
    if not participants:
        return [clean_text]

    positions: list[tuple[int, str]] = []
    for participant in participants:
        marker = participant.strip()
        if not marker:
            continue
        start = _section_start(clean_text, marker)
        if start is not None:
            positions.append((start, marker))

    if len(positions) < 2:
        return [clean_text]

    positions.sort()
    title = clean_text[: positions[0][0]].strip()
    messages: list[str] = []
    for index, (start, _) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(clean_text)
        chunk = clean_text[start:end].strip()
        if not chunk:
            continue
        messages.append(f"{title}\n\n{chunk}".strip() if title else chunk)
    return messages or [clean_text]
