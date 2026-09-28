# -*- coding: utf-8 -*-
"""
Two kinds of online translation, both via the free MyMemory API, both optional
(YO_B_ONLINE_TRANSLATION=false disables both) and both wrapped in a short timeout
and a broad except: a slow or unreachable network must never hang a request or
crash the app.

1. lookup_online(word, target) — a best-effort fallback for a single Pidgin/
   Franc-anglais word Yo-B's own dictionary doesn't cover (translation.py's
   to_french/to_english directions). There's no public API that knows Yaoundé
   Pidgin, so the source language is *guessed* as the other real language —
   which is exactly why results need to be filtered hard: a wrong guess on an
   invented or slang word easily produces a fluent-looking but meaningless
   answer (e.g. "YO" -> "OJ"). See _MIN_MATCH_SINGLE_WORD below.

2. translate_sentence_online(text, source, target) — a normal, direct
   translation between two REAL languages (French <-> English) for
   translation.py's french_to_english/english_to_french directions. No
   guessing is involved here — both language codes are exactly what the user
   selected — so this is ordinary machine translation, not a dictionary
   fallback, and is held to a lighter quality bar.
"""

import logging

try:
    import requests
except ImportError:  # pragma: no cover - requests is in requirements.txt
    requests = None

logger = logging.getLogger(__name__)

_MYMEMORY_URL = "https://api.mymemory.translated.net/get"
_TARGET_CODE = {"french": "fr", "english": "en"}
# MyMemory has no "auto-detect" source language (a langpair like "auto|fr" is invalid
# and — critically — the API answers that with HTTP 200 and an *error explanation*
# sitting in responseData.translatedText, which looks exactly like a real translation
# unless it's specifically checked for). Since we don't know a lone word's source
# language, we guess it as the *other* language from the target.
_GUESSED_SOURCE = {"french": "en", "english": "fr"}

# Substrings MyMemory's own error/help text is known to contain — never treated as a
# real translation even if the HTTP call otherwise "succeeds".
_ERROR_MARKERS = (
    "invalid source language", "invalid target language", "langpair=",
    "iso 639", "rfc3066", "must specify", "no translation found",
)

# MyMemory's own confidence score for a single-word lookup with a *guessed* source
# language (0.0-1.0). Below this, results are frequently a wrong/unrelated word
# (e.g. "YO" -> "OJ", "QUOI" -> "QUOI ?") rather than an actual translation, so they
# are rejected exactly like a lexicon miss instead of being shown as an answer.
_MIN_MATCH_SINGLE_WORD = 0.6

# Below this length, MyMemory's translation-memory match score stops being a
# reliable signal at all: very short strings ("YO", "OK", "na") are frequently
# confused with unrelated abbreviations or chat-speak in whatever crowdsourced
# translation memory MyMemory draws from, and can come back with a *high*
# reported match despite being nonsense for our purposes (observed live: "YO"
# translated to "OJ"). Below this length, the lookup isn't attempted at all —
# no confidence score is trusted at this length, so there is nothing to check.
_MIN_LENGTH_FOR_ONLINE_LOOKUP = 3

_PUNCT_STRIP = " \t\n\r.,!?;:\"'()«»\u201c\u201d\u2019"


def _looks_like_api_error(text):
    lowered = text.lower()
    return any(marker in lowered for marker in _ERROR_MARKERS)


def _match_score(body):
    try:
        return float(body.get("responseData", {}).get("match", 0))
    except (TypeError, ValueError):
        return 0.0


def lookup_online(word, target, timeout_seconds=4.0):
    """Best-effort translation of a single word with a *guessed* source language.
    Returns None on any failure, low-confidence match, too-short input, or a
    response that isn't confidently a real translation — callers must treat that
    exactly like 'the dictionary has no entry either'."""
    if requests is None or not word or not word.strip():
        return None
    if len(word.strip()) < _MIN_LENGTH_FOR_ONLINE_LOOKUP:
        return None
    try:
        response = requests.get(
            _MYMEMORY_URL,
            params={"q": word, "langpair": _GUESSED_SOURCE[target] + "|" + _TARGET_CODE[target]},
            timeout=(2.0, timeout_seconds),
        )
        response.raise_for_status()
        body = response.json()
        if body.get("responseStatus") not in (200, "200"):
            return None
        translated = body.get("responseData", {}).get("translatedText")
        if not translated or not translated.strip():
            return None
        translated = translated.strip()
        if _looks_like_api_error(translated):
            logger.warning("online translation returned an API error string for %r -> %s: %s",
                            word, target, translated)
            return None
        if translated.strip(_PUNCT_STRIP).lower() == word.strip(_PUNCT_STRIP).lower():
            return None  # MyMemory echoed the input back (punctuation-insensitive)
        if len(translated) > 80:
            return None  # a one-word query answered with a paragraph is not a translation
        if _match_score(body) < _MIN_MATCH_SINGLE_WORD:
            logger.info("online translation for %r -> %s below confidence threshold: %r (match=%s)",
                        word, target, translated, body.get("responseData", {}).get("match"))
            return None
        return translated
    except Exception:
        logger.warning("online translation lookup failed for %r -> %s", word, target, exc_info=True)
        return None


def translate_sentence_online(text, source_lang, target_lang, timeout_seconds=6.0):
    """Direct whole-sentence translation between two REAL languages (source_lang and
    target_lang are exactly what the user picked — 'fr' or 'en' — never guessed).
    Returns None on any failure."""
    if requests is None or not text or not text.strip():
        return None
    try:
        response = requests.get(
            _MYMEMORY_URL,
            params={"q": text, "langpair": source_lang + "|" + target_lang},
            timeout=(2.0, timeout_seconds),
        )
        response.raise_for_status()
        body = response.json()
        if body.get("responseStatus") not in (200, "200"):
            return None
        translated = body.get("responseData", {}).get("translatedText")
        if not translated or not translated.strip():
            return None
        translated = translated.strip()
        if _looks_like_api_error(translated):
            logger.warning("online sentence translation returned an API error string for %r -> %s: %s",
                            source_lang, target_lang, translated)
            return None
        return translated
    except Exception:
        logger.warning("online sentence translation failed for %s -> %s", source_lang, target_lang, exc_info=True)
        return None
