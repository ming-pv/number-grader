# Local AI Model Setup — Handwriting Recognition

This sets up a local vision-model server (running on a computer you control) that
the grader app can call instead of, or alongside, the built-in Tesseract OCR.
Tesseract struggles with messy handwriting; a small vision-language model (VLM)
reads it far more reliably because it understands context ("ignore the crossed-out
part", "ignore the Thai unit label next to the number").

Do this once per computer you want to use as a model server. The phone-side app
code is already updated to call whichever server URL you give it — no code changes
needed per machine, just these setup steps.

---

## What you're building

```
Phone (grader app, HTTPS via GitHub Pages)
   |
   |  HTTPS request with a cropped answer-box image
   v
Tailscale tunnel  →  Computer running Ollama + a vision model
   |
   v
Recognized text sent back to the phone, graded locally as before
```

The phone's camera page needs a secure context (HTTPS) to work at all, and an
HTTPS page cannot call a plain-HTTP server (browsers block this as "mixed
content"). Tailscale gives the computer a real `https://` address reachable from
the phone without dealing with certificates yourself.

---

## Part 1 — Install Ollama and pull a model

### 1.1 Install Ollama

- **Windows**: `winget install --id Ollama.Ollama -e`, or download from https://ollama.com/download
- **Mac**: `brew install ollama`, or download from https://ollama.com/download
- **Linux**: `curl -fsSL https://ollama.com/install.sh | sh`

Verify it's running:
```bash
ollama --version
```

### 1.2 Pull the model

```bash
ollama pull qwen2.5vl:3b
```

This downloads ~3.2GB. **Use `qwen2.5vl:3b`, not `moondream`** — both were tested
directly against real handwritten answer crops from this project's sample sheets.
`moondream` (1.8B) was fast (~5-7s/image) but unreliable: it correctly read one
crop and then silently failed (empty output) on most others. `qwen2.5vl:3b`
correctly read every test crop, including ignoring a Thai unit label next to a
number and reading a comma-separated number — but took **~35 seconds per image
on a CPU-only laptop** (no dedicated GPU). If the computer you're setting up has
an NVIDIA GPU, Ollama will use it automatically and this drops to a few seconds —
worth checking `nvidia-smi` first if speed matters.

Test it works:
```bash
ollama run qwen2.5vl:3b "Say hello"
```

### 1.3 Enable CORS so the browser page can call it

By default Ollama **rejects** requests from any web page origin (verified: a
request with an `Origin` header from an unrecognized site gets HTTP 403). You
must explicitly allow the origin the grader app is served from.

**Windows** (PowerShell, as the same user Ollama runs as):
```powershell
setx OLLAMA_ORIGINS "*"
```
Then **quit Ollama from the system tray and relaunch it** (env var changes only
take effect on a fresh start — Ollama runs as a background tray app on Windows,
not a service that reloads config automatically).

**Mac/Linux** (if running Ollama manually):
```bash
OLLAMA_ORIGINS="*" ollama serve
```
Or set it persistently in your shell profile (`~/.zshrc`, `~/.bashrc`) and restart
your terminal + Ollama.

`OLLAMA_ORIGINS="*"` allows any site to call your local Ollama — fine for this
use case since it's only reachable via your private Tailscale tunnel (see Part
2), not the open internet. If you want to be stricter, set it to the exact
origin instead, e.g. `setx OLLAMA_ORIGINS "https://ming-pv.github.io"`.

### 1.4 Verify

```bash
curl http://localhost:11434/api/tags
```
Should list `qwen2.5vl:3b` in the response.

---

## Part 2 — Expose it to your phone via Tailscale

### 2.1 Install Tailscale on the computer

- **Windows**: `winget install --id Tailscale.Tailscale -e`
- **Mac**: `brew install tailscale`, or from https://tailscale.com/download
- **Linux**: `curl -fsSL https://tailscale.com/install.sh | sh`

Then sign in (opens a browser once):
```bash
tailscale up
```
Sign in with any account (Google/Microsoft/GitHub all work) — this becomes your
"tailnet". Free tier covers personal use easily.

### 2.2 Install Tailscale on your phone

Get it from the App Store / Play Store, and **sign in with the same account**
you used on the computer. This puts the phone on the same private tailnet, so
`tailscale serve` (private, not `funnel`) is reachable from it — nobody outside
your tailnet can reach your Ollama instance this way.

### 2.3 Expose Ollama's port over HTTPS

On the computer:
```bash
tailscale serve --bg 11434
```
(If that exact flag doesn't exist in your installed version, run
`tailscale serve --help` — the general form is `tailscale serve <port>` to proxy
a local port over HTTPS on your tailnet.)

Get the URL:
```bash
tailscale serve status
```
This shows something like `https://your-computer-name.your-tailnet.ts.net` — that's
the address the phone will use. It stays reachable as long as both the computer
and Ollama are running and Tailscale is connected — no need to redo this each
session unless you reboot the computer (rerun `tailscale serve --bg 11434` after
a reboot if it doesn't auto-resume).

### 2.4 Verify from the phone

With the phone on Tailscale and connected to the internet (any network — it
doesn't need to share WiFi with the computer), open this in the phone's browser:
```
https://your-computer-name.your-tailnet.ts.net/api/tags
```
You should see the same JSON listing as the `curl` test above. If this doesn't
work, the phone isn't on the tailnet correctly, or `tailscale serve` isn't
running — check `tailscale status` on both devices.

---

## Part 3 — Point the grader app at your server

Open the grader app on your phone, go to its settings (the AI server URL field —
see the app-side notes below), and enter:
```
https://your-computer-name.your-tailnet.ts.net
```

The app will try this server first for reading each answer box; if it's
unreachable (computer off, Tailscale down, etc.) it automatically falls back to
the built-in Tesseract OCR, so the app keeps working even without the server —
just less accurately on messy handwriting.

---

## Doing this on multiple computers

Repeat Parts 1–2 on each computer you want available as a model server (e.g. a
backup laptop). Each gets its own Tailscale hostname. On grading day, just pick
whichever computer is powered on and enter *that* one's URL into the app — or
keep several running and switch the URL if one becomes unavailable.

If you want Claude to do this setup on a given computer instead of doing it by
hand: hand this file to a Claude Code session running **on that computer** and
ask it to follow Parts 1–2. Steps requiring interactive login (`tailscale up`,
the phone-side app sign-in) still need a human at the keyboard/phone — Claude
can drive everything else (install, pull model, set env vars, run `serve`,
verify with curl).

---

## Known limitations

- **Speed**: ~35s per answer box on CPU-only hardware, ×5 boxes (less if earlier
  boxes read cleanly and don't need retries) ≈ 1-3 minutes per sheet. A GPU
  computer will be much faster. If this is too slow in practice, tell Claude —
  the app can be changed to only call the AI model for boxes Tesseract already
  failed to parse, instead of using it for every box.
- **Security**: `tailscale serve` keeps this private to your tailnet (people you've
  invited/your own devices), not the public internet. Don't use `tailscale
  funnel` for this unless you specifically want it publicly reachable.
- **The computer must stay on and awake** for the phone to reach it during
  grading — check sleep/power settings if it keeps dropping.
