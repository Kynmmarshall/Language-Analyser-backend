# -*- coding: utf-8 -*-
"""
Custom lexical analyzer for informal urban communication in Yaoundé.
Classifies tokens into: NOUN, VERB, DET, PRON, PREP, CONJ, SLANG, CODEMIX,
NUMBER, PUNCT, UNKNOWN.

This is a hand-written lexer (regex-based tokenizer + dictionary lookup),
built as an alternative to a LEX/FLEX specification, per the assignment's
"custom lexical analyzer in any programming language" option.
"""

import re

# ---------------------------------------------------------------------------
# 1. Lexical specification (regular expressions for token types)
# ---------------------------------------------------------------------------

# Multi-word phrases are matched FIRST (longest match), before single-word
# tokenization, so that expressions like "small money" or "no dey" are kept
# together as one lexical unit instead of being split into separate words.
PHRASES = {
    "small money":      "SLANG",
    "no wahala":        "SLANG",
    "quick quick":      "SLANG",
    "je wanda":         "SLANG",
    "zéro zéro":        "SLANG",
    "zero zero":        "SLANG",
    "dey for front":    "CODEMIX",
    "on est ensemble":  "CODEMIX",
    "c'est how much":   "CODEMIX",
    "c est how much":   "CODEMIX",
}

# Word-level dictionaries (lower-case). Order of the checks below matters:
# NOUN > VERB > DET > PRON > PREP > CONJ > SLANG > (fallback heuristics).
NOUNS = {
    "tchop", "quartier", "bendskin", "taxi", "moto", "chairman", "madame",
    "essence", "courant", "réseau", "reseau", "pluie", "gendarme",
    "contrôle", "controle", "étudiant", "etudiant", "université", "universite",
    "prix", "route", "argent", "école", "ecole", "voiture", "car", "road",
    "bus", "station", "market", "marché", "marche", "drink", "money", "price",
    "morning",
}

VERBS = {
    "drop", "hala", "go", "come", "sabi", "waka",
    "dash", "comot", "spoil", "reduce", "sell", "stop", "wait", "work",
}

# Pidgin aspect/auxiliary markers (progressive "dey", completive "don",
# copula "be", modal "wan"/"fit"): these attach to a following main verb
# rather than acting as the sentence's own verb, so they are tagged
# separately and are NOT mapped onto the VERB grammar terminal.
AUX_WORDS = {"dey", "don", "be", "wan", "fit"}

SLANG_WORDS = {
    "hmmm", "garrr", "zéro-zéro", "zero-zero", "ekiee", "wesh", "mola",
    "nyanga", "wuna", "sha", "abeg", "oh", "small", "quick", "eh",
    "yo", "bonjour", "salut", "merci",
}

DETERMINERS = {"the", "this", "that", "dis", "dat", "some", "a", "le", "la", "les"}
PRONOUNS = {"me", "you", "i", "we", "dem", "na", "on", "quoi", "qui", "this-one"}
PREPOSITIONS = {"for", "to", "from", "with", "since"}
CONJUNCTIONS = {"and", "but", "or", "then", "ou", "mais"}

FRENCH_HINTS = {
    "le", "la", "les", "de", "du", "des", "et", "est", "un", "une",
    "où", "quand", "comment", "pourquoi", "combien",
    "bien", "très", "ici", "là", "ça", "oui", "non",
    "toujours", "jamais", "beaucoup", "peu", "tout", "rien",
    "maintenant", "après", "avant", "aujourd'hui",
}
ENGLISH_HINTS = {"is", "are", "the", "and", "of", "to", "at"}

WORD_RE = re.compile(r"[A-Za-zÀ-ÿ']+|\d+(?:[.,]\d+)?|[^\sA-Za-zÀ-ÿ0-9]")
NUMBER_RE = re.compile(r"^\d+(?:[.,]\d+)?$")
PUNCT_RE = re.compile(r"^[^\sA-Za-zÀ-ÿ0-9]+$")


def _classify_word(word):
    w = word.lower()
    if NUMBER_RE.match(w):
        return "NUMBER"
    if PUNCT_RE.match(w):
        return "PUNCT"
    if w in NOUNS:
        return "NOUN"
    if w in VERBS:
        return "VERB"
    if w in AUX_WORDS:
        return "AUX"
    if w in DETERMINERS:
        return "DET"
    if w in PRONOUNS:
        return "PRON"
    if w in PREPOSITIONS:
        return "PREP"
    if w in CONJUNCTIONS:
        return "CONJ"
    if w in SLANG_WORDS:
        return "SLANG"
    if w in FRENCH_HINTS:
        return "FRENCH"
    if w in ENGLISH_HINTS:
        return "ENGLISH"
    # Unknown word: if it mixes accented (French-leaning) and plain ascii
    # patterns in the surrounding sentence this is typically code-mixing;
    # by default we tag it CODEMIX so it stands out for manual review.
    return "CODEMIX"


def _placeholder_letters(n):
    """Encode `n` (>=1) using only lowercase a-z, so the resulting placeholder is a
    single run of word characters and survives WORD_RE's tokenization unsplit (unlike
    a placeholder containing digits, which WORD_RE's separate NUMBER branch would
    fragment back out into multiple tokens)."""
    letters = ""
    while True:
        n, rem = divmod(n - 1, 26)
        letters = chr(97 + rem) + letters
        if n == 0:
            return letters


def tokenize(text):
    """
    Returns a list of {token, category, span} dicts.
    Step 1: replace known multi-word phrases with a single placeholder.
    Step 2: tokenize the remainder word-by-word / punctuation-by-punctuation.
    Step 3: classify every token via the dictionaries above.
    """
    if not text:
        return []

    working = text
    phrase_tags = {}
    placeholder_id = 0
    # Longest phrases first so overlapping shorter phrases don't win early.
    for phrase in sorted(PHRASES, key=len, reverse=True):
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        while pattern.search(working):
            placeholder_id += 1
            key = "xphrasemarkerx{}x".format(_placeholder_letters(placeholder_id))
            phrase_tags[key] = (pattern.search(working).group(0), PHRASES[phrase])
            working = pattern.sub(" {} ".format(key), working, count=1)

    raw_tokens = WORD_RE.findall(working)
    tokens = []
    for tok in raw_tokens:
        if tok in phrase_tags:
            surface, category = phrase_tags[tok]
            tokens.append({"token": surface, "category": category})
        else:
            tokens.append({"token": tok, "category": _classify_word(tok)})
    return tokens


def token_frequency(list_of_token_lists):
    """Aggregate token frequency and category variation across many sentences."""
    freq = {}
    category_counts = {}
    for tokens in list_of_token_lists:
        for t in tokens:
            key = t["token"].lower()
            freq[key] = freq.get(key, 0) + 1
            category_counts[t["category"]] = category_counts.get(t["category"], 0) + 1
    ranked = sorted(freq.items(), key=lambda kv: (-kv[1], kv[0]))
    return {
        "token_frequency": [{"token": k, "count": v} for k, v in ranked],
        "category_counts": category_counts,
    }
