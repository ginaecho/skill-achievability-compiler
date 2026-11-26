import re


def name_tokens(name: str) -> list[str]:
    """Return the unique name and hyphen-separated parts, longest first."""
    return sorted({name} | set(name.split("-")), key=len, reverse=True)


def masked(text: str, name: str) -> str:
    """Return text with matching name tokens masked after lower-casing."""
    t = text.lower()
    for tok in name_tokens(name):
        if len(tok) >= 3:
            t = re.sub(r"\b" + re.escape(tok) + r"\b", "x", t)
    return t
