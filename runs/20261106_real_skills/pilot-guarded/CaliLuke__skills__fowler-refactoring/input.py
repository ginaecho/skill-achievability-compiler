import re

def masked(text: str, name: str) -> str:
    """The text with the skill's own name and its parts replaced, lower-cased."""
    t = text.lower()
    for tok in sorted({name} | set(name.split("-")), key=len, reverse=True):
        if len(tok) >= 3:
            t = re.sub(r"\b" + re.escape(tok) + r"\b", "x", t)
    return t
