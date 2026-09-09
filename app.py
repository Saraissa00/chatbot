import io
import os
import re
from pathlib import Path

import requests
from docx import Document
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from PyPDF2 import PdfReader
from pydantic import BaseModel

load_dotenv()  # reads API keys from a local .env file, so nobody has to type one in

app = FastAPI(title="Chatbot")
STATIC_DIR = Path(__file__).parent / "static"

STORE = {"filename": None, "text": None, "history": []}
MAX_HISTORY_TURNS = 10  # keep the last N user+assistant exchanges

# Tried in order. Each needs its matching *_API_KEY set in .env to be used —
# providers with no key configured are skipped. When one is rate-limited (429)
# or errors out, the next one in the list is tried automatically.
#
# The OpenRouter entry uses "models" (plural) — OpenRouter's own built-in
# fallback: it tries each model in that list itself before we ever see an
# error. Note this only helps when ONE specific model is overloaded — the
# free-tier request cap on OpenRouter is per ACCOUNT, not per model, so if
# your whole account hits its daily free limit, every OpenRouter model fails
# together and we fall through to the Groq entry below (a separate company,
# separate quota) instead.
#
# 26B-A4B confirmed from the user's own OpenRouter code sample. The 31B one
# is inferred from the same "-it" (instruction-tuned) naming pattern but not
# separately confirmed — check its API tab on openrouter.ai if it errors.
#
# Cerebras is the third, added as another separate company with its own free
# tier, for when BOTH OpenRouter and Groq are out for the day.
#
# NOTE: as of when this was set up, this Cerebras account returned "payment
# required" on every model except gemma-4-31b, which 404s outright (listed
# under GET /v1/models but not actually usable via chat completions). Add a
# payment method in the Cerebras billing tab to unlock gpt-oss-120b below —
# until then this fallback step will always fail, which is harmless (it's
# the last resort; OpenRouter and Groq above it are the ones doing the work).
PROVIDERS = [
    {
        "name": "OpenRouter",
        "env_var": "OPENROUTER_API_KEY",
        "url": "https://openrouter.ai/api/v1/chat/completions",
        "models": ["google/gemma-4-26b-a4b-it:free", "google/gemma-4-31b-it:free"],
    },
    {
        "name": "Groq",
        "env_var": "GROQ_API_KEY",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "models": ["openai/gpt-oss-20b"],
    },
    {
        "name": "Cerebras",
        "env_var": "CEREBRAS_API_KEY",
        "url": "https://api.cerebras.ai/v1/chat/completions",
        "models": ["gpt-oss-120b"],
    },
]


# Matched with regex (not the LLM) so greetings are recognized 100% of the
# time — even a typo like "hii" — instead of depending on a small free model
# to notice on its own, which was inconsistent.
GREETING_PATTERNS = [
    r"h+e*y+",
    r"h+i+",
    r"h+e+l+o+",
    r"y+o+",
    r"sup",
    r"good\s?(morning|afternoon|evening|night)",
    r"(thanks|thank\s?you|thx|ty)",
    r"ok(ay)?",
    r"(bye|goodbye|see\s?ya|cya)",
    r"how(’|'| a)?re? (you|u)( doing)?",
]
GREETING_RE = re.compile(r"^(" + "|".join(GREETING_PATTERNS) + r")[\s!.?]*$", re.IGNORECASE)


def is_greeting(text: str) -> bool:
    return bool(GREETING_RE.fullmatch(text.strip()))


def extract_text(filename: str, content: bytes) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(content))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if name.endswith(".docx"):
        doc = Document(io.BytesIO(content))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())
    return content.decode("utf-8", errors="ignore")


def call_llm(messages: list) -> tuple:
    """Returns (answer, provider_name) — the caller/UI can show which one answered."""
    tried = []
    for provider in PROVIDERS:
        api_key = os.environ.get(provider["env_var"])
        if not api_key:
            continue  # no key configured for this one — skip straight to the next

        models = provider["models"]
        body = {
            "messages": messages,
            # OpenRouter accepts a "models" list (tries each in order itself);
            # everyone else (Groq included) wants a single "model" string.
            **({"models": models} if provider["name"] == "OpenRouter" else {"model": models[0]}),
        }
        if any(m.startswith("openai/gpt-oss") for m in models):
            body["reasoning_effort"] = "low"  # keep the free reasoning model fast and cheap

        try:
            response = requests.post(
                provider["url"],
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=body,
                timeout=60,
            )
        except requests.exceptions.RequestException as e:
            tried.append(f"{provider['name']}: request failed ({e})")
            continue

        if response.status_code == 429:
            tried.append(f"{provider['name']}: rate limited")
            continue  # this one's out of free quota for now — fall through to the next

        if not response.ok:
            tried.append(f"{provider['name']}: error {response.status_code}")
            continue

        content = response.json()["choices"][0]["message"]["content"]
        if content and content.strip():
            return content, provider["name"]
        tried.append(f"{provider['name']}: empty response")

    if not tried:
        raise HTTPException(
            500, "No API key configured — set at least one of: " +
            ", ".join(p["env_var"] for p in PROVIDERS) + " in .env."
        )
    raise HTTPException(503, "All configured providers failed: " + "; ".join(tried))


@app.get("/", response_class=HTMLResponse)
def root():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/status")
def status():
    return {"status": "ok", "current_file": STORE["filename"]}


@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    content = await file.read()
    text = extract_text(file.filename, content)
    if not text.strip():
        raise HTTPException(400, "Couldn't extract any text from that file.")
    STORE["filename"] = file.filename
    STORE["text"] = text
    STORE["history"] = []  # new document — start the conversation over
    return {"filename": file.filename, "characters": len(text)}


@app.post("/clear")
def clear_chat():
    STORE["history"] = []
    return {"status": "cleared"}


class ChatRequest(BaseModel):
    question: str
    mode: str = "document"  # "document" (answer only from the uploaded file) or "general" (normal chatbot)


DOCUMENT_SYSTEM_PROMPT = (
    "You're chatting with a user about the document below. Answer their question using "
    "ONLY the document below. If the answer isn't in the document — including general "
    "knowledge questions unrelated to it, like capitals or trivia — say so clearly, e.g. "
    "\"I couldn't find that in the uploaded document — I can only answer questions about "
    "it.\" Don't just say 'I don't know' with no explanation, and don't make anything up.\n"
    "Keep answers simple and basic: plain everyday language, no jargon, as short as "
    "possible while still fully answering — a sentence or two is usually enough. Use the "
    "earlier messages in this conversation to understand follow-up questions (e.g. 'what "
    "about the other one?').\n\n"
    "DOCUMENT ({filename}):\n{context}"
)

GENERAL_SYSTEM_PROMPT = (
    "You're a helpful general-purpose chat assistant, like ChatGPT — answer from your own "
    "knowledge, not just from any uploaded document. Keep answers simple and basic: plain "
    "everyday language, no jargon, as short as possible while still fully answering. Use the "
    "earlier messages in this conversation to understand follow-up questions."
)


@app.post("/chat")
def chat(req: ChatRequest):
    if is_greeting(req.question):
        # Handled directly, with no LLM call at all — 100% consistent, and
        # doesn't depend on a small free model reliably noticing small talk.
        answer = (
            f"Hi! Ask me anything about \"{STORE['filename']}\"." if req.mode == "document"
            else "Hi! Ask me anything."
        )
        STORE["history"].append({"role": "user", "content": req.question})
        STORE["history"].append({"role": "assistant", "content": answer})
        STORE["history"] = STORE["history"][-(MAX_HISTORY_TURNS * 2):]
        return {"answer": answer, "provider": None}

    if req.mode == "document":
        if not STORE["text"]:
            raise HTTPException(400, "No file uploaded yet — POST a file to /upload first.")
        system_message = DOCUMENT_SYSTEM_PROMPT.format(
            filename=STORE["filename"], context=STORE["text"][:12000]
        )
    else:
        system_message = GENERAL_SYSTEM_PROMPT

    messages = (
        [{"role": "system", "content": system_message}]
        + STORE["history"]
        + [{"role": "user", "content": req.question}]
    )
    answer, provider_name = call_llm(messages)

    STORE["history"].append({"role": "user", "content": req.question})
    STORE["history"].append({"role": "assistant", "content": answer})
    STORE["history"] = STORE["history"][-(MAX_HISTORY_TURNS * 2):]

    return {"answer": answer, "provider": provider_name}
