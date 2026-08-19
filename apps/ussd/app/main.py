# apps/ussd/app/main.py — USSD webhook receiver (POST /ussd) + /simulate test endpoint; a thin adapter: session/menu handling only, delegates matching to apps/api
import logging

from flask import Flask, request
from flask_cors import CORS

from app import api_client as api_client_module
from app.menu_tree import get_node, search_counties, translate
from app.session_store import RedisSessionStore, SessionStoreError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("ussd.main")

app = Flask(__name__)

# DEV-ONLY CORS for the local phone-simulator UI (browser page calls us from a different origin).
# Allow ALL origins on /simulate and /ussd ONLY. flask-cors reflects any request Origin (allow-all)
# when one is sent, or emits `*` when absent. MUST be restricted to an explicit origin allow-list
# (or removed) before any real deployment — /simulate and /ussd are currently unauthenticated.
# /health is intentionally excluded so the readiness probe surface stays unchanged.
CORS(
    app,
    resources={
        r"/simulate": {"origins": "*"},
        r"/ussd": {"origins": "*"},
    },
)

session_store = RedisSessionStore()
api_client = api_client_module.ApiClient()

# Free-text nodes route typed input to a per-node handler (declaratively marked free_text in the
# menu tree). This keeps the free-text dispatch table-driven rather than a hardcoded if/else chain.
FREE_TEXT_HANDLERS = {}


def _render_node_text(node, context: dict) -> str:
    """Body of a menu screen without the CON/END prefix."""
    text = node.prompt_fn(context) if node.prompt_fn else (translate(context, node.prompt_key) if node.prompt_key else node.prompt)
    if node.terminal:
        return text
    lines = [text]
    for choice in sorted(node.options, key=lambda c: (len(c), c)):
        opt = node.options[choice]
        label = translate(context, opt.label_key) if opt.label_key else opt.label
        lines.append(f"{choice}. {label}")
    # Footer rules (Part 1 nav rework):
    #   - "0. Back" on every screen that actually has somewhere to go back to (node.back).
    #   - "00. Home" on every other screen; the welcome/home screen itself says "00. End" because
    #     there is nothing to go home to from home.
    if node.back:
        lines.append(f"0. {translate(context, 'back')}")
    if node.id == "welcome":
        lines.append(f"00. {translate(context, 'end')}")
    else:
        lines.append(f"00. {translate(context, 'home')}")
    return "\n".join(lines)


def render(node_id: str, context: dict) -> str:
    node = get_node(node_id, context)
    prefix = "END " if node.terminal else "CON "
    return prefix + _render_node_text(node, context)


def _enter_results(session: dict) -> str:
    """Run the matching call for the stored location+service, then render the results screen."""
    context = session["context"]
    location = context.get("location") or {}
    service = context.get("service") or ""
    try:
        matches = api_client.match_clinics(location["lat"], location["lng"], service)
    except api_client_module.ApiClientError as exc:
        logger.error("BLOCKING ISSUE: could not delegate matching to apps/api: %s", exc)
        return "END " + translate(context, "service_unavailable")
    context["results"] = matches
    session["node"] = "results"
    if not matches:
        session["node"] = "sub_location"
        return (
            "END "
            + translate(
                context,
                "no_matches",
                service=service,
                location=location.get("name", "your area"),
            )
        )
    # A match result is shown: ask apps/api to SMS the farmer the clinic name/distance/unique code
    # (fire-and-forget — a missing SMS config must never break the flow; see apps/api /notify).
    try:
        top = matches[0]
        api_client.notify(
            "match",
            session.get("phone", ""),
            {
                "clinic_name": top.get("name", ""),
                "distance_km": top.get("distance_km"),
                "unique_code": top.get("unique_code", ""),
                "service": service,
                "county": location.get("name", ""),
            },
        )
    except api_client_module.ApiClientError:
        logger.warning("Notify (match) failed — continuing without SMS", exc_info=True)
    return render("results", context)


def _enter_county_search(session: dict, query: str) -> str:
    """Type-to-search for a county: filter the 47-county list, then show numbered matches.

    USSD-native long-list pattern — the farmer types letters (as much or as little as they want,
    from 1 letter up to the full name; NO fixed length restriction) and the system returns numbered
    matches. More than PAGE_SIZE matches use the same continuous-numbering pagination as the service
    list ("98" = next page). Zero matches shows a clear retry message and stays on this node.
    """
    context = session["context"]
    matches = search_counties(query)
    if not matches:
        return "CON " + translate(context, "county_no_match") + "\n" + _render_node_text(get_node("county_search", context), context)
    context["county_matches"] = matches
    context["county_matches_page"] = 0  # a fresh search always starts at page 1
    session["node"] = "county_matches"
    return render("county_matches", context)


def _enter_sub_location(session: dict, text: str) -> str:
    """Store the farmer's free-text sub-location/area (e.g. "Kilimani", "Ruiru town") as TEXT.

    Deliberately NOT geocoded. LOGGED APPROXIMATION (not a bug): matching still uses the COUNTY
    CENTROID coordinate (from the chosen county) regardless of whether a sub-location was given —
    the sub-location is kept on context only for the farmer's record, until real geocoding is built.
    (Option "9" skips this step entirely — handled as a menu option, not via this free-text handler.)
    """
    context = session["context"]
    context["sub_location"] = text
    session["node"] = "results"
    return _enter_results(session)


def _enter_custom_service(session: dict, text: str) -> str:
    """A service not listed in the catalogue was typed as free text: store it AND flag it clearly
    as a free-text/uncatalogued service (`context["custom_service"] = True`) so it is distinguishable
    from catalogue matches later (e.g. for future admin review — no catalogue assumption)."""
    context = session["context"]
    context["service"] = text
    context["custom_service"] = True
    session["node"] = "county_search"
    return render("county_search", context)


def _enter_verify_license(session: dict, license_number: str) -> str:
    """Run the KVB license lookup for the typed license number, then render the result screen.

    Thin adapter discipline: the adapter only forwards the number to apps/api (which calls OUT to
    KVB) and renders the answer. No licensing logic lives here.
    """
    context = session["context"]
    context["license_number"] = license_number
    session["node"] = "verify_license_result"
    try:
        result = api_client.verify_license(license_number)
    except api_client_module.LicenseNotFoundError:
        return (
            f"END No vet is registered with KVB license number {license_number}. "
            f"Please double-check the number."
        )
    except api_client_module.ApiClientError as exc:
        logger.error("BLOCKING ISSUE: could not delegate KVB license verification to apps/api: %s", exc)
        return "END " + translate(context, "service_unavailable")
    context["verify_result"] = result
    # A verify lookup completed: SMS the farmer the result they just saw, and let apps/api send the
    # board a lookup summary (fire-and-forget; never breaks the flow).
    try:
        api_client.notify(
            "verify",
            session.get("phone", ""),
            {
                "license_number": license_number,
                "name": result.get("name", ""),
                "license_type": result.get("license_type", ""),
                "status": result.get("status", ""),
            },
        )
    except api_client_module.ApiClientError:
        logger.warning("Notify (verify) failed — continuing without SMS", exc_info=True)
    return render("verify_license_result", context)


FREE_TEXT_HANDLERS.update({
    "county_search": _enter_county_search,
    "sub_location": _enter_sub_location,
    "custom_service": _enter_custom_service,
    "verify_license": _enter_verify_license,
})


def _reset_flow_context(context: dict) -> None:
    """'00. Home' pressed away from the welcome screen: jump home AND reset the in-progress flow.

    The language choice is session-level (chosen on the very first screen) and survives; every other
    collected selection (animal_type, service, county location, sub-location, results, ...) is
    cleared so the farmer genuinely starts over. The session itself is NOT deleted — it stays alive.
    """
    keep = context.get("language")
    context.clear()
    if keep:
        context["language"] = keep


def handle_choice(session_id: str, session: dict, choice: str) -> str:
    """Advance the session by one keypress: follow the node's option to its target node."""
    context = session.setdefault("context", {})
    node_id = session["node"]

    if choice in ("00", "000"):
        # "00" is CONTEXT-DEPENDENT (Part 1 nav rework):
        #   - On the welcome/home screen it ENDS the session (goodbye, state deleted).
        #   - On ANY OTHER screen it jumps straight back to the welcome/home screen WITHOUT ending
        #     the session, resetting in-progress selections but keeping the session alive.
        if node_id == "welcome":
            session_store.delete(session_id)
            return "END " + translate(context, "goodbye")
        _reset_flow_context(context)
        session["node"] = "welcome"
        return render("welcome", context)

    node = get_node(node_id, context)

    if choice == "0":
        if node.back:
            session["node"] = node.back
            # Leaving a paginated list resets its page so a fresh look starts at page 1.
            if node.page_key:
                context[node.page_key] = 0
        return render(session["node"], context)

    target = node.options.get(choice)
    if target is None:
        # Free-text input nodes (declaratively marked free_text in menu_tree.py) accept any typed
        # text (county search, sub-location, custom service, a KVB license number) instead of
        # numbered options. "00"/"000"/"0" are handled above as home/end/back, so a free-text node
        # can never swallow those control presses.
        if node.free_text:
            handler = FREE_TEXT_HANDLERS.get(node_id)
            if handler:
                return handler(session, choice)
        return "CON " + translate(context, "invalid_choice") + "\n" + _render_node_text(node, context)

    if node.store and target.value is not None:
        context[node.store] = target.value
    if target.page is not None and node.page_key:
        # "98" next-page on a paginated list: advance that list's page in context.
        context[node.page_key] = target.page

    if target.next == "results":
        session["node"] = "results"
        return _enter_results(session)

    session["node"] = target.next
    return render(target.next, context)


def handle_request(session_id: str, phone: str, text: str) -> str:
    """Process one webhook call (one keypress worth of input) and return the next menu body."""
    if not session_id:
        logger.error("BLOCKING ISSUE: webhook received without a session_id")
        return "END Service error. Please try again."

    try:
        session = session_store.load(session_id)
    except SessionStoreError:
        logger.error("BLOCKING ISSUE: Redis unavailable for session %s — no in-memory fallback (statelessness)", session_id)
        return "END " + translate({}, "service_unavailable")

    if session is None:
        # A brand-new session starts at the LANGUAGE screen (before Welcome) so the farmer can
        # choose English or Kiswahili for the whole session.
        session = {"node": "language", "phone": phone, "context": {}}

    inputs = [part.strip() for part in text.split("*") if part.strip()] if text else []

    if not inputs:
        body = render(session["node"], session["context"])
    else:
        body = handle_choice(session_id, session, inputs[-1])

    # USSD sessions end when the response is an END screen (terminal details, "00", no-match).
    # Only persist on a CON continuation; ended sessions are cleared so state can't linger or resurrect.
    if body.startswith("CON "):
        try:
            session_store.save(session_id, session)
        except SessionStoreError:
            logger.error("BLOCKING ISSUE: Redis unavailable for session %s — no in-memory fallback (statelessness)", session_id)
            return "END " + translate(session["context"], "service_unavailable")
    else:
        try:
            session_store.delete(session_id)
        except SessionStoreError:
            logger.error("BLOCKING ISSUE: Redis delete failed for ended session %s", session_id)

    return body


@app.route("/ussd", methods=["POST"])
def ussd_webhook():
    """Endpoint a real telecom USSD gateway POSTs to on every keypress."""
    session_id = request.values.get("sessionId") or request.values.get("session_id")
    phone = request.values.get("phoneNumber") or request.values.get("phone") or "+254700000000"
    text = request.values.get("text", "")
    return handle_request(session_id, phone, text)


@app.route("/simulate", methods=["GET", "POST"])
def simulate():
    """Local sandbox mimic of a USSD gateway (Africa's Talking-style): curl keystrokes, see menu text.
    Reuses the same session_id and accumulates `text` (joined with *) exactly like a gateway would."""
    session_id = request.values.get("session_id") or request.values.get("sessionId") or "test-session"
    phone = request.values.get("phone") or request.values.get("phoneNumber") or "+254700000000"
    if request.values.get("reset") in ("1", "true", "yes"):
        session_store.delete(session_id)
        return f"Session {session_id} reset."
    text = request.values.get("text", "")
    return handle_request(session_id, phone, text)


@app.route("/health", methods=["GET"])
def health():
    """Readiness probe. Redis is the hard dependency; if it is unreachable this is a blocking issue."""
    redis_ok = session_store.ping()
    if not redis_ok:
        logger.error("BLOCKING ISSUE: Redis ping failed at /health")
    return {"status": "ok" if redis_ok else "redis_unreachable", "redis": "connected" if redis_ok else "unreachable"}


if __name__ == "__main__":
    # Local dev convenience (outside Docker). In the container gunicorn serves the app.
    app.run(host="0.0.0.0", port=8001)