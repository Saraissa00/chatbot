# Chatbot

**Try it:** https://chatbot-nxuj.onrender.com/ (free tier — sleeps after 15 min idle, wakes automatically in ~30-50s on the next visit)

A small self-contained AI chatbot: a FastAPI backend and one plain HTML/JS page, no build step, no framework.

## Demo

![demo](docs/chatbot-demo.gif)
![screenshot](docs/chatbot-screenshot.jpg)

## About

It works two ways, switched with a toggle in the page itself:

- **General Chat** (default) — answers like a normal assistant, from its own knowledge.
- **From Document** — upload a file (`.txt`, `.pdf`, `.docx`, `.csv`) and it answers strictly from that file's content, refusing anything outside it.

It remembers the last few messages of the conversation, so follow-up questions work naturally, and it automatically switches between two free AI providers if one runs out of quota — so it keeps answering without you having to do anything.

## Features

- **Two chat modes** — General Chat and From Document, toggled in the page itself
- **Conversation memory** — remembers the last 10 exchanges, so follow-ups like "what about the other one?" resolve correctly
- **Automatic provider fallback** — tries Google Gemma (via OpenRouter) first, then Groq if the free quota runs out, with a small "via OpenRouter / via Groq" tag on each reply so you can tell which one answered
- **Instant greetings** — "hi", "hey", "thanks" etc. are recognized by pattern-matching, not by asking the AI, so they cost no API call
- **Honest "not found" answers** — in Document mode, if something isn't in the file it says so clearly instead of a bare "I don't know"
- **Plain REST API** — point any external tool at `/chat` directly, no auth needed

## Requirements

- Python 3.10+
- A free API key from [openrouter.ai/keys](https://openrouter.ai/keys) (starts with `sk-or-`)
- Optionally, a free key from [console.groq.com/keys](https://console.groq.com/keys) for the fallback provider

## Getting Started

**1. Clone and enter the project:**
```bash
git clone https://github.com/Saraissa00/chatbot.git
cd chatbot
```

**2. Add your API key(s):**
```bash
cp .env.example .env
```
Open `.env` and paste your OpenRouter key after `OPENROUTER_API_KEY=`. Add `GROQ_API_KEY=` too if you want the fallback provider — leave it blank otherwise. No key ever appears anywhere in the app's UI or responses.

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Run the server:**
```bash
uvicorn app:app --port 8600
```

**5. Open it in your browser:**
[http://localhost:8600](http://localhost:8600) — no key prompt, no login, it just works.

### Provider fallback order

1. **Gemma (free)** on OpenRouter — primary
2. **Gemma backup model (free)** on OpenRouter — same-provider fallback if the first is overloaded
3. **Groq** — a separate company with its own free quota, used only if OpenRouter is exhausted or down

### Testing this against another tool

Because it's a real HTTP API, you can point any external testing tool at it directly:
- **Endpoint:** `http://localhost:8600/chat`
- **Auth:** none
- **Body:** `{"question": "your question", "mode": "general"}` (or `"mode": "document"` after uploading via `/upload`)
- **Answer is at:** `answer` in the JSON response

Interactive API docs are also available at `http://localhost:8600/docs`.

## Notes

- Only one document is "remembered" at a time — uploading a new one replaces the last and starts the conversation over.
- Everything lives in memory only. Stopping the server forgets the document and the conversation.
- Free-tier models — fine for testing and demos, not sized for production traffic.
- `.env` is gitignored — your keys stay local and are never committed.

## Tech Stack

- **FastAPI** — backend and HTTP API
- **HTML/JS** — frontend, no build step or framework
- **OpenRouter + Groq** — free-tier LLM providers with automatic fallback
- **Render** — deployment
