# -*- coding: utf-8 -*-
"""
Yo-B backend — Compiler Construction (CS4110) mini-project
Lexical and Syntactic Analysis of Informal Urban Communication in Yaoundé.

Run:
    pip install -r requirements.txt
    python app.py

Then open http://localhost:5000 in a browser (the frontend/ folder is
served automatically).
"""

import json
import os

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

import lexer
import grammar_utils
import parser_ll1
import translation
from online_translation import lookup_online, translate_sentence_online

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
FRONTEND_DIR = os.path.join(BASE_DIR, "..", "frontend")

ONLINE_TRANSLATION_ENABLED = os.environ.get("YO_B_ONLINE_TRANSLATION", "true").strip().lower() in (
    "1", "true", "yes", "on",
)
ONLINE_TRANSLATION_TIMEOUT = float(os.environ.get("YO_B_ONLINE_TRANSLATION_TIMEOUT", 4.0))

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def load_json(name):
    with open(os.path.join(DATA_DIR, name), "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(DATA_DIR, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_final_grammar():
    return load_json("grammar.json")["after_left_factoring"]


# ---------------------------------------------------------------------------
# frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


# ---------------------------------------------------------------------------
# 1. Data collection
# ---------------------------------------------------------------------------

@app.route("/api/statements", methods=["GET"])
def get_statements():
    return jsonify(load_json("statements.json"))


@app.route("/api/statements", methods=["POST"])
def add_statement():
    body = request.get_json(force=True) or {}
    text = (body.get("text") or "").strip()
    topic = (body.get("topic") or "Uncategorized").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400

    data = load_json("statements.json")
    next_id = max([s["id"] for s in data["statements"]], default=0) + 1
    data["statements"].append({"id": next_id, "topic": topic, "text": text})
    save_json("statements.json", data)
    return jsonify(data), 201


# ---------------------------------------------------------------------------
# 2. Lexical analysis
# ---------------------------------------------------------------------------

@app.route("/api/lexer/tokenize", methods=["POST"])
def lexer_tokenize():
    body = request.get_json(force=True) or {}
    text = body.get("text", "")
    return jsonify({"text": text, "tokens": lexer.tokenize(text)})


@app.route("/api/lexer/frequency", methods=["GET"])
def lexer_frequency():
    data = load_json("statements.json")
    all_tokens = [lexer.tokenize(s["text"]) for s in data["statements"]]
    return jsonify(lexer.token_frequency(all_tokens))


# ---------------------------------------------------------------------------
# 3. Syntactic analysis
# ---------------------------------------------------------------------------

@app.route("/api/grammar", methods=["GET"])
def grammar_stages():
    return jsonify(load_json("grammar.json"))


@app.route("/api/grammar/analysis", methods=["GET"])
def grammar_analysis():
    """FIRST sets, FOLLOW sets and the LL(1) parsing table for the final
    (left-recursion-removed, left-factored) grammar."""
    grammar = get_final_grammar()
    return jsonify(grammar_utils.analyze_grammar(grammar))


# ---------------------------------------------------------------------------
# 4. Parser
# ---------------------------------------------------------------------------

def _run_parser_on_text(text):
    grammar = get_final_grammar()
    analysis = grammar_utils.analyze_grammar(grammar)
    tokens = lexer.tokenize(text)
    terminals, skipped = grammar_utils.tag_sentence(tokens)
    result = parser_ll1.parse(grammar, analysis["table"], terminals)
    return {
        "text": text,
        "tokens": tokens,
        "terminals": terminals,
        "skipped_tokens": skipped,
        "accepted": result["accepted"],
        "error": result["error"],
        "error_type": result["error_type"],
        "error_params": result["error_params"],
        "trace": result["trace"],
    }


@app.route("/api/parser/parse", methods=["POST"])
def parser_parse():
    body = request.get_json(force=True) or {}
    text = body.get("text", "")
    if not text.strip():
        return jsonify({"error": "text is required"}), 400
    return jsonify(_run_parser_on_text(text))


@app.route("/api/parser/test-suite", methods=["GET"])
def parser_test_suite():
    data = load_json("statements.json")
    results = [_run_parser_on_text(s["text"]) for s in data["statements"]]
    accepted = sum(1 for r in results if r["accepted"])
    return jsonify({
        "total": len(results),
        "accepted": accepted,
        "rejected": len(results) - accepted,
        "results": results,
    })


# ---------------------------------------------------------------------------
# 5. Translator (Pidgin/Franc-anglais <-> French/English)
# ---------------------------------------------------------------------------

VALID_DIRECTIONS = {
    "to_french", "to_english", "from_french", "from_english",
    "french_to_english", "english_to_french",
}
# Directions with no Pidgin dictionary path at all — these are only possible when
# the online translator is available, since there is nothing else to fall back on.
ONLINE_ONLY_DIRECTIONS = {"french_to_english", "english_to_french"}


@app.route("/api/translate", methods=["POST"])
def translate_text():
    body = request.get_json(force=True) or {}
    text = (body.get("text") or "").strip()
    direction = body.get("direction", "")

    if not text:
        return jsonify({"error": "text is required"}), 400
    if direction not in VALID_DIRECTIONS:
        return jsonify({"error": "direction must be one of " + ", ".join(sorted(VALID_DIRECTIONS))}), 400
    if direction in ONLINE_ONLY_DIRECTIONS and not ONLINE_TRANSLATION_ENABLED:
        return jsonify({
            "error": "Direct French \u2194 English translation needs the online translator, "
                     "which is currently disabled on this server (YO_B_ONLINE_TRANSLATION=false)."
        }), 400

    online_lookup = None
    sentence_online_lookup = None
    if ONLINE_TRANSLATION_ENABLED:
        def online_lookup(word, target_lang):
            return lookup_online(word, target_lang, timeout_seconds=ONLINE_TRANSLATION_TIMEOUT)

        def sentence_online_lookup(sentence, source_code, target_code):
            return translate_sentence_online(sentence, source_code, target_code, timeout_seconds=ONLINE_TRANSLATION_TIMEOUT)

    result = translation.translate(
        text, direction, online_lookup=online_lookup, sentence_online_lookup=sentence_online_lookup
    )
    return jsonify(result)


# ---------------------------------------------------------------------------
# 6. Health (used by PM2/Nginx to check the process is alive)
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
