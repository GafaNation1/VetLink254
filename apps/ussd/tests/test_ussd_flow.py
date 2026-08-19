# apps/ussd/tests/test_ussd_flow.py — full session-flow logic using an in-memory session store and a mocked api_client
# Runs handle_request directly (the same code path the /ussd webhook and /simulate use),
# so the whole find-a-vet flow is proven without Redis or a live apps/api.
from app.main import handle_request

MATCHES = [
    {
        "id": 2,
        "name": "PetCare Global Clinic",
        "distance_km": 2.216,
        "unique_code": "VL254-KE-00002",
        "services": ["consultation", "vaccination"],
        "county": "Nairobi",
        "sub_county": "Westlands",
        "verification_status": "verified",
    }
]


def _to_county_search(sid, phone):
    """Drive a fresh English session from the language screen to the county-search screen."""
    handle_request(sid, phone, "")
    handle_request(sid, phone, "1")       # English
    handle_request(sid, phone, "1")       # Find a vet
    handle_request(sid, phone, "1")       # Dog
    return handle_request(sid, phone, "1")  # service page 1 -> Consultation -> county search


class TestFullFindVetFlow:
    def test_complete_flow(self, flow, fake_api_factory):
        fake = fake_api_factory(matches=MATCHES)
        sid = "+254700000001"
        phone = sid

        body = handle_request(sid, phone, "")
        assert body.startswith("CON ")
        assert "Chagua lugha / Choose language" in body
        assert "1. English" in body
        assert "2. Kiswahili" in body

        body = handle_request(sid, phone, "1")
        assert body.startswith("CON ")
        assert "Welcome to VetLink254 (Home)" in body
        assert "Find a vet" in body
        # Part 1: the welcome screen footer says "00. End" (nothing to go home to from home).
        assert "00. End" in body
        assert "00. Home" not in body

        body = handle_request(sid, phone, "1*1")
        assert body.startswith("CON ")
        assert "What type of animal?" in body

        body = handle_request(sid, phone, "1*1*1")
        assert body.startswith("CON ")
        assert "What service is needed? (Page 1/3)" in body
        assert "1. Consultation" in body
        assert "98. More options" in body
        # Part 1: non-welcome screens say "0. Back" and "00. Home".
        assert "0. Back" in body
        assert "00. Home" in body

        body = handle_request(sid, phone, "1*1*1*1")
        assert body.startswith("CON ")
        assert "Type part of your county name" in body
        assert "00. Home" in body

        body = handle_request(sid, phone, "1*1*1*1*nai")
        assert body.startswith("CON ")
        assert "Counties matching:" in body
        assert "1. Nairobi" in body

        body = handle_request(sid, phone, "1*1*1*1*nai*1")
        assert body.startswith("CON ")
        assert "Type your area, or reply 9 to skip:" in body

        body = handle_request(sid, phone, "1*1*1*1*nai*1*Kilimani")
        assert body.startswith("CON ")
        assert "PetCare Global Clinic" in body
        assert "2.216 km" in body
        # The adapter called apps/api with Nairobi's centroid coords and the canonical service name.
        assert fake.calls[-1] == {
            "lat": -1.2921,
            "lng": 36.8219,
            "service": "Consultation",
            "limit": 3,
        }
        # After a match result, the adapter asked apps/api to SMS the farmer the clinic summary.
        assert fake.notify_calls and fake.notify_calls[-1]["event"] == "match"
        assert fake.notify_calls[-1]["phone"] == phone
        assert fake.notify_calls[-1]["context"]["clinic_name"] == "PetCare Global Clinic"

        body = handle_request(sid, phone, "1*1*1*1*nai*1*Kilimani*1")
        assert body.startswith("END ")
        assert "PetCare Global Clinic" in body
        assert "VL254-KE-00002" in body

        # An END screen must clear the session so state cannot resurrect.
        assert flow.load(sid) is None

    def test_no_matches_ends_cleanly(self, flow, fake_api_factory):
        fake_api_factory(matches=[])
        sid = "+254700000002"
        phone = sid
        body = None
        for text in ("", "1", "1", "1", "1", "nai", "1", "Ruiru town"):
            body = handle_request(sid, phone, text)
        assert body.startswith("END ")
        assert "No verified clinics offer" in body
        assert flow.load(sid) is None

    def test_api_unavailable_ends_with_service_message(self, flow, fake_api_factory):
        fake_api_factory(error="apps/api unreachable")
        sid = "+254700000003"
        phone = sid
        body = None
        for text in ("", "1", "1", "1", "1", "nai", "1", "Ruiru town"):
            body = handle_request(sid, phone, text)
        assert body.startswith("END ")
        assert "Service temporarily unavailable" in body
        assert flow.load(sid) is None

    def test_back_navigation(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000005"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1")
        body = handle_request(sid, phone, "0")
        assert body.startswith("CON ")
        assert "What type of animal?" in body

    def test_invalid_choice_is_rejected(self, flow):
        sid = "+254700000006"
        phone = sid
        handle_request(sid, phone, "")
        body = handle_request(sid, phone, "9")
        assert body.startswith("CON ")
        assert "Invalid choice. Please try again." in body
        # session stays alive so the user can retry
        assert flow.load(sid) is not None


class TestHomeVsEnd:
    """Part 1 nav rework: "00" is context-dependent — end only from the welcome/home screen."""

    def test_00_on_welcome_screen_ends_session(self, flow):
        sid = "+254700000004"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        body = handle_request(sid, phone, "00")
        assert body == "END Thank you for using VetLink254. Goodbye!"
        assert flow.load(sid) is None

    def test_00_from_mid_flow_returns_to_home_without_ending_session(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000020"
        phone = sid
        # Drive deep into the flow: language -> welcome -> find vet -> animal -> service.
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1*1")
        handle_request(sid, phone, "1*1*1")
        body = handle_request(sid, phone, "1*1*1*00")
        assert body.startswith("CON ")
        assert "Welcome to VetLink254 (Home)" in body
        # The session is still alive (NOT deleted), and the language choice survived the reset.
        stored = flow.load(sid)
        assert stored is not None
        assert stored["node"] == "welcome"
        assert stored["context"]["language"] == "en"

    def test_00_mid_flow_resets_in_progress_selections(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000021"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1*1")
        handle_request(sid, phone, "1*1*1")
        # select Consultation (so animal_type + service are in context)
        handle_request(sid, phone, "1*1*1*1")
        body = handle_request(sid, phone, "1*1*1*1*00")
        assert "Welcome to VetLink254 (Home)" in body
        stored = flow.load(sid)
        # animal_type/service/location etc were cleared; only language survived.
        assert "animal_type" not in stored["context"]
        assert "service" not in stored["context"]
        assert "location" not in stored["context"]
        assert stored["context"].get("language") == "en"
        # Starting over works: "1" from the welcome screen goes to find-a-vet again.
        body = handle_request(sid, phone, "1")
        assert "What type of animal?" in body

    def test_00_from_home_still_ends_even_with_prior_flow(self, flow, fake_api_factory):
        # After returning home mid-flow, pressing "00" again ends the session for real.
        fake_api_factory(matches=MATCHES)
        sid = "+254700000022"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1*1")
        handle_request(sid, phone, "1*1*1")        # service page 1
        body = handle_request(sid, phone, "1*1*1*00")  # back home mid-flow
        assert "Welcome to VetLink254 (Home)" in body
        body = handle_request(sid, phone, "00")   # now on home -> end
        assert body.startswith("END ")
        assert "Goodbye" in body
        assert flow.load(sid) is None

    def test_000_behaves_like_00(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000023"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1*1")
        body = handle_request(sid, phone, "1*1*000")
        assert "Welcome to VetLink254 (Home)" in body
        assert flow.load(sid) is not None


class TestCountySearch:
    def test_zero_county_matches_shows_retry_and_stays_on_node(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000007"
        phone = sid
        _to_county_search(sid, phone)
        body = handle_request(sid, phone, "zzzz")
        assert body.startswith("CON ")
        assert "No county found for that text. Try different letters." in body
        assert flow.load(sid) is not None
        # typing a real county now proceeds to the matches screen
        body = handle_request(sid, phone, "nai")
        assert body.startswith("CON ")
        assert "1. Nairobi" in body

    def test_county_search_returns_multiple_matches(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000008"
        phone = sid
        _to_county_search(sid, phone)
        body = handle_request(sid, phone, "kis")
        assert body.startswith("CON ")
        assert "1. Kisumu" in body
        assert "2. Kisii" in body

    def test_single_letter_search_is_allowed_and_paginates(self, flow, fake_api_factory):
        # Part 2: no fixed input-length restriction — 1 letter is a valid query, and more than
        # PAGE_SIZE matches paginate with the SAME continuous-numbering pattern as services.
        fake_api_factory(matches=MATCHES)
        sid = "+254700000024"
        phone = sid
        _to_county_search(sid, phone)
        body = handle_request(sid, phone, "a")
        assert body.startswith("CON ")
        assert "Counties matching:" in body
        assert "1. " in body and "9. " in body
        assert "98. More options" in body  # overflow uses the shared next-page key
        # Advance to page 2 of the county matches.
        body = handle_request(sid, phone, "a*98")
        assert body.startswith("CON ")
        assert "10. " in body  # continuous numbering continues on page 2
        assert "98. More options" in body

    def test_can_select_county_on_later_page_via_continuous_number(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000025"
        phone = sid
        _to_county_search(sid, phone)
        handle_request(sid, phone, "a")
        handle_request(sid, phone, "a*98")
        # Pick county number 10 (the first item on page 2) by its continuous number.
        body = handle_request(sid, phone, "a*98*10")
        assert body.startswith("CON ")
        assert "Type your area, or reply 9 to skip:" in body
        stored = flow.load(sid)
        assert stored["context"]["location"]["name"] != ""  # a county was stored


class TestServicePagination:
    def test_next_page_uses_98_and_numbering_is_continuous(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000009"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1")

        body = handle_request(sid, phone, "1*1*1*98")
        assert body.startswith("CON ")
        assert "Page 2/3" in body
        assert "10. " in body  # continuous numbering continues (item 10 is the 1st of page 2)

        body = handle_request(sid, phone, "1*1*1*98*98")
        assert body.startswith("CON ")
        assert "Page 3/3" in body
        assert "25. Type a service not listed" in body

        # Back from page 3 returns to page 1 (page resets when leaving the service list).
        body = handle_request(sid, phone, "1*1*1*98*98*0")
        assert body.startswith("CON ")
        assert "What type of animal?" in body
        body = handle_request(sid, phone, "1*1*1*98*98*0*1")
        assert body.startswith("CON ")
        assert "Page 1/3" in body

    def test_select_service_by_continuous_number_on_page_2(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000026"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1")
        # Jump to page 2, then type "12" to pick item 12 directly (its continuous number).
        body = handle_request(sid, phone, "1*1*1*98")
        assert "12." in body
        body = handle_request(sid, phone, "1*1*1*98*12")
        assert body.startswith("CON ")
        assert "Type part of your county name" in body
        stored = flow.load(sid)
        assert stored["context"]["service"] == "Adoption Inquiry"  # SERVICES[11]
        assert "12." not in body

    def test_last_page_custom_service_free_text_is_flagged(self, flow, fake_api_factory):
        fake = fake_api_factory(matches=MATCHES)
        sid = "+254700000010"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1")
        handle_request(sid, phone, "1")

        # Navigate to the custom-service node (page 3's extra "25" option), one keypress per call.
        handle_request(sid, phone, "1*1*1*98")
        body = handle_request(sid, phone, "1*1*1*98*98")
        assert body.startswith("CON ")
        assert "Page 3/3" in body
        body = handle_request(sid, phone, "1*1*1*98*98*25")
        assert body.startswith("CON ")
        assert "Type the name of the service needed:" in body

        body = handle_request(sid, phone, "1*1*1*98*98*25*Pet grooming")
        assert body.startswith("CON ")
        assert "Type part of your county name" in body

        body = handle_request(sid, phone, "1*1*1*98*98*25*Pet grooming*nai")
        assert body.startswith("CON ")
        assert "1. Nairobi" in body

        body = handle_request(sid, phone, "1*1*1*98*98*25*Pet grooming*nai*1")
        assert body.startswith("CON ")
        assert "Type your area, or reply 9 to skip:" in body

        body = handle_request(sid, phone, "1*1*1*98*98*25*Pet grooming*nai*1*Ruiru town")
        assert body.startswith("CON ")
        # The custom service name was stored and matched (canonical value == the typed text).
        assert fake.calls[-1]["service"] == "Pet grooming"
        assert fake.notify_calls and fake.notify_calls[-1]["context"]["service"] == "Pet grooming"
        # The free-text custom service is FLAGGED in context for future admin review.
        stored = flow.load(sid)
        assert stored["context"]["custom_service"] is True
        assert stored["context"]["service"] == "Pet grooming"


class TestOptionalSubLocation:
    def test_skip_sub_location_with_9_proceeds_to_results(self, flow, fake_api_factory):
        fake = fake_api_factory(matches=MATCHES)
        sid = "+254700000027"
        phone = sid
        _to_county_search(sid, phone)
        handle_request(sid, phone, "nai")
        body = handle_request(sid, phone, "nai*1")
        assert body.startswith("CON ")
        assert "Type your area, or reply 9 to skip:" in body
        # Reply "9" skips the sub-location and proceeds straight to the match results.
        body = handle_request(sid, phone, "nai*1*9")
        assert body.startswith("CON ")
        assert "PetCare Global Clinic" in body
        stored = flow.load(sid)
        assert "sub_location" not in stored["context"]  # nothing stored when skipped
        # Matching still used the county centroid (Part 3 logged approximation).
        assert fake.calls[-1]["lat"] == -1.2921
        assert fake.calls[-1]["lng"] == 36.8219

    def test_free_text_sub_location_is_stored(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000028"
        phone = sid
        _to_county_search(sid, phone)
        handle_request(sid, phone, "nai")
        handle_request(sid, phone, "nai*1")       # Nairobi -> sub-location screen
        body = handle_request(sid, phone, "nai*1*Kilimani")
        assert "PetCare Global Clinic" in body
        stored = flow.load(sid)
        assert stored["context"]["sub_location"] == "Kilimani"

    def test_sub_location_skip_option_is_visible_in_sw(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000029"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "2")      # Kiswahili
        handle_request(sid, phone, "2*1")    # Find a vet
        handle_request(sid, phone, "2*1*1")  # Mbwa -> service
        handle_request(sid, phone, "2*1*1*1")  # Consultation -> county search
        handle_request(sid, phone, "2*1*1*1*nai")
        body = handle_request(sid, phone, "2*1*1*1*nai*1")
        assert body.startswith("CON ")
        assert "jibu 9 kuruka" in body
        assert "9. Ruka" in body


class TestBilingualFlow:
    def test_kiswahili_flow_renders_swahili_text(self, flow, fake_api_factory):
        fake_api_factory(matches=MATCHES)
        sid = "+254700000017"
        phone = sid

        body = handle_request(sid, phone, "")
        assert body.startswith("CON ")
        assert "Chagua lugha / Choose language" in body

        body = handle_request(sid, phone, "2")
        assert body.startswith("CON ")
        assert "Karibu VetLink254 (Nyumbani)" in body
        assert "Tafuta daktari wa mifugo" in body
        assert "00. Maliza" in body  # welcome footer in SW

        body = handle_request(sid, phone, "2*1")
        assert body.startswith("CON ")
        assert "Mnyama wa aina gani?" in body
        assert "00. Nyumbani" in body  # non-welcome footer in SW

        body = handle_request(sid, phone, "2*1*1")
        assert body.startswith("CON ")
        assert "Huduma gani inahitajika? (Ukurasa 1/3)" in body
        assert "1. Ushauri wa daktari" in body

        body = handle_request(sid, phone, "2*1*1*1")
        assert body.startswith("CON ")
        assert "Andika sehemu ya jina la kaunti" in body

        body = handle_request(sid, phone, "2*1*1*1*nai")
        assert body.startswith("CON ")
        assert "Kaunti zinazolingana:" in body

        body = handle_request(sid, phone, "2*1*1*1*nai*1")
        assert body.startswith("CON ")
        assert "Andika eneo lako, au jibu 9 kuruka" in body

        body = handle_request(sid, phone, "2*1*1*1*nai*1*Ruiru")
        assert body.startswith("CON ")
        assert "Kliniki karibu na Nairobi (1 zimepatikana):" in body

        body = handle_request(sid, phone, "2*1*1*1*nai*1*Ruiru*1")
        assert body.startswith("END ")
        assert "Asante kwa kutumia VetLink254" in body
        assert flow.load(sid) is None

    def test_swahili_goodbye_and_back(self, flow):
        sid = "+254700000018"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "2")
        body = handle_request(sid, phone, "00")
        assert body == "END Asante kwa kutumia VetLink254. Kwaheri!"
        assert flow.load(sid) is None

    def test_language_applies_to_home_footer_too(self, flow, fake_api_factory):
        # Part 5: "00. Home" footer renders in the session language on mid-flow screens.
        fake_api_factory(matches=MATCHES)
        sid = "+254700000030"
        phone = sid
        handle_request(sid, phone, "")
        handle_request(sid, phone, "1")
        body = handle_request(sid, phone, "1*1")
        assert body.startswith("CON ")
        assert "00. Home" in body  # English footer
        handle_request(sid, phone, "1*1*0")  # back to welcome
        handle_request(sid, phone, "1*1*0*1")  # English already set, back to find vet
        handle_request(sid, phone, "1*1*0*1*0")  # back to welcome
        # Start a fresh SW session and check the SW footer on a mid-flow screen.
        handle_request(sid, phone, "00")  # still on welcome -> end
        sid2 = "+254700000031"
        handle_request(sid2, phone, "")
        handle_request(sid2, phone, "2")
        body = handle_request(sid2, phone, "2*1")
        assert body.startswith("CON ")
        assert "00. Nyumbani" in body
