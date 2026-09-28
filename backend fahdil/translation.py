# -*- coding: utf-8 -*-
"""
Word-for-word translator between Yaoundé Pidgin/Franc-anglais and French/English.

This is a transparent GLOSS reader, not a fluent machine-translation engine: each word
is looked up in a small curated dictionary and replaced in place, in the same order it
appeared. That keeps it honest about what it knows — a word this dictionary doesn't
cover is shown as such (and, optionally, sent to a free public translation API as a
best-effort fallback) rather than silently invented.

Two directions are supported:
  - FORWARD  (pidgin/francanglais -> french/english): tokenizes with the same lexer
    used for the lexical/syntactic analyzer, then looks up each token's gloss.
  - REVERSE  (french/english -> pidgin/francanglais): a plain word split, then a
    reverse lookup built once from the same glossary (so the two directions can never
    drift out of sync with each other).
"""

import re

import lexer

# ---------------------------------------------------------------------------
# The glossary: every word/phrase the lexer already recognizes, with its
# French and English meaning plus a short usage note for slang/pidgin terms
# (shown in the UI as the word's "meaning", the way a language analyzer would).
# ---------------------------------------------------------------------------

GLOSSARY = {
    # --- nouns ---
    "tchop":      {"french": "nourriture",              "english": "food"},
    "quartier":   {"french": "quartier",                "english": "neighborhood"},
    "bendskin":   {"french": "moto-taxi",                "english": "motorcycle taxi"},
    "taxi":       {"french": "taxi",                     "english": "taxi"},
    "moto":       {"french": "moto",                     "english": "motorcycle"},
    "chairman":   {"french": "chef / patron (familier)", "english": "boss / respected elder (informal)"},
    "madame":     {"french": "madame",                   "english": "madam / ma'am"},
    "essence":    {"french": "essence",                  "english": "fuel / petrol"},
    "courant":    {"french": "courant (électrique)",     "english": "electricity"},
    "réseau":     {"french": "réseau",                   "english": "network"},
    "reseau":     {"french": "réseau",                   "english": "network"},
    "pluie":      {"french": "pluie",                    "english": "rain"},
    "gendarme":   {"french": "gendarme",                 "english": "police officer"},
    "contrôle":   {"french": "contrôle (de police)",     "english": "checkpoint"},
    "controle":   {"french": "contrôle (de police)",     "english": "checkpoint"},
    "étudiant":   {"french": "étudiant",                 "english": "student"},
    "etudiant":   {"french": "étudiant",                 "english": "student"},
    "université": {"french": "université",               "english": "university"},
    "universite": {"french": "université",               "english": "university"},
    "prix":       {"french": "prix",                     "english": "price"},
    "route":      {"french": "route",                    "english": "road"},
    "argent":     {"french": "argent",                   "english": "money"},
    "école":      {"french": "école",                    "english": "school"},
    "ecole":      {"french": "école",                    "english": "school"},
    "voiture":    {"french": "voiture",                  "english": "car"},
    "car":        {"french": "voiture",                  "english": "car"},
    "road":       {"french": "route",                    "english": "road"},
    "bus":        {"french": "bus",                      "english": "bus"},
    "station":    {"french": "station",                  "english": "station"},
    "market":     {"french": "marché",                   "english": "market"},
    "marché":     {"french": "marché",                   "english": "market"},
    "marche":     {"french": "marché",                   "english": "market"},
    "drink":      {"french": "boisson",                  "english": "drink"},
    "money":      {"french": "argent",                   "english": "money"},
    "price":      {"french": "prix",                     "english": "price"},
    "morning":    {"french": "matin",                    "english": "morning"},

    # --- verbs ---
    "drop":   {"french": "déposer",                "english": "to drop off"},
    "hala":   {"french": "réclamer / interpeller",  "english": "to holler at / demand (slang)",
               "meaning": "used to insistently ask someone for money or attention"},
    "go":     {"french": "aller",                   "english": "to go"},
    "come":   {"french": "venir",                   "english": "to come"},
    "sabi":   {"french": "savoir / connaître",      "english": "to know / know how to",
               "meaning": "Pidgin verb of knowledge or skill"},
    "waka":   {"french": "marcher",                 "english": "to walk",
               "meaning": "Pidgin verb, also used for 'to go about / travel around'"},
    "dash":   {"french": "offrir / donner",         "english": "to give (as a gift)",
               "meaning": "Pidgin: to give something freely, often money"},
    "comot":  {"french": "sortir",                  "english": "to get out / leave",
               "meaning": "Pidgin form of 'come out'"},
    "spoil":  {"french": "gâter / abîmer",          "english": "to spoil / ruin"},
    "reduce": {"french": "réduire",                 "english": "to reduce"},
    "sell":   {"french": "vendre",                  "english": "to sell"},
    "stop":   {"french": "arrêter",                 "english": "to stop"},
    "wait":   {"french": "attendre",                "english": "to wait"},
    "work":   {"french": "travailler / fonctionner","english": "to work"},

    # --- aspect/auxiliary markers ---
    "dey": {"french": "être en train de",   "english": "is/are (-ing)",
            "meaning": "progressive aspect marker: attaches to the verb that follows it"},
    "don": {"french": "déjà",               "english": "already / has/have (done)",
            "meaning": "completive aspect marker: the action is finished"},
    "be":  {"french": "être",               "english": "to be"},
    "wan": {"french": "vouloir",            "english": "to want"},
    "fit": {"french": "pouvoir",            "english": "to be able to / can"},

    # --- slang / interjections ---
    "hmmm":  {"french": "hmmm",                         "english": "hmmm",
              "meaning": "interjection of thought or hesitation"},
    "garrr": {"french": "argh",                         "english": "argh",
              "meaning": "interjection of frustration"},
    "ekiee": {"french": "eh !",                         "english": "eh!",
              "meaning": "interjection of surprise"},
    "wesh":  {"french": "salut / quoi de neuf",          "english": "hey / what's up",
              "meaning": "casual greeting, borrowed slang"},
    "mola":  {"french": "mec / pote",                    "english": "dude / buddy",
              "meaning": "informal address term for a friend"},
    "nyanga": {"french": "élégance / frime",             "english": "style / showing off",
               "meaning": "used for someone dressing or acting flashy"},
    "wuna":  {"french": "vous (pluriel)",                "english": "you all / y'all",
              "meaning": "Pidgin second-person plural pronoun"},
    "sha":   {"french": "quand même / de toute façon",   "english": "anyway / still",
              "meaning": "emphasis particle placed at the end of a clause"},
    "abeg":  {"french": "s'il te plaît",                 "english": "please",
              "meaning": "Pidgin polite request marker"},
    "oh":    {"french": "oh",                            "english": "oh",
              "meaning": "emphatic interjection, common sentence-ender in Pidgin"},
    "small": {"french": "petit / un peu",                "english": "small / a little"},
    "quick": {"french": "vite",                          "english": "quick / fast"},
    "eh":    {"french": "eh",                            "english": "eh",
              "meaning": "interjection seeking agreement"},

    # --- determiners ---
    "the": {"french": "le / la / les", "english": "the"},
    "this": {"french": "ce / cette",   "english": "this"},
    "that": {"french": "ce / cette",   "english": "that"},
    "dis":  {"french": "ce / cette",   "english": "this", "meaning": "Pidgin form of 'this'"},
    "dat":  {"french": "ce / cette",   "english": "that", "meaning": "Pidgin form of 'that'"},
    "some": {"french": "quelques / du", "english": "some"},
    "a":    {"french": "un / une",     "english": "a"},
    "le":   {"french": "le",           "english": "the (masc.)"},
    "la":   {"french": "la",           "english": "the (fem.)"},
    "les":  {"french": "les",          "english": "the (plural)"},

    # --- pronouns ---
    "me":  {"french": "moi / me",         "english": "me"},
    "you": {"french": "tu / toi",         "english": "you"},
    "i":   {"french": "je",               "english": "I"},
    "we":  {"french": "nous",             "english": "we"},
    "dem": {"french": "ils / elles / eux","english": "they / them",
            "meaning": "Pidgin third-person plural pronoun"},
    "na":  {"french": "c'est",            "english": "it is / that's",
            "meaning": "Pidgin copula, used to emphasize what follows"},
    "on":  {"french": "on",               "english": "we / one",
            "meaning": "French impersonal pronoun, very common in Francanglais speech"},
    "quoi": {"french": "quoi",            "english": "what",
             "meaning": "French interrogative pronoun, common in questions like 'on dit quoi ?'"},
    "qui": {"french": "qui",              "english": "who"},

    # --- other common French function words (used verbatim in Francanglais) ---
    "où":        {"french": "où", "english": "where"},
    "quand":     {"french": "quand", "english": "when"},
    "comment":   {"french": "comment", "english": "how"},
    "pourquoi":  {"french": "pourquoi", "english": "why"},
    "combien":   {"french": "combien", "english": "how much / how many"},
    "bien":      {"french": "bien", "english": "well / good"},
    "très":      {"french": "très", "english": "very"},
    "ici":       {"french": "ici", "english": "here"},
    "là":        {"french": "là", "english": "there"},
    "ça":        {"french": "ça", "english": "that / it"},
    "oui":       {"french": "oui", "english": "yes"},
    "non":       {"french": "non", "english": "no"},
    "toujours":  {"french": "toujours", "english": "always / still"},
    "jamais":    {"french": "jamais", "english": "never"},
    "beaucoup":  {"french": "beaucoup", "english": "a lot / many"},
    "peu":       {"french": "peu", "english": "little / few"},
    "tout":      {"french": "tout", "english": "all / everything"},
    "rien":      {"french": "rien", "english": "nothing"},
    "maintenant": {"french": "maintenant", "english": "now"},
    "après":     {"french": "après", "english": "after / afterwards"},
    "avant":     {"french": "avant", "english": "before"},
    "aujourd'hui": {"french": "aujourd'hui", "english": "today"},

    # --- greetings / common interjections ---
    "yo":      {"french": "salut / hé", "english": "hey / yo",
                "meaning": "informal greeting interjection, common in Francanglais street speech"},
    "bonjour": {"french": "bonjour", "english": "hello / good morning"},
    "salut":   {"french": "salut", "english": "hi / bye (informal)"},
    "merci":   {"french": "merci", "english": "thank you"},

    # --- prepositions ---
    "for":   {"french": "pour / à", "english": "for / at"},
    "to":    {"french": "à",        "english": "to"},
    "from":  {"french": "de",       "english": "from"},
    "with":  {"french": "avec",     "english": "with"},
    "since": {"french": "depuis",   "english": "since"},

    # --- conjunctions ---
    "and":  {"french": "et",          "english": "and"},
    "but":  {"french": "mais",        "english": "but"},
    "or":   {"french": "ou",          "english": "or"},
    "then": {"french": "puis / alors","english": "then"},
    "mais": {"french": "mais",        "english": "but"},
    "ou":   {"french": "ou",          "english": "or"},

    # --- fixed phrases (kept as multiword keys, spaces included) ---
    "small money":     {"french": "un peu d'argent (souvent un pot-de-vin)",
                         "english": "a little money (often implying a bribe/tip)",
                         "meaning": "slang for a small, often informal, payment"},
    "no wahala":       {"french": "pas de problème", "english": "no problem"},
    "quick quick":     {"french": "très vite", "english": "very quickly"},
    "je wanda":        {"french": "je suis étonné(e)", "english": "I'm astonished / surprised"},
    "zero zero":       {"french": "instantanément", "english": "instantly / right away"},
    "zéro zéro":       {"french": "instantanément", "english": "instantly / right away"},
    "dey for front":   {"french": "être devant / en avance", "english": "to be ahead / in front"},
    "on est ensemble": {"french": "on est ensemble", "english": "we're together (in solidarity)",
                         "meaning": "a Cameroonian expression of shared hardship/solidarity"},
    "c'est how much":  {"french": "c'est combien", "english": "how much is it"},
    "c est how much":  {"french": "c'est combien", "english": "how much is it"},
}


def _clean_gloss_for_reverse_index(text):
    """Pull the single most useful word out of a gloss like 'le / la / les' or
    'chef / patron (familier)' so it can be a reverse-lookup key."""
    text = re.sub(r"\([^)]*\)", "", text)          # drop parenthetical notes
    first = re.split(r"[\/,]", text)[0].strip().lower()
    return first


def _build_reverse_index(field):
    index = {}
    for pidgin_word, entry in GLOSSARY.items():
        gloss = entry.get(field, "")
        if not gloss:
            continue
        key = _clean_gloss_for_reverse_index(gloss)
        if key and key not in index:
            index[key] = pidgin_word
    return index


FRENCH_TO_PIDGIN = _build_reverse_index("french")
ENGLISH_TO_PIDGIN = _build_reverse_index("english")

_WORD_RE = re.compile(r"[A-Za-zÀ-ÿ']+|[^\sA-Za-zÀ-ÿ]+")


def _split_words(text):
    """Plain word/punctuation split used for the reverse (into-Pidgin) direction,
    where there is no need for the full lexer's grammar-terminal classification."""
    return _WORD_RE.findall(text)


def _entry_for(word):
    return GLOSSARY.get(word.lower())


def translate_forward(text, target):
    """Pidgin/Franc-anglais -> french|english, using the same lexer as the analyzer."""
    tokens = lexer.tokenize(text)
    words = []
    unresolved = []
    for token in tokens:
        raw = token["token"]
        entry = _entry_for(raw)
        if entry and entry.get(target):
            words.append({
                "source": raw,
                "translation": entry[target],
                "meaning": entry.get("meaning", entry.get(target)),
                "status": "dictionary",
            })
        else:
            words.append({"source": raw, "translation": raw, "meaning": None, "status": "unresolved"})
            if token["category"] not in ("PUNCT", "NUMBER"):
                unresolved.append(raw)
    return words, unresolved


def translate_reverse(text, source_language):
    """french|english -> Pidgin/Franc-anglais, via the reverse index."""
    index = FRENCH_TO_PIDGIN if source_language == "french" else ENGLISH_TO_PIDGIN
    words = []
    unresolved = []
    for raw in _split_words(text):
        pidgin = index.get(raw.lower())
        if pidgin:
            entry = GLOSSARY.get(pidgin, {})
            words.append({
                "source": raw,
                "translation": pidgin,
                "meaning": entry.get("meaning", entry.get(source_language)),
                "status": "dictionary",
            })
        else:
            words.append({"source": raw, "translation": raw, "meaning": None, "status": "unresolved"})
            if re.match(r"^[A-Za-zÀ-ÿ']+$", raw):
                unresolved.append(raw)
    return words, unresolved


def render_sentence(words):
    return " ".join(w["translation"] for w in words)


_REAL_LANGUAGE_CODE = {"french": "fr", "english": "en"}


def translate(text, direction, online_lookup=None, sentence_online_lookup=None):
    """
    direction is one of:
      "to_french", "to_english"       — Pidgin/Franc-anglais -> a real language
      "from_french", "from_english"   — a real language -> Pidgin/Franc-anglais
      "french_to_english", "english_to_french" — direct translation between two
                                          real languages (no Pidgin involved at all)

    online_lookup(word, target_lang) -> str | None: a word-level fallback for the
    "to_*" directions, called only for a word Yo-B's own dictionary doesn't cover.
    sentence_online_lookup(text, source_code, target_code) -> str | None: a
    whole-sentence translator for the two real-language directions, where there is
    no dictionary at all — ordinary machine translation, not a Pidgin gloss.
    """
    if direction in ("french_to_english", "english_to_french"):
        source_lang, target_lang = direction.split("_to_")
        used_online = False
        if sentence_online_lookup is not None:
            translated = sentence_online_lookup(
                text, _REAL_LANGUAGE_CODE[source_lang], _REAL_LANGUAGE_CODE[target_lang]
            )
        else:
            translated = None
        if translated:
            used_online = True
            words = [{"source": text, "translation": translated, "meaning": None, "status": "online"}]
            unresolved = []
        else:
            words = [{"source": text, "translation": text, "meaning": None, "status": "unresolved"}]
            unresolved = [text]
        return {
            "source_text": text,
            "direction": direction,
            "translated_text": render_sentence(words),
            "words": words,
            "used_online_fallback": used_online,
            "unresolved_words": unresolved,
        }

    if direction == "to_french":
        words, unresolved = translate_forward(text, "french")
    elif direction == "to_english":
        words, unresolved = translate_forward(text, "english")
    elif direction == "from_french":
        words, unresolved = translate_reverse(text, "french")
    elif direction == "from_english":
        words, unresolved = translate_reverse(text, "english")
    else:
        raise ValueError("unknown direction: {}".format(direction))

    used_online = False
    if online_lookup is not None and direction in ("to_french", "to_english"):
        target = "french" if direction == "to_french" else "english"
        for word in words:
            if word["status"] != "unresolved":
                continue
            looked_up = online_lookup(word["source"], target)
            if looked_up:
                word["translation"] = looked_up
                word["meaning"] = looked_up
                word["status"] = "online"
                used_online = True
                if word["source"] in unresolved:
                    unresolved.remove(word["source"])

    return {
        "source_text": text,
        "direction": direction,
        "translated_text": render_sentence(words),
        "words": words,
        "used_online_fallback": used_online,
        "unresolved_words": list(dict.fromkeys(unresolved)),
    }
