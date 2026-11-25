# Community Health Assistant (Kenya) — v1 scaffold

## Design in one picture
User message (EN/SW)
  → 1. Triage rules (triage.py)      sets urgency: emergency / urgent / routine; deterministic, clinician-reviewable
  → 2. Location (facilities.py)      area must be stated; never guessed
  → 3. Facility ranking              filters by needed service + 24h (emergency), ranks by distance + cost band
  → 4. LLM explanation (llm.py)      only rewrites the decision in simple EN/SW; output guard + safe template fallback
  → Reply: urgency, 1-3 facilities, distance, cost, "phone ahead"

## Why this shape
- Your main risks (far facility, unaffordable facility) are handled in code: distance/cost ranking, `far` and `over_budget` flags are shown to the user.
- "Connect, don't diagnose": the LLM never chooses the level or the facility, and the system prompt forbids naming conditions.
- Privacy: no names, no storage, no logging of message text.

## Run
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...        # optional; without it the safe template reply is used
uvicorn chw.app:app --reload        # chat UI at http://127.0.0.1:8000/  (API docs at /docs)
pytest

## Before real use
1. Replace data/facilities.json (sample data!) with the Kenya Master Health Facility List, add cost bands and SHA acceptance, and verify them by phone.
2. Replace approximate coordinates in data/areas.json with a proper gazetteer or map geocoder.
3. Have clinicians review every rule in triage.py and the emergency/helpline numbers.
4. Build your 500+ example test set (EN + SW) and run the spot checks from your Evaluation section.
