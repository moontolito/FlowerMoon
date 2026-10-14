"""Editable bilingual category profiles for quotation-document analysis."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from uuid import uuid4


PROFILE_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class CategoryDefinition:
    category_id: str
    group: str
    name_ro: str
    name_en: str
    description: str
    enabled: bool
    color: str
    terms_ro: tuple[str, ...]
    terms_en: tuple[str, ...]
    context_ro: tuple[str, ...]
    context_en: tuple[str, ...]

    @property
    def display_name(self) -> str:
        return self.name_en or self.name_ro

    @property
    def subject_terms(self) -> tuple[str, ...]:
        return _unique_terms(self.terms_ro + self.terms_en)

    @property
    def context_terms(self) -> tuple[str, ...]:
        return _unique_terms(self.context_ro + self.context_en)


@dataclass(frozen=True, slots=True)
class CategoryProfile:
    profile_id: str
    name: str
    schema_version: int
    categories: tuple[CategoryDefinition, ...]


def _terms(value: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in value.split(";") if part.strip())


def _unique_terms(terms: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    result = []
    for term in terms:
        identity = " ".join(term.casefold().split())
        if identity and identity not in seen:
            seen.add(identity)
            result.append(term)
    return tuple(result)


def new_category() -> CategoryDefinition:
    return CategoryDefinition(
        category_id=uuid4().hex,
        group="Custom",
        name_ro="Categorie nouă",
        name_en="New category",
        description="",
        enabled=True,
        color="#607d8b",
        terms_ro=(),
        terms_en=(),
        context_ro=(),
        context_en=(),
    )


def default_profile() -> CategoryProfile:
    common_obligation_ro = _terms(
        "trebuie;este obligatoriu;va furniza;va transmite;este responsabil;se solicită;cerut de client"
    )
    common_obligation_en = _terms(
        "shall;must;is required;required to;shall provide;shall submit;contractor shall;client requires"
    )

    def category(
        category_id: str,
        group: str,
        name_ro: str,
        name_en: str,
        description: str,
        color: str,
        terms_ro: str,
        terms_en: str,
        context_ro: tuple[str, ...] = common_obligation_ro,
        context_en: tuple[str, ...] = common_obligation_en,
    ) -> CategoryDefinition:
        return CategoryDefinition(
            category_id=category_id,
            group=group,
            name_ro=name_ro,
            name_en=name_en,
            description=description,
            enabled=True,
            color=color,
            terms_ro=_terms(terms_ro),
            terms_en=_terms(terms_en),
            context_ro=context_ro,
            context_en=context_en,
        )

    categories = (
        category(
            "mandatory_obligations",
            "Contractual",
            "Obligații obligatorii",
            "Mandatory obligations",
            "Formulări care pot crea o obligație directă pentru ofertant sau contractor.",
            "#c62828",
            "trebuie;este obligatoriu;obligatoriu;va furniza;va executa;este responsabil;se va asigura",
            "shall;must;is required;required to;shall provide;shall perform;contractor shall;responsible for",
            (),
            (),
        ),
        category(
            "contract_scope",
            "Contractual",
            "Contract, scope și responsabilități",
            "Contract, scope and responsibilities",
            "Contractul, comanda, cerințele și limitele responsabilităților.",
            "#8e244d",
            "contract;contractor;cerință;cerințe;comandă;comandă contractuală;scopul furnizării;inclus;exclus;responsabilitate;în sarcina clientului;în sarcina furnizorului;limită de furnizare;interfață",
            "contract;contractor;requirement;requirements;requirments;order;contract order;purchase order;scope of supply;included;excluded;responsibility;battery limits;supply boundary;by client;by contractor;interface",
        ),
        category(
            "client_documents",
            "Contractual",
            "Documente cerute de client",
            "Required client documents",
            "Documentația, reviziile, aprobările și termenele de transmitere.",
            "#1565c0",
            "document;documentație;desen;plan;calcul;memoriu de calcul;fișă tehnică;certificat;manual;registru documente;listă documente;spre aprobare;documentație finală;conform execuției;revizie",
            "document;documentation;document submittal;vendor document;drawing;datasheet;calculation;calculation note;certificate;certification;manual;document register;VDRL;MDR;approval;review;as-built;final documentation;revision;shall submit;shall provide;must provide;must submit;document package;technical file;specification",
        ),
        category(
            "delivery_schedule",
            "Contractual",
            "Termene și condiții de livrare",
            "Delivery terms and schedule",
            "Date, etape, durate, întârzieri și penalități de livrare.",
            "#ef6c00",
            "termen de livrare;condiții de livrare;condițiile de livrare;termen limită;durată de execuție;etapă;reper;întârziere;prelungire;penalitate;valabilitate ofertă;dată scadentă",
            "terms of delivery;delivery terms;delivery schedule;deadline;lead time;milestone;completion date;due date;delay;extension;penalty for delay;liquidated damages;validity period;timeframe",
        ),
        category(
            "commercial_payment",
            "Comercial",
            "Condiții comerciale și plată",
            "Commercial and payment terms",
            "Preț, monedă, taxe, garanții și condiții de plată.",
            "#6a1b9a",
            "preț;monedă;plată;avans;reținere;garanție bancară;garanție de bună execuție;TVA;taxă;ajustare de preț;facturare",
            "price;currency;payment;advance payment;retention;bank guarantee;performance bond;VAT;tax;price adjustment;invoice;invoicing",
        ),
        category(
            "legal_risk",
            "Contractual",
            "Angajamente legale și risc",
            "Legal commitments and risk",
            "Răspundere, despăgubiri, reziliere, litigii și confidențialitate.",
            "#ad1457",
            "răspundere;despăgubire;penalitate;încălcare;reziliere;confidențialitate;proprietate intelectuală;litigiu;lege aplicabilă;forță majoră",
            "liable;liability;indemnity;indemnification;damages;penalty;breach;termination;confidentiality;intellectual property;dispute;dispute resolution;governing law;force majeure;payment terms",
        ),
        category(
            "changes_deviations",
            "Contractual",
            "Modificări, clarificări și deviații",
            "Changes, clarifications and deviations",
            "Schimbări de scope, excepții, ipoteze și neconcordanțe.",
            "#7b1fa2",
            "modificare;comandă suplimentară;abatere;deviație;excepție;clarificare;ipoteză;neconcordanță;conflict documente",
            "variation;change order;deviation;exception;clarification;assumption;discrepancy;document conflict;conflict of documents",
        ),
        category(
            "engineering_design",
            "Tehnic",
            "Proiectare și inginerie",
            "Engineering and design",
            "Bazele de proiectare, calculele și livrabilele de inginerie.",
            "#0277bd",
            "proiectare;bază de proiectare;durată de viață;memoriu de calcul;analiză structurală;încărcare;plan de ansamblu;desen de execuție;aprobare proiect",
            "engineering;design;design basis;design life;calculation;structural analysis;load;layout;general arrangement;shop drawing;design approval",
        ),
        category(
            "shelter_manufacturing",
            "Producție",
            "Producția shelterului metalic",
            "Metal shelter manufacturing",
            "Fabricație, structură, panouri, sudură și toleranțe.",
            "#2e7d32",
            "fabricație;producție;sudură;tăiere;asamblare;toleranță dimensională;structură metalică;tablă;profil;șasiu;cadru de bază;panou de perete;acoperiș;pardoseală",
            "fabrication;manufacturing;cutting;assembly;dimensional tolerance;structural steel;sheet metal;profile;base frame;wall panel;roof panel;floor",
        ),
        category(
            "coating_corrosion",
            "Producție",
            "Protecție anticorozivă și vopsire",
            "Corrosion protection and coating",
            "Pregătirea suprafeței, sisteme de vopsire și galvanizare.",
            "#558b2f",
            "coroziune;protecție anticorozivă;pregătirea suprafeței;sablare;vopsire;galvanizare;grund;strat final;culoare RAL",
            "corrosion;corrosive;corrosion resistance;pitting;corrosion protection;surface preparation;blasting;coating;paint system;NACE;galvanizing;cathodic protection;primer;topcoat;color code;RAL",
        ),
        category(
            "electrical_systems",
            "Tehnic",
            "Echipamente și instalații electrice",
            "Electrical equipment and systems",
            "Distribuție, UPS, cabluri, iluminat și protecții electrice.",
            "#00695c",
            "tablou electric;distribuție electrică;transformator;UPS;baterie;iluminat;priză;cablu;pat de cablu;împământare;legare echipotențială;paratrăsnet;iluminat de urgență;alarmă incendiu",
            "switchboard;distribution board;MCC;transformer;UPS;battery;lighting;socket;cable;cable tray;earthing;grounding;bonding;lightning protection;emergency lighting;fire alarm",
        ),
        category(
            "hvac_environment",
            "Tehnic",
            "HVAC și condiții interioare",
            "HVAC and internal conditions",
            "Climatizare, ventilație, temperatură, umiditate și presurizare.",
            "#00838f",
            "HVAC;aer condiționat;ventilație;încălzire;răcire;temperatură interioară;umiditate;sarcină termică;presurizare;filtrare",
            "HVAC;air conditioning;ventilation;heating;cooling;internal temperature;humidity;heat load;pressurization;filtration",
        ),
        category(
            "external_conditions",
            "Tehnic",
            "Condiții de mediu și încărcări",
            "Environmental conditions and loads",
            "Mediul exterior, încărcări climatice și zone periculoase.",
            "#455a64",
            "temperatură exterioară;încărcare din vânt;încărcare din zăpadă;seismic;umiditate;praf;mediu coroziv;altitudine;grad de protecție;zonă periculoasă",
            "ambient temperature;wind load;snow load;seismic;humidity;dust;corrosive atmosphere;altitude;IP rating;hazardous area;ATEX",
        ),
        category(
            "quality_testing",
            "Calitate",
            "Calitate, inspecții și teste",
            "Quality, inspection and testing",
            "Planuri de calitate, puncte de inspecție și teste FAT/SAT.",
            "#5d4037",
            "planul calității;plan de inspecție;inspecție;punct de oprire;punct de asistare;test de fabrică;test la amplasament;raport de test;neconformitate;listă de observații",
            "quality plan;ITP;inspection;inspections;test;testing;audit;validation;verification;acceptance criteria;hold point;witness point;FAT;SAT;factory acceptance test;site acceptance test;test report;NCR;non-conformance;rework;scrap;punch list",
        ),
        category(
            "standards_certification",
            "Calitate",
            "Standarde și certificări",
            "Standards and certification",
            "Standarde aplicabile, marcaje și inspecții terțe.",
            "#37474f",
            "standard aplicabil;cod;reglementare;marcaj CE;declarație de conformitate;certificare;inspecție terță parte",
            "applicable standard;code;regulation;CE marking;declaration of conformity;certification;third-party inspection",
        ),
        category(
            "subcontractors",
            "Commercial",
            "Subcontractanți și furnizori",
            "Subcontractors and suppliers",
            "Approval, obligations and liability for subcontracted supply.",
            "#7b5e57",
            "subcontractant;furnizor;subfurnizor;externalizare;aprobare subcontractant;răspundere subcontractant",
            "subcontractor;subcontractors;subcontracting;subcontracted;subcontract;subcontracts;supplier;suppliers;vendor;vendors;outsourcing;third-party supplier;subcontract approval;subcontract obligations;subcontract liability",
        ),
        category(
            "welding",
            "Manufacturing",
            "Sudură și calificări",
            "Welding and qualifications",
            "Welding procedures, personnel qualifications and heat treatment.",
            "#8d6e63",
            "sudură;sudor;procedură de sudare;calificare sudor;tratament termic;hartă suduri",
            "weld;welding;welder;welders;weldment;WPS;PQR;WPQR;PWHT;weld map",
        ),
        category(
            "materials",
            "Technical",
            "Materiale",
            "Materials",
            "Material families and construction materials.",
            "#546e7a",
            "material;aliaj;oțel;metal;polimer;plastic;ceramică;lemn;textil",
            "material;alloy;steel;metal;polymer;plastic;ceramic;wood;textile",
        ),
        category(
            "performance",
            "Technical",
            "Performanță și proprietăți",
            "Performance and properties",
            "Performance, durability, reliability and compatibility requirements.",
            "#3949ab",
            "performanță;durabilitate;sustenabilitate;compatibilitate;fiabilitate;proprietate;caracteristică",
            "performance;durability;sustainability;compatibility;reliability;property;characteristic",
        ),
        category(
            "packing_transport",
            "Livrare",
            "Ambalare, transport și livrare",
            "Packing, transport and delivery",
            "Ambalare, conservare, manipulare și limite de transport.",
            "#f57f17",
            "ambalare;conservare;transport;manipulare;ridicare;punct de ridicare;centru de greutate;gabarit de transport;loc de livrare;Incoterms",
            "packing;packaging;preservation;shipping;shipment;transport;freight;logistics;customs;handling;lifting;lifting point;center of gravity;transport dimensions;delivery location;Incoterms;FOB;CIF;EXW;DDP;insurance",
        ),
        category(
            "installation_commissioning",
            "Livrare",
            "Instalare și punere în funcțiune",
            "Installation and commissioning",
            "Lucrări la amplasament, supervizare, pornire și instruire.",
            "#e65100",
            "instalare;montaj;lucrări în șantier;punere în funcțiune;supervizare;pornire;instruire",
            "installation;erection;site work;commissioning;supervision;startup;training",
        ),
        category(
            "warranty_spares",
            "Post-livrare",
            "Garanție, mentenanță și piese de schimb",
            "Warranty, maintenance and spare parts",
            "Garanții, defecte, mentenanță și consumabile.",
            "#4527a0",
            "garanție;perioadă de garanție;defect;răspundere pentru defecte;piese de schimb;consumabile;mentenanță;service",
            "warranty;warranty period;defect;defects liability;spare parts;recommended spares;consumables;maintenance;service",
        ),
    )
    return CategoryProfile(
        profile_id="metal_shelter_quotation_ro_en",
        name="Metal Shelter Quotation - RO/EN",
        schema_version=PROFILE_SCHEMA_VERSION,
        categories=categories,
    )


def upgrade_profile(profile: CategoryProfile) -> CategoryProfile:
    """Add newly required defaults without removing user categories or custom terms."""
    required = default_profile()
    existing = {category.category_id: category for category in profile.categories}
    upgraded = []
    for category in profile.categories:
        baseline = next(
            (item for item in required.categories if item.category_id == category.category_id), None
        )
        if baseline is None:
            upgraded.append(category)
            continue
        upgraded.append(
            replace(
                category,
                terms_ro=_unique_terms(category.terms_ro + baseline.terms_ro),
                terms_en=_unique_terms(category.terms_en + baseline.terms_en),
                context_ro=_unique_terms(category.context_ro + baseline.context_ro),
                context_en=_unique_terms(category.context_en + baseline.context_en),
            )
        )
    upgraded.extend(
        category for category in required.categories if category.category_id not in existing
    )
    return replace(profile, categories=tuple(upgraded))


class CategoryProfileStore:
    def __init__(self, storage_dir: str | Path | None = None) -> None:
        default_dir = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PDF Analyzer" / "profiles"
        self.storage_dir = Path(storage_dir) if storage_dir else default_dir

    def load(self, profile_id: str = "metal_shelter_quotation_ro_en") -> CategoryProfile:
        path = self._path(profile_id)
        if not path.is_file():
            return default_profile()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            categories = tuple(self._category_from_payload(item) for item in payload.pop("categories"))
            profile = upgrade_profile(CategoryProfile(categories=categories, **payload))
            self.validate(profile)
            return profile
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return default_profile()

    def save(self, profile: CategoryProfile) -> None:
        self.validate(profile)
        path = self._path(profile.profile_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(profile), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(path)

    @staticmethod
    def validate(profile: CategoryProfile) -> None:
        if profile.schema_version != PROFILE_SCHEMA_VERSION or not profile.name.strip():
            raise ValueError("The category profile is invalid or incompatible.")
        identifiers = [category.category_id for category in profile.categories]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("Category identifiers must be unique.")
        for category in profile.categories:
            if not category.name_ro.strip() or not category.subject_terms:
                raise ValueError("Every category requires a name and subject terms.")

    def _path(self, profile_id: str) -> Path:
        return self.storage_dir / f"{profile_id}.json"

    @staticmethod
    def _category_from_payload(payload: dict) -> CategoryDefinition:
        data = dict(payload)
        for field in ("terms_ro", "terms_en", "context_ro", "context_en"):
            data[field] = tuple(data.get(field, ()))
        return CategoryDefinition(**data)
