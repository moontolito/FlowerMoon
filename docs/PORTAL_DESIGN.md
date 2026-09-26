# Pagina de intrare FlowerMoon

Problema observată: utilizatorul ajungea la un desktop gol, confunda portul VNC cu pagina web și trebuia să pornească aplicația manual. Testul anterior a confirmat desenarea aplicației în container, dar nu a reprodus cauza exactă a sesiunii albe din capturile utilizatorului.

Soluție: o singură pagină pe portul 8000, o acțiune principală pentru Transport și o acțiune secundară pentru Nesting. Conexiunea la desktop, pornirea și starea aplicației sunt gestionate de portal. Erorile au explicație și buton de reîncercare, în locul unui canvas gol.

Logo-ul furnizat este păstrat. Culorile urmează aplicația existentă: accent `#82478c`, fundal `#fafafa`, suprafețe albe și contururi `#e2e2e7`. Controalele au focus vizibil, stările conexiunii sunt anunțate prin `role=status`, iar pagina de intrare se adaptează la ecrane mici. Interfața desktop păstrează propriul layout, scalat în browser; lucrul detaliat este destinat unui laptop/desktop.

Verificări: testele UI existente păstrează comportamentul aplicației; testele browser verifică acțiunea principală, desenarea reală, reîncărcarea, navigarea înapoi, lățimea mobilă, Nesting și reîncercarea după eroare. Capturile generate de workflow permit verificarea vizuală. Un test de randare nu validează disponibilitatea viitoare a surselor externe meteo/routing.

Rezultat verificat pe 26 septembrie 2026: [rularea GitHub Actions](https://github.com/moontolito/FlowerMoon/actions/runs/36238396301) a trecut cele 51 de teste Transport, 8 teste ale portalului, 10 verificări UI, pornirea containerului real și cele 2 scenarii Chromium. Capturile desktop (1440 × 1000) și mobil (390 px lățime) au fost inspectate: conținut lizibil, fără suprapuneri sau derulare orizontală pe pagina de intrare; aplicația reală este vizibilă în browser. Interfața GitHub de creare a unui Codespace și sesiunea veche a utilizatorului nu au fost controlate în acest test.
