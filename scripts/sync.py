"""Haal activiteiten op bij intervals.icu en zet ze in data/activities.json.

Slaat alleen RUWE data op. Geen scores, geen factoren. Zo kun je de weging in
config.json blijven tweaken zonder ooit opnieuw te hoeven syncen.

Athleten komen uit de omgevingsvariabele ATHLETES_JSON:

    [{"name": "Bart", "athlete_id": "i123456", "api_key": "xxx"}, ...]

Draaien:  python scripts/sync.py [dagen_terug]

De eerste keer wil je verder terugkijken dan de dagelijkse sync:
    python scripts/sync.py 120
"""

import json
import os
import sys
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import requests

BASE = "https://intervals.icu/api/v1"
ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / "data" / "activities.json"

# Velden die we bewaren. Verifieer deze met scripts/inspect_fields.py voordat
# je hierop vertrouwt -- intervals.icu kan veldnamen wijzigen.
FIELDS = ("id", "type", "start_date_local", "distance", "moving_time",
          "icu_training_load", "source", "name")


def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def load_athletes() -> list[dict]:
    raw = os.environ.get("ATHLETES_JSON")
    if not raw:
        sys.exit("ATHLETES_JSON ontbreekt. Zet hem als GitHub Secret of lokaal in je shell.")
    athletes = json.loads(raw)
    for a in athletes:
        missing = {"name", "athlete_id", "api_key"} - a.keys()
        if missing:
            sys.exit(f"Athlete mist velden {missing}: {a.get('name', '?')}")
    return athletes


def fetch(athlete: dict, oldest: date, newest: date) -> list[dict]:
    r = requests.get(
        f"{BASE}/athlete/{athlete['athlete_id']}/activities",
        params={"oldest": oldest.isoformat(), "newest": newest.isoformat()},
        auth=("API_KEY", athlete["api_key"]),
        timeout=60,
    )
    if r.status_code == 401:
        raise RuntimeError(f"{athlete['name']}: key geweigerd (401). Key vervallen of fout athlete_id?")
    r.raise_for_status()
    return r.json()


def slim(activity: dict, athlete: dict) -> dict:
    out = {k: activity.get(k) for k in FIELDS}
    out["athlete"] = athlete["name"]
    out["athlete_id"] = athlete["athlete_id"]
    # Handmatig ingevoerde activiteiten gooien we niet weg, we markeren ze --
    # build.py telt ze wel mee maar de site laat zien welk deel handmatig is.
    # source is altijd gevuld (GARMIN_CONNECT / UPLOAD / MANUAL / STRAVA / ...),
    # dus handmatig herken je aan de waarde, niet aan de afwezigheid.
    out["manual"] = (activity.get("source") or "").upper() == "MANUAL"
    return out


def main() -> None:
    cfg = load_config()
    athletes = load_athletes()

    lookback = int(sys.argv[1]) if len(sys.argv) > 1 else cfg["sync_lookback_days"]
    newest = date.today()
    oldest = newest - timedelta(days=lookback)

    store: dict[str, dict] = {}
    if STORE.exists():
        store = {a["id"]: a for a in json.loads(STORE.read_text(encoding="utf-8"))}

    # Namen uit een vorige ronde bijtrekken. Nodig voor activiteiten van voor we
    # athlete_id gingen opslaan -- die kan de hernoeming hieronder niet vinden.
    aliases = cfg.get("athlete_aliases", {})
    if aliases:
        fixed = 0
        for stored in store.values():
            new = aliases.get(stored.get("athlete"))
            if new:
                stored["athlete"] = new
                fixed += 1
        if fixed:
            print(f"{fixed} activiteiten hernoemd via athlete_aliases.")

    print(f"Sync {oldest} t/m {newest} voor {len(athletes)} atleten.\n")

    unmapped: Counter = Counter()
    factors = cfg["sport_factors"]

    for athlete in athletes:
        try:
            activities = fetch(athlete, oldest, newest)
        except Exception as exc:  # noqa: BLE001
            print(f"  {athlete['name']}: MISLUKT -- {exc}")
            continue

        # Hernoem je iemand in ATHLETES_JSON, dan moeten ook zijn oude activiteiten
        # mee. Anders verschijnt hij als twee atleten in het klassement.
        for stored in store.values():
            if stored.get("athlete_id") == athlete["athlete_id"]:
                stored["athlete"] = athlete["name"]

        with_load = 0
        for raw in activities:
            if not raw.get("id"):
                continue
            slimmed = slim(raw, athlete)
            store[slimmed["id"]] = slimmed
            if slimmed.get("icu_training_load"):
                with_load += 1
            if slimmed.get("type") and slimmed["type"] not in factors:
                unmapped[slimmed["type"]] += 1

        n = len(activities)
        coverage = f"{with_load / n * 100:.0f}%" if n else "n.v.t."
        print(f"  {athlete['name']:<12} {n:>3} activiteiten, load op {coverage}")

    STORE.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(store.values(), key=lambda a: a.get("start_date_local") or "")
    STORE.write_text(json.dumps(ordered, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"\n{len(ordered)} activiteiten opgeslagen in {STORE.relative_to(ROOT)}.")

    if unmapped:
        print("\nOnbekende sporttypes (krijgen factor 0 tot je ze in config.json zet):")
        for sport_type, count in unmapped.most_common():
            print(f"  {sport_type}  ({count}x)")


if __name__ == "__main__":
    main()
