"""LLM only EXPLAINS decisions already made by triage.py + facilities.py. It never picks facilities or levels."""
import json, os

SYSTEM = """You are Afya Msaidizi, a community health navigation assistant in Kenya.
You receive JSON with a triage level, an area and a shortlist of facilities chosen by the system.
Rules:
- Reply in the user's language (en = English, sw = Kiswahili) in simple, warm, short sentences (max ~120 words).
- NEVER diagnose or name a condition. Say a health worker must examine the person.
- State the urgency level exactly as given. If level is emergency, tell them to go to the nearest emergency facility first.
- Recommend health facilities near the user's location. Start with the shortlist when it fits, and add other facilities in or near that area only if you are confident they exist (or found them by search). If you cannot tell where the user is, ask for their area or estate.
- Recommend ONLY facilities in the shortlist, with distance and cost band. If a facility is flagged far or over_budget, say so plainly.
- For each facility give the name, roughly where it is or how far, and the cost when known. Say plainly when a facility is far, or may be costly for a low budget.
- Say costs and hours may have changed and to phone ahead. Do not invent facts, prices or phone numbers.
- Do not ask for names or personal details."""

MSG = {
 "en": {"emergency": "This may be an EMERGENCY. Go straight to the nearest emergency facility.",
        "urgent": "Please see a health worker TODAY.",
        "routine": "Please see a health worker in the next few days.",
        "self_care": "This may not need a clinic visit, but see a health worker if it gets worse.",
        "unclear": "I am not sure how serious this is. If it is severe or getting worse, call 999 or 112 or go to the nearest emergency facility. Tell me more about how you feel.",
        "cant": "I can't diagnose you; a health worker needs to examine you.",
        "near": "Nearest options for you", "far": "(far from you)", "cost": "cost", "dist": "km away",
        "over": "(may be above a low budget)", "ask": "Which area or estate are you in? I need it to find a clinic near you.",
        "note": "Costs and hours may have changed, so please phone ahead."},
 "sw": {"emergency": "Hii inaweza kuwa DHARURA. Nenda moja kwa moja kwenye kituo cha dharura kilicho karibu.",
        "urgent": "Tafadhali muone mhudumu wa afya LEO.",
        "routine": "Tafadhali muone mhudumu wa afya ndani ya siku chache.",
        "self_care": "Huenda hauhitaji kliniki, lakini muone mhudumu wa afya ikiwa hali itazidi.",
        "unclear": "Sina uhakika jinsi hali hii ilivyo mbaya. Ikiwa ni kali au inazidi, piga 999 au 112 au nenda kituo cha dharura kilicho karibu. Niambie zaidi unavyohisi.",
        "cant": "Siwezi kukutambua ugonjwa; mhudumu wa afya anahitaji kukuchunguza.",
        "near": "Vituo vilivyo karibu nawe", "far": "(iko mbali)", "cost": "gharama", "dist": "km",
        "over": "(inaweza kuwa juu ya bajeti ndogo)", "ask": "Uko eneo gani au mtaa gani? Ninahitaji kujua ili nikutafutie kliniki karibu nawe.",
        "note": "Gharama na saa za kazi zinaweza kubadilika, tafadhali piga simu kwanza."},
}

def template(lang, level, picks):
    m = MSG[lang]
    lines = [m[level], m["cant"]]
    if not picks:
        return "\n".join(lines + [m["ask"]])
    lines.append(m["near"] + ":")
    for f in picks:
        flags = (" " + m["far"] if f["far"] else "") + (" " + m["over"] if f["over_budget"] else "")
        lines.append(f"- {f['name']}, {f['distance_km']} {m['dist']}, {m['cost']}: {f['cost']}{flags}")
    lines.append(m["note"])
    return "\n".join(lines)

TRIAGE_SYSTEM = """You are a triage assistant for a Kenyan community health navigation tool. Read the user's message (English or Kiswahili) and output ONLY a JSON object, no other text:
{"level": "emergency|urgent|routine|self_care", "needs": ["general_outpatient","pediatrics","maternity","emergency"], "reasons": ["short phrase"]}
Rules: Do NOT diagnose. Choose the level by how quickly a health worker should see the person. When unsure between two levels, choose the more urgent one. Use "emergency" for anything life-threatening: breathing trouble, chest pain, collapse, seizure, heavy bleeding, severe injury or burns, stroke signs, self-harm risk, pregnancy danger signs, very sick infants. "needs" lists only the services required."""

def llm_triage(message):
    if not os.getenv("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic
        r = anthropic.Anthropic().messages.create(model=os.getenv("CHW_MODEL", "claude-sonnet-5-5"), max_tokens=200,
                                                  system=TRIAGE_SYSTEM, messages=[{"role": "user", "content": message}])
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text")
        data = json.loads(text[text.index("{"): text.rindex("}") + 1])
        if data.get("level") not in ("emergency", "urgent", "routine", "self_care"):
            return None
        allowed = {"general_outpatient", "pediatrics", "maternity", "emergency"}
        data["needs"] = [n for n in data.get("needs", []) if n in allowed]
        data["reasons"] = [str(x)[:60] for x in data.get("reasons", [])][:5]
        return data
    except Exception:
        return None   # fall back to the rules alone

def reply(message, lang, triage, picks, area, budget):
    fallback = template(lang, "unclear" if triage.labels == ["unclear"] else triage.level, picks)
    if not os.getenv("ANTHROPIC_API_KEY"):
        return fallback
    try:
        import anthropic
        facts = {"language": lang, "user_message": message, "triage_level": triage.level, "area": area, "budget": budget,
                 "shortlist": [{k: f[k] for k in ("name", "distance_km", "cost", "phone", "far", "over_budget", "open24")} for f in picks]}
        kwargs = {}
        if os.getenv("CHW_WEB_SEARCH") == "1":   # optional: let the model look up real facilities near the user
            kwargs["tools"] = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
        r = anthropic.Anthropic().messages.create(model=os.getenv("CHW_MODEL", "claude-sonnet-5-5"), max_tokens=800,
                                                  system=SYSTEM, messages=[{"role": "user", "content": json.dumps(facts)}], **kwargs)
        text = "".join(b.text for b in r.content if getattr(b, "type", None) == "text").strip()
        # output guard: non-empty, and the emergency numbers must be present when it is an emergency
        if not text or (triage.level == "emergency" and "999" not in text):
            return fallback
        return text
    except Exception:
        return fallback   # never fail silently into no answer: fall back to the safe template