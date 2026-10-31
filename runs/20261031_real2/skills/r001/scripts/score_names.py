#!/usr/bin/env python3
"""
Brand Name Quality Scorer

Scores brand name candidates on multiple dimensions aligned with
the 100-point brand naming rubric:
  - Length and brevity (5 pts)
  - Pronounceability / CV pattern analysis (10 pts)
  - Syllable count (included in pronounceability)
  - Spellability / radio test (8 pts)
  - Memorability heuristics (12 pts)
  - Sound profile analysis (phoneme family classification)
  - Phonetic uniqueness (Metaphone/Soundex for conflict detection)

Usage:
    score_names.py <name> [<name>...]  [--json] [--compare NAME]

Examples:
    score_names.py acmevault pixelshift zentrade
    score_names.py myproject --compare competitor
    score_names.py brandname --json

Phonetic algorithms adapted from pyphonetics ([host-1]).
Sound symbolism rules derived from Klink (2000), Yorkston & Menon (2004).
"""

import argparse
import json
import re
import unicodedata
from itertools import groupby

# --- Metaphone Algorithm (ported from pyphonetics) ---

METAPHONE_RULES = [
    (r'[^a-z]', r''),
    (r'([bcdfhjklmnpqrstvwxyz])\1+', r'\1'),
    (r'^ae', r'E'),
    (r'^[gkp]n', r'N'),
    (r'^wr', r'R'),
    (r'^x', r'S'),
    (r'^wh', r'W'),
    (r'mb$', r'M'),
    (r'(?!^)sch', r'SK'),
    (r'th', r'0'),
    (r't?ch|sh', r'X'),
    (r'c(?=ia)', r'X'),
    (r'[st](?=i[ao])', r'X'),
    (r's?c(?=[iey])', r'S'),
    (r'[cq]', r'K'),
    (r'dg(?=[iey])', r'J'),
    (r'd', r'T'),
    (r'g(?=h[^aeiou])', r''),
    (r'gn(ed)?', r'N'),
    (r'([^g]|^)g(?=[iey])', r'\1J'),
    (r'g+', r'K'),
    (r'ph', r'F'),
    (r'([aeiou])h(?=\b|[^aeiou])', r'\1'),
    (r'[wy](?![aeiou])', r''),
    (r'z', r'S'),
    (r'v', r'F'),
    (r'(?!^)[aeiou]+', r''),
]


def metaphone(word: str) -> str:
    """Generate Metaphone phonetic code for a word."""
    word = unicodedata.normalize('NFKD', word).encode('ascii', 'ignore').decode('ascii')
    word = word.lower().strip()
    for pattern, replacement in METAPHONE_RULES:
        word = re.sub(pattern, replacement, word)
    return word.upper()


# --- Soundex Algorithm (ported from pyphonetics) ---

SOUNDEX_MAP = {}
_key = 'AEIOUYWHBPFVCSKGJQXZDTLMNR'
_val = '000000DD111122222222334556'
for k, v in zip(_key, _val):
    SOUNDEX_MAP[k] = v


def soundex(word: str) -> str:
    """Generate Soundex code for a word."""
    word = unicodedata.normalize('NFKD', word).encode('ascii', 'ignore').decode('ascii')
    word = re.sub(r'[^A-Za-z]', '', word).upper()
    if not word:
        return ''
    first = word[0]
    coded = ''.join(SOUNDEX_MAP.get(c, '') for c in word if SOUNDEX_MAP.get(c, '') != 'D')
    if coded and coded[0] == SOUNDEX_MAP.get(first, ''):
        coded = coded[1:]
    squeezed = ''.join(k for k, _ in groupby(coded))
    squeezed = squeezed.replace('0', '')
    return (first + squeezed + '0000')[:4]


# --- Levenshtein Distance ---

def levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein(s2, s1)
    if not s2:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


# --- Syllable Counting (heuristic for any word including invented) ---

def count_syllables(word: str) -> int:
    """Estimate syllable count using vowel cluster heuristic."""
    word = word.lower().strip()
    if not word:
        return 0
    # Count vowel groups
    count = len(re.findall(r'[aeiouy]+', word))
    # Adjust for silent-e at end
    if word.endswith('e') and not word.endswith('le') and count > 1:
        count -= 1
    # Adjust for common suffixes
    if word.endswith('ed') and not word.endswith(('ted', 'ded')) and count > 1:
        count -= 1
    return max(count, 1)


# --- Pronounceability Score ---

def pronounceability_score(word: str) -> float:
    """
    Score how pronounceable a word is (0.0 to 1.0).
    Based on consonant-vowel alternation patterns.
    Higher score = more pronounceable.
    """
    word = word.lower()
    if not word or not word.isalpha():
        return 0.0

    vowels = set('aeiouy')
    pattern = ''.join('V' if c in vowels else 'C' for c in word)

    # Penalize long consonant clusters (>3 consecutive consonants)
    long_clusters = re.findall(r'C{4,}', pattern)
    cluster_penalty = len(long_clusters) * 0.2

    # Reward CV alternation (ideal pronounceability pattern)
    transitions = sum(1 for i in range(len(pattern) - 1) if pattern[i] != pattern[i + 1])
    max_transitions = len(pattern) - 1
    alternation_score = transitions / max_transitions if max_transitions > 0 else 0

    # Penalize no vowels
    vowel_ratio = pattern.count('V') / len(pattern)
    if vowel_ratio < 0.15:
        return 0.1

    score = alternation_score - cluster_penalty
    # Bonus for starting with a consonant (natural in English)
    if pattern.startswith('C'):
        score += 0.05

    return max(0.0, min(1.0, score))


# --- Sound Profile Analysis (based on sound symbolism research) ---

FRONT_VOWELS = set('eiy')    # /i/, /ɪ/, /e/ — smallness, lightness, speed
BACK_VOWELS = set('oua')     # /u/, /o/, /ɑ/ — largeness, power, warmth
PLOSIVES = set('ptkbdg')     # strength, power, durability
FRICATIVES = set('fvszsj')   # smoothness, speed, sleekness ('j' for sh-like)
NASALS = set('mng')          # warmth, comfort, nurturing
LIQUIDS = set('lr')          # flow (l) or energy (r)
VOICELESS = set('ptkfs')     # refinement, quality
VOICED = set('bdgvz')        # strength, power


def sound_profile(word: str) -> dict:
    """Analyze the phoneme composition and classify brand sound attributes."""
    word = word.lower()
    letters = [c for c in word if c.isalpha()]
    if not letters:
        return {"cv_pattern": "", "attributes": []}

    vowels = set('aeiouy')
    cv = ''.join('V' if c in vowels else 'C' for c in letters)

    # Classify dominant sound families
    consonants = [c for c in letters if c not in vowels]
    vowel_chars = [c for c in letters if c in vowels]

    attrs = []
    if consonants:
        plosive_ratio = sum(1 for c in consonants if c in PLOSIVES) / len(consonants)
        fricative_ratio = sum(1 for c in consonants if c in FRICATIVES) / len(consonants)
        nasal_ratio = sum(1 for c in consonants if c in NASALS) / len(consonants)

        if plosive_ratio >= 0.5:
            attrs.append("strong/powerful")
        if fricative_ratio >= 0.5:
            attrs.append("smooth/fast")
        if nasal_ratio >= 0.5:
            attrs.append("warm/friendly")

    if vowel_chars:
        front_ratio = sum(1 for c in vowel_chars if c in FRONT_VOWELS) / len(vowel_chars)
        back_ratio = sum(1 for c in vowel_chars if c in BACK_VOWELS) / len(vowel_chars)

        if front_ratio >= 0.6:
            attrs.append("light/nimble")
        elif back_ratio >= 0.6:
            attrs.append("bold/substantial")

    # Detect special patterns
    if letters[0] in PLOSIVES:
        attrs.append("memorable-start")
    if any(letters[i] == letters[i+1] for i in range(len(letters)-1)):
        attrs.append("friendly (doubled letters)")

    # Check phonaesthemes
    w = word[:2]
    if w == 'gl':
        attrs.append("gl- (light/vision)")
    elif w == 'sw':
        attrs.append("sw- (smooth movement)")
    elif w == 'sn':
        attrs.append("sn- (quick movement)")
    elif w == 'cr':
        attrs.append("cr- (breaking/power)")

    if not attrs:
        attrs.append("neutral")

    return {
        "cv_pattern": cv,
        "attributes": attrs,
    }


# --- Spellability Score (radio test) ---

# Letter combinations that cause spelling confusion
CONFUSING_PATTERNS = [
    (r'ph', 'could be spelled with "f"'),
    (r'([^s])c(?=[iey])', '"c" could be "s"'),
    (r'ght', 'silent letters'),
    (r'ough', 'unpredictable pronunciation'),
    (r'([aeiou])\1', 'doubled vowels'),
    (r'ei|ie', 'i-before-e confusion'),
    (r'ck', 'could be just "k"'),
]


def spellability_score(word: str) -> float:
    """
    Score how easily someone can spell the name after hearing it once (0.0 to 1.0).
    Higher = easier to spell. Based on the 'radio test' concept.
    """
    word = word.lower()
    if not word or not word.isalpha():
        return 0.3

    score = 1.0

    # Penalize confusing letter patterns
    for pattern, _ in CONFUSING_PATTERNS:
        if re.search(pattern, word):
            score -= 0.1

    # Penalize numbers or special characters in the original
    if not word.isalpha():
        score -= 0.3

    # Penalize unusual/ambiguous spellings
    # Words with more than expected consonant clusters are harder
    clusters = re.findall(r'[^aeiouy]{3,}', word)
    score -= len(clusters) * 0.1

    # Bonus for simple, phonetically regular words
    if re.match(r'^([bcdfghjklmnpqrstvwxyz]?[aeiouy])+[bcdfghjklmnpqrstvwxyz]?$', word):
        score += 0.1  # perfectly regular CV pattern

    return max(0.0, min(1.0, round(score, 2)))


# --- Memorability Score ---

def memorability_score(word: str) -> float:
    """
    Estimate memorability (0.0 to 1.0).
    Based on research: initial plosives, alliteration, rhythm, and brevity
    increase recall. From brand naming rubric (12 pts / 100).
    """
    word = word.lower()
    if not word or not word.isalpha():
        return 0.3

    score = 0.5  # base

    # Initial plosive significantly increases recall
    if word[0] in PLOSIVES:
        score += 0.15

    # Alliteration / sound repetition (e.g., coca-cola, tiktok)
    if len(word) >= 4:
        # Check for repeated syllable-like patterns
        half = len(word) // 2
        if word[:half] == word[half:half*2]:
            score += 0.15
        # Check for repeated consonant sounds
        consonants = [c for c in word if c not in 'aeiouy']
        if consonants and consonants.count(consonants[0]) >= 2:
            score += 0.05

    # Brevity bonus (shorter = more memorable)
    if len(word) <= 5:
        score += 0.1
    elif len(word) <= 8:
        score += 0.05
    elif len(word) > 12:
        score -= 0.1

    # Concrete/simple letter combinations
    syllables = count_syllables(word)
    if syllables <= 2:
        score += 0.1
    elif syllables >= 4:
        score -= 0.1

    return max(0.0, min(1.0, round(score, 2)))


# --- Brand Name Scorer ---

def score_name(name: str, compare_to: list = None) -> dict:
    """Score a brand name on multiple quality dimensions aligned with the 100-point rubric."""
    result = {
        "name": name,
        "length": len(name),
        "syllables": count_syllables(name),
        "metaphone": metaphone(name),
        "soundex": soundex(name),
        "pronounceability": round(pronounceability_score(name), 2),
        "spellability": spellability_score(name),
        "memorability": memorability_score(name),
    }

    # Sound profile analysis
    profile = sound_profile(name)
    result["cv_pattern"] = profile["cv_pattern"]
    result["sound_attributes"] = profile["attributes"]

    # Length score (rubric: 5 pts): 4-8 chars ideal
    if 4 <= len(name) <= 8:
        result["length_score"] = 1.0
    elif len(name) < 4:
        result["length_score"] = round(max(0.4, 1.0 - (4 - len(name)) * 0.2), 2)
    elif len(name) <= 11:
        result["length_score"] = round(max(0.6, 1.0 - (len(name) - 8) * 0.1), 2)
    elif len(name) <= 15:
        result["length_score"] = 0.4
    else:
        result["length_score"] = 0.0

    # Syllable score: 1-2 ideal (trochee pattern), 3 acceptable
    syl = result["syllables"]
    if 1 <= syl <= 2:
        result["syllable_score"] = 1.0
    elif syl == 3:
        result["syllable_score"] = 0.8
    else:
        result["syllable_score"] = round(max(0.2, 1.0 - (syl - 3) * 0.2), 2)

    # Overall score (weighted to approximate 100-point rubric proportions)
    result["overall_score"] = round(
        result["memorability"] * 0.20 +        # memorability (12/100)
        result["pronounceability"] * 0.18 +     # pronounceability (10/100)
        result["spellability"] * 0.14 +          # spellability (8/100)
        result["length_score"] * 0.10 +          # length/brevity (5/100)
        result["syllable_score"] * 0.10 +        # syllable quality
        (0.18 if name.isalpha() and name.islower() else 0.09) +  # simplicity/cleanness
        0.10,  # base score for remaining qualitative criteria (assessed by Claude)
        2
    )

    # Phonetic similarity to comparison names
    if compare_to:
        conflicts = []
        for other in compare_to:
            m_dist = levenshtein(metaphone(name), metaphone(other))
            s_match = soundex(name) == soundex(other)
            if m_dist <= 1 or s_match:
                conflicts.append({
                    "name": other,
                    "metaphone_distance": m_dist,
                    "soundex_match": s_match,
                    "risk": "high" if m_dist == 0 else "medium",
                })
        if conflicts:
            result["phonetic_conflicts"] = conflicts

    return result


def format_markdown(results: list) -> str:
    """Format scoring results as markdown."""
    lines = [
        "| Name | Len | Syl | Pronounce | Spell | Memorize | Score | Metaphone |",
        "|------|-----|-----|-----------|-------|----------|-------|-----------|",
    ]

    for r in results:
        lines.append(
            f"| {r['name']} | {r['length']} | {r['syllables']} | "
            f"{r['pronounceability']} | {r['spellability']} | {r['memorability']} | "
            f"**{r['overall_score']}** | {r['metaphone']} |"
        )

    # Highlight best
    if len(results) > 1:
        best = max(results, key=lambda r: r['overall_score'])
        lines.append(f"\n**Top pick:** {best['name']} (score: {best['overall_score']})")

    # Sound profiles
    lines.append("\n**Sound profiles:**")
    for r in results:
        attrs = ", ".join(r.get("sound_attributes", ["—"]))
        lines.append(f"- **{r['name']}**: {attrs}")

    # Show any phonetic conflicts
    for r in results:
        if "phonetic_conflicts" in r:
            lines.append(f"\n**Phonetic conflicts for {r['name']}:**")
            for c in r["phonetic_conflicts"]:
                lines.append(f"- Sounds like \"{c['name']}\" (risk: {c['risk']})")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Score brand name quality")
    parser.add_argument("names", nargs="+", help="Brand name candidates to score")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON")
    parser.add_argument("--compare", nargs="*", default=[], help="Names to check phonetic conflicts against")

    args = parser.parse_args()
    compare = args.compare if args.compare else None

    results = [score_name(n, compare_to=compare) for n in args.names]

    if args.json_output:
        print(json.dumps(results, indent=2))
    else:
        print(format_markdown(results))


if __name__ == "__main__":
    main()
