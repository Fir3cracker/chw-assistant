from fastapi import FastAPI
from pydantic import BaseModel, Field
from .triage import assess, detect_lang, detect_budget, combine 
from .facilities import find_area, shortlist
from .llm import reply, llm_triage

app = FastAPI(title="Community Health Assistant (Kenya)")

# Dev-friendly CORS so the page works even if opened from another origin/port. Restrict origins in production.
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)
    area: str | None = None      # optional: from a location picker
    budget: str | None = None    # "low" | "any"

@app.post("/chat")
def chat(body: ChatIn):
    # Privacy: nothing is stored or logged here (no names, no message text).
    lang = detect_lang(body.message)
    t = assess(body.message)
    area = find_area(body.area or "") or find_area(body.message)   # never guess a location
    budget = body.budget or detect_budget(body.message)
    picks = shortlist(area, t.level, t.needs, budget) if area else []
    return {"language": lang, "triage_level": t.level, "area": area, "facilities": picks,
            "reply": reply(body.message, lang, t, picks, area, budget)}

# --- frontend (served from the same origin so fetch("/chat") just works) ---
from pathlib import Path
from fastapi.responses import FileResponse
from .facilities import AREAS

@app.get("/areas")
def areas():
    return sorted(n.title() for n in AREAS)

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(Path(__file__).parent / "static" / "index.html")
