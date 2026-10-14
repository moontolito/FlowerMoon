# PDF Analyzer — aplicație desktop Python

PDF Analyzer este un reader PDF local construit integral în Python cu PySide6
și PyMuPDF. Nu folosește HTML, JavaScript, WebView, server web sau servicii
cloud.

Versiunea curentă include readerul din Milestone 1 și fundația de text din
Milestone 1.5: detectare text nativ, OCR local opțional și cache de coordonate.
Milestone 2A adaugă selecție, copiere și highlight-uri locale persistente.
Milestone 2B a introdus citări stabile și navigare la fragmentul sursă; în
Milestone 2G acestea au evoluat în note cu comentarii și taguri.
Milestone 2C adaugă liste de cuvinte-cheie, rezultate grupate și transformarea
rezultatelor în dovezi verificabile.
Milestone 2D adaugă un profil bilingv editabil pentru analiza documentelor de
ofertare, corelare pe paragraf/proximitate și scoruri explicabile de relevanță.
Milestone 2E fixează tema albă, adaugă o listă de lucru cu mai multe PDF-uri,
combinare locală și stări de analiză transferabile între colegi.
Milestone 2F adaugă exportul PDF standard. Milestone 2G introduce notele cu
comentarii, filtrare pe taguri și raportul grupat inserat înaintea PDF-ului.
Milestone 3A introduce interfața în engleză și proiecte portabile cu mai multe
PDF-uri și status de citire persistent pentru fiecare document.
Milestone 3B completează viewerul nativ cu thumbnails progresive, outline/bookmarks,
rotire cu selecții și marcaje aliniate, Save As, print și fullscreen.
Milestone 3C extinde profilul editabil cu categoriile industriale solicitate și
adaugă tabul `Standards` pentru standarde, certificate de material și coduri de
documente tehnice clasificate după contextul de obligație.

Milestone 3D adauga doua moduri de cautare: `Exact Search`, implicit si complet
determinist, si `Expanded Search`, care foloseste un dictionar tehnic local pentru
variante gramaticale, sinonime controlate si abrevieri industriale. Previzualizarea
arata cate forme vor fi cautate, iar fiecare rezultat extins indica termenul cerut,
forma gasita si regula care a produs potrivirea.

Milestone 3E adauga `Bilingual Search RO/EN`, bazat pe un dictionar local editabil.
Conceptele romanesti si englezesti sunt echivalente controlate, nu traduceri
generate automat. Dictionarul personal este salvat local si inclus in profilul de
analiza transferabil catre colegi. Profilurile mai vechi raman compatibile si
primesc automat dictionarul bilingv standard.

Milestone 3F adauga un dashboard pentru toate PDF-urile din workspace. Acesta
centralizeaza numarul de pagini, reading status, note si taguri, permite filtrarea
si deschiderea directa a documentului si poate exporta un raport general PDF.

Milestone 3G extinde dashboardul cu selectie pe documente si un export complet.
Modul `Full annotated package` combina overview-ul, rapoartele pe taguri si copiile
adnotate ale PDF-urilor selectate intr-un singur fisier navigabil.

Milestone 3H adauga bookmark-uri personale editabile, iar Milestone 3I introduce
filtrarea determinista a zgomotului din antete, subsoluri, numerotarea paginilor
si blocurile repetitive. Milestone 3J adauga masti vizuale dreptunghiulare pentru
includerea sau excluderea zonelor din analiza. Milestone 3K extinde mastile cu
Freehand, Polygon, copiere controlata si detectarea paginilor similare.
Milestone 3L adauga un raport Excel operational si editabil pentru documentele
selectate din dashboard, fara sa schimbe exporturile PDF existente.
Milestone 3M transforma automat toate rezultatele Categories si Standards in
note persistente cu taguri, pastrand rerularea analizei fara duplicate.
Milestone 3N elimina trunchierea din raportul PDF general: numele documentelor si
toate tagurile sunt afisate integral, iar Reading Status ramane editabil.
Milestone 3O securizeaza exportul Excel: textul extras din PDF, comentariile,
tagurile si numele documentelor sunt scrise ca text literal. Continutul care
incepe cu `=` nu mai este confundat cu o formula, iar formulele si hyperlinkurile
controlate de aplicatie raman active.
Milestone 4A adauga analiza batch pentru toate PDF-urile selectate si un raport
de management cu dashboard complet, toate rezultatele Categories/Standards,
delegare pe departamente si comentarii editabile.

## Pornire

1. Instalează dependențele o singură dată:
   `py -m pip install -r requirements.txt`
2. Rulează `Deschide PDF Analyzer.bat`.

În această etapă nu se generează EXE. Testarea se face numai prin BAT/Python.

## OCR local

OCR-ul necesită Tesseract 5 instalat local. Aplicația caută automat instalarea
standard Windows și verifică modelele `eng` și `ron`. Dacă motorul sau o limbă
lipsește, readerul continuă să funcționeze, iar panoul afișează o eroare
controlată. OCR-ul nu este pornit automat: după audit, utilizatorul apasă
`Rulează OCR` numai dacă există pagini fără text.

Paginile sunt pregătite implicit la 350 DPI pentru recunoaștere. Pentru desenele
foarte mari, rezoluția este limitată automat după numărul de pixeli pentru a evita
un consum necontrolat de memorie.

După finalizarea auditului textului, selectează textul cu mouse-ul. `Ctrl+C` îl
copiază, iar click dreapta oferă `Copiază`, `Evidențiază` și, peste un marcaj,
`Elimină evidențierea`. Marcajele sunt locale și nu modifică PDF-ul.

Acțiunea `Creează notă` deschide un dialog cu textul selectat, un comentariu
personal și taguri separate prin virgulă. Click pe notă păstrează zoomul,
navighează la pagina sursă și marchează temporar fragmentul. Notele sunt salvate
local separat de highlight-uri și nu modifică documentul.

În tabul `Căutare` poți introduce termeni pe linii separate sau poți lipi o listă
Markdown. Căutarea este locală și exactă, acceptă expresii din mai multe cuvinte,
grupează rezultatele și păstrează coordonatele fiecărei apariții. Selectează un
rezultat și apasă `Creează notă`. Termenul sau categoria este propus automat ca tag.

Tabul `Categorii` conține un profil RO/EN pentru oferte de sheltere metalice:
contract, obligații, documente cerute, termene, comercial, juridic, proiectare,
producție, electric, HVAC, calitate, transport, instalare și garanție. `Editează`
permite activarea, redenumirea sau completarea termenilor și adăugarea unor
categorii proprii. Termenii de subiect produc rezultate; termeni precum `shall`,
`must` și `trebuie` cresc relevanța când apar în același paragraf sau în apropiere.
Fiecare rezultat arată pagina, nivelul, scorul și motivele din tooltip.

Tabul `Standards` detectează local referințe ISO, EN, DIN, IEC, ASTM, ANSI, BS,
NF, JIS, API, NACE și SAE, certificate EN 10204 de tip 2.1, 2.2, 3.1 și 3.2,
precum și TDS, SDS, MSDS, DoC, DoP, CoC, CoA, MTC și CMTR. Rezultatele sunt
clasificate ca referințe sau cerințe obligatorii în funcție de formulările din
același paragraf. Click pe rezultat navighează la sursă, iar `Create Note`
deschide dialogul normal de comentariu și taguri.

`Deschide PDF-uri` acceptă unul sau mai multe documente. Când lista conține mai
multe fișiere, selectorul din header permite schimbarea documentului activ, iar
`Combină` creează un PDF nou în ordinea listei. Fișierele sursă nu sunt modificate.

În Milestone 3A, controalele au fost traduse în engleză: `Open PDFs`, `Combine`,
`Open Project` și `Save Project`. Un proiect `.pdfanalyzer-project.json` păstrează
ordinea PDF-urilor și statusul fiecăruia: `Not Read`, `Reading in Progress`, `Read`,
`Reviewed`, `Approved` sau `Needs Attention`. Căile sunt relative când proiectul și
PDF-urile pot fi mutate împreună. Fișierele lipsă sunt raportate controlat și nu
sunt șterse automat din proiect.

`Salvează stare` exportă profilul complet de categorii și lista din tabul
`Căutare`. Fișierul rezultat poate fi trimis unui coleg și aplicat cu `Încarcă
stare`. PDF-urile, evidențierile și notele nu sunt incluse în acest fișier.

Panoul `Detalii` este ascuns implicit pentru a lăsa mai mult spațiu readerului.
OCR-ul rămâne accesibil direct din toolbar. Interfața folosește momentan numai
tema albă, inclusiv editorul de categorii și toate câmpurile de text.

`Exportă adnotat` creează o copie nouă a documentului activ. Tagurile bifate în
tabul `Taguri` determină notele incluse. Raportul este inserat înaintea PDF-ului,
cu fiecare tag ca titlu și cu comentariile, pagina și link-ul către fragment sub
el. Highlight-urile manuale rămân galbene, iar notele sunt exportate ca
highlight-uri albastre discrete cu comentarii PDF standard. Nu se mai exportă
chenare dreptunghiulare. Originalul nu este modificat.

## Milestone 3D - Exact and Expanded Search

Modul extins este optional si nu schimba lista introdusa de utilizator. Exemple:
`subcontractor` poate identifica `supplier` sau `vendor`, `certificate` poate
identifica `certification`, iar `welding procedure specification` poate identifica
abrevierea `WPS`. Extinderile sunt locale, vizibile si verificabile; aplicatia nu
foloseste cautare semantica, traducere automata sau servicii cloud in acest
milestone.

## Milestone 3E - Bilingual Search RO/EN

Modul bilingv extinde termenii introdusi cu echivalente romanesti si englezesti
din 31 de concepte initiale pentru contracte, obligatii, documente, termene,
calitate, productie, sudura, electric, HVAC, livrare, instalare, garantie si
conditii comerciale. Sunt incluse forme romanesti uzuale cu si fara diacritice.

Butonul `Edit Dictionary` permite modificarea termenilor existenti si adaugarea
unor concepte personale. Fiecare concept necesita un nume, cel putin un termen
romanesc si cel putin un termen englezesc. Rezultatele arata expresia ceruta,
forma gasita si conceptul bilingv care a produs potrivirea.

`Exact Search` ramane modul implicit. Nici dictionarul bilingv, nici celelalte
moduri de cautare nu modifica PDF-ul si nu trimit continutul in cloud.

## Milestone 3F - Multi-document Analysis Dashboard

Butonul `Dashboard` inspecteaza in background toate PDF-urile incarcate si afiseaza
totalurile proiectului, apoi cate un rand pentru fiecare document: pagini, reading
status, note si taguri. Documentele lipsa sau invalide raman in lista cu o eroare
controlata. Lista poate fi filtrata dupa status sau tag, iar dublu-click deschide
PDF-ul selectat.

Reading status poate fi modificat direct in dashboard si actualizeaza proiectul
curent din memorie. Pentru persistenta in fisier se foloseste in continuare
`Save Project`.

`Export Overview PDF` creeaza un raport consolidat separat, fara sa modifice sau
sa combine PDF-urile sursa. Campul reading status al fiecarui document este un
formular PDF editabil in readerele compatibile. Modificarile facute ulterior in
raport nu se sincronizeaza automat inapoi in aplicatie.

## Milestone 3G - Consolidated Annotated Export

Coloana `Include` din dashboard controleaza documentele exportate. `Select Visible`
si `Clear Visible` opereaza numai asupra randurilor afisate de filtre. Documentele
lipsa sau invalide nu pot fi selectate.

Modul `Overview only` exporta doar raportul general pentru documentele bifate.
Modul `Full annotated package` creeaza un singur PDF in aceasta ordine:

1. overview-ul workspace-ului;
2. raportul pe taguri al primului document;
3. primul PDF cu highlights si comentarii;
4. aceeasi structura pentru urmatoarele documente.

Filtrul `Tag` activ limiteaza notele din pachet, dar nu elimina highlight-urile
manuale. Notele din fiecare tag sunt ordonate dupa pagina pe care apar in document.
Bookmark-urile globale permit navigarea la fiecare document, raport si fragment,
iar linkurile interne raman functionale dupa combinare.

Niciun mod de export nu poate suprascrie un PDF sursa. Fisierele originale nu sunt
modificate.

## Milestone 3H - Editable Bookmarks

Tabul `Bookmarks` separa cuprinsul original al PDF-ului de semnele create in
aplicatie:

- `PDF Bookmarks` contine structura existenta in fisier si ramane nemodificata;
- `My Bookmarks` contine bookmark-urile personale, salvate local pentru fiecare
  document.

`Add` memoreaza pagina, pozitia curenta si nivelul de zoom. Bookmark-ul poate fi
redenumit, sters, mutat in sus sau in jos si organizat ierarhic prin
`Indent`/`Outdent`. Selectarea lui revine la zona memorata chiar daca pagina a fost
rotita sau fereastra redimensionata.

`Generate from Notes and Tags` creeaza o structura navigabila cu tagurile drept
capitole si notele drept subcapitole. Generarea nu sterge bookmark-urile personale
existente. Atat exportul individual, cat si pachetul consolidat includ structura
`My Bookmarks`, fara sa modifice PDF-urile sursa.

Bookmark-urile personale sunt pastrate in profilul local al aplicatiei. Editarea
bookmark-urilor intr-o copie PDF exportata nu se sincronizeaza inapoi in
aplicatie.

## Milestone 3I - Search Noise Filtering

In tabul `Search`, optiunile `Headers`, `Footers`, `Page numbers` si
`Repeated text` controleaza zonele excluse din analiza. Ele sunt activate implicit
si se aplica identic pentru Search, Categories si Standards.

Filtrarea creeaza doar o vedere temporara a textului pentru analiza. Textul
original, cache-ul OCR, selectia, highlight-urile si notele nu sunt modificate.
Fiecare sumar afiseaza numarul de cuvinte filtrate, iar debifarea tuturor
optiunilor reproduce cautarea nefiltrata.

Blocurile repetitive sunt acceptate ca zgomot numai daca apar pe majoritatea
paginilor si sunt in zonele marginale sau contin indicatori controlati de tabel
tehnic, precum `revision` ori `document number`. Astfel, paragrafele de corp
repetate accidental nu sunt eliminate automat.

Optiunile sunt incluse in `Save Profile` si restaurate prin `Load Profile`.
Profilurile mai vechi raman compatibile si primesc setarile implicite. Procesarea
este complet locala si nu modifica PDF-ul sursa.

## Milestone 3J - Visual Area Masking

Butonul `Masks` deschide instrumentele de mascare vizuala. Se selecteaza
`Ignore area` sau `Keep area`, apoi `Current page` sau `All pages`. Dupa activarea
`Draw Rectangle`, utilizatorul trage direct peste pagina PDF:

- zonele rosii `Ignore` elimina din analiza cuvintele aflate in interior;
- zonele verzi `Keep` limiteaza pagina la una sau mai multe zone pastrate.

Mastile sunt stocate in coordonate normalizate si raman aliniate la zoom,
redimensionare si rotire. Lista permite navigarea la zona sursa, eliminarea unei
masti sau stergerea tuturor mastilor.

Mastile sunt salvate local pentru documentul curent. `Save Profile` si
`Load Profile` din tabul `Masks` folosesc un fisier separat
`.pdfanalyzer-mask.json`, transferabil catre un coleg. Un profil este validat
complet inainte sa inlocuiasca mastile documentului.

Filtrarea se aplica numai la urmatoarea rulare Search, Categories sau Standards.
PDF-ul, textul/OCR-ul, highlight-urile si notele nu sunt modificate. Instrumentele
avansate Freehand, Polygon si pagini similare sunt documentate separat in 3K.

## Milestone 3K - Advanced Visual Masking

Selectorul de forma din tabul `Masks` ofera:

- `Rectangle`: tragere de la un colt la cel opus;
- `Freehand`: desenare continua cu mouse-ul;
- `Polygon`: click pentru fiecare varf si dublu-click pentru finalizare.

`Redraw` pastreaza masca veche pana cand este finalizata o geometrie noua valida.
`Copy Pages` accepta pagini si intervale, de exemplu `2, 4-7`. Duplicatele exacte
nu sunt create.

`Apply Similar` compara local dimensiunea paginii, densitatea textului si
distributia acestuia intr-o grila geometrica. Aplicatia afiseaza paginile si
scorurile detectate si cere confirmare inainte de copiere. Nu se foloseste AI si
nu se aplica nimic automat.

`Undo` si `Redo` pastreaza pana la 50 de stari ale mastilor in sesiunea
documentului. Fiecare stare acceptata este salvata local. Profilurile Rectangle
din Milestone 3J sunt actualizate automat la schema noua si raman compatibile.

Escape anuleaza desenul activ. Pentru Polygon, Enter poate finaliza forma dupa
alegerea a cel putin trei puncte.

## Milestone 3L - Editable Excel Report

Butonul `Export Excel` din dashboard creeaza un fisier `.xlsx` separat pentru
documentele bifate. Filtrul `Tag` activ limiteaza notele incluse; `All tags`
exporta toate notele documentelor selectate.

Workbook-ul contine:

- `Summary`: totaluri calculate prin formule si distributia reading status;
- `Documents`: PDF, pagini, status editabil, numar de note si taguri;
- `Notes`: textul selectat, comentariul editabil, tagul, pagina si linkul PDF;
- `Tags`: numarul de aparitii si documentele acoperite;
- `Lists`: lista ascunsa folosita pentru validarea Reading Status.

Celulele galbene sunt editabile. Reading Status foloseste un dropdown controlat,
iar totalurile si numarul aparitiilor pe tag sunt formule Excel. Titlurile PDF si
linkurile din `Notes` deschid fisierul sursa; suportul pentru saltul exact la
pagina depinde de readerul PDF asociat in Windows. Excel poate afisa avertismente
de securitate pentru linkuri catre fisiere locale.

Modificarile facute in workbook nu se sincronizeaza inapoi in PDF Analyzer.
PDF-urile nu sunt incluse in `.xlsx`, nu sunt modificate si trebuie pastrate la
caile indicate pentru ca linkurile sa functioneze. Exporturile PDF individuale,
overview si pachet consolidat raman disponibile si neschimbate.

## Milestone 3M - Automatic Analysis Notes

La finalul analizei `Categories`, fiecare rezultat gasit este salvat automat ca
nota persistenta. Textul notei este paragraful sursa, comentariul explica
categoria si relevanta, iar numele categoriei devine tag.

La finalul `Analyze Standards`, fiecare standard, certificat sau document tehnic
detectat devine nota. Nota primeste doua taguri: clasificarea, de exemplu
`Mandatory Standard`, si referinta concreta, de exemplu `ISO 9001`.

Notele automate sunt create in ordinea aparitiei in document. Rularea repetata a
aceleiasi analize nu creeaza duplicate: sumarul afiseaza cate note au fost
adaugate si cate existau deja. Butoanele `Create Custom Note` raman disponibile
pentru comentarii sau taguri personale suplimentare.

Notele pot fi filtrate sau eliminate individual in tabul `Tags`. Daca o nota
automata este eliminata si analiza este rulata din nou, rezultatul lipsa va fi
creat din nou. Filtrele de zgomot si mastile vizuale se aplica inaintea analizei,
deci sunt salvate numai rezultatele vizibile pentru regulile active.

PDF-ul sursa nu este modificat. Notele devin highlights si comentarii PDF numai
in copiile exportate.

## Milestone 3N - Complete Editable PDF Overview

Raportul PDF creat din Dashboard nu mai scurteaza numele documentelor sau
tagurile cu `...`. Fiecare document foloseste un rand cu inaltime dinamica:

- numarul si numele complet al fisierului;
- numarul de pagini si note;
- lista completa de taguri, impartita automat pe mai multe linii;
- Reading Status intr-un camp PDF editabil.

Lista generala de taguri din partea de sus este de asemenea completa si se
imparte pe linii. Randurile se pagineaza automat, au index separat, accent
albastru si alternanta discreta de fundal. Campurile Reading Status folosesc un
fundal albastru deschis si un contur vizibil pentru a indica faptul ca pot fi
editate.

Layoutul este folosit atat pentru `Overview only`, cat si pentru prima parte a
unui `Full annotated package`. Numele si tagurile nu sunt eliminate pentru a
forta raportul pe o singura pagina; se adauga pagini atunci cand este necesar.

Editarea campurilor depinde in continuare de suportul pentru formulare PDF al
readerului folosit. PDF-urile sursa si celelalte tipuri de export nu sunt
modificate.

## Milestone 3O - Safe Excel Text Export

- Continutul extras din PDF si introdus de utilizator este exportat ca text
  literal, inclusiv atunci cand incepe cu `=`.
- Conversia automata a textului in formule sau URL-uri este dezactivata.
- Formulele Summary/Tags si hyperlinkurile catre PDF sunt create explicit si
  raman functionale.
- Exportul este protejat impotriva formulelor accidentale sau injectate prin
  textul documentelor.

## Milestone 4A - Workspace Batch Analysis and Management Report

Butonul `Analyze Selected` din Dashboard ruleaza Categories si Standards pentru
toate PDF-urile bifate intr-o singura operatie. Sunt folosite profilul de
categorii, filtrele de zgomot, mastile fiecarui document, textul nativ si OCR-ul
deja existent in cache. OCR-ul nu este pornit automat; paginile care inca au
nevoie de OCR sunt raportate separat.

Toate rezultatele sunt salvate automat drept note cu taguri. Rularea repetata nu
creeaza duplicate, iar eroarea unui document nu opreste analiza celorlalte.

Modul nou `Management report` exporta:

- dashboardul pentru toate documentele selectate;
- numele complete ale fisierelor si toate tagurile, cu randuri dinamice;
- toate constatarile Categories, Standards si notele personale;
- comentariul analistului si textul sursa integral, pe pagini de continuare;
- un selector PDF editabil `Delegated to` pentru Quality, Welding, Painting,
  Engineering, Production, Procurement, Commercial, Legal, HSE sau Project
  Management;
- un camp PDF editabil pentru comentariul managerului;
- bookmarks pentru documente si grupurile de taguri.

Raportul de management nu adauga paginile PDF sursa. Pentru un pachet care
include si documentele adnotate ramane disponibil `Full annotated package`.
Modificarile facute de manager in PDF-ul exportat nu se sincronizeaza inapoi in
aplicatie.

## Teste

`py -m unittest discover -s tests -v`

## Arhitectură

```text
PySide6 UI
    ↓
PdfSession (validare și stare thread-safe)
    ↓
PyMuPDF (citire și randare locală)
```

Randarea paginilor are loc într-un worker, nu în thread-ul interfeței. Paginile
sunt încărcate progresiv și eliberate când sunt departe de zona vizibilă.

OCR-ul folosește local Tesseract cu limbile `eng+ron`. Textul nativ are prioritate;
OCR-ul este rulat numai pentru paginile detectate fără strat de text și numai la
cererea utilizatorului. Niciun document nu este trimis în cloud.
