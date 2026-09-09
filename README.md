# File Q&A Bot

A tiny real AI project: upload a file, then ask it questions — it answers only from that file's content, using a free OpenRouter model. Built so you have a real, working AI agent to point your AI Tester tool at.

The API key lives in one local file (`.env`), set once. After that, nobody using the app — you, a teammate, or the AI Tester tool — ever needs to type in a key.

## 1. One-time setup: add your key(s)

1. Get a free key at **openrouter.ai/keys** (starts with `sk-or-`).
2. Open the `.env` file in this folder (plain text file, opens in Notepad).
3. Paste it after `OPENROUTER_API_KEY=`, so it reads like:
   `OPENROUTER_API_KEY=sk-or-v1-xxxxxxxx`
4. Save the file.

That's it — you never do this again, and no key ever appears anywhere in the app's UI or responses.

### Automatic fallback when a free tier runs out

The app tries models in this order:
1. **Google: Gemma 4 26B A4B (free)** on OpenRouter — primary. Efficient MoE model, big context, good general Q&A quality.
2. **Google: Gemma 4 31B (free)** on OpenRouter — same-provider backup if the first is temporarily overloaded (OpenRouter's own built-in model fallback).
3. **Groq** — a completely different company with its own separate free quota, used only if OpenRouter's account-wide free limit is hit (OpenRouter's free cap is per account, not per model, so switching models alone doesn't help once *that's* exhausted — a different provider does).
4. **Cerebras** — a third, separate company with its own separate free quota, used only if both OpenRouter and Groq are exhausted or down. Same reasoning as Groq: a different company's quota is the only thing that helps once an account-wide limit is hit.

`.env` has `GROQ_API_KEY=` and `CEREBRAS_API_KEY=` lines for steps 3 and 4. Get a free Groq key at **console.groq.com/keys** and a free Cerebras key at **cloud.cerebras.ai** (Platform → API Keys), and paste each in the same way as the OpenRouter one. Leave either blank if you don't want that fallback — the app just uses whichever keys are actually filled in.

Every bot reply in the chat page now shows a small **"via OpenRouter" / "via Groq" / "via Cerebras"** tag underneath it, so you can tell at a glance which one actually answered — handy for noticing when your primary free tier has run out for the day.

⚠️ Two model IDs are unconfirmed spellings, not verified by me directly:
- `google/gemma-4-31b-it:free` — inferred from the same naming pattern as the 26B one (which *was* confirmed from your own OpenRouter code sample).
- `llama3.1-8b` (Cerebras) — Cerebras's free-tier model name at the time this was written, not independently confirmed.

If either errors, open the provider's own docs/dashboard and check the exact model string matches what's in `PROVIDERS` in `app.py` — edit it there if it doesn't.

## 2. Install dependencies (only needed once)

```
cd "C:\Users\USER\OneDrive - Balqa Applied University\Desktop\projects\Chatbot\Chatbot Code"
.venv\Scripts\activate
pip install -r requirements.txt
```

(Already done for you — skip this unless you're setting it up on a different machine.)

## 3. Run the server

```
cd "C:\Users\USER\OneDrive - Balqa Applied University\Desktop\projects\Chatbot\Chatbot Code"
.venv\Scripts\activate
uvicorn app:app --port 8600
```

Leave that running. The server is now at `http://localhost:8600` — no key prompt, no login, it just works.

## 4. Try it yourself first (no coding needed)

Open `http://localhost:8600/docs` in your browser — that's an interactive test page.
- Expand **POST /upload**, click "Try it out", choose a file (txt/pdf/docx/csv), click Execute.
- Expand **POST /chat**, click "Try it out", type `{"question": "your question here"}`, click Execute — you'll get the answer back.

## 5. Point your AI Tester tool at it

In the AI Tester app, Test & Score tab → API (HTTP):
- **API endpoint URL**: `http://localhost:8600/chat`
- **Authentication**: None
- **Request body template**: `{"question": "{{question}}"}`  (this is already the default)
- **Response is plain text**: leave unchecked
- **Where's the answer in the response?**: `answer`  (this is already the default)

Upload the same file to the bot first (step 4), then it's ready — every question the AI Tester sends will get answered from that file, and no one testing it ever sees or needs the API key.

## Notes

- Only one file is "remembered" at a time — uploading a new one replaces the old one.
- The server keeps the file's text in memory only; nothing is saved to disk, and it's forgotten when you stop the server.
- Free models — fine for testing, not for production traffic.
- `.env` is in `.gitignore` — if this folder is ever pushed to GitHub, the key stays local and is never uploaded.
