> Actualizare surse 2026-09-26: [SOURCE_ALIGNMENT.md](SOURCE_ALIGNMENT.md). Descrierile NASA / Valhalla DEM de mai jos sunt istorice; sursele active sunt Open-Meteo Historical si Copernicus GLO-90.

> Global update 2026-09-26: see [GLOBAL_ARCHITECTURE.md](GLOBAL_ARCHITECTURE.md). This specification supersedes older Romania-only assumptions, automatic C3/C5 suggestions and ERA5-Land adapter descriptions.

# Temperaturi climatice automate

Alegerea coordonatelor livrării pornește automat, în fundal, consultarea ultimilor
30 de ani calendaristici compleți (în 2026: 1996–2025). Rezultatul se salvează în
`siteConditions.climate`, iar temperaturile rezultate au metadate proprii.
Nu este necesară selectarea fiecărei valori. Corecțiile manuale sunt păstrate.

## Date și interpretare

- Sursă implicită fără cont: NASA POWER Daily API, temperaturi MERRA-2, zile în timp solar local.
- Adaptor alternativ configurabil: Open-Meteo Historical API, model explicit ERA5-Land;
  dacă este configurat și eșuează, se revine automat la NASA POWER.
- Se folosesc maximele/minimele zilnice la 2 m și temperatura medie zilnică.
- `Extreme climatice istorice`: maximul maximelor zilnice / minimul minimelor zilnice.
- `Extreme ale mediilor zilnice`: maximul și minimul seriei mediilor zilnice,
  nu media anuală, prognoza sau temperaturile unei zile curente.
- Temperaturile de proiect și intervalele implicite au fost eliminate la cererea
  utilizatorului. Valorile afișate sunt direct extremele istorice, fără limite
  +45/−30 °C, margini sau rotunjire conservatoare. Editarea manuală rămâne disponibilă.
- Cheile interne legacy `temperature.maxDesign/minDesign` sunt păstrate pentru
  compatibilitate, dar metadatele și etichetele definesc temperaturi istorice,
  nu temperaturi normative de proiectare. Noile valori au status CALCULATED.
- Reanaliza este regională, nu o stație meteo la amplasament. Seriile nu definesc
  perioade de revenire, factori de siguranță sau efecte climatice viitoare.
- Nu se atribuie valori climatice umidităților 100/26/90, al căror sens nu este documentat.

Seria este acceptată numai dacă fiecare zi, inclusiv zilele bisecte, are toate
cele trei valori finite în °C și minim ≤ medie ≤ maxim. Datele incomplete sau
sentinelele de lipsă sunt respinse. La eșec, nu se inventează temperaturi și nu
se introduc valori implicite; mesajul indică indisponibilitatea climei.
La schimbarea destinației, datele vechi nu pot fi atribuite noului punct.

## Persistență și surse

Cache per coordonate/perioadă/configurație în `data/climate-cache/` (sau lângă
fișierul de stare specificat). Rezultatele și data consultării sunt refolosite;
Refresh location forțează actualizarea. Salvat în proiect: sursa, modelul,
intervalul, numărul de zile, datele extremelor și regula de calcul.

Open-Meteo are condiții distincte pentru utilizarea comercială a API-ului;
pentru un endpoint configurat se pot seta `FLOWERMOON_CLIMATE_URL` și
`FLOWERMOON_CLIMATE_API_KEY`. Cheia nu este salvată în proiect sau în cache.
Folosirea sursei NASA de rezervă este afișată explicit, fără amestecarea seriilor.

Instalarea folosește implicit NASA POWER; nu presupune eligibilitatea pentru
API-ul gratuit Open-Meteo. Adaptorul Open-Meteo a fost de asemenea verificat live.

- https://open-meteo.com/en/docs/historical-weather-api
- https://open-meteo.com/en/terms
- https://power.larc.nasa.gov/docs/services/api/temporal/daily/

## Verificare

`test_climate.py`: perioadă, zile bisecte, extreme, lipsuri/unități, fallback NASA,
cache, eliminarea limitelor de proiect, suprascrieri manuale și schimbarea destinației.
`verify_climate_ui.py`: completare, afișare, salvare, răspuns întârziat,
indisponibilitate și tema întunecată.

Verificare live ERA5-Land pentru 44.17, 28.65: 10.958 zile, 1996–2025,
extreme +36,4/−16,0 °C, extreme medii zilnice +30,7/−14,0 °C. Grila raportată
de furnizor: 44.100006, 28.699997. Nu se aplică nicio anvelopă de proiect.
Acesta este un punct public de test, nu o validare a unui proiect al utilizatorului.

Testul live complet prin NASA POWER/MERRA-2, pentru același punct și perioadă:
extreme +35,85/−12,97 °C, extreme medii zilnice +30,49/−11,13 °C.
Diferențele dintre reanalize sunt păstrate vizibile prin identificarea sursei.
