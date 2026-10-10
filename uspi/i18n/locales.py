"""i18n stub (architecture section 11.3: local-language, screen-reader
friendly warnings; section 12.2: per-language ECE slicing).
"""
from __future__ import annotations

DEFAULT_LOCALE = "en"

WARNING_OVERRIDES = {
    "en": {},
    "hi": {
        "tier2_warn": "कई जोखिम संकेतक यह सुझाव देते हैं कि यह धोखाधड़ी का प्रयास हो सकता है। "
        "OTP, पासवर्ड या पैसे साझा न करें, और स्वतंत्र रूप से सत्यापित करें।",
    },
}


def localize_warning(tier: str, default_text: str, locale: str = DEFAULT_LOCALE) -> str:
    return WARNING_OVERRIDES.get(locale, {}).get(tier, default_text)
