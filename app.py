import hashlib
import io
import os
import re
import tempfile

import streamlit as st

try:
    from elevenlabs.client import ElevenLabs
except ImportError:
    ElevenLabs = None

try:
    from gtts import gTTS
except ImportError:
    gTTS = None

st.set_page_config(page_title="Saarthi AI", page_icon="🛺", layout="centered")

# ---------- Demo data (fictional, for prototype only) ----------
RIDE_OPTIONS = [
    {"provider": "Ride Option A (Demo)", "kind": "Auto", "fare": 120, "eta": 6},
    {"provider": "Ride Option B (Demo)", "kind": "Auto", "fare": 145, "eta": 4},
    {"provider": "Ride Option C (Demo)", "kind": "Cab", "fare": 210, "eta": 8},
]
DEMO_DRIVER = {"name": "Demo Driver", "vehicle": "Demo Auto", "number": "KA 00 AB 1234"}

TEXT = {
    "en": {
        "choose": "Choose your language",
        "ask": "Where do you want to go?",
        "type": "Type destination or say 'Option 1', 'Option 2', 'Option 3'",
        "speak": "Speak your destination or chosen option",
        "going": "Going to {dest}. Choose a ride option.",
        "opt_line": "Option {n}: {kind}, {fare} rupees, arrives in {eta} minutes.",
        "no_dest": "I could not understand the destination. Please try again.",
        "no_opt": "I did not catch which option you want. Please tap a button or say Option 1, Option 2, or Option 3.",
        "booked": ("Demo booking confirmed. Vehicle {number}, {vehicle}, driver {name}, "
                   "arrives in {eta} minutes. Fare {fare} rupees. This is test data, not a real booking."),
        "change": "Change language",
        "restart": "Start over",
        "bye": "Hi! Tell me where you want to go.",
        "cnt": "Voice recording needs a newer Streamlit version. Please type your request.",
        "tts_missing": "Voice output needs gTTS. Run: pip install gTTS",
        "choose_prompt": "Tap a button below, or speak/type 'Option 1', 'Option 2', or 'Option 3':",
    },
    "kn": {
        "choose": "ನಿಮ್ಮ ಭಾಷೆಯನ್ನು ಆರಿಸಿ",
        "ask": "ನೀವು ಎಲ್ಲಿಗೆ ಹೋಗಬೇಕು?",
        "type": "ಗಮ್ಯಸ್ಥಾನ ಅಥವಾ 'ಆಯ್ಕೆ 1', 'ಆಯ್ಕೆ 2', 'ಆಯ್ಕೆ 3' ಎಂದು ಟೈಪ್ ಮಾಡಿ",
        "speak": "ನಿಮ್ಮ ಗಮ್ಯಸ್ಥಾನ ಅಥವಾ ಆಯ್ಕೆಯನ್ನು ಹೇಳಿ",
        "going": "{dest} ಗೆ ಹೋಗಲಾಗುತ್ತದೆ. ಒಂದು ಆಯ್ಕೆ ಆರಿಸಿ.",
        "opt_line": "ಆಯ್ಕೆ {n}: {kind}, {fare} ರೂಪಾಯಿ, {eta} ನಿಮಿಷದಲ್ಲಿ ತಲುಪುತ್ತದೆ.",
        "no_dest": "ಗಮ್ಯಸ್ಥಾನ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಮತ್ತೆ ಪ್ರಯತ್ನಿಸಿ.",
        "no_opt": "ನಿಮ್ಮ ಆಯ್ಕೆ ಅರ್ಥವಾಗಲಿಲ್ಲ. ದಯವಿಟ್ಟು ಬಟನ್ ಒತ್ತಿ ಅಥವಾ ಆಯ್ಕೆ ಒಂದು, ಎರಡು, ಅಥವಾ ಮೂರು ಎಂದು ಹೇಳಿ.",
        "booked": ("ಡೆಮೊ ಬುಕಿಂಗ್ ದೃಢಪಟ್ಟಿದೆ. ವಾಹನ {number}, {vehicle}, ಚಾಲಕ {name}, "
                   "{eta} ನಿಮಿಷದಲ್ಲಿ ತಲುಪುತ್ತದೆ. ದರ {fare} ರೂಪಾಯಿ. ಇದು ಪರೀಕ್ಷಾ ಮಾಹಿತಿ."),
        "change": "ಭಾಷೆ ಬದಲಿಸಿ",
        "restart": "ಮತ್ತೆ ಪ್ರಾರಂಭಿಸಿ",
        "bye": "ನಮಸ್ಕಾರ! ನೀವು ಎಲ್ಲಿಗೆ ಹೋಗಬೇಕು ಹೇಳಿ.",
        "cnt": "ಧ್ವನಿ ಸೌಲಭ್ಯಕ್ಕೆ ಹೊಸ Streamlit ಆವೃತ್ತಿ ಬೇಕು. ದಯವಿಟ್ಟು ಟೈಪ್ ಮಾಡಿ.",
        "tts_missing": "ಧ್ವನಿ ಔಟ್‌ಪುಟ್‌ಗೆ gTTS ಬೇಕು. pip install gTTS ಎಂದು ಚಲಾಯಿಸಿ.",
        "choose_prompt": "ಕೆಳಗಿನ ಬಟನ್ ಒತ್ತಿ, ಅಥವಾ 'ಆಯ್ಕೆ 1', 'ಆಯ್ಕೆ 2', 'ಆಯ್ಕೆ 3' ಎಂದು ಹೇಳಿ:",
    },
}

# ---------- Session state ----------
defaults = {"lang": None, "messages": [], "options": [], "last_audio": None, "speak": None}
for k, v in defaults.items():
    st.session_state.setdefault(k, v)


def reset_trip():
    st.session_state.messages = []
    st.session_state.options = []
    st.session_state.last_audio = None
    st.session_state.speak = None


def destination_from(text):
    text = text.strip()
    patterns = [
        r"(?:go to|travel to|take me to|ride to|book (?:an? )?(?:auto|cab|ride)? ?to)\s+(.+)",
        r"^(.+?)\s*(?:ಗೆ|ಕ್ಕೆ)\s+(?:ಹೋಗ|ಬೇಕು)",
    ]
    for p in patterns:
        m = re.search(p, text, re.IGNORECASE)
        if m:
            return m.group(1).strip(" .?!,")
    return text.strip(" .?!,")


def parse_option_choice(text):
    """Match spoken/typed text in English or Kannada to an option index (0, 1, 2)."""
    t = text.lower().strip()

    # Check Option 1 / First / One (English & Kannada)
    if any(w in t for w in ["1", "one", "first", "option a", "ಒಂದು", "ಒಂದನೇ", "ಮೊದಲ", "೧"]):
        return 0
    # Check Option 2 / Second / Two
    if any(w in t for w in ["2", "two", "second", "option b", "ಎರಡು", "ಎರಡನೇ", "೨"]):
        return 1
    # Check Option 3 / Third / Three / Cab
    if any(w in t for w in ["3", "three", "third", "option c", "cab", "ಮೂರು", "ಮೂರನೇ", "ಕ್ಯಾಬ್", "೩"]):
        return 2
    # Fallback if user just says "Auto" / "ಆಟೋ" -> picks first Auto
    if any(w in t for w in ["auto", "ಆಟೋ"]):
        return 0

    return None


def transcribe(data, lang):
    try:
        import speech_recognition as sr
    except ImportError:
        st.error("Install speech_recognition: pip install SpeechRecognition")
        return ""
    recognizer = sr.Recognizer()
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        with sr.AudioFile(path) as source:
            audio = recognizer.record(source)
        code = "kn-IN" if lang == "kn" else "en-IN"
        return recognizer.recognize_google(audio, language=code)
    except sr.UnknownValueError:
        return ""
    except Exception as e:
        st.error(f"Could not process audio: {e}")
        return ""
    finally:
        os.remove(path)



def make_speech(text, lang):
    """Return MP3 bytes using ElevenLabs if configured, otherwise fall back to gTTS."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if ElevenLabs is not None and api_key:
        client = ElevenLabs(api_key=api_key)
        audio = client.text_to_speech.convert(
            text=text,
            voice_id="JBFqnCBsd6RMkjVDRZzb",  # George (supports multilingual models)
            model_id="eleven_v4",
            output_format="mp3_44100_128",
        )
        # audio may be an iterable/generator of byte chunks
        if isinstance(audio, (bytes, bytearray)):
            return bytes(audio)
        return b"".join(chunk for chunk in audio if isinstance(chunk, (bytes, bytearray)))

    if gTTS is None:
        return None
    buf = io.BytesIO()
    gTTS(text=text, lang=lang).write_to_fp(buf)
    return buf.getvalue()


def options_speech(lang):
    t = TEXT[lang]
    return " ".join(
        t["opt_line"].format(n=i + 1, kind=o["kind"], fare=o["fare"], eta=o["eta"])
        for i, o in enumerate(RIDE_OPTIONS)
    )


def book(opt):
    t = TEXT[st.session_state.lang]
    msg = t["booked"].format(number=DEMO_DRIVER["number"], vehicle=DEMO_DRIVER["vehicle"],
                             name=DEMO_DRIVER["name"], eta=opt["eta"], fare=opt["fare"])
    st.session_state.messages.append({"role": "assistant", "text": msg})
    st.session_state.options = []
    st.session_state.speak = msg


def handle_request(text):
    t = TEXT[st.session_state.lang]
    st.session_state.messages.append({"role": "user", "text": text})

    # If options are currently on screen, check if the user spoke/typed an option choice
    if st.session_state.options:
        idx = parse_option_choice(text)
        if idx is not None and 0 <= idx < len(st.session_state.options):
            book(st.session_state.options[idx])
            return
        else:
            # Repeat options prompt if they didn't clearly pick 1, 2, or 3
            st.session_state.messages.append({"role": "assistant", "text": t["no_opt"]})
            st.session_state.speak = t["no_opt"]
            return

    # Otherwise, treat the input as a destination request
    dest = destination_from(text)
    if not dest:
        st.session_state.messages.append({"role": "assistant", "text": t["no_dest"]})
        st.session_state.options = []
        st.session_state.speak = t["no_dest"]
        return

    going = t["going"].format(dest=dest)
    st.session_state.messages.append({"role": "assistant", "text": going})
    st.session_state.options = RIDE_OPTIONS
    st.session_state.speak = going + " " + options_speech(st.session_state.lang)


# ---------- Screen 1: language only ----------
if st.session_state.lang is None:
    st.title("Saarthi AI")
    st.subheader(TEXT["en"]["choose"] + " / " + TEXT["kn"]["choose"])
    c1, c2 = st.columns(2)
    if c1.button("English", use_container_width=True):
        st.session_state.lang = "en"
        st.rerun()
    if c2.button("ಕನ್ನಡ", use_container_width=True):
        st.session_state.lang = "kn"
        st.rerun()
    st.stop()

# ---------- Screen 2: one request box ----------
lang = st.session_state.lang
t = TEXT[lang]
st.title(t["ask"])

top1, top2 = st.columns(2)
if top1.button(t["change"], use_container_width=True):
    st.session_state.lang = None
    reset_trip()
    st.rerun()
if top2.button(t["restart"], use_container_width=True):
    reset_trip()
    st.rerun()

if not st.session_state.messages:
    st.info(t["bye"])

for m in st.session_state.messages:
    st.chat_message("user" if m["role"] == "user" else "assistant").write(m["text"])

# Ride options as buttons
if st.session_state.options:
    st.caption(t["choose_prompt"])
for i, opt in enumerate(st.session_state.options):
    label = f"Option {i+1}: {opt['kind']} · ₹{opt['fare']} · {opt['eta']} min · {opt['provider']}"
    if st.button(label, key=f"opt_{i}", use_container_width=True):
        book(opt)
        st.rerun()

# Spoken output: plays once per new message
if st.session_state.speak:
    speech = make_speech(st.session_state.speak, lang)
    if speech:
        st.audio(speech, format="audio/mp3", autoplay=True)
    else:
        st.warning(t["tts_missing"])
    st.session_state.speak = None

# Voice input (needs Streamlit with st.audio_input)
if hasattr(st, "audio_input"):
    st.caption(t["speak"])
    audio = st.audio_input(t["speak"], label_visibility="collapsed")
    if audio is not None:
        data = audio.getvalue()
        digest = hashlib.md5(data).hexdigest()
        if digest != st.session_state.last_audio:
            st.session_state.last_audio = digest
            text = transcribe(data, lang)
            if text:
                handle_request(text)
                st.rerun()
else:
    st.caption(t["cnt"])

# Single chat box
typed = st.chat_input(t["type"])
if typed:
    handle_request(typed)
    st.rerun()