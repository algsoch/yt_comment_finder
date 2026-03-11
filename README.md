<div align="center">

<img src="https://img.shields.io/badge/built%20by-algsoch-ff6b00?style=for-the-badge&logo=github" alt="built by algsoch"/>
<img src="https://img.shields.io/badge/FastAPI-0.135-009688?style=for-the-badge&logo=fastapi" alt="FastAPI"/>
<img src="https://img.shields.io/badge/Python-3.14-3776AB?style=for-the-badge&logo=python" alt="Python"/>
<img src="https://img.shields.io/badge/YouTube%20API%20v3-FF0000?style=for-the-badge&logo=youtube" alt="YouTube API"/>

# 📺 YouTube Comment Finder

**Search YouTube comments by username or keyword — with live scanning progress, browse mode, and beautiful dark UI.**

[**▶ Watch Demo**](https://youtu.be/qsttpVf8XNU) &nbsp;·&nbsp;
[**GitHub**](https://github.com/algsoch/yt_comment_finder) &nbsp;·&nbsp;
[**LinkedIn**](https://www.linkedin.com/in/algsoch)

</div>

---

## 💡 Why I Built This

I built this tool out of a real personal frustration.

I post on YouTube and I wanted to **find specific comments** — filter by a person's name, search for a keyword someone mentioned, or just scroll through every comment one by one. YouTube's own interface gives you no way to do that. You can't search comments natively. You can't filter. You just scroll forever.

I also build AI projects (like **[Cognivise](https://github.com/algsoch)** — a cognitive AI agent that watches, listens, and adapts to learners in real time), and I wanted to track conversations around topics I was building in — comments mentioning "AI agents", "real-time", "Watch Party" sessions, etc.

So I built this: a fast, clean tool that streams through all comments on any YouTube video in real time, highlights matches, and lets you browse every single comment one at a time.

---

## ✨ Features

<table>
<tr>
<td width="50%">

**🔍 Smart Search**
- Filter by **username** (partial, case-insensitive)
- Filter by **keyword** (partial, case-insensitive)
- Supports `watch?v=`, `/shorts/`, `youtu.be/`, `/embed/` URLs

</td>
<td width="50%">

**⚡ Live SSE Streaming**
- Real-time progress bar with `X / Total · Y%`
- Page-by-page dashboard: threads, replies, speed, matches
- Server-sent events — no polling

</td>
</tr>
<tr>
<td>

**🔦 Beautiful Keyword Highlighting**
- Matched words glow amber with a ring outline
- Matched comment cards get an orange left-border accent
- All with zero layout shift

</td>
<td>

**👁 Browse All Mode**
- Full-screen overlay to browse every comment one at a time
- Arrow keys / tap to navigate
- Auto-advances as new comments stream in

</td>
</tr>
<tr>
<td>

**📱 Fully Responsive**
- Works on desktop, tablet, and phone
- Browse overlay becomes a bottom sheet on mobile
- iOS scroll zoom prevention

</td>
<td>

**🛑 Stop Anytime**
- Stop button cancels the stream mid-scan
- Server detects client disconnect and stops fetching

</td>
</tr>
</table>

---

## 🚀 Quick Start

### 1 · Clone

```bash
git clone https://github.com/algsoch/yt_comment_finder.git
cd yt_comment_finder
```

### 2 · Create virtual environment

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
```

### 3 · Install dependencies

```bash
pip install -r requirements.txt
```

### 4 · Add your YouTube API key

Create a `.env` file in the project root:

```env
YOUTUBE_API_KEY=your_api_key_here
```

> **Get a free API key:** [Google Cloud Console](https://console.cloud.google.com/) → Enable **YouTube Data API v3** → Credentials → Create API Key.

### 5 · Run

```bash
uvicorn main:app --reload
```

Open **[http://localhost:8000](http://localhost:8000)** in your browser.

---

## 🗂 Project Structure

```
yt_comment_finder/
├── main.py                 # FastAPI app — SSE streaming, YouTube API
├── templates/
│   └── index.html          # Full single-page UI (Jinja2)
├── static/
│   └── style.css           # All styles — dark theme, responsive
├── requirements.txt
└── .env                    # Your API key (not committed)
```

---

## 🔧 How It Works

```
Browser                     FastAPI Server              YouTube API
  │                              │                           │
  │   GET /stream-search?...     │                           │
  │ ─────────────────────────►  │                           │
  │                              │  videos?part=statistics   │
  │                              │ ─────────────────────────►│
  │   SSE: stats event           │◄─────────────────────────│
  │◄────────────────────────    │                           │
  │                              │  commentThreads (page 1)  │
  │                              │ ─────────────────────────►│
  │   SSE: progress + results    │◄─────────────────────────│
  │◄────────────────────────    │    ... repeat until done  │
  │                              │                           │
  │   SSE: done                  │                           │
  │◄────────────────────────    │                           │
```

**SSE Events emitted:**

| Event | Payload |
|-------|---------|
| `stats` | `{ title, comment_count, thumbnail }` |
| `log` | `{ msg }` — page fetch status lines |
| `progress` | `{ scanned, total, matched }` |
| `result` | full comment object (author, text, likes, …) |
| `done` | `{ total, matched, stopped }` |
| `error` | `{ message }` |

---

## 📦 Tech Stack

| Layer | Tech |
|-------|------|
| Backend | **FastAPI** 0.135 + **uvicorn** |
| HTTP client | **httpx** async |
| Streaming | **Server-Sent Events** (SSE) |
| Templating | **Jinja2** |
| Frontend | Vanilla JS — no frameworks |
| Styles | Plain CSS — dark theme, CSS custom properties |
| API | YouTube Data API v3 |

---

## 🙋 About

Built by **Vicky Kumar** — [@algsoch](https://github.com/algsoch)

I'm building **Cognivise** — a closed-loop cognitive AI agent designed to watch, listen, and adapt to learners in real time. Moving beyond simple monitoring toward something closer to how a teacher observes students in a classroom.

- 🐙 GitHub: [github.com/algsoch](https://github.com/algsoch)
- 💼 LinkedIn: [linkedin.com/in/algsoch](https://www.linkedin.com/in/algsoch)

---

<div align="center">
<sub>© 2026 Vicky Kumar · algsoch · MIT License</sub>
</div>
