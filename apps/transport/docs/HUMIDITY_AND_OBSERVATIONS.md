> Actualizare surse 2026-09-26: [SOURCE_ALIGNMENT.md](SOURCE_ALIGNMENT.md). Descrierile NASA / Valhalla DEM de mai jos sunt istorice; sursele active sunt Open-Meteo Historical si Copernicus GLO-90.

# Umiditate automată și observații — 2026-09-26

Această actualizare înlocuiește comportamentul anterior de ascundere a valorilor disponibile din hărți atunci când aplicabilitatea trebuie verificată.

## Valori și observații

- Valoarea numerică din harta regională rămâne afișată la altitudini ≥1000 m, cu mențiunea explicită în Observații că aplicabilitatea necesită verificare/calcul specific. Nu devine valoare normativă validată.
- Lângă o frontieră, dacă există o țară identificată și un adaptor cu valori pentru punct, valorile sunt păstrate cu observația de verificare a jurisdicției.
- Dacă există mai multe valori candidate în poligoane, lista le poate afișa separat, fără a selecta arbitrar una. `candidateValues` și `candidateValue` rămân distincte în datele salvate.
- Dacă sursa nu conține nicio valoare, nu există adaptor sau metoda nu este validată, nu se generează un număr. Nu sunt reintroduse reguli automate C3/C5.
- Valorile manuale sunt păstrate; cele din altă locație rămân marcate pentru verificare.

## Umiditate

Sursă globală: [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), parametrul `RH2M`, umiditate relativă la 2 m, `%`. [Metodologia NASA](https://power.larc.nasa.gov/docs/methodology/meteorology/) precizează că parametrii zilnici, cu excepțiile documentate, se bazează pe medii/sume ale valorilor orare. RH2M zilnic reprezintă media zilnică, nu extrema orară.

Perioadă: ultimii 30 de ani calendaristici încheiați; în 2026: 1996-01-01 — 2025-12-31, 10.958 zile. Agregare în baza temporală returnată de sursă (implicit NASA LST).

Metodă descriptivă proprie `rh-daily-max-mean-min-v1`:

- maxim = maximul mediilor zilnice valide;
- medie = suma mediilor zilnice valide / numărul lor;
- minim = minimul mediilor zilnice valide.

Nu sunt extreme orare, măsurători la amplasament, TOW sau un calcul ISO. Etichetele și observațiile descriu explicit baza zilnică. Unitățile trebuie să fie `%`; valori lipsă, bool, nonfinite, sub 0 sau peste 100 sunt excluse. O serie parțială poate produce rezultate, dar acestea au status VERIFY și proporția zilelor valide în Observații. O serie fără nicio valoare validă nu produce rezultate. Date cu format/calendar/perioadă invalide sunt respinse.

Cache separat `humidity-cache` lângă proiect, cu răspunsul brut, cererea, data extragerii și SHA256. Butonul Actualizează datele poate reinteroga sursa. Cererea rulează independent de temperatură și rută, iar răspunsurile pentru o destinație veche sunt ignorate.

Înregistrări noi: `humidity.maximum`, `humidity.mean`, `humidity.minimum`, `humidityAnalysis`. Datele manuale istorice `humidity.value1/2/3` nu sunt reinterpretate; apar separat dacă au valori. Restul fluxului de salvare/export păstrează proveniența.

Verificare live: Constanța 44.18,28.63 — maxim 100%, medie 76.13575835006388%, minim 43.58%; Tokyo 35.6762,139.6503 — maxim 98.79%, medie 80.50889122102573%, minim 46.74%. Ambele răspunsuri acoperă 10.958 zile. Valorile afișate sunt rotunjite la două zecimale; cele salvate păstrează precizia calculului. Vezi `humidity-live-report.json`.

## Ordinea listei

1. Locație: livrare, țară, altitudine amplasament.
2. Transport: plecare, condiție de livrare, distanță, altitudine rută, transport/protecție maritimă.
3. Climă și umiditate: temperaturi, umiditate maximă/medie/minimă.
4. Expunere și corozivitate: coastă, mediu maritim, categorii manuale/propuneri.
5. Condiții structurale: ag, Tc, zăpadă, vânt.
6. Indicatori suplimentari: TOW, index și aerosoli; disponibilitate explicită.

Coloane distincte: Parametru / Valoare / Sursă-stare / Observații. Selecția unui rând arată un extras de detalii; Surse & detalii și exportul JSON includ explicațiile și proveniența.

Teste: agregare RH, leap day, serie incompletă, unități și date invalide, cache/refresh, suprascrieri manuale, schimbarea destinației, răspuns întârziat, păstrarea valorilor de hartă, ordinea grupurilor și verificări native Tk în ambele teme.
