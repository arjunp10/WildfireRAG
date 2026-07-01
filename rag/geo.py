"""Geographic helpers: state name/abbrev mapping and question geo-extraction."""
import re

# Full state name (lowercase) → 2-letter abbreviation
_STATE_NAMES: dict[str, str] = {
    'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
    'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
    'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
    'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
    'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
    'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
    'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
    'new hampshire': 'NH', 'new jersey': 'NJ', 'new mexico': 'NM', 'new york': 'NY',
    'north carolina': 'NC', 'north dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
    'oregon': 'OR', 'pennsylvania': 'PA', 'rhode island': 'RI', 'south carolina': 'SC',
    'south dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
    'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west virginia': 'WV',
    'wisconsin': 'WI', 'wyoming': 'WY',
}

# reverse_geocoder admin1 full name → abbreviation
ADMIN1_TO_ABBREV: dict[str, str] = {name.title(): abbrev for name, abbrev in _STATE_NAMES.items()}
# Fix multi-word states that .title() handles correctly already, but ensure edge cases:
ADMIN1_TO_ABBREV.update({
    'New Hampshire': 'NH', 'New Jersey': 'NJ', 'New Mexico': 'NM', 'New York': 'NY',
    'North Carolina': 'NC', 'North Dakota': 'ND', 'South Carolina': 'SC',
    'South Dakota': 'SD', 'West Virginia': 'WV', 'Rhode Island': 'RI',
})

_ALL_ABBREVS: set[str] = set(_STATE_NAMES.values())

# Region aliases → list of state abbreviations
_REGIONS: dict[str, list[str]] = {
    'northern california': ['CA'],
    'southern california': ['CA'],
    'norcal': ['CA'],
    'socal': ['CA'],
    'bay area': ['CA'],
    'pacific northwest': ['WA', 'OR'],
    'southwest': ['AZ', 'NM', 'NV', 'UT'],
    'rocky mountains': ['CO', 'WY', 'MT', 'ID'],
    'rockies': ['CO', 'WY', 'MT', 'ID'],
    'great plains': ['KS', 'NE', 'OK', 'TX', 'SD', 'ND'],
    'great basin': ['NV', 'UT', 'ID', 'OR'],
    'southeast': ['FL', 'GA', 'AL', 'MS', 'SC', 'NC', 'TN', 'VA'],
    'appalachian': ['NC', 'VA', 'TN', 'WV', 'KY'],
    'gulf coast': ['TX', 'LA', 'MS', 'AL', 'FL'],
    'midwest': ['MN', 'WI', 'MI', 'OH', 'IN', 'IL', 'MO', 'IA'],
    'new england': ['ME', 'NH', 'VT', 'MA', 'RI', 'CT'],
}


def extract_geo(question: str) -> tuple[list[str], int | None]:
    """
    Extract US state abbreviations and a year (2000-2026) from a question string.
    Returns (sorted list of state abbrevs, year or None).
    """
    q = question.lower()
    states: set[str] = set()

    # Regional phrases (check longest first to avoid partial matches)
    for phrase, abbrevs in sorted(_REGIONS.items(), key=lambda x: -len(x[0])):
        if phrase in q:
            states.update(abbrevs)

    # Full state names
    for name, abbrev in _STATE_NAMES.items():
        if re.search(r'\b' + re.escape(name) + r'\b', q):
            states.add(abbrev)

    # 2-letter abbreviations in original (case-sensitive, word-boundary)
    for abbrev in _ALL_ABBREVS:
        if re.search(r'\b' + abbrev + r'\b', question):
            states.add(abbrev)

    # Year in range 2000-2026
    years = re.findall(r'\b(200[0-9]|201[0-9]|202[0-6])\b', question)
    year = int(years[0]) if years else None

    return sorted(states), year


def build_where(states: list[str], year: int | None) -> dict | None:
    """Build a ChromaDB where clause from extracted geo. Returns None if nothing to filter."""
    conditions = []
    if states:
        if len(states) == 1:
            conditions.append({'state': {'$eq': states[0]}})
        else:
            conditions.append({'state': {'$in': states}})
    if year is not None:
        conditions.append({'year': {'$eq': year}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {'$and': conditions}
