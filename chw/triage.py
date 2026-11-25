"""Rule-based triage. Deterministic and auditable: runs BEFORE the LLM and sets the urgency level.
All rules (EN + SW) must be reviewed by a clinician before real-world use."""
import re
from dataclasses import dataclass, field

LEVELS = ["self_care", "routine", "urgent", "emergency"]

# (regex, label, level, services needed)
RULES = [
    (r"chest pain|maumivu ya kifua|kifuani", "chest pain", "emergency", ["emergency"]),
    (r"(can'?t|cannot|struggling to) breathe|difficulty breathing|shortness of breath|kupumua kwa shida|nashindwa kupumua|anashindwa kupumua", "breathing difficulty", "emergency", ["emergency"]),
    (r"unconscious|passed out|collapsed|amezimia|nimezimia|amepoteza fahamu", "loss of consciousness", "emergency", ["emergency"]),
    (r"seizure|convuls|degedege|kifafa", "seizure", "emergency", ["emergency"]),
    (r"heavy bleeding|bleeding (a lot|heavily)|damu nyingi|anavuja damu", "heavy bleeding", "emergency", ["emergency"]),
    (r"suicid|kill myself|want to die|kujiua|kujidhuru", "self-harm risk", "emergency", ["emergency"]),
    (r"nose ?bleed|damu puani", "nosebleeds", "urgent", ["general_outpatient"]),
    (r"vomit|kutapika|diarrh|kuhara", "vomiting/diarrhoea", "routine", ["general_outpatient"]),
    (r"fever|homa", "fever", "routine", ["general_outpatient"]),
    (r"headache|maumivu ya kichwa|kichwa kinauma", "headache", "routine", ["general_outpatient"]),
    (r"cough|kikohozi", "cough", "routine", ["general_outpatient"]),
    (r"pregnan|mimba|mjamzito", "pregnancy", "routine", ["maternity"]),
]
CHILD = r"\b(baby|infant|toddler|child|my (son|daughter|kid)|mtoto|mwanangu|kichanga)\b"
CHILD_BUMP = {"fever", "vomiting/diarrhoea", "cough"}  # these are more urgent in young children

@dataclass
class Triage:
    level: str = "routine"
    labels: list = field(default_factory=list)
    needs: list = field(default_factory=lambda: ["general_outpatient"])
    child: bool = False

def assess(text: str) -> Triage:
    t = text.lower()
    level, labels, needs = "routine", [], []
    child = bool(re.search(CHILD, t))
    for pattern, label, lvl, svc in RULES:
        if re.search(pattern, t):
            labels.append(label)
            if label in CHILD_BUMP and child:
                lvl = "urgent"
            if LEVELS.index(lvl) > LEVELS.index(level):
                level = lvl
            needs += [s for s in svc if s not in needs]
    if "pregnancy" in labels and re.search(r"bleed|damu", t):
        level, needs = "emergency", ["emergency"]
    if "emergency" in needs:
        needs = ["emergency"]
    if child and "emergency" not in needs:
        needs.append("pediatrics")
    return Triage(level, labels, needs or ["general_outpatient"], child)

SW_HINTS = {"mimi", "nina", "naishi", "mtoto", "homa", "kichwa", "maumivu", "sijui", "tafadhali",
            "nahisi", "ninaumwa", "naumwa", "wapi", "hospitali", "kliniki", "kwa", "sina", "pesa", "damu"}
def detect_lang(text: str) -> str:
    words = set(re.findall(r"[a-z]+", text.lower()))
    return "sw" if len(words & SW_HINTS) >= 2 else "en"

LOW_BUDGET = r"cheap|afford|low cost|no money|free|sina pesa|bei nafuu|rahisi|bure"
ANY_BUDGET = r"private|any price|best hospital|pesa si shida"
def detect_budget(text: str) -> str:
    t = text.lower()
    if re.search(ANY_BUDGET, t):
        return "any"
    return "low"  # safe default for the target community; cost is always shown to the user
def combine(rules, llm):
    """The LLM may RAISE urgency or add needs, never lower what the rules found."""
    if not llm:
        return rules
    level = max(rules.level, llm["level"], key=LEVELS.index)
    labels = rules.labels + [r for r in llm["reasons"] if r not in rules.labels]
    needs = list(rules.needs)
    for n in llm["needs"]:
        if n not in needs:
            needs.append(n)
    if level == "emergency":
        needs = ["emergency"]
    return Triage(level, labels, needs, rules.child)
