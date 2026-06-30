"""
parser.py
---------
Turns a free-text Telegram message into a structured transaction:

    {"amount": float, "category": str, "note": str, "type": "expense"|"income"}

Designed to be readable and easy to edit — all the keyword lists that drive
category guessing and income detection live in plain Python dicts/lists near
the top of the file, so you can add new merchants/keywords in seconds.

This module has ZERO external dependencies and zero network calls — it is
pure string processing, so it's trivial to unit test (see test_parser.py).
"""

import re

# ---------------------------------------------------------------------------
# 1. CATEGORY KEYWORDS  (edit freely — order matters: first match wins)
# ---------------------------------------------------------------------------
CATEGORY_KEYWORDS = {
    "travel": [
        "ola", "uber", "rapido", "metro", "auto", "petrol", "diesel", "fuel",
        "cab", "taxi", "bus", "train", "irctc", "flight", "indigo", "parking",
        "toll", "fastag",
    ],
    "food": [
        "swiggy", "zomato", "dinner", "lunch", "breakfast", "chai", "tea",
        "coffee", "restaurant", "dominos", "pizza", "burger", "starbucks",
        "ccd", "food", "snack", "biryani", "eatsure", "dhaba", "canteen",
    ],
    "groceries": [
        "blinkit", "zepto", "bigbasket", "instamart", "grocery", "groceries",
        "vegetables", "veggies", "milk", "dmart", "reliance fresh", "kirana",
    ],
    "clothes": [
        "myntra", "ajio", "zara", "h&m", "shirt", "jeans", "shoes", "tshirt",
        "t-shirt", "footwear", "clothes", "clothing", "apparel", "nike",
        "adidas", "lifestyle", "pantaloons",
    ],
    "rent": [
        "rent", "landlord", "lease", "maintenance", "society maintenance",
    ],
    "bills": [
        "electricity", "wifi", "broadband", "recharge", "mobile bill",
        "water bill", "gas bill", "dth", "internet", "jio", "airtel", "vi ",
        "phone bill", "credit card bill", "emi",
    ],
    "luxuries": [
        "netflix", "prime video", "hotstar", "spotify", "gym", "movie",
        "pvr", "inox", "bookmyshow", "luxury", "spa", "salon", "party",
        "club", "alcohol", "beer", "wine", "smoke", "cigarette",
    ],
    "investments": [
        "sip", "etf", "stocks", "mutual fund", "mf", "groww", "zerodha",
        "upstox", "investment", "invested", "rd", "fd", "ppf", "nps",
        "gold", "crypto", "bitcoin",
    ],
    "health": [
        "doctor", "medicine", "pharmacy", "hospital", "medical", "apollo",
        "clinic", "dentist", "checkup", "health", "insurance premium",
        "gym fee",
    ],
    "education": [
        "course", "udemy", "coursera", "tuition", "fees", "book", "books",
        "exam", "school", "college", "class", "education",
    ],
}

# fallback if nothing matches
DEFAULT_CATEGORY = "other"

# ---------------------------------------------------------------------------
# 2. INCOME KEYWORDS — if any of these appear, type = "income"
# ---------------------------------------------------------------------------
INCOME_KEYWORDS = [
    "salary", "refund", "cashback", "received", "credited", "credit",
    "got paid", "payout", "bonus", "interest credited", "reimbursement",
    "reimbursed", "income", "got",
]

# words to strip out of the note once the amount + currency markers are removed
FILLER_WORDS = {
    "rs", "rs.", "inr", "₹", "spent", "spend", "paid", "pay", "on", "for",
    "got", "received", "credited", "credit", "of", "a", "an", "the",
}

# ---------------------------------------------------------------------------
# 3. AMOUNT PARSING
# ---------------------------------------------------------------------------
# Matches things like: 500   1,250   1.5k   2l   2L   rs 500   ₹500   500rs
_AMOUNT_RE = re.compile(
    r"""
    (?:rs\.?\s*|₹\s*|inr\s*)?          # optional leading currency marker
    (?P<num>\d+(?:,\d{2,3})*(?:\.\d+)?)  # the number itself (with optional commas/decimals)
    \s*
    (?P<suffix>k|l|lac|lakh|lakhs|cr|crore)?  # optional magnitude suffix
    \s*
    (?:rs\.?|₹|inr)?                  # optional trailing currency marker
    """,
    re.IGNORECASE | re.VERBOSE,
)

_SUFFIX_MULTIPLIER = {
    "k": 1_000,
    "l": 100_000,
    "lac": 100_000,
    "lakh": 100_000,
    "lakhs": 100_000,
    "cr": 10_000_000,
    "crore": 10_000_000,
}


def _find_amount(text: str):
    """
    Scans the message for the best amount candidate.
    Returns (amount: float, matched_span: (start, end)) or (None, None).
    """
    best = None
    for m in _AMOUNT_RE.finditer(text):
        num_str = m.group("num")
        if not num_str:
            continue
        try:
            num = float(num_str.replace(",", ""))
        except ValueError:
            continue

        suffix = (m.group("suffix") or "").lower()
        multiplier = _SUFFIX_MULTIPLIER.get(suffix, 1)
        amount = num * multiplier

        if amount > 0:
            best = (amount, m.span())
            break
    return best if best else (None, None)


# ---------------------------------------------------------------------------
# 4. CATEGORY GUESSING
# ---------------------------------------------------------------------------
def _guess_category(text_lower: str) -> str:
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                return category
    return DEFAULT_CATEGORY


# ---------------------------------------------------------------------------
# 5. INCOME DETECTION
# ---------------------------------------------------------------------------
def _is_income(text_lower: str) -> bool:
    return any(kw in text_lower for kw in INCOME_KEYWORDS)


# ---------------------------------------------------------------------------
# 6. NOTE EXTRACTION — message minus the amount substring minus filler words
# ---------------------------------------------------------------------------
def _build_note(original_text: str, amount_span) -> str:
    text = original_text
    if amount_span:
        start, end = amount_span
        text = text[:start] + " " + text[end:]

    tokens = re.findall(r"[A-Za-z][A-Za-z']*", text)
    kept = [t for t in tokens if t.lower() not in FILLER_WORDS]

    note = " ".join(kept).strip()
    if not note:
        note = "misc"
    return note


# ---------------------------------------------------------------------------
# 7. PUBLIC ENTRY POINT
# ---------------------------------------------------------------------------
def parse_message(text: str):
    """
    Parse a free-text message into a transaction dict, or return None if no
    amount could be detected (caller should ask the user to clarify).
    """
    if not text or not text.strip():
        return None

    text = text.strip()
    text_lower = text.lower()

    amount, span = _find_amount(text)
    if amount is None:
        return None

    category = _guess_category(text_lower)
    txn_type = "income" if _is_income(text_lower) else "expense"
    if txn_type == "income":
        category = "income"

    note = _build_note(text, span)

    return {
        "amount": round(amount, 2),
        "category": category,
        "note": note,
        "type": txn_type,
    }


if __name__ == "__main__":
    samples = [
        "spent 500 on ola",
        "swiggy 420 dinner",
        "1.5k myntra shirt",
        "got salary 75000",
        "₹250 chai with friends",
        "2l investment in stocks",
        "rs 1,250 electricity bill",
        "500rs petrol",
        "received cashback 45",
    ]
    for s in samples:
        print(s, "->", parse_message(s))
