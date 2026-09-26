# FlowerMoon în Codespaces

## Utilizare

[Creează spațiul de testare](https://codespaces.new/moontolito/FlowerMoon?quickstart=1), așteaptă configurarea și deschide pagina FlowerMoon. Există un singur port destinat utilizatorului: **8000**. Butonul **Deschide aplicația** pregătește conexiunea și afișează Transport. În mod normal nu folosești terminalul.

Pagina arată starea pornirii; dacă conexiunea se întrerupe, afișează **Încearcă din nou**. Reîncărcarea paginii reconectează aceeași sesiune. Închiderea și redeschiderea paginii nu închide aplicația. Dacă ai închis chiar fereastra Transport, revenirea în pagina `/app` o pornește din nou.

Un link către sesiune are forma `https://NUMELE-SESIUNII-8000.app.github.dev/`. Adaugă `/app` pentru deschidere directă. Folosește adresa generată de Codespaces, nu un nume copiat din capturile altui tester. Linkul este disponibil numai cât timp sesiunea rulează; când este oprită, reia sesiunea din [lista Codespaces](https://github.com/codespaces).

## Actualizarea unui Codespace existent

O sesiune creată înainte de această versiune nu primește automat fișierele și imaginea nouă. Pentru o sesiune curată folosește butonul din README. Nu șterge sesiunea veche dacă ai date de păstrat.

Pentru actualizarea celei existente, o singură dată:

1. În panoul **Source Control**, folosește meniul **… → Pull** pentru a lua versiunea nouă de pe `main`. Păstrează/rezolvă separat eventualele modificări locale; nu folosi resetări distructive.
2. Deschide paleta de comenzi cu **Ctrl+Shift+P** și alege **Codespaces: Rebuild Container**.
3. După reconstruire, deschide **8000 — FlowerMoon**. Linkurile vechi către 5901/6080 nu sunt pagina de intrare nouă.

## Date și testeri

Proiectele, cache-urile și exporturile rămân în `apps/transport/data/` și nu sunt comise în repository. Exporturile pot fi descărcate din Explorer-ul Codespaces. Aplicația desktop rulează pe Linux în sesiune; Microsoft Excel nu este instalat acolo.

Repository-ul și portul sunt private. Un tester trebuie să aibă acces la repository și să creeze propria sesiune; autentificarea GitHub protejează accesul. Nu este un serviciu public permanent. Configurația nu schimbă limitele de cheltuieli ale contului.

## Pentru dezvoltare

Portalul `web/portal/server.py` servește pagina, resursele noVNC și conexiunea WebSocket pe aceeași origine/port. Browserul nu trebuie să deschidă 6080 sau 5901. Serviciul pornește aplicația cu interpreterul fix `/opt/flowermoon-venv/bin/python`; o confirmare periodică de la bucla Tk stabilește dacă fereastra este activă. Browserul așteaptă și un cadru desenat înainte să ascundă starea de încărcare.

Hook-urile `postStartCommand` și `postAttachCommand` pornesc idempotent serviciul detașat de terminal. Un lock împiedică instanțele duplicate. Logurile sunt în `.runtime/portal.log` și `.runtime/transport.log`; nu sunt expuse prin HTTP. Setările VNC sunt interne containerului, protejat de accesul privat GitHub.

GitHub Actions verifică testele Transport, contractul portalului, containerul real desktop-lite și conectarea efectivă în Chromium prin noVNC. Artefactul `flowermoon-browser-verification` conține capturi și raportul ferestrei. Aceasta verifică aplicația și configurația containerului; autentificarea și interfața GitHub Codespaces sunt gestionate de GitHub.

Referințe: [crearea unui Codespace](https://docs.github.com/en/codespaces/developing-in-a-codespace/creating-a-codespace-for-a-repository), [configurația devcontainer](https://containers.dev/implementors/json_reference/), [desktop-lite](https://github.com/devcontainers/features/tree/main/src/desktop-lite), [API noVNC](https://github.com/novnc/noVNC/blob/v1.6.0/docs/API.md).
