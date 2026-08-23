"""Bouw de twee bestanden die de site inleest.

  docs/data.json     Per atleet, per dag, per sport: afstand en load. De site
                       rekent hier zelf de scores mee uit, zodat bezoekers aan
                       de factoren kunnen schuiven. Bevat geen trainingsnamen
                       en geen activiteit-IDs -- dit bestand staat publiek.

  docs/history.json  De hall of fame. Winnaars van afgeronde weken en maanden,
                       vastgezet met de OFFICIELE weging uit config.json. Loopt
                       dus niet mee met de sliders van de bezoeker.

Draaien:  python scripts/build2.py
"""

import json
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "activities.json"
OUT_DATA = ROOT / "docs" / "data.json"
OUT_HIST = ROOT / "docs" / "history.json"

MONTHS_NL = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
             "augustus", "september", "oktober", "november", "december"]


def activity_date(activity: dict) -> date | None:
    raw = activity.get("start_date_local")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def to_day_rows(activities: list[dict]) -> list[list]:
    """Dicht de activiteiten samen tot een rij per atleet/dag/sport.

    Scheelt fors in bestandsgrootte en haalt alles weg wat niet nodig is om
    een klassement te tekenen -- geen trainingsnamen, geen tijdstippen.
    """
    buckets: dict[tuple, dict] = defaultdict(
        lambda: {"km": 0.0, "load": 0.0, "n": 0, "manual": 0.0})

    for act in activities:
        day = activity_date(act)
        if not day:
            continue
        key = (act["athlete"], day.isoformat(), act.get("type") or "Onbekend")
        b = buckets[key]
        km = (act.get("distance") or 0) / 1000
        b["km"] += km
        b["load"] += act.get("icu_training_load") or 0
        b["n"] += 1
        if act.get("manual"):
            b["manual"] += km

    rows = []
    for (athlete, day, sport), b in sorted(buckets.items()):
        rows.append([athlete, day, sport, round(b["km"], 2),
                     round(b["load"]), b["n"], round(b["manual"], 2)])
    return rows


def score_window(rows: list[list], cfg: dict, start: date, end: date) -> list[dict]:
    """Reken een klassement uit met de officiele weging. Spiegelt de JS in de site."""
    factors = cfg["sport_factors"]
    totals: dict[str, dict] = defaultdict(lambda: {"eq": 0.0, "load": 0.0, "n": 0})

    for athlete, day, sport, km, load, n, _manual in rows:
        d = date.fromisoformat(day)
        if not (start <= d <= end):
            continue
        t = totals[athlete]
        t["eq"] += km * factors.get(sport, 0.0)
        t["load"] += load
        t["n"] += n

    if not totals:
        return []

    blend = cfg["blend_load_pct"] / 100
    top_eq = max((t["eq"] for t in totals.values())) or 1
    top_load = max((t["load"] for t in totals.values())) or 1

    out = []
    for name, t in totals.items():
        out.append({
            "name": name,
            "score": round((t["eq"] / top_eq) * 100 * (1 - blend)
                           + (t["load"] / top_load) * 100 * blend, 1),
            "eq_km": round(t["eq"], 1),
            "load": round(t["load"]),
            "activities": t["n"],
        })
    out.sort(key=lambda r: -r["score"])
    return out


def closed_weeks(rows: list[list], cfg: dict, today: date) -> list[dict]:
    """Alle volledig afgeronde weken (maandag t/m zondag), nieuwste eerst."""
    if not rows:
        return []
    first = date.fromisoformat(rows[0][1])
    this_monday = today - timedelta(days=today.weekday())

    out = []
    monday = this_monday - timedelta(days=7)
    while monday >= first - timedelta(days=7) and len(out) < cfg["hall_of_fame"]["max_weeks"]:
        sunday = monday + timedelta(days=6)
        ranked = score_window(rows, cfg, monday, sunday)
        ranked = [r for r in ranked if r["activities"] >= cfg["hall_of_fame"]["min_activities"]]
        if ranked:
            out.append({
                "label": f"Week {monday.isocalendar().week}",
                "sub": f"{monday.strftime('%-d')} – {sunday.strftime('%-d')} {MONTHS_NL[sunday.month - 1]}",
                "start": monday.isoformat(),
                "end": sunday.isoformat(),
                "winner": ranked[0]["name"],
                "score": ranked[0]["score"],
                "eq_km": ranked[0]["eq_km"],
                "margin": round(ranked[0]["score"] - ranked[1]["score"], 1) if len(ranked) > 1 else None,
                "runner_up": ranked[1]["name"] if len(ranked) > 1 else None,
            })
        monday -= timedelta(days=7)
    return out


def closed_months(rows: list[list], cfg: dict, today: date) -> list[dict]:
    """Alle volledig afgeronde kalendermaanden, nieuwste eerst."""
    if not rows:
        return []
    first = date.fromisoformat(rows[0][1])

    out = []
    year, month = today.year, today.month
    for _ in range(cfg["hall_of_fame"]["max_months"] + 1):
        month -= 1
        if month == 0:
            year, month = year - 1, 12
        start = date(year, month, 1)
        end = date(year + (month == 12), month % 12 + 1, 1) - timedelta(days=1)
        if end < first:
            break
        ranked = score_window(rows, cfg, start, end)
        ranked = [r for r in ranked if r["activities"] >= cfg["hall_of_fame"]["min_activities"]]
        if ranked:
            out.append({
                "label": MONTHS_NL[month - 1].capitalize(),
                "sub": str(year),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "winner": ranked[0]["name"],
                "score": ranked[0]["score"],
                "eq_km": ranked[0]["eq_km"],
                "margin": round(ranked[0]["score"] - ranked[1]["score"], 1) if len(ranked) > 1 else None,
                "runner_up": ranked[1]["name"] if len(ranked) > 1 else None,
            })
    return out


def main() -> None:
    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    if not STORE.exists():
        raise SystemExit("data/activities.json ontbreekt. Draai eerst scripts/sync.py.")

    activities = json.loads(STORE.read_text(encoding="utf-8"))
    rows = to_day_rows(activities)
    today = date.today()

    athletes = sorted({r[0] for r in rows})
    data = {
        "generated_at": datetime.now().isoformat(timespec="minutes"),
        "schema": ["athlete", "date", "sport", "km", "load", "count", "manual_km"],
        "canonical": {
            "blend_load_pct": cfg["blend_load_pct"],
            "factors": cfg["sport_factors"],
            "labels": cfg["sport_labels"],
        },
        "athletes": athletes,
        "rows": rows,
    }
    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    OUT_DATA.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")),
                        encoding="utf-8")

    weeks = closed_weeks(rows, cfg, today)
    months = closed_months(rows, cfg, today)

    tally: dict[str, dict] = defaultdict(lambda: {"weeks": 0, "months": 0})
    for w in weeks:
        tally[w["winner"]]["weeks"] += 1
    for m in months:
        tally[m["winner"]]["months"] += 1
    crowns = sorted(
        ({"name": n, **v} for n, v in tally.items()),
        key=lambda c: (-c["months"], -c["weeks"], c["name"]),
    )

    OUT_HIST.write_text(json.dumps({
        "generated_at": data["generated_at"],
        "weeks": weeks,
        "months": months,
        "crowns": crowns,
    }, ensure_ascii=False, indent=1), encoding="utf-8")

    size = OUT_DATA.stat().st_size / 1024
    print(f"{len(rows)} dagregels voor {len(athletes)} atleten -> data.json ({size:.0f} kB)")
    print(f"{len(weeks)} afgeronde weken, {len(months)} afgeronde maanden -> history.json")
    if crowns:
        top = crowns[0]
        print(f"Meeste titels: {top['name']} ({top['months']}x maand, {top['weeks']}x week)")


if __name__ == "__main__":
    main()
