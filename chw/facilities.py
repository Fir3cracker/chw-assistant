import json, math, pathlib, re

DATA = pathlib.Path(__file__).parent / "data"
FACILITIES = json.loads((DATA / "facilities.json").read_text())
AREAS = {k.lower(): v for k, v in json.loads((DATA / "areas.json").read_text()).items()}
COST = {"low": 0, "medium": 1, "high": 2}
COST_KM = 4      # one cost step is treated like 4 km of travel for low-budget users (tune with community input)
FAR_KM = 5

def find_area(text: str):
    t = text.lower()
    for name in sorted(AREAS, key=len, reverse=True):   # longest match first
        if re.search(r"\b" + re.escape(name) + r"\b", t):
            return name
    return None

def km(a, b):
    (la1, lo1), (la2, lo2) = a, b
    p = math.pi / 180
    h = math.sin((la2 - la1) * p / 2) ** 2 + math.cos(la1 * p) * math.cos(la2 * p) * math.sin((lo2 - lo1) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))

def shortlist(area: str, level: str, needs: list, budget: str, k: int = 3):
    here = AREAS[area]
    emergency = level == "emergency"
    want = set(needs)
    def fits(f, req):
        return req <= set(f["services"]) and (f["open24"] or not emergency)
    pool = [f for f in FACILITIES if fits(f, want)]
    if not pool:  # relax: fall back to general care rather than returning nothing
        pool = [f for f in FACILITIES if fits(f, {"emergency"} if emergency else {"general_outpatient"})]
    out = []
    for f in pool:
        d = km(here, (f["lat"], f["lon"]))
        penalty = COST_KM * COST[f["cost"]] if (budget == "low" and not emergency) else 0
        out.append((d + penalty, {**f, "distance_km": round(d, 1),
                                  "far": d > FAR_KM,
                                  "over_budget": budget == "low" and f["cost"] != "low" and not emergency}))
    return [x[1] for x in sorted(out, key=lambda x: x[0])[:k]]
