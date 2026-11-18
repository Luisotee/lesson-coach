"""The languages the packs are translated into (PLAN, "Languages"), with the name the
translator is given. Wave 1 is Akelius's own languages; wave 2 adds the refugee settings."""

from __future__ import annotations

WAVE_1: dict[str, str] = {
    "ar": "Arabic (Modern Standard Arabic)",
    "fr": "French",
    "de": "German",
    "el": "Greek",
    "it": "Italian",
    "pt": "European Portuguese",
    "pt-BR": "Brazilian Portuguese",
    "ru": "Russian",
    "es": "Spanish",
    "sv": "Swedish",
    "pl": "Polish",
    "kk": "Kazakh (Cyrillic script)",
}

WAVE_2: dict[str, str] = {
    "uk": "Ukrainian",
    "tr": "Turkish",
    "fa": "Persian (Farsi)",
    "ur": "Urdu",
    "hi": "Hindi",
    "bn": "Bengali",
    "zh-Hans": "Simplified Chinese",
    "sw": "Swahili",
    "so": "Somali",
    "ti": "Tigrinya",
    "ps": "Pashto",
    "prs": "Dari (Afghan Persian)",
}

LANGUAGES: dict[str, str] = {**WAVE_1, **WAVE_2}
