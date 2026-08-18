# Kilometerklassement

Klassement voor een vriendengroep op basis van intervals.icu. Geen database,
geen backend. Een GitHub Action haalt vijf keer per dag de activiteiten op en
commit twee JSON-bestanden; Netlify serveert `public/`.

## Wat draait waar

| Waar | Wat |
|---|---|
| GitHub Action | Ophalen bij intervals.icu, samenvoegen, hall of fame vastzetten |
| `data/activities.json` | Ruwe opslag, groeit mee, staat in de privérepo |
| `public/data.json` | Geanonimiseerd, per atleet/dag/sport. Publiek. |
| `public/history.json` | Hall of fame, officiële weging. Publiek. |
| Browser | Scores uitrekenen, sliders, periodes wisselen |

De scores worden dus bij élk bezoek opnieuw berekend, in de browser. Daarom
kunnen bezoekers aan de factoren schuiven zonder dat het iets kost.

## Opzetten

**1. Verifieer de veldnamen** met je eigen key (intervals.icu → Settings →
Developer Settings):

```bash
pip install -r requirements.txt
python scripts/inspect_fields.py i123456 jouw_api_key
```

Staan `distance`, `moving_time`, `icu_training_load`, `type` en `source` erin?
Zo niet, pas `FIELDS` in `scripts/sync.py` aan.

**2. Eerste vulling, lokaal.** Kijk ver terug zodat de hall of fame meteen
historie heeft:

```bash
export ATHLETES_JSON='[{"name":"Bart","athlete_id":"i123456","api_key":"..."}]'
python scripts/sync.py 400
python scripts/build.py
cd public && python -m http.server 8000
```

Open http://localhost:8000. Let op: rechtstreeks `index.html` openen werkt
niet, want de browser blokkeert dan de fetch van `data.json`.

**3. Repo privé, secret zetten.** Settings → Secrets and variables → Actions →
New repository secret, naam `ATHLETES_JSON`.

**4. Netlify koppelen.** New site from Git → publish directory `public`,
build command leeg.

## Iemand toevoegen

Pas de secret `ATHLETES_JSON` aan, meer niet. Bij de eerstvolgende run staat
hij in het klassement, met terugwerkende kracht tot zover de lookback reikt.
Wil je zijn volle historie, draai dan lokaal één keer `python scripts/sync.py 400`
en commit het resultaat.

## Weging aanpassen

Alles in `config.json`, daarna `python scripts/build.py`.

- `sport_factors` — omrekening naar equivalente kilometers. Basis is
  tijd-equivalentie met hardlopen als anker: factor = 11 / gemiddelde snelheid
  in km/u. Sporten die ontbreken krijgen factor 0; `sync.py` meldt onbekende
  types.
- `blend_load_pct` — 0 is puur afstand, 100 is puur load. Beide worden
  genormaliseerd op de koploper, dus de score loopt van 0 tot 100.
- `hall_of_fame.min_activities` — onder dit aantal tel je niet mee voor een
  titel. Voorkomt dat iemand met één activiteit een lege week wint.

**Let op:** de hall of fame wordt bij elke build opnieuw uitgerekend met de
huidige weging. Verander je de factoren, dan verandert de geschiedenis mee.
Wil je dat niet, bevries `history.json` door hem uit de `git add` in de
workflow te halen.

## Sync-frequentie

`.github/workflows/sync.yml`, standaard vijf keer per dag. De workflow commit
alleen als er iets veranderd is, dus een lege run kost geen Netlify-build.
GitHub's cron is niet punctueel — een run kan tientallen minuten later vallen
of overgeslagen worden.

## Grenzen

Ongeveer veertig atleten is het praktische plafond: de sync doet één API-call
per persoon, en een klassement van vijftig namen leest niet meer prettig.
`data.json` groeit met circa 100 kB per jaar bij tien actieve atleten.
