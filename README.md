# FlowerMoon

Aplicații FlowerMoon într-un singur spațiu: planificare transport, date despre amplasament și optimizare Nesting.

- **Transport:** alegi destinația, verifici traseul și vehiculul, consulți temperatura, umiditatea, altitudinea și condițiile de mediu disponibile. Poți modifica valorile și exporta calculul în Excel.
- **Nesting:** instrumentul existent pentru aranjarea pieselor, accesibil din aceeași pagină de intrare.

## Deschide FlowerMoon în browser

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/moontolito/FlowerMoon?quickstart=1)

1. Apasă **Open in GitHub Codespaces** de mai sus și creează spațiul de testare.
2. Așteaptă configurarea inițială. Pagina **FlowerMoon** se deschide automat; dacă browserul blochează deschiderea, apasă **Open in Browser** pentru **8000 — FlowerMoon** în panoul **Ports**.
3. Apasă **Deschide aplicația**. Pornirea și conectarea sunt automate.

Nu trebuie să rulezi comenzi Python, să alegi un desktop sau să introduci o parolă VNC. Poți salva adresa paginii FlowerMoon în favorite; funcționează cât timp Codespace-ul respectiv este pornit. Pagina `/app` deschide direct Transport.

**Ai deja un Codespace din versiunea veche?** Acesta păstrează configurația veche până la actualizare și reconstruire. Cea mai simplă variantă este un Codespace nou de pe `main`, din butonul de mai sus. Pentru a păstra datele din cel existent, vezi [actualizarea unei sesiuni existente](docs/CODESPACES.md#actualizarea-unui-codespace-existent).

Repozitoriul și portul rămân private. Fiecare tester cu acces la repository își creează propriul Codespace; linkul unei sesiuni private nu este un site public. Codespaces folosește cota contului GitHub. Oprește sesiunea când termini testarea.

## Fișiere organizate

```text
apps/
  transport/
    src/         codul aplicației și interfața
    assets/      logo, șablon Excel, date geografice și hărți
    tests/       teste unitare, verificări UI și exemple de date
    docs/        surse, climă și reguli pentru amplasament
    vendor/      tema Sun Valley și licența originală
    run.py       pornirea locală
    hosted.py    pornirea în browser
  nesting/       instrumentul HTML existent
web/portal/      pagina FlowerMoon și serviciul de conectare
tests/browser/  teste pentru deschidere, reconectare și erori
scripts/        pornire și verificare a containerului
docs/           ghid Codespaces și decizii de interfață
.devcontainer/  configurarea mediului de testare
.github/        verificări automate GitHub Actions
```

Proiectele și exporturile rămân în `apps/transport/data/`, în sesiunea ta, și nu sunt încărcate în Git. Pentru descărcarea unui Excel, salvează-l în `apps/transport/data/exports`, apoi alege **Download** din Explorer-ul Codespaces.

[Ghid Transport și limitele datelor](apps/transport/README.md) · [Ghid Codespaces](docs/CODESPACES.md) · [Verificări automate](https://github.com/moontolito/FlowerMoon/actions/workflows/transport-tests.yml)
