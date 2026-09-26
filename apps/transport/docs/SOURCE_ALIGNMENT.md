# Sursele solicitate și integrarea efectivă

Actualizat 26 septembrie 2026. Acest document înlocuiește descrierile surselor active din documentele anterioare. Rapoartele NASA rămân dovezi istorice, nu descriu furnizorul actual.

## 1. Data Sources

| Parametru | Sursa cerută / utilizată | Acces și unități | Stare reală |
|---|---|---|---|
| Traseu, km, timp | OSM + Valhalla | Server Valhalla configurat; km, s | Integrat; acoperire dependentă de server |
| Altitudine punct și maxim eșantionat pe traseu | Copernicus DEM GLO-90, ediția 2021 | GeoTIFF public AWS; m EGM2008 | Integrat; DSM nominal 90 m, suprafață cu vegetație și clădiri |
| Temperatură | Open-Meteo Historical / ERA5 | `temperature_2m_max,min,mean` zilnic; °C | Integrat; 30 ani compleți, grilă globală |
| RH maximă / medie / minimă | Open-Meteo Historical / ERA5 | `relative_humidity_2m` orar; % | Integrat; 30 ani compleți solicitați, acoperire validă afișată |
| Țară și granițe | Natural Earth 1:10m | GIS local, poligoane | Integrat; generalizare cartografică |
| Distanță de coastă | Natural Earth 1:50m, varianta GIS permisă în tabel | Calcul local; km | Integrat; nu măsoară salinitatea |
| Vânt meteo, precipitații, ninsoare, strat/SWE | Open-Meteo Historical | Variabile dependente de model | Planificate, încă neextrase de aplicație |
| SO₂ / aerosoli de sare marină | CAMS Global EAC4 | ADS, cont/token/licență | Neintegrat; nu există rezultate CAMS în aplicație |
| SO₂ regional | CAMS European AQ Reanalyses | ADS, acoperire europeană | Neintegrat; nu este tratat ca sursă globală |
| Hazard seismic PGA | EFEHR / ESHM20 | Date Euro-Mediteraneene | Neintegrat; nu este tratat ca furnizor global |
| ag, Tc, sk, qb, pentru România | Hărțile UTCB/Encipedia integrate anterior la cererea utilizatorului | KML regional; g, s, kN/m², kPa | Păstrate separat, orientative și de verificat; nu sunt EFEHR/Open-Meteo |

Sursele active nu mai includ NASA POWER sau altitudinea `/height` Valhalla. Lipsa datelor nu declanșează înlocuirea cu o sursă diferită.

Documentație oficială:

- [Open-Meteo Historical API](https://open-meteo.com/en/docs/historical-weather-api)
- [Copernicus DEM](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM), [arhiva publică GLO-90 și licența](https://registry.opendata.aws/copernicus-dem/), [formatul GeoTIFF](https://copernicus-dem-30m.s3.amazonaws.com/readme.html)
- [Valhalla](https://github.com/valhalla/valhalla), [OpenStreetMap](https://www.openstreetmap.org/), [Natural Earth](https://www.naturalearthdata.com/)
- [CAMS EAC4](https://ads.atmosphere.copernicus.eu/datasets/cams-global-reanalysis-eac4?tab=overview), [CAMS European reanalyses](https://www.copernicus.eu/en/access-data/copernicus-services-catalogue/cams-european-air-quality-reanalyses)
- [EFEHR ESHM20](https://hazard.efehr.org/en/Documentation/specific-hazard-models/europe/eshm2020-overview/), [raportul modelului](https://doi.org/10.12686/a15)

## 2. Calculated Parameters

Temperatură: max/min ale extremelor zilnice ERA5 și max/min ale mediilor zilnice. RH: max, min și `sum(RH valide) / număr ore valide`, din seria orară UTC. Sunt statistici descriptive implementate de FlowerMoon, nu valori normative sau măsurători la amplasament. Perioada în 2026: 1996–2025. Pentru RH incompletă se păstrează statisticile disponibile, cu fracția de acoperire și observația de verificare; datele duplicate sau invalide structural sunt respinse.

Altitudine: cel mai apropiat eșantion DSM folosind metadatele GeoTIFF RasterPixelIsPoint, EPSG:4326. Datum vertical EGM2008. Pe traseu: maximum din cel mult 512 puncte, pas nominal 500 m, mărit pentru trasee lungi. Nu este garantat maximul continuu între puncte. Dacă profilul este incomplet, maximul traseului este indisponibil; cota destinației rămâne separată. Lipsa dalei nu devine automat zero.

Coastă: distanță sferică minimă față de segmente GIS; metodă geometrică proprie, fără praguri de clasificare ISO.

## 3. Corrosion Estimation

TOW și Corrosion Environment Index rămân neimplementate/nevalidate. RH orară singură nu permite calculul TOW: trebuie extrasă și temperatura orară sincronizată și verificată metoda exactă în ediția standardului. Nu se atribuie C3/C5 din coastă, umiditate sau transport maritim. CAMS nu este simulat cu date meteo.

## 4. API / Data Extraction

Open-Meteo: `https://archive-api.open-meteo.com/v1/archive`, model explicit `era5`, `timezone=UTC`, `cell_selection=nearest`. Cache separat pentru temperatură și RH; identificatorul include endpoint, variabile, coordonate, perioadă și versiunea metodei. Rezultatele păstrează furnizorul efectiv, parametrii fără cheie, coordonatele cerute și cele returnate, unitățile, data extragerii și SHA-256 al răspunsului JSON serializat.

`FLOWERMOON_CLIMATE_API_KEY` selectează implicit endpointul abonat `https://customer-archive-api.open-meteo.com/v1/archive`. `FLOWERMOON_CLIMATE_URL` poate configura un endpoint HTTPS autorizat; cheia se păstrează separat, niciodată în URL-ul configurat, cache sau raport. Nu este necesar să trimiteți cheia în conversație. [Condițiile oficiale](https://open-meteo.com/en/terms) limitează API-ul gratuit la utilizări necomerciale; utilizarea comercială necesită accesul corespunzător. Niciun abonament nu este creat de aplicație.

Copernicus: `https://copernicus-dem-90m.s3.amazonaws.com/`, fără cont AWS. Numele dalelor folosește coordonatele colțului sud-vestic; fișierul include `COG_30` pentru eșantionarea de 3 secunde de arc a GLO-90, nu pentru produsul GLO-30. Cache local în `data/copernicus-dem-cache`, cu URL, momentul descărcării și hash-ul fiecărei dale. Citirea folosește Pillow, deja folosit de aplicație. Datele de vegetație/clădiri nu sunt eliminate.

CAMS și EFEHR sunt înscrise în registru cu `installed=False` și `configured=False`; nu se emit cereri sau rezultate din aceste surse. Integrarea CAMS necesită implementarea extragerii ADS, acceptarea licenței și configurarea accesului, nu doar introducerea unei chei.

## 5. Architecture

- `weather_config.py`: endpointul și politica de sursă meteorologică.
- `climate.py`, `humidity.py`: validare, statistici și cache pentru Historical API.
- `elevation.py`: citirea și eșantionarea GLO-90.
- `site_sources.py`: combină altitudinea, GIS și adaptoarele regionale.
- `site_environment/registry.py`: capacități active versus planificate și limite geografice.
- `site_conditions.py`: migrare cu arhivarea rezultatelor vechilor surse; valorile manuale sunt păstrate.
- Interfața arată proveniența efectivă și observațiile; nu schimbă eticheta unor valori NASA în Open-Meteo.

## 6. Validation & Limitations

Verificările automate includ: statistici orare și zile bisecte, unități, lipsuri și duplicate, cache, lipsa cheilor din rapoarte, migrare, coordonate din emisfere diferite, citirea centrelor GeoTIFF, profil incomplet, păstrarea modificărilor manuale și respingerea răspunsurilor pentru destinația anterioară. Verificările live sunt în `source-live-report.json`; perioadele de test sunt consemnate pentru fiecare locație. Verificarea unui punct nu certifică acoperirea fiecărei locații mondiale.

Valorile naționale ag/Tc/sk/qb nu sunt interschimbabile cu PGA, vântul meteo sau grosimea zăpezii. ESHM20 nu înlocuiește reglementările naționale. România rămâne doar un adaptor regional, nu limita arhitecturii.
