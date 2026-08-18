"""Dump de ruwe velden van een paar activiteiten.

Draai dit EEN KEER met je eigen key voordat je de rest gebruikt. De veldnamen
van intervals.icu kunnen wijzigen, en sync.py gaat uit van de namen die je
hier ziet. Vergelijk de output met FIELDS in sync.py.

    python scripts/inspect_fields.py <athlete_id> <api_key>
"""

import json
import sys

import requests

BASE = "https://intervals.icu/api/v1"


def main() -> None:
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)

    athlete_id, api_key = sys.argv[1], sys.argv[2]

    r = requests.get(
        f"{BASE}/athlete/{athlete_id}/activities",
        params={"oldest": "2026-01-01", "newest": "2026-12-31", "limit": 3},
        auth=("API_KEY", api_key),
        timeout=30,
    )
    r.raise_for_status()
    activities = r.json()

    if not activities:
        print("Geen activiteiten gevonden in dit bereik.")
        return

    print(f"{len(activities)} activiteiten opgehaald.\n")
    print("Beschikbare velden op de eerste activiteit:")
    for key in sorted(activities[0].keys()):
        print(f"  {key}")

    print("\nEerste activiteit, volledig:")
    print(json.dumps(activities[0], indent=2, ensure_ascii=False)[:4000])


if __name__ == "__main__":
    main()
