"""Extract and normalize city from address payloads."""


def normalize_city_name(value: str) -> str:
    return (value or "").strip().lower()


def extract_city_from_address(address: dict | None) -> str:
    if not address:
        return ""
    for key in ("city", "locality", "town", "province", "state"):
        val = address.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""
