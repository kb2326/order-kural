"""Every sentence the agent speaks about orders, bills, khata or answers is built here, by code, from facts the tools
returned. The AI never writes these, so the numbers it says are always the numbers that were saved.

Malayalam (ml-IN) and Kannada (kn-IN) templates: check with a native speaker."""
from __future__ import annotations

from app.domain.money import format_inr

LANGUAGES = ("ta-IN", "hi-IN", "ml-IN", "kn-IN", "en-IN")
DEFAULT = "ta-IN"


def lang(code: str | None) -> str:
    """Map any speech-to-text language code to one we speak; unknown languages get English."""
    if not code:
        return DEFAULT
    base = code.split("-")[0].lower()
    return next((l for l in LANGUAGES if l.startswith(base + "-")), "en-IN")


def money(paise: int) -> str:
    """₹26,552 when there are no paise, else ₹3,131.10."""
    text = format_inr(paise)
    return text[:-3] if text.endswith(".00") else text


T: dict[str, dict[str, str]] = {
    "staged": {
        "en-IN": "{customer}: {changes}. Order total {total}.{problems} Say sari to save.",
        "ta-IN": "{customer}: {changes}. மொத்தம் {total}.{problems} சேமிக்க சரி சொல்லுங்க.",
        "hi-IN": "{customer}: {changes}. कुल {total}.{problems} सेव करने के लिए हाँ बोलिए.",
        "ml-IN": "{customer}: {changes}. ആകെ {total}.{problems} സേവ് ചെയ്യാൻ ശരി എന്ന് പറയൂ.",
        "kn-IN": "{customer}: {changes}. ಒಟ್ಟು {total}.{problems} ಉಳಿಸಲು ಸರಿ ಎಂದು ಹೇಳಿ.",
    },
    "saved": {
        "en-IN": "Saved. {customer} order total {total}.",
        "ta-IN": "சேமிச்சாச்சு. {customer} ஆர்டர் மொத்தம் {total}.",
        "hi-IN": "सेव हो गया. {customer} का ऑर्डर कुल {total}.",
        "ml-IN": "സേവ് ചെയ്തു. {customer} ഓർഡർ ആകെ {total}.",
        "kn-IN": "ಉಳಿಸಲಾಗಿದೆ. {customer} ಆರ್ಡರ್ ಒಟ್ಟು {total}.",
    },
    "discarded": {
        "en-IN": "Cancelled. Nothing was saved.",
        "ta-IN": "ரத்து பண்ணிட்டேன். எதுவும் சேமிக்கல.",
        "hi-IN": "रद्द कर दिया. कुछ सेव नहीं हुआ.",
        "ml-IN": "റദ്ദാക്കി. ഒന്നും സേവ് ചെയ്തിട്ടില്ല.",
        "kn-IN": "ರದ್ದು ಮಾಡಿದೆ. ಏನೂ ಉಳಿಸಿಲ್ಲ.",
    },
    "nothing_pending": {
        "en-IN": "Nothing is waiting for sari.",
        "ta-IN": "சரி சொல்ல எதுவும் காத்திருக்கல.",
        "hi-IN": "हाँ बोलने के लिए कुछ बाकी नहीं है.",
        "ml-IN": "ശരി പറയാൻ ഒന്നും കാത്തിരിക്കുന്നില്ല.",
        "kn-IN": "ಸರಿ ಹೇಳಲು ಏನೂ ಬಾಕಿ ಇಲ್ಲ.",
    },
    "need_yes": {
        "en-IN": "Say sari to save, or cancel.",
        "ta-IN": "சேமிக்க சரி சொல்லுங்க, இல்லன்னா வேண்டாம் சொல்லுங்க.",
        "hi-IN": "सेव करने के लिए हाँ बोलिए, या रद्द कीजिए.",
        "ml-IN": "സേവ് ചെയ്യാൻ ശരി പറയൂ, അല്ലെങ്കിൽ വേണ്ട എന്ന് പറയൂ.",
        "kn-IN": "ಉಳಿಸಲು ಸರಿ ಎನ್ನಿ, ಇಲ್ಲವೇ ಬೇಡ ಎನ್ನಿ.",
    },
    "other_pending": {
        "en-IN": "First say sari or cancel for {customer}.",
        "ta-IN": "முதல்ல {customer} க்கு சரி இல்லன்னா வேண்டாம் சொல்லுங்க.",
        "hi-IN": "पहले {customer} के लिए हाँ या रद्द बोलिए.",
        "ml-IN": "ആദ്യം {customer} ന് ശരി അല്ലെങ്കിൽ വേണ്ട എന്ന് പറയൂ.",
        "kn-IN": "ಮೊದಲು {customer} ಗೆ ಸರಿ ಅಥವಾ ಬೇಡ ಎನ್ನಿ.",
    },
    "ask_customer": {
        "en-IN": "Which customer is this for?",
        "ta-IN": "இது எந்த கஸ்டமருக்கு?",
        "hi-IN": "यह किस कस्टमर के लिए है?",
        "ml-IN": "ഇത് ഏത് കസ്റ്റമറിനാണ്?",
        "kn-IN": "ಇದು ಯಾವ ಗ್ರಾಹಕರಿಗೆ?",
    },
    "ask_customer_near": {
        "en-IN": "Is this for {near}, or a new customer?",
        "ta-IN": "இது {near} க்கா, இல்ல புது கஸ்டமரா?",
        "hi-IN": "क्या यह {near} के लिए है, या नया कस्टमर?",
        "ml-IN": "ഇത് {near} ക്കാണോ, അതോ പുതിയ കസ്റ്റമറോ?",
        "kn-IN": "ಇದು {near} ಗೆ ಆ, ಅಥವಾ ಹೊಸ ಗ್ರಾಹಕರೇ?",
    },
    "bill_staged": {
        "en-IN": "GST invoice for {customer}, total {total} including GST. Say sari to make it.",
        "ta-IN": "{customer} க்கு GST பில், GST சேர்த்து மொத்தம் {total}. பில் போட சரி சொல்லுங்க.",
        "hi-IN": "{customer} का GST बिल, GST सहित कुल {total}. बिल बनाने के लिए हाँ बोलिए.",
        "ml-IN": "{customer} ന് GST ബിൽ, GST ഉൾപ്പെടെ ആകെ {total}. ബിൽ ഉണ്ടാക്കാൻ ശരി പറയൂ.",
        "kn-IN": "{customer} ಗೆ GST ಬಿಲ್, GST ಸೇರಿ ಒಟ್ಟು {total}. ಬಿಲ್ ಮಾಡಲು ಸರಿ ಎನ್ನಿ.",
    },
    "bill_saved": {
        "en-IN": "Bill {number} made, total {total}. Added to the khata.",
        "ta-IN": "பில் நம்பர் {number} போட்டாச்சு, மொத்தம் {total}. கணக்குல சேர்த்தாச்சு.",
        "hi-IN": "बिल नंबर {number} बन गया, कुल {total}. खाते में जोड़ दिया.",
        "ml-IN": "ബിൽ നമ്പർ {number} ആയി, ആകെ {total}. കണക്കിൽ ചേർത്തു.",
        "kn-IN": "ಬಿಲ್ ನಂಬರ್ {number} ಆಯಿತು, ಒಟ್ಟು {total}. ಖಾತೆಗೆ ಸೇರಿಸಲಾಗಿದೆ.",
    },
    "payment_staged": {
        "en-IN": "{customer} paid {amount} by {mode}. Say sari to save.",
        "ta-IN": "{customer} {mode} ல {amount} கொடுத்திருக்காங்க. சேமிக்க சரி சொல்லுங்க.",
        "hi-IN": "{customer} ने {mode} से {amount} दिए. सेव करने के लिए हाँ बोलिए.",
        "ml-IN": "{customer} {mode} വഴി {amount} തന്നു. സേവ് ചെയ്യാൻ ശരി പറയൂ.",
        "kn-IN": "{customer} {mode} ಮೂಲಕ {amount} ಕೊಟ್ಟಿದ್ದಾರೆ. ಉಳಿಸಲು ಸರಿ ಎನ್ನಿ.",
    },
    "payment_saved": {
        "en-IN": "Payment saved. {customer} still owes {balance}.",
        "ta-IN": "பணம் சேமிச்சாச்சு. {customer} இன்னும் {balance} தரணும்.",
        "hi-IN": "पेमेंट सेव हो गया. {customer} पर अभी {balance} बाकी है.",
        "ml-IN": "പണം സേവ് ചെയ്തു. {customer} ഇനി {balance} തരാനുണ്ട്.",
        "kn-IN": "ಹಣ ಉಳಿಸಲಾಗಿದೆ. {customer} ಇನ್ನೂ {balance} ಕೊಡಬೇಕು.",
    },
    "shipped_staged": {
        "en-IN": "Mark {customer} order as shipped{by}? Say sari.",
        "ta-IN": "{customer} ஆர்டர் அனுப்பியாச்சுன்னு{by} போடவா? சரி சொல்லுங்க.",
        "hi-IN": "{customer} का ऑर्डर भेज दिया{by}, ऐसा लिखूँ? हाँ बोलिए.",
        "ml-IN": "{customer} ഓർഡർ അയച്ചു{by} എന്ന് ചേർക്കട്ടെ? ശരി പറയൂ.",
        "kn-IN": "{customer} ಆರ್ಡರ್ ಕಳುಹಿಸಲಾಗಿದೆ{by} ಎಂದು ಹಾಕಲೇ? ಸರಿ ಎನ್ನಿ.",
    },
    "shipped_saved": {
        "en-IN": "{customer} order marked as shipped.",
        "ta-IN": "{customer} ஆர்டர் அனுப்பியாச்சுன்னு போட்டாச்சு.",
        "hi-IN": "{customer} का ऑर्डर भेजा गया, लिख दिया.",
        "ml-IN": "{customer} ഓർഡർ അയച്ചതായി ചേർത്തു.",
        "kn-IN": "{customer} ಆರ್ಡರ್ ಕಳುಹಿಸಲಾಗಿದೆ ಎಂದು ಹಾಕಲಾಗಿದೆ.",
    },
    "to_ship": {
        "en-IN": "{count} orders to ship: {names}.",
        "ta-IN": "அனுப்ப வேண்டியது {count} ஆர்டர்: {names}.",
        "hi-IN": "भेजने के लिए {count} ऑर्डर: {names}.",
        "ml-IN": "അയക്കാനുള്ളത് {count} ഓർഡർ: {names}.",
        "kn-IN": "ಕಳುಹಿಸಬೇಕಾದ {count} ಆರ್ಡರ್: {names}.",
    },
    "to_ship_none": {
        "en-IN": "Nothing is waiting to ship.",
        "ta-IN": "அனுப்ப வேண்டிய ஆர்டர் எதுவும் இல்ல.",
        "hi-IN": "भेजने के लिए कोई ऑर्डर नहीं है.",
        "ml-IN": "അയക്കാനുള്ള ഓർഡർ ഒന്നുമില്ല.",
        "kn-IN": "ಕಳುಹಿಸಬೇಕಾದ ಆರ್ಡರ್ ಯಾವುದೂ ಇಲ್ಲ.",
    },
    "customer_summary": {
        "en-IN": "{customer}: {lines} items in the open order. Balance {balance}.",
        "ta-IN": "{customer}: திறந்த ஆர்டர்ல {lines} ஐட்டம். பாக்கி {balance}.",
        "hi-IN": "{customer}: खुले ऑर्डर में {lines} आइटम. बाकी {balance}.",
        "ml-IN": "{customer}: തുറന്ന ഓർഡറിൽ {lines} ഐറ്റം. ബാക്കി {balance}.",
        "kn-IN": "{customer}: ತೆರೆದ ಆರ್ಡರ್‌ನಲ್ಲಿ {lines} ಐಟಂ. ಬಾಕಿ {balance}.",
    },
    "item_count": {
        "en-IN": "{item}: {quantity} pieces ordered in the last {days} days.",
        "ta-IN": "{item}: கடந்த {days} நாள்ல {quantity} பீஸ் ஆர்டர் வந்திருக்கு.",
        "hi-IN": "{item}: पिछले {days} दिनों में {quantity} पीस का ऑर्डर आया.",
        "ml-IN": "{item}: കഴിഞ്ഞ {days} ദിവസത്തിൽ {quantity} പീസ് ഓർഡർ വന്നു.",
        "kn-IN": "{item}: ಕಳೆದ {days} ದಿನಗಳಲ್ಲಿ {quantity} ಪೀಸ್ ಆರ್ಡರ್ ಬಂದಿದೆ.",
    },
    "problems": {
        "en-IN": "{customer}: {problems_text}. Nothing was added. Please say it again.",
        "ta-IN": "{customer}: {problems_text}. எதுவும் சேர்க்கல. திரும்ப சொல்லுங்க.",
        "hi-IN": "{customer}: {problems_text}. कुछ नहीं जोड़ा. फिर से बोलिए.",
        "ml-IN": "{customer}: {problems_text}. ഒന്നും ചേർത്തില്ല. വീണ്ടും പറയൂ.",
        "kn-IN": "{customer}: {problems_text}. ಏನೂ ಸೇರಿಸಿಲ್ಲ. ಮತ್ತೆ ಹೇಳಿ.",
    },
    "no_open_order": {
        "en-IN": "There is no open order for {customer}.",
        "ta-IN": "{customer} க்கு திறந்த ஆர்டர் எதுவும் இல்ல.",
        "hi-IN": "{customer} का कोई खुला ऑर्डर नहीं है.",
        "ml-IN": "{customer} ന് തുറന്ന ഓർഡർ ഒന്നുമില്ല.",
        "kn-IN": "{customer} ಗೆ ತೆರೆದ ಆರ್ಡರ್ ಇಲ್ಲ.",
    },
    "cannot_answer": {
        "en-IN": "I can answer: what is to ship, a customer's order or balance, and item counts.",
        "ta-IN": "நான் சொல்லக்கூடியது: அனுப்ப வேண்டியது, ஒரு கஸ்டமர் ஆர்டர் அல்லது பாக்கி, ஐட்டம் எண்ணிக்கை.",
        "hi-IN": "मैं बता सकता हूँ: क्या भेजना है, किसी कस्टमर का ऑर्डर या बाकी, और आइटम की गिनती.",
        "ml-IN": "എനിക്ക് പറയാനാകുന്നത്: അയക്കാനുള്ളത്, ഒരു കസ്റ്റമറുടെ ഓർഡർ അല്ലെങ്കിൽ ബാക്കി, ഐറ്റം എണ്ണം.",
        "kn-IN": "ನಾನು ಹೇಳಬಲ್ಲದು: ಕಳುಹಿಸಬೇಕಾದದ್ದು, ಗ್ರಾಹಕರ ಆರ್ಡರ್ ಅಥವಾ ಬಾಕಿ, ಐಟಂ ಎಣಿಕೆ.",
    },
}

PROBLEM_LABEL = {"en-IN": "Check", "ta-IN": "கவனிக்க", "hi-IN": "ध्यान दें", "ml-IN": "ശ്രദ്ധിക്കുക",
                 "kn-IN": "ಗಮನಿಸಿ"}
BY = {"en-IN": " by {t}", "ta-IN": " ({t})", "hi-IN": " ({t})", "ml-IN": " ({t})", "kn-IN": " ({t})"}


def render(kind: str, facts: dict, language: str) -> str:
    language = language if language in LANGUAGES else lang(language)
    f = dict(facts)
    if kind == "ask_customer" and f.get("near"):
        kind = "ask_customer_near"
    if kind == "to_ship" and not f.get("orders"):
        kind = "to_ship_none"
    if "total_paise" in f:
        f["total"] = money(f["total_paise"])
    if "amount_paise" in f:
        f["amount"] = money(f["amount_paise"])
    if "balance_paise" in f:
        f["balance"] = money(f["balance_paise"])
    if "changes" in f:
        f["changes"] = "; ".join(f["changes"])
    if kind == "problems":
        f["problems_text"] = "; ".join(f.get("problems") or [])
    if "problems" in f:
        f["problems"] = (f" {PROBLEM_LABEL[language]}: " + "; ".join(f["problems"]) + ".") if f["problems"] else ""
    if kind == "to_ship":
        f["count"] = len(f["orders"])
        f["names"] = ", ".join(o["customer"] for o in f["orders"])
    if kind == "customer_summary":
        f["lines"] = len(f["open_lines"])
    if kind == "shipped_staged":
        f["by"] = BY[language].format(t=f["transport"]) if f.get("transport") else ""
    if kind == "payment_staged":
        f["mode"] = (f.get("mode") or "cash").upper()
    return T[kind][language].format(**f)
