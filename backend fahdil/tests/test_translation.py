# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import translation
import online_translation


def test_forward_translation_to_french_uses_dictionary():
    result = translation.translate("Bendskin hala me small money", "to_french")
    words = {w["source"]: w for w in result["words"]}
    assert words["Bendskin"]["translation"] == "moto-taxi"
    assert words["Bendskin"]["status"] == "dictionary"
    assert result["used_online_fallback"] is False


def test_forward_translation_to_english_uses_dictionary():
    result = translation.translate("Taxi drop me for quartier", "to_english")
    assert "taxi" in result["translated_text"].lower()
    assert "neighborhood" in result["translated_text"].lower()


def test_on_pronoun_is_translated_not_flagged_unresolved():
    result = translation.translate("On go tchop", "to_english")
    words = {w["source"]: w for w in result["words"]}
    assert words["On"]["status"] == "dictionary"
    assert "one" in words["On"]["translation"].lower() or "we" in words["On"]["translation"].lower()


def test_quoi_is_translated_not_flagged_unresolved():
    result = translation.translate("On dit quoi", "to_english")
    words = {w["source"]: w for w in result["words"]}
    assert words["quoi"]["status"] == "dictionary"
    assert words["quoi"]["translation"].lower() == "what"


def test_common_french_function_words_are_covered():
    # A systematic audit found these extremely common French words entirely
    # missing from the dictionary (falling through to CODEMIX/"not found").
    # Each must now resolve as a real dictionary entry, not an online guess.
    words = ["qui", "où", "quand", "comment", "pourquoi", "combien", "bien",
              "très", "ici", "là", "ça", "oui", "non", "toujours", "jamais",
              "beaucoup", "peu", "tout", "rien", "maintenant", "après", "avant",
              "mais", "ou"]
    for word in words:
        assert word in translation.GLOSSARY, f"{word!r} missing from GLOSSARY"
        assert translation.GLOSSARY[word]["english"], f"{word!r} has no english gloss"


def test_yo_is_a_real_greeting_interjection_not_invented():
    # "yo" is attested informal greeting slang (parallel to the existing "wesh"),
    # not a random invented translation — it now has an honest dictionary entry.
    result = translation.translate("Yo", "to_english")
    assert result["words"][0]["status"] == "dictionary"
    assert "hey" in result["words"][0]["translation"].lower()


def test_unresolved_word_is_flagged_not_invented():
    result = translation.translate("blahblah quartier", "to_french")
    assert "blahblah" in result["unresolved_words"]
    words = {w["source"]: w for w in result["words"]}
    assert words["blahblah"]["status"] == "unresolved"
    assert words["blahblah"]["translation"] == "blahblah"


def test_reverse_translation_english_to_pidgin():
    result = translation.translate("the money for the road", "from_english")
    words = {w["source"]: w for w in result["words"]}
    assert words["money"]["translation"] == "argent"
    assert words["road"]["translation"] == "route"


def test_reverse_translation_french_to_pidgin():
    result = translation.translate("argent pour la route", "from_french")
    words = {w["source"]: w for w in result["words"]}
    assert words["argent"]["status"] == "dictionary"


def test_reverse_direction_never_uses_online_fallback():
    # Even if an online_lookup callable is supplied, the reverse direction must
    # never call it — no public API is trained on Yaoundé Pidgin as a target.
    calls = []
    def fake_lookup(word, target):
        calls.append(word)
        return "SHOULD-NOT-BE-USED"
    translation.translate("some unresolved word here", "from_english", online_lookup=fake_lookup)
    assert calls == []


def test_invalid_direction_raises():
    import pytest
    with pytest.raises(ValueError):
        translation.translate("hello", "sideways")


def test_french_to_english_uses_sentence_online_lookup():
    calls = []
    def fake_sentence_lookup(text, source, target):
        calls.append((text, source, target))
        return "I am going to the market"
    result = translation.translate("Je vais au marché", "french_to_english", sentence_online_lookup=fake_sentence_lookup)
    assert result["translated_text"] == "I am going to the market"
    assert result["used_online_fallback"] is True
    assert calls == [("Je vais au marché", "fr", "en")]


def test_english_to_french_uses_sentence_online_lookup():
    calls = []
    def fake_sentence_lookup(text, source, target):
        calls.append((text, source, target))
        return "Je vais au marché"
    result = translation.translate("I am going to the market", "english_to_french", sentence_online_lookup=fake_sentence_lookup)
    assert result["translated_text"] == "Je vais au marché"
    assert calls == [("I am going to the market", "en", "fr")]


def test_real_language_direction_without_lookup_is_unresolved():
    result = translation.translate("Je vais au marché", "french_to_english", sentence_online_lookup=None)
    assert result["used_online_fallback"] is False
    assert result["translated_text"] == "Je vais au marché"  # unchanged
    assert result["unresolved_words"] == ["Je vais au marché"]


def test_real_language_direction_lookup_failure_is_unresolved():
    result = translation.translate("Je vais au marché", "french_to_english", sentence_online_lookup=lambda *a: None)
    assert result["used_online_fallback"] is False
    assert result["words"][0]["status"] == "unresolved"


# --- online_translation.py: the bug fixed in this revision ----------------------

def test_online_lookup_rejects_known_api_error_text():
    error_text = (
        "'AUTO' IS AN INVALID SOURCE LANGUAGE . EXAMPLE: LANGPAIR=EN|IT USING 2 "
        "LETTER ISO OR RFC3066 LIKE ZH-CN. ALMOST ALL LANGUAGES SUPPORTED BUT SOME "
        "MAY HAVE NO CONTENT"
    )
    assert online_translation._looks_like_api_error(error_text) is True


def test_online_lookup_does_not_flag_a_plausible_translation():
    assert online_translation._looks_like_api_error("réclamer de l'argent") is False


def test_online_lookup_never_sends_auto_as_source_language():
    # The bug: langpair="auto|fr" is invalid and MyMemory answers with HTTP 200 and
    # its own error text embedded as the "translation". The fix guesses a real
    # source-language code instead of ever sending "auto".
    assert "auto" not in online_translation._GUESSED_SOURCE.values()
    assert online_translation._GUESSED_SOURCE["french"] in ("en", "fr")
    assert online_translation._GUESSED_SOURCE["english"] in ("en", "fr")


def test_online_lookup_rejects_low_confidence_match():
    # The second bug: even a well-formed, non-error response can be a wrong guess
    # (e.g. "YO" -> "OJ", "QUOI" -> "QUOI ?") when the source language was only
    # guessed. MyMemory's own match score catches this even when the text itself
    # looks like a plausible word.
    assert online_translation._match_score({"responseData": {"match": 0.2}}) == 0.2
    assert online_translation._match_score({"responseData": {}}) == 0.0
    assert online_translation._MIN_MATCH_SINGLE_WORD >= 0.5


def test_online_lookup_never_calls_network_for_very_short_words():
    # "YO" was observed live to translate to "OJ" with a reportedly high
    # confidence score from MyMemory — a two-letter chat-speak word is simply too
    # short for a translation-memory match score to mean anything, so it must be
    # rejected before any network call is even made (also saves the request).
    def _must_not_be_called(*args, **kwargs):
        raise AssertionError("requests.get must not be called for a too-short word")
    original_get = online_translation.requests.get
    online_translation.requests.get = _must_not_be_called
    try:
        assert online_translation.lookup_online("YO", "french") is None
        assert online_translation.lookup_online("ok", "english") is None
    finally:
        online_translation.requests.get = original_get
    assert len("YO") < online_translation._MIN_LENGTH_FOR_ONLINE_LOOKUP


def test_online_lookup_echo_check_is_punctuation_insensitive():
    # "QUOI" -> "QUOI ?" must be treated as an echo (same word, punctuation added),
    # not a real translation.
    stripped = "QUOI ?".strip(online_translation._PUNCT_STRIP).lower()
    assert stripped == "quoi"
