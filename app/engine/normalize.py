import re
import unicodedata


def normalized_text(value: str | None) -> str:
    if not value:
        return ""
    plain = unicodedata.normalize("NFKD", value)
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", plain.strip()).upper()
