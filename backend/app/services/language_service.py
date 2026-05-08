from __future__ import annotations

from collections.abc import Iterable
from typing import Any

LANGUAGE_LABELS_BY_CODE: dict[str, str] = {
    "af": "Afrikaans",
    "afr": "Afrikaans",
    "am": "Amharic",
    "amh": "Amharic",
    "ar": "Arabic",
    "ara": "Arabic",
    "az": "Azerbaijani",
    "aze": "Azerbaijani",
    "be": "Belarusian",
    "bel": "Belarusian",
    "bg": "Bulgarian",
    "bul": "Bulgarian",
    "bn": "Bengali",
    "ben": "Bengali",
    "bo": "Tibetan",
    "bod": "Tibetan",
    "tib": "Tibetan",
    "bs": "Bosnian",
    "bos": "Bosnian",
    "ca": "Catalan",
    "cat": "Catalan",
    "cs": "Czech",
    "ces": "Czech",
    "cze": "Czech",
    "cy": "Welsh",
    "cym": "Welsh",
    "wel": "Welsh",
    "da": "Danish",
    "dan": "Danish",
    "de": "German",
    "deu": "German",
    "ger": "German",
    "el": "Greek",
    "ell": "Greek",
    "gre": "Greek",
    "en": "English",
    "eng": "English",
    "es": "Spanish",
    "spa": "Spanish",
    "et": "Estonian",
    "est": "Estonian",
    "eu": "Basque",
    "eus": "Basque",
    "baq": "Basque",
    "fa": "Persian",
    "fas": "Persian",
    "per": "Persian",
    "fi": "Finnish",
    "fin": "Finnish",
    "fr": "French",
    "fra": "French",
    "fre": "French",
    "ga": "Irish",
    "gle": "Irish",
    "gl": "Galician",
    "glg": "Galician",
    "he": "Hebrew",
    "heb": "Hebrew",
    "hi": "Hindi",
    "hin": "Hindi",
    "hr": "Croatian",
    "hrv": "Croatian",
    "hu": "Hungarian",
    "hun": "Hungarian",
    "hy": "Armenian",
    "hye": "Armenian",
    "arm": "Armenian",
    "id": "Indonesian",
    "ind": "Indonesian",
    "is": "Icelandic",
    "isl": "Icelandic",
    "ice": "Icelandic",
    "it": "Italian",
    "ita": "Italian",
    "ja": "Japanese",
    "jpn": "Japanese",
    "ka": "Georgian",
    "kat": "Georgian",
    "geo": "Georgian",
    "kk": "Kazakh",
    "kaz": "Kazakh",
    "km": "Khmer",
    "khm": "Khmer",
    "ko": "Korean",
    "kor": "Korean",
    "la": "Latin",
    "lat": "Latin",
    "lo": "Lao",
    "lao": "Lao",
    "lt": "Lithuanian",
    "lit": "Lithuanian",
    "lv": "Latvian",
    "lav": "Latvian",
    "mn": "Mongolian",
    "mon": "Mongolian",
    "mr": "Marathi",
    "mar": "Marathi",
    "ms": "Malay",
    "msa": "Malay",
    "may": "Malay",
    "mul": "Multiple languages",
    "my": "Burmese",
    "mya": "Burmese",
    "bur": "Burmese",
    "ne": "Nepali",
    "nep": "Nepali",
    "nl": "Dutch",
    "nld": "Dutch",
    "dut": "Dutch",
    "no": "Norwegian",
    "nor": "Norwegian",
    "pl": "Polish",
    "pol": "Polish",
    "pt": "Portuguese",
    "por": "Portuguese",
    "ro": "Romanian",
    "ron": "Romanian",
    "rum": "Romanian",
    "ru": "Russian",
    "rus": "Russian",
    "sa": "Sanskrit",
    "san": "Sanskrit",
    "sk": "Slovak",
    "slk": "Slovak",
    "slo": "Slovak",
    "sl": "Slovenian",
    "slv": "Slovenian",
    "sq": "Albanian",
    "sqi": "Albanian",
    "alb": "Albanian",
    "sr": "Serbian",
    "srp": "Serbian",
    "sv": "Swedish",
    "swe": "Swedish",
    "sw": "Swahili",
    "swa": "Swahili",
    "ta": "Tamil",
    "tam": "Tamil",
    "te": "Telugu",
    "tel": "Telugu",
    "th": "Thai",
    "tha": "Thai",
    "tr": "Turkish",
    "tur": "Turkish",
    "uk": "Ukrainian",
    "ukr": "Ukrainian",
    "und": "Undetermined",
    "ur": "Urdu",
    "urd": "Urdu",
    "uz": "Uzbek",
    "uzb": "Uzbek",
    "vi": "Vietnamese",
    "vie": "Vietnamese",
    "xh": "Xhosa",
    "xho": "Xhosa",
    "yi": "Yiddish",
    "yid": "Yiddish",
    "zh": "Chinese",
    "zho": "Chinese",
    "chi": "Chinese",
    "zu": "Zulu",
    "zul": "Zulu",
}
LANGUAGE_LABELS_BY_CODE.update(
    {label.casefold(): label for label in set(LANGUAGE_LABELS_BY_CODE.values())}
)


def _language_values(value: Any) -> Iterable[str]:
    values = value if isinstance(value, (list, tuple, set)) else [value]
    for item in values:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            yield text


def normalize_language_values(value: Any) -> list[str]:
    labels: list[str] = []
    seen: set[str] = set()

    for raw_value in _language_values(value):
        label = LANGUAGE_LABELS_BY_CODE.get(raw_value.casefold(), raw_value)
        label_key = label.casefold()
        if label_key in seen:
            continue
        seen.add(label_key)
        labels.append(label)

    return labels


def derive_b1g_language_values(record: dict[str, Any]) -> list[str]:
    existing_labels = normalize_language_values(record.get("b1g_language_sm"))
    if existing_labels:
        return existing_labels
    return normalize_language_values(record.get("dct_language_sm"))


def ensure_b1g_language(record: dict[str, Any]) -> dict[str, Any]:
    labels = derive_b1g_language_values(record)
    if labels:
        record["b1g_language_sm"] = labels
    return record
