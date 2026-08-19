# apps/ussd/app/menu_tree.py — Declarative USSD menu tree + fixed option lists for the "find nearest vet" flow (thin adapter, no business logic)
#
# USSD HAS NO GPS: location is chosen via the USSD-native "type to search" pattern (free text ->
# county-name filter -> numbered matches) rather than any fake device-location read. Coordinates are
# approximate COUNTY CENTROIDS only — a known, logged limitation (no geocoding infrastructure), so
# matching uses the county centroid, not the farmer's exact sub-location, until real geocoding is built.
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


# --- Languages ---------------------------------------------------------------
# The language choice is the VERY FIRST screen. "en"/"sw" are stored in session context for the rest
# of the session and drive every prompt/label via TRANSLATIONS below.
LANGUAGES = {
    "1": {"code": "en", "name": "English"},
    "2": {"code": "sw", "name": "Kiswahili"},
}

# --- Fixed option lists — menu-level constants only. Matching itself is delegated to apps/api
# over HTTP (see api_client.py), never re-implemented here.
ANIMALS = {
    "1": {"name": "Dog"},
    "2": {"name": "Cat"},
    "3": {"name": "Cattle"},
    "4": {"name": "Poultry"},
    "5": {"name": "Other"},
}

# Comprehensive veterinary service catalogue (PetCare business plan, architecture.md §3) — the
# canonical names below are exactly what is matched against clinic `services` (case-insensitive).
# Labels shown on screen are translated via the per-service `sw` name; the stored/matched value is
# always the canonical English name. The Clinic model's `services` field needs NO structural change.
SERVICES: List[Dict[str, str]] = [
    {"name": "Consultation", "sw": "Ushauri wa daktari"},
    {"name": "Vaccination", "sw": "Chanjo"},
    {"name": "Deworming & Tick/Flea Treatment", "sw": "Kutibu minyoo, utitiri na viroboto"},
    {"name": "Minor Surgery", "sw": "Upasuaji mdogo"},
    {"name": "Major Surgery", "sw": "Upasuaji mkubwa"},
    {"name": "Emergency / Mobile Visit", "sw": "Dharura / Ziara ya daktari kwa mnyama"},
    {"name": "Grooming", "sw": "Usafi wa mnyama"},
    {"name": "Boarding", "sw": "Kuwekwa wanyama"},
    {"name": "Dog / Pet Training", "sw": "Mafunzo ya mbwa / mnyama"},
    {"name": "Breeding Consultation", "sw": "Ushauri wa uzalishaji"},
    {"name": "Pet Sales Inquiry", "sw": "Uchunguzi wa uuzaji wa mnyama"},
    {"name": "Adoption Inquiry", "sw": "Uchunguzi wa kuasili mnyama"},
    {"name": "Laboratory Tests", "sw": "Uchunguzi wa maabara"},
    {"name": "Nutrition Advice", "sw": "Ushauri wa lishe"},
    {"name": "Dental Care", "sw": "Utunzaji wa meno"},
    {"name": "Castration / Spaying", "sw": "Kuhasiwa / kufanya upasuaji wa uzazi"},
    {"name": "Hoof Care", "sw": "Utunzaji wa kwato"},
    {"name": "Microchipping", "sw": "Kuambatisha chip ya utambulisho"},
    {"name": "Ultrasound / Imaging", "sw": "Ultrasound / Picha ya ndani ya mwili"},
    {"name": "Farm Health Visit", "sw": "Ziara ya afya ya shambani"},
    {"name": "Bulk Drug Purchase", "sw": "Ununuzi wa dawa kwa wingi"},
    {"name": "Post-Surgery Care", "sw": "Huduma ya baada ya upasuaji"},
    {"name": "Pregnancy / Whelping Care", "sw": "Huduma ya mimba / kujifungua"},
    {"name": "Euthanasia / Cremation", "sw": "Kutolewa kwa mnyama kwa amani / kuchoma mwili"},
]

# Pagination (ONE reusable pattern for both the service catalogue and any long county-search result):
#   - Up to PAGE_SIZE items per screen.
#   - Numbering is CONTINUOUS across pages (page 1 = items 1-9, page 2 = items 10-18, ...): the
#     number shown on screen IS the selection key, so typing "14" selects item 14 wherever it appears.
#   - NEXT_PAGE_KEY ("98") is reserved as "show the next page" and must never collide with a real item
#     number — keep the total item count well under ~90. DESIGN RULE (logged): all paginated lists
#     today (services + county matches) are far below that limit, so "98" is always safe.
PAGE_SIZE = 9
NEXT_PAGE_KEY = "98"

# The full official list of all 47 Kenya counties. USSD has no GPS, so we use the type-to-search
# pattern: the farmer types part of a county name, we filter (case-insensitive substring) and show
# numbered matches. Coordinates are APPROXIMATE COUNTY CENTROIDS (documented approximation — known,
# logged limitation: no geocoding infrastructure / no paid geocoding key, so matching uses the county
# centroid until real geocoding is built). They are used purely as lat/lng args for apps/api's match.
COUNTIES: List[Dict[str, Any]] = [
    {"name": "Mombasa", "lat": -4.0435, "lng": 39.6682},
    {"name": "Kwale", "lat": -4.1817, "lng": 39.4606},
    {"name": "Kilifi", "lat": -3.6305, "lng": 39.8499},
    {"name": "Tana River", "lat": -0.9200, "lng": 39.5660},
    {"name": "Lamu", "lat": -2.2748, "lng": 40.9027},
    {"name": "Taita-Taveta", "lat": -3.3167, "lng": 38.4833},
    {"name": "Garissa", "lat": -0.4536, "lng": 39.6460},
    {"name": "Wajir", "lat": 1.7500, "lng": 40.0667},
    {"name": "Mandera", "lat": 3.9167, "lng": 41.8333},
    {"name": "Marsabit", "lat": 2.3333, "lng": 37.9833},
    {"name": "Isiolo", "lat": 0.3542, "lng": 37.5822},
    {"name": "Meru", "lat": 0.0500, "lng": 37.6500},
    {"name": "Tharaka-Nithi", "lat": -0.2967, "lng": 37.7233},
    {"name": "Embu", "lat": -0.5333, "lng": 37.4500},
    {"name": "Kitui", "lat": -1.3667, "lng": 38.0167},
    {"name": "Machakos", "lat": -1.5167, "lng": 37.2667},
    {"name": "Makueni", "lat": -1.8000, "lng": 37.6167},
    {"name": "Nyandarua", "lat": -0.2167, "lng": 36.4500},
    {"name": "Nyeri", "lat": -0.4200, "lng": 36.9500},
    {"name": "Kirinyaga", "lat": -0.5000, "lng": 37.2833},
    {"name": "Murang'a", "lat": -0.7500, "lng": 37.1333},
    {"name": "Kiambu", "lat": -1.1667, "lng": 36.8333},
    {"name": "Turkana", "lat": 3.3333, "lng": 35.5833},
    {"name": "West Pokot", "lat": 1.5000, "lng": 35.1167},
    {"name": "Samburu", "lat": 1.1833, "lng": 36.6667},
    {"name": "Trans Nzoia", "lat": 1.0333, "lng": 34.9833},
    {"name": "Uasin Gishu", "lat": 0.5167, "lng": 35.2833},
    {"name": "Elgeyo-Marakwet", "lat": 0.7667, "lng": 35.5500},
    {"name": "Nandi", "lat": 0.1667, "lng": 35.1167},
    {"name": "Baringo", "lat": 0.6500, "lng": 35.9833},
    {"name": "Laikipia", "lat": 0.3667, "lng": 36.8833},
    {"name": "Nakuru", "lat": -0.3031, "lng": 36.0800},
    {"name": "Narok", "lat": -1.0833, "lng": 35.8667},
    {"name": "Kajiado", "lat": -2.1000, "lng": 36.7833},
    {"name": "Kericho", "lat": -0.3667, "lng": 35.2833},
    {"name": "Bomet", "lat": -0.7833, "lng": 35.3333},
    {"name": "Kakamega", "lat": 0.2833, "lng": 34.7500},
    {"name": "Vihiga", "lat": 0.0333, "lng": 34.7167},
    {"name": "Bungoma", "lat": 0.5667, "lng": 34.5500},
    {"name": "Busia", "lat": 0.4667, "lng": 34.1167},
    {"name": "Siaya", "lat": 0.0600, "lng": 34.2833},
    {"name": "Kisumu", "lat": -0.0917, "lng": 34.7680},
    {"name": "Homa Bay", "lat": -0.5200, "lng": 34.4500},
    {"name": "Migori", "lat": -1.0667, "lng": 34.4667},
    {"name": "Kisii", "lat": -0.6833, "lng": 34.7667},
    {"name": "Nyamira", "lat": -0.5667, "lng": 34.9833},
    {"name": "Nairobi", "lat": -1.2921, "lng": 36.8219},
]


def search_counties(query: str) -> List[Dict[str, Any]]:
    """Case-insensitive substring filter over the county list (the USSD type-to-search pattern)."""
    q = (query or "").strip().lower()
    if not q:
        return []
    return [c for c in COUNTIES if q in c["name"].lower()]


# --- Bilingual prompts/labels -------------------------------------------------
# English is canonical; Kiswahili is best-effort. Technical terms flagged with a "TODO-SW" comment
# are phrasing worth a native-speaker review later — they are common, understood phrasings, not
# invented nonsense.
TRANSLATIONS: Dict[str, Dict[str, str]] = {
    "en": {
        "language_prompt": "Chagua lugha / Choose language",
        "welcome": "Welcome to VetLink254 (Home)",
        "option_find_vet": "Find a vet",
        "option_verify_vet": "Verify a vet",
        "prompt_animal": "What type of animal?",
        "prompt_service": "What service is needed?",
        "page": "Page",
        "more": "More options",
        "custom_service_option": "Type a service not listed",
        "prompt_custom_service": "Type the name of the service needed:",
        "prompt_county_search": "Type part of your county name to search (1 letter or more):",
        "prompt_county_matches": "Counties matching:",
        "county_no_match": "No county found for that text. Try different letters.",
        "prompt_sub_location": "Type your area, or reply 9 to skip:",
        "skip": "Skip",
        "prompt_results": "Nearby clinics:",
        "results_prompt": "Clinics near {location} ({count} found):",
        "no_matches": "No verified clinics offer {service} near {location} right now. Try another service or area next time.",
        "distance": "Distance",
        "unique_code": "Unique code",
        "services": "Services",
        "county_sub_county": "County / Sub-county",
        "prompt_verify_license": "Enter the vet's KVB license number:",
        "verified_vet": "{name} is a VERIFIED KVB {license_type}.",
        "not_verified": "KVB license {number} is {status}. This vet is NOT currently verified.",
        "thank_you": "Thank you for using VetLink254.",
        "back": "Back",
        "home": "Home",
        "end": "End",
        "invalid_choice": "Invalid choice. Please try again.",
        "goodbye": "Thank you for using VetLink254. Goodbye!",
        "service_unavailable": "Service temporarily unavailable. Please try again shortly.",
        # Animal type labels (values stored are the canonical English names for clarity).
        "animal_1": "Dog",
        "animal_2": "Cat",
        "animal_3": "Cattle",
        "animal_4": "Poultry",
        "animal_5": "Other",
    },
    "sw": {
        "language_prompt": "Chagua lugha / Choose language",
        "welcome": "Karibu VetLink254 (Nyumbani)",
        "option_find_vet": "Tafuta daktari wa mifugo",
        "option_verify_vet": "Thibitisha daktari wa mifugo",
        "prompt_animal": "Mnyama wa aina gani?",
        "prompt_service": "Huduma gani inahitajika?",
        "page": "Ukurasa",
        "more": "Chaguzi zaidi",
        "custom_service_option": "Andika huduma isiyoorodheshwa",
        "prompt_custom_service": "Andika jina la huduma inayohitajika:",
        "prompt_county_search": "Andika sehemu ya jina la kaunti (herufi 1 au zaidi):",
        "prompt_county_matches": "Kaunti zinazolingana:",
        "county_no_match": "Hakuna kaunti iliyopatikana kwa maandishi hayo. Jaribu herufi nyingine.",
        "prompt_sub_location": "Andika eneo lako, au jibu 9 kuruka:",
        "skip": "Ruka",
        "prompt_results": "Kliniki za karibu:",
        "results_prompt": "Kliniki karibu na {location} ({count} zimepatikana):",
        "no_matches": "Hakuna kliniki iliyothibitishwa inayotoa {service} karibu na {location} kwa sasa. Jaribu huduma au eneo jingine baadaye.",
        "distance": "Umbali",
        "unique_code": "Nambari maalum",
        "services": "Huduma",
        "county_sub_county": "Kaunti / Eneo ndogo",
        "prompt_verify_license": "Andika nambari ya leseni ya KVB ya daktari:",
        # TODO-SW: "VERIFIED"/"NOT currently verified" phrasing — common and clear, worth native review.
        "verified_vet": "{name} ni daktari ALIYETHIBITISHWA wa KVB ({license_type}).",
        "not_verified": "Leseni ya KVB {number} ni {status}. Daktari huyu HAJATHIBITISHWA kwa sasa.",
        "thank_you": "Asante kwa kutumia VetLink254.",
        "back": "Nyuma",
        "home": "Nyumbani",
        "end": "Maliza",
        "invalid_choice": "Chaguo si sahihi. Tafadhali jaribu tena.",
        "goodbye": "Asante kwa kutumia VetLink254. Kwaheri!",
        "service_unavailable": "Huduma haipatikani kwa sasa. Tafadhali jaribu tena baadaye.",
        # Animal type labels.
        "animal_1": "Mbwa",
        "animal_2": "Paka",
        "animal_3": "Ng'ombe",
        "animal_4": "Kuku",
        "animal_5": "Nyingine",
    },
}


def translate(context: Dict, key: str, **kwargs) -> str:
    """Resolve a message id in the session's language (default English)."""
    lang = context.get("language", "en")
    table = TRANSLATIONS.get(lang) or TRANSLATIONS["en"]
    template = table.get(key) or TRANSLATIONS["en"].get(key) or key
    if kwargs:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError):
            return template
    return template


@dataclass
class MenuOption:
    """One numbered choice on a menu node: where it leads, what value to store."""
    next: str
    value: Any = None
    label: str = ""
    # label_key: message id in TRANSLATIONS rendered in the session's language (overrides `label`).
    label_key: Optional[str] = None
    # page: when set, selecting this option jumps the paginated `service` node to that page index.
    page: Optional[int] = None


@dataclass
class MenuNode:
    """A declarative menu screen. `options` maps a keypress -> MenuOption.

    - store: if set, the chosen option's `value` is saved into session context under this key.
    - back: node id to return to when the user presses 0.
    - terminal: when True the screen is an `END` message (no further input).
    - prompt_fn: optional callable(context) -> str for nodes whose text is dynamic.
    - prompt_key: message id in TRANSLATIONS rendered in the session's language.
    - free_text: when True the node takes free-text input (county search, sub-location, a license
      number, a custom service) instead of numbered options; the typed text is routed to the
      engine's per-node free-text handler.
    - page_key: for paginated list nodes (service, county_matches), the session-context key that
      stores the current page index; the engine resets it to 0 on back and advances it on "98".
    """
    id: str
    prompt: str = ""
    options: Dict[str, MenuOption] = field(default_factory=dict)
    store: Optional[str] = None
    back: Optional[str] = None
    terminal: bool = False
    prompt_fn: Optional[Callable[[Dict], str]] = None
    prompt_key: Optional[str] = None
    free_text: bool = False
    page_key: Optional[str] = None


def _build_static_nodes() -> Dict[str, MenuNode]:
    return {
        # Language FIRST, before Welcome. Bilingual by construction (both choices readable to a
        # first-time caller); once chosen it is stored and everything below renders in that language.
        "language": MenuNode(
            id="language",
            prompt="Chagua lugha / Choose language",
            store="language",
            options={
                "1": MenuOption(next="welcome", value="en", label="English"),
                "2": MenuOption(next="welcome", value="sw", label="Kiswahili"),
            },
        ),
        "welcome": MenuNode(
            id="welcome",
            prompt_key="welcome",
            options={
                "1": MenuOption(next="find_vet", label_key="option_find_vet"),
                "2": MenuOption(next="verify_license", label_key="option_verify_vet"),
            },
        ),
        "find_vet": MenuNode(
            id="find_vet",
            prompt_key="prompt_animal",
            store="animal_type",
            back="welcome",
            options={k: MenuOption(next="service", value=v["name"], label_key=f"animal_{k}") for k, v in ANIMALS.items()},
        ),
        # `service` is paginated (PAGE_SIZE per page, continuous numbering) and built dynamically by
        # get_node() — this static entry is only a structure/back-navigation placeholder that
        # get_node() overrides at render time.
        "service": MenuNode(
            id="service",
            prompt_key="prompt_service",
            store="service",
            back="find_vet",
            page_key="service_page",
        ),
        # Type-to-search for a long list (USSD-native): free text filters county names.
        "county_search": MenuNode(
            id="county_search",
            prompt_key="prompt_county_search",
            back="service",
            free_text=True,
        ),
        # Numbered county matches (dynamic, built from the search results in context; paginated with
        # continuous numbering when more than PAGE_SIZE counties match).
        "county_matches": MenuNode(
            id="county_matches",
            store="location",
            back="county_search",
            page_key="county_matches_page",
        ),
        # Free-text sub-location/area (e.g. "Kilimani", "Ruiru town") — stored as TEXT only; it is
        # NOT geocoded. Known approximation: matching uses the county centroid, not this sub-location.
        # The prompt is OPTIONAL: option "9" skips it (stores nothing, proceeds to results) because
        # many farmers won't know formal administrative sub-county names. Any other typed text is
        # stored as the free-text sub-location via the free-text handler.
        "sub_location": MenuNode(
            id="sub_location",
            prompt_key="prompt_sub_location",
            back="county_matches",
            free_text=True,
            options={
                "9": MenuOption(next="results", value=None, label_key="skip"),
            },
        ),
        "custom_service": MenuNode(
            id="custom_service",
            prompt_key="prompt_custom_service",
            back="service",
            free_text=True,
        ),
        "results": MenuNode(
            id="results",
            prompt="Nearby clinics:",
            back="sub_location",
        ),
        "clinic_details": MenuNode(
            id="clinic_details",
            terminal=True,
            prompt_fn=_format_clinic_details,
        ),
        "verify_license": MenuNode(
            id="verify_license",
            prompt_key="prompt_verify_license",
            store="license_number",
            back="welcome",
            free_text=True,
        ),
        "verify_license_result": MenuNode(
            id="verify_license_result",
            terminal=True,
            prompt_fn=_format_verify_license_result,
        ),
    }


def _format_verify_license_result(context: Dict) -> str:
    """END-screen body for the "verify a vet" flow, rendered from the API's live lookup result.

    Thin presentation only — the vet's license STATUS comes from apps/api (which calls OUT to KVB);
    no licensing logic lives in the USSD adapter.
    """
    result = context.get("verify_result") or {}
    license_number = context.get("license_number") or ""
    if result.get("status") == "active":
        name = result.get("name") or "This vet"
        license_type = result.get("license_type") or "veterinary practitioner"
        return translate(context, "verified_vet", name=name, license_type=license_type) + "\n" + translate(context, "thank_you")
    status = result.get("status") or "unknown"
    return (
        translate(context, "not_verified", number=license_number, status=status)
        + "\n"
        + translate(context, "thank_you")
    )


def _format_clinic_details(context: Dict) -> str:
    """END-screen body for a single clinic, rendered from the match result stored in context."""
    clinic = context.get("clinic") or {}
    services = ", ".join(clinic.get("services") or []) or "n/a"
    sub_county = clinic.get("sub_county") or "n/a"
    county = clinic.get("county") or "n/a"
    return "\n".join([
        clinic.get("name", "Unknown clinic"),
        f"{translate(context, 'distance')}: {clinic.get('distance_km')} km",
        f"{translate(context, 'unique_code')}: {clinic.get('unique_code') or 'n/a'}",
        f"{translate(context, 'services')}: {services}",
        f"{translate(context, 'county_sub_county')}: {county} / {sub_county}",
        translate(context, "thank_you"),
    ])


NODES = _build_static_nodes()


def build_paginated_node(
    node_id: str,
    entries: List[Dict[str, Any]],
    context: Dict,
    page_key: str,
    prompt: str,
    store: Optional[str] = None,
    back: Optional[str] = None,
    item_next: str = "results",
    extra_last: Optional[tuple] = None,
) -> MenuNode:
    """THE ONE reusable paginated-list node builder (service catalogue AND county-search results).

    Rules (shared by every paginated list, logged as the single pagination contract):
      - Up to PAGE_SIZE items per screen.
      - Continuous numbering ACROSS pages: item i is always keyed "i" (page 2 shows 10-18, not
        restarting at 1), so the number shown IS the selection key.
      - NEXT_PAGE_KEY ("98") is reserved for "next page" and can never collide with an item number
        while the total item count stays well under ~90 (design rule logged in menu_tree.py).
      - "0" back / "00" home are handled generically by the engine on every page (Part 1 rework).
      - `extra_last`: an optional (next, label_key) entry appended on the LAST page — used by the
        service catalogue to offer free-text custom-service entry after the final catalogue item.
    """
    total_pages = max(1, -(-len(entries) // PAGE_SIZE))
    page = min(max(int(context.get(page_key, 0) or 0), 0), total_pages - 1)
    start = page * PAGE_SIZE
    chunk = entries[start:start + PAGE_SIZE]
    node = MenuNode(id=node_id, prompt=prompt, store=store, back=back, page_key=page_key)
    for i, entry in enumerate(chunk, start=start + 1):
        node.options[str(i)] = MenuOption(
            next=item_next,
            value=entry["value"],
            label=entry["label"],
        )
    if page < total_pages - 1:
        node.options[NEXT_PAGE_KEY] = MenuOption(next=node_id, page=page + 1, label_key="more")
    elif extra_last is not None:
        extra_next, extra_label_key = extra_last
        node.options[str(len(entries) + 1)] = MenuOption(next=extra_next, label_key=extra_label_key)
    return node


def build_service_node(context: Dict) -> MenuNode:
    """Build the paginated service screen for the current page (PAGE_SIZE per page, continuous
    numbering; "98" = next page). The last page's extra entry leads to free-text custom-service
    entry (a service not listed is stored verbatim and flagged `custom_service: True` in context)."""
    lang = context.get("language", "en")
    entries = [
        {"label": svc["sw"] if lang == "sw" else svc["name"], "value": svc["name"]}
        for svc in SERVICES
    ]
    total_pages = max(1, -(-len(entries) // PAGE_SIZE))
    page = min(max(int(context.get("service_page", 0) or 0), 0), total_pages - 1)
    prompt = translate(context, "prompt_service")
    if total_pages > 1:
        prompt += f" ({translate(context, 'page')} {page + 1}/{total_pages})"
    return build_paginated_node(
        node_id="service",
        entries=entries,
        context=context,
        page_key="service_page",
        prompt=prompt,
        store="service",
        back="find_vet",
        item_next="county_search",
        extra_last=("custom_service", "custom_service_option"),
    )


def build_county_matches_node(context: Dict) -> MenuNode:
    """Build the numbered county-match screen from the search results. No fixed input-length limit
    on the search, so a broad query can match more than PAGE_SIZE counties — the SAME continuous-
    numbering pagination as the service list handles the overflow ("98" = next page)."""
    matches = context.get("county_matches") or []
    entries = [
        {"label": c["name"], "value": {"name": c["name"], "lat": c["lat"], "lng": c["lng"]}}
        for c in matches
    ]
    total_pages = max(1, -(-len(entries) // PAGE_SIZE))
    page = min(max(int(context.get("county_matches_page", 0) or 0), 0), total_pages - 1)
    prompt = translate(context, "prompt_county_matches")
    if total_pages > 1:
        prompt += f" ({translate(context, 'page')} {page + 1}/{total_pages})"
    return build_paginated_node(
        node_id="county_matches",
        entries=entries,
        context=context,
        page_key="county_matches_page",
        prompt=prompt,
        store="location",
        back="county_search",
        item_next="sub_location",
    )


def build_results_node(matches: list, location_name: str, context: Optional[Dict] = None) -> MenuNode:
    """Dynamically build the results screen from the match engine response (up to 3 clinics)."""
    node = MenuNode(
        id="results",
        prompt=translate(context or {}, "results_prompt", location=location_name, count=len(matches)),
        store="clinic",
        back="sub_location",
    )
    for index, match in enumerate(matches, start=1):
        node.options[str(index)] = MenuOption(
            next="clinic_details",
            value=match,
            label=f"{match.get('name')} - {match.get('distance_km')} km",
        )
    return node


def get_node(node_id: str, context: Dict) -> MenuNode:
    """Resolve a node id to a MenuNode. Dynamic nodes (service, county_matches, results) are rebuilt
    from session context because their options depend on the current page / search / match response."""
    if node_id == "service":
        return build_service_node(context)
    if node_id == "county_matches":
        return build_county_matches_node(context)
    if node_id == "results":
        matches = context.get("results") or []
        location = (context.get("location") or {}).get("name", "")
        return build_results_node(matches, location, context)
    return NODES[node_id]