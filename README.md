# HELIX-9D Research Assistant

FastAPI chatbot with streamed OpenAI responses, rolling per-session memory, binary conversion and science lookup tools, and basic per-session rate limiting.

## Run locally
```powershell
py -m pip install -r requirements.txt
$env:OPENAI_API_KEY="your-key-here"
py -m uvicorn app:app --reload
```
Visit http://127.0.0.1:8000

## Render deployment
Use the Render dashboard to create a Blueprint from this repository, reading `render.yaml`. Configure `OPENAI_API_KEY` as a secret in Render. Never commit API keys to GitHub. Verify `/health` and a real streamed `/chat` response.

## Status
The repository contains the online deployment version of the chatbot. It has not yet been deployed to Render or verified with a real OpenAI API key. The fuller course assignment ZIP, including report, tests, evaluation scripts, and MP4, is a separate deliverable.

## Security note
Per-conversation rate limiting is not sufficient for a public paid API endpoint: use access control, provider spending limits, and consider global rate limiting before sharing broadly. Memory is in-process and resets on restart.
