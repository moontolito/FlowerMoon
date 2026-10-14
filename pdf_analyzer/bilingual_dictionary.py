"""Editable deterministic Romanian-English search dictionary."""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import uuid4


DICTIONARY_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class BilingualEntry:
    entry_id: str
    name: str
    terms_ro: tuple[str, ...]
    terms_en: tuple[str, ...]

    @property
    def all_terms(self) -> tuple[str, ...]:
        return _unique_terms(self.terms_ro + self.terms_en)


@dataclass(frozen=True, slots=True)
class BilingualDictionary:
    schema_version: int
    name: str
    entries: tuple[BilingualEntry, ...]


def _unique_terms(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        term = " ".join(value.split())
        identity = term.casefold()
        if term and identity not in seen:
            seen.add(identity)
            result.append(term)
    return tuple(result)


def _entry(
    entry_id: str,
    name: str,
    terms_ro: str,
    terms_en: str,
) -> BilingualEntry:
    return BilingualEntry(
        entry_id=entry_id,
        name=name,
        terms_ro=_unique_terms(tuple(terms_ro.split(";"))),
        terms_en=_unique_terms(tuple(terms_en.split(";"))),
    )


def default_dictionary() -> BilingualDictionary:
    entries = (
        _entry(
            "contract",
            "Contract",
            "contract;contractual;acord;acord contractual",
            "contract;contractual;agreement;contract agreement",
        ),
        _entry(
            "contractor",
            "Contractor",
            "contractant;antreprenor;executant",
            "contractor;main contractor",
        ),
        _entry(
            "supplier",
            "Supplier / subcontractor",
            "furnizor;furnizori;subcontractant;subcontractanți;subcontractanti",
            "supplier;suppliers;vendor;vendors;subcontractor;subcontractors",
        ),
        _entry(
            "requirements",
            "Requirements",
            "cerință;cerințe;cerinta;cerinte;cerințe tehnice;cerinte tehnice",
            "requirement;requirements;technical requirements;required",
        ),
        _entry(
            "obligation",
            "Mandatory obligation",
            "trebuie;este obligatoriu;va trebui;are obligația;are obligatia",
            "shall;must;is required to;mandatory;obligation",
        ),
        _entry(
            "order",
            "Order",
            "comandă;comanda;comandă contractuală;comanda contractuala",
            "order;contract order;purchase order",
        ),
        _entry(
            "quotation",
            "Quotation / offer",
            "ofertă;oferta;cerere de ofertă;cerere de oferta;propunere comercială;propunere comerciala",
            "quotation;request for quotation;RFQ;offer;commercial proposal;bid",
        ),
        _entry(
            "delivery_terms",
            "Delivery terms",
            "termeni de livrare;condiții de livrare;conditii de livrare;termen de livrare;program de livrare",
            "terms of delivery;delivery terms;delivery schedule;delivery date;lead time",
        ),
        _entry(
            "deadline",
            "Deadline",
            "termen limită;termen limita;data limită;data limita;scadență;scadenta",
            "deadline;due date;time limit;expiry date",
        ),
        _entry(
            "milestone",
            "Milestone",
            "etapă;etapa;reper;jalon;termen intermediar",
            "milestone;project milestone;intermediate deadline",
        ),
        _entry(
            "documents",
            "Required documents",
            "document;documente;documentație;documentatie;documente solicitate;documente necesare",
            "document;documents;documentation;required documents;submittals",
        ),
        _entry(
            "drawing",
            "Drawings",
            "desen;desene;plan;planuri;desen tehnic;desene tehnice",
            "drawing;drawings;technical drawing;general arrangement;GA drawing",
        ),
        _entry(
            "approval",
            "Approval",
            "aprobare;aprobări;aprobari;aprobat;acceptare",
            "approval;approvals;approved;acceptance",
        ),
        _entry(
            "inspection",
            "Inspection",
            "inspecție;inspectie;inspecții;inspectii;verificare;control",
            "inspection;inspections;inspect;verification;check",
        ),
        _entry(
            "testing",
            "Testing",
            "test;teste;testare;încercare;incercare;încercări;incercari",
            "test;tests;testing;verification test",
        ),
        _entry(
            "quality",
            "Quality",
            "calitate;asigurarea calității;asigurarea calitatii;controlul calității;controlul calitatii",
            "quality;quality assurance;quality control;QA;QC",
        ),
        _entry(
            "certificate",
            "Certificates",
            "certificat;certificate;certificare;certificat de material",
            "certificate;certificates;certification;material certificate;material test certificate",
        ),
        _entry(
            "standard",
            "Standards and codes",
            "standard;standarde;normă;norma;norme;cod tehnic",
            "standard;standards;code;codes;technical code",
        ),
        _entry(
            "manufacturing",
            "Manufacturing",
            "producție;productie;fabricație;fabricatie;execuție;executie",
            "manufacturing;production;fabrication;workmanship",
        ),
        _entry(
            "welding",
            "Welding",
            "sudură;sudura;sudare;sudor;procedură de sudare;procedura de sudare",
            "weld;welding;welder;welding procedure specification;WPS",
        ),
        _entry(
            "coating",
            "Painting and coating",
            "vopsire;vopsea;acoperire;protecție anticorozivă;protectie anticoroziva",
            "painting;paint;coating;protective coating;corrosion protection",
        ),
        _entry(
            "electrical",
            "Electrical",
            "electric;electrice;echipament electric;echipamente electrice;tablou electric",
            "electrical;electrical equipment;switchboard;distribution board",
        ),
        _entry(
            "hvac",
            "HVAC",
            "ventilație;ventilatie;climatizare;încălzire;incalzire;răcire;racire",
            "HVAC;ventilation;air conditioning;heating;cooling",
        ),
        _entry(
            "packing",
            "Packing",
            "ambalare;ambalaj;conservare;protecție pentru transport;protectie pentru transport",
            "packing;packaging;preservation;transport protection",
        ),
        _entry(
            "transport",
            "Transport",
            "transport;expediere;livrare;manipulare;ridicare",
            "transport;shipping;shipment;delivery;handling;lifting",
        ),
        _entry(
            "installation",
            "Installation",
            "instalare;montaj;lucrări la amplasament;lucrari la amplasament",
            "installation;erection;site work;site installation",
        ),
        _entry(
            "commissioning",
            "Commissioning",
            "punere în funcțiune;punere in functiune;pornire;probe de punere în funcțiune",
            "commissioning;startup;start-up;commissioning tests",
        ),
        _entry(
            "warranty",
            "Warranty",
            "garanție;garantie;perioadă de garanție;perioada de garantie",
            "warranty;warranty period;guarantee;defects liability period",
        ),
        _entry(
            "penalty",
            "Penalties and damages",
            "penalitate;penalități;penalitati;daune;daune-interese",
            "penalty;penalties;damages;liquidated damages",
        ),
        _entry(
            "force_majeure",
            "Force majeure",
            "forță majoră;forta majora;caz de forță majoră;caz de forta majora",
            "force majeure;act of God",
        ),
        _entry(
            "payment",
            "Payment",
            "plată;plata;condiții de plată;conditii de plata;termen de plată;termen de plata",
            "payment;payment terms;terms of payment;payment schedule",
        ),
    )
    return BilingualDictionary(DICTIONARY_SCHEMA_VERSION, "Quotation RO-EN", entries)


def new_entry() -> BilingualEntry:
    return BilingualEntry(
        entry_id=f"custom_{uuid4().hex}",
        name="New concept",
        terms_ro=("termen românesc",),
        terms_en=("English term",),
    )


class BilingualDictionaryStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        default_dir = (
            Path(os.environ.get("LOCALAPPDATA", Path.home()))
            / "PDF Analyzer"
            / "profiles"
        )
        self.storage_dir = Path(storage_dir) if storage_dir else default_dir

    def load(self) -> BilingualDictionary:
        path = self.storage_dir / "bilingual_dictionary.json"
        if not path.is_file():
            return default_dictionary()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            dictionary = dictionary_from_payload(payload)
            self.validate(dictionary)
            return dictionary
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return default_dictionary()

    def save(self, dictionary: BilingualDictionary) -> None:
        self.validate(dictionary)
        path = self.storage_dir / "bilingual_dictionary.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(dictionary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary.replace(path)

    @staticmethod
    def validate(dictionary: BilingualDictionary) -> None:
        if (
            dictionary.schema_version != DICTIONARY_SCHEMA_VERSION
            or not dictionary.name.strip()
            or not dictionary.entries
        ):
            raise ValueError("The bilingual dictionary is invalid or incompatible.")
        identifiers = [entry.entry_id for entry in dictionary.entries]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Bilingual dictionary identifiers must be unique.")
        for entry in dictionary.entries:
            if not re.fullmatch(r"[a-z0-9_]{2,80}", entry.entry_id):
                raise ValueError("Every bilingual concept requires a stable identifier.")
            if not entry.name.strip() or not entry.terms_ro or not entry.terms_en:
                raise ValueError(
                    "Every bilingual concept requires a name and terms in both languages."
                )
            if any(len(term) > 100 for term in entry.all_terms):
                raise ValueError("Bilingual search terms cannot exceed 100 characters.")


def dictionary_from_payload(payload: dict) -> BilingualDictionary:
    if not isinstance(payload, dict):
        raise ValueError("The bilingual dictionary payload must be an object.")
    data = dict(payload)
    raw_entries = data.pop("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("The bilingual dictionary entries must be a list.")
    parsed_entries: list[BilingualEntry] = []
    for item in raw_entries:
        if not isinstance(item, dict):
            raise ValueError("Every bilingual dictionary entry must be an object.")
        terms_ro = item["terms_ro"]
        terms_en = item["terms_en"]
        if (
            not isinstance(terms_ro, list)
            or not isinstance(terms_en, list)
            or not all(isinstance(term, str) for term in terms_ro + terms_en)
        ):
            raise ValueError("Bilingual dictionary terms must be text lists.")
        parsed_entries.append(
            BilingualEntry(
                entry_id=str(item["entry_id"]),
                name=str(item["name"]),
                terms_ro=tuple(terms_ro),
                terms_en=tuple(terms_en),
            )
        )
    return BilingualDictionary(entries=tuple(parsed_entries), **data)
