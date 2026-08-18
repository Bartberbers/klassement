# Kilometerklassement — projectbrief

Dit bestand heet `CLAUDE.md` zodat Claude Code het automatisch inleest bij het
openen van de map. Zet het in de hoofdmap van het project.

## Wat dit is

Een klassement voor een vriendengroep die traint met verschillende sporten
(roeien, ergometer, fietsen, hardlopen, zwemmen). Iedereen logt op
intervals.icu. Het doel is één gezamenlijk klassement, plus een erelijst van
week- en maandwinnaars.

Gebouwd voor ongeveer tien vrienden, niet voor publiek gebruik. Geen accounts,
geen inloggen. De eigenaar (Bart) beheert de API-keys handmatig.

## Huidige status

De code is compleet. De API-velden zijn op 15 augustus 2026 geverifieerd tegen
Bart's echte account (520 activiteiten). Wat nog niet gebeurd is:

- `sync.py` heeft nog nooit voor de hele groep gedraaid; alleen losse
  leescontroles op één account.
- Nog niet online gezet.

De bestanden in `public/` bevatten nu nepdata van zeven verzonnen atleten. Die
worden overschreven zodra `scripts/build.py` op echte data draait.

## Architectuur

Geen server, geen database. Drie lagen:

```
intervals.icu API
      ↓  scripts/sync.py           (GitHub Action, 5× per dag)
data/activities.json               (ruwe opslag, groeit mee, privé)
      ↓  scripts/build.py
public/data.json                   (geanonimiseerd, per atleet/dag/sport)
public/history.json                (hall of fame, officiële weging)
      ↓  Netlify serveert public/
browser                            (rekent scores uit, tekent de site)
```

De git-repo is de database. `data/activities.json` wordt elke run gecommit en
groeit aan; versiegeschiedenis komt gratis mee.

### Waarom de scores in de browser worden berekend

Zodat bezoekers aan de omrekenfactoren kunnen schuiven en het klassement live
zien herschikken. Dat is bewust het leukste onderdeel van de site: het maakt de
discussie over "telt fietsen te zwaar mee" aanschouwelijk.

De hall of fame wordt daarentegen **serverside vastgezet** met de officiële
weging uit `config.json`. Anders zou "winnaar van week 32" meeschuiven met wat
de bezoeker toevallig heeft ingesteld, en dan is het geen erelijst meer.

## Bestandsstructuur

```
klassement/
├── CLAUDE.md                    dit bestand
├── README.md                    installatiehandleiding voor de eigenaar
├── config.json                  factoren, weging, hall-of-fame-instellingen
├── requirements.txt             alleen `requests`
├── data/
│   └── activities.json          ruwe activiteiten (aangemaakt door sync.py)
├── scripts/
│   ├── inspect_fields.py        eenmalig: dump ruwe API-velden
│   ├── sync.py                  ophalen + upsert
│   └── build.py                 data.json + history.json genereren
├── public/
│   ├── index.html               de hele site, één bestand
│   ├── data.json                gegenereerd
│   └── history.json             gegenereerd
└── .github/workflows/sync.yml   cron, 5× per dag
```

Scripts draaien vanuit de hoofdmap (`python3 scripts/build.py`). De testserver
draait vanuit `public/` (`python3 -m http.server 8000`).

## Het scoremodel

Kilometers zijn niet vergelijkbaar tussen sporten, dus elke sport heeft een
omrekenfactor naar "equivalente kilometers". De basis is tijd-equivalentie met
hardlopen als anker: `factor = 11 / gemiddelde snelheid in km/u`. Fietsen komt
zo op 0.40, roeien op 0.85, zwemmen op 3.5.

De eindscore mengt twee genormaliseerde grootheden:

```
score = (eq_km / eq_km_koploper) × 100 × (1 − b)
      + (load  / load_koploper)  × 100 × b          waarbij b = blend_load_pct / 100
```

Beide worden op de koploper genormaliseerd, dus de score loopt altijd van 0 tot
100 en de nummer 1 heeft per definitie 100.

`icu_training_load` komt van intervals.icu en vereist hartslag- of
vermogensdata. De eigenaar heeft bevestigd dat iedereen in de groep een
hartslagband draagt; in de steekproef zat de dekking op 518 van 520. `sync.py`
logt per atleet het dekkingspercentage, zodat zichtbaar is als dat niet meer
klopt.

**Ergometer telt alleen via load.** `VirtualRow` staat bewust op factor 0. De
API levert voor binnenroeien geen afstand, dus een factor zou toch niets doen —
maar bij een atleet wiens apparaat wél meters doorgeeft zou hij ineens wel
tellen, en dan is de groep niet meer gelijk behandeld. Factor 0 sluit dat af.
Krachttraining, wandelen en skiën staan om dezelfde reden op 0. `VirtualRide`
staat wél op 0.4: daar komen soms echte kilometers binnen en dat is zo gewenst.

**De JS in `index.html` en de Python in `build.py` implementeren dezelfde
formule.** Wijzig je er één, wijzig dan de ander mee, anders wijkt de hall of
fame af van wat de site toont.

## Beslissingen die niet ongedaan gemaakt moeten worden

- **Geen OAuth, geen self-service koppeling.** Bewust gekozen: het scheelt een
  backend. De eigenaar verzamelt de keys zelf en zet ze in één GitHub Secret
  `ATHLETES_JSON`. Als het project ooit buiten de vriendengroep groeit is
  OAuth 2.0 met scopes de juiste route — intervals.icu ondersteunt dat, maar je
  moet een app laten registreren bij de ontwikkelaar.
- **Sync kijkt 21 dagen terug, niet 1.** Mensen uploaden hun training soms dagen
  later of corrigeren hem achteraf. Upsert gaat op activity ID, dus correcties
  overschrijven zonder duplicaten.
- **De workflow commit alleen bij wijziging.** Dat spaart Netlify-buildminuten
  (300 per maand gratis) bij vijf runs per dag.
- **Handmatig ingevoerde activiteiten worden geteld, niet geweerd.** Ze krijgen
  een label op de site. Op intervals.icu kun je zonder bestand een activiteit
  intikken; meestal is dat geen fraude maar een dubbele import. Zichtbaar maken
  werkt beter dan wegfilteren.
- **De site is in het Nederlands**, inclusief codecommentaar.

## Wat de API echt teruggeeft

Geverifieerd op 15 augustus 2026 tegen 520 activiteiten van één account. Alle
acht velden die `sync.py` gebruikt bestaan:

```
id, type, start_date_local, distance (meters), moving_time (seconden),
icu_training_load, source, name
```

Let op bij wijzigingen:

- **`id` is een string** (`"i175858124"`), geen getal. De upsert gaat daar goed
  mee om, maar reken er niet op dat je erop kunt sorteren als getal.
- **`source` is altijd gevuld**: `GARMIN_CONNECT`, `UPLOAD`, `MANUAL`. De oude
  aanname `manual = not bool(source)` was dus altijd onwaar en markeerde nooit
  iets. Nu: `source == "MANUAL"`. Handmatige activiteiten hebben ook
  `file_type: null` en geen `external_id`, maar `source` is de duidelijkste test.
- **`distance` is `null` bij binnensporten.** In de steekproef: alle 65
  `VirtualRow`, 20 van 22 `VirtualRide`, alle `WeightTraining`, alle `Workout`.
  Ook `icu_distance` en `average_speed` zijn daar leeg — de meters komen niet
  mee van Garmin, ze zijn nergens op te halen. `build.py` vangt dit af met
  `(act.get("distance") or 0)`.
- **`icu_training_load` zat op 518 van 520.** Alleen twee `Workout`-activiteiten
  misten hem. De aanname dat iedereen een hartslagband draagt klopt.

Authenticatie gaat via basic auth: gebruikersnaam letterlijk `API_KEY`,
wachtwoord is de persoonlijke key. Basis-URL `https://intervals.icu/api/v1`.

Sporttypes die niet in `config.json` staan krijgen factor 0. `sync.py` print aan
het eind welke onbekende types het is tegengekomen — die lijst is de bron voor
het aanvullen van `sport_factors` en `sport_labels`. Uit de eerste controle
kwamen `OpenWaterSwim`, `AlpineSki`, `Transition` en `Workout`; die staan er nu
in. Verwacht meer zodra de rest van de groep is aangesloten.

## Privacy

De repo is privé, maar de Netlify-site is openbaar. `public/data.json` bevat
voornamen met dagelijkse afstanden en load; trainingsnamen, tijdstippen en
activiteit-ID's zijn er bewust uit gelaten. Wie het adres heeft kan dit zien.
Houd dat zo bij wijzigingen: voeg niets toe aan `data.json` wat je niet publiek
wilt hebben.

## Hoe de site eruitziet

`public/index.html` tekent het klassement als een roeibaan in bovenaanzicht:
links een uitslagkolom, rechts één doorlopend stuk water met per atleet een
baan, een boot en een gekleurd kielzog dat de sportverdeling toont. De baan is
ingezoomd op het veld — de laatste ligt op de startlijn, de koploper op de
finish — zodat er altijd spreiding is, ook in week 1. Achter elke boot staat de
achterstand in punten, niet in kilometers: de positie volgt de score inclusief
load, en een gat in kilometers zou daar niet mee overeenkomen.

De afspeelknop speelt de gekozen periode dag voor dag af. Tijdens die replay
schakelt de baan naar een absolute schaal, genormaliseerd op de eindstand van de
periode. Dat moet: normaliseer je per dag op de koploper van die dag, dan ligt
de leider altijd op de finish en vaart er niemand vooruit. Na afloop springt het
beeld terug naar de ingezoomde stand.

Sporten zonder afstand krijgen geen schuif in het "wat als"-paneel, want er valt
niets om te rekenen. Dat filter zit in `renderKnobs` en kijkt of er kilometers
in de data staan, niet of de sport voorkomt.

## Openstaande wensen

- "Wie zit in vorm"-indicator op basis van trend in plaats van totaal. Idee:
  grotere boeggolf bij wie boven zijn eigen gemiddelde zit.
- Eventueel de hall of fame bevriezen zodat een latere wijziging van de factoren
  de geschiedenis niet herschrijft (nu wordt hij elke build opnieuw berekend).

Vervallen: "grafiek van scoreverloop over de tijd" — de replay op de baan doet
dit, en beter dan een lijngrafiek zou doen.

## Praktisch plafond

Ongeveer veertig atleten. De sync doet één API-call per persoon, en een
klassement van vijftig namen leest niet meer prettig. `data.json` groeit met
ruwweg 100 kB per jaar bij tien actieve atleten.
