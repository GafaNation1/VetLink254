# apps/ussd/tests/test_menu_tree.py — declarative menu tree structure and option resolution
import math

from app.menu_tree import (
    ANIMALS,
    COUNTIES,
    NEXT_PAGE_KEY,
    NODES,
    PAGE_SIZE,
    SERVICES,
    build_county_matches_node,
    build_results_node,
    build_service_node,
    get_node,
    search_counties,
    translate,
)


class TestNodeStructure:
    def test_all_nodes_present(self):
        assert set(NODES) == {
            "language", "welcome", "find_vet", "service", "county_search", "county_matches",
            "sub_location", "custom_service", "results", "clinic_details",
            "verify_license", "verify_license_result",
        }

    def test_language_is_first_node(self):
        node = NODES["language"]
        assert node.store == "language"
        assert node.options["1"].next == "welcome"
        assert node.options["1"].value == "en"
        assert node.options["2"].next == "welcome"
        assert node.options["2"].value == "sw"
        assert "Choose language" in node.prompt  # bilingual by construction

    def test_welcome_has_find_a_vet_and_verify_a_vet(self):
        node = NODES["welcome"]
        assert node.options["1"].next == "find_vet"
        assert node.options["1"].label_key == "option_find_vet"
        assert node.options["1"].value is None
        assert node.options["2"].next == "verify_license"
        assert node.options["2"].label_key == "option_verify_vet"
        assert node.options["2"].value is None

    def test_find_vet_options_resolve_animals(self):
        node = NODES["find_vet"]
        assert node.store == "animal_type"
        assert node.back == "welcome"
        for key, animal in ANIMALS.items():
            opt = node.options[key]
            assert opt.value == animal["name"]
            assert opt.next == "service"
            assert opt.label_key == f"animal_{key}"

    def test_all_47_counties_present_with_coordinates(self):
        assert len(COUNTIES) == 47
        assert all(c["name"] and isinstance(c["lat"], float) and isinstance(c["lng"], float) for c in COUNTIES)
        names = [c["name"] for c in COUNTIES]
        assert len(set(names)) == 47  # no duplicates
        for expected in ("Nairobi", "Mombasa", "Kisumu", "Nakuru", "Uasin Gishu", "Kisii", "Turkana"):
            assert expected in names

    def test_county_search_is_case_insensitive_substring(self):
        assert [c["name"] for c in search_counties("NAI")] == ["Nairobi"]
        assert {c["name"] for c in search_counties("kis")} == {"Kisumu", "Kisii"}
        assert [c["name"] for c in search_counties("nairobi")] == ["Nairobi"]
        assert search_counties("zzzz") == []
        assert search_counties("") == []

    def test_county_search_has_no_fixed_length_restriction(self):
        # Part 2: a single letter is a valid query (no 3-letter minimum).
        one_letter = search_counties("a")
        assert len(one_letter) > 1
        # Full county name is also valid.
        assert [c["name"] for c in search_counties("Mombasa")] == ["Mombasa"]
        assert search_counties("mombasa") == [COUNTIES[0]]
        # A 2-letter fragment is valid and yields a mid-size result.
        two_letter = search_counties("ni")
        assert len(two_letter) >= 1

    def test_county_search_narrow_query_reduces_matches(self):
        broad = search_counties("ni")
        narrow = search_counties("nit")
        assert len(broad) > len(narrow)

    def test_service_catalogue_is_roughly_20_to_25(self):
        assert 20 <= len(SERVICES) <= 25

    def test_county_matches_and_custom_service_are_free_text(self):
        assert NODES["county_search"].free_text is True
        assert NODES["sub_location"].free_text is True
        assert NODES["custom_service"].free_text is True

    def test_clinic_details_is_terminal(self):
        node = NODES["clinic_details"]
        assert node.terminal is True
        assert callable(node.prompt_fn)

    def test_pagination_design_rules(self):
        # PAGE_SIZE 9 per screen; "98" is the reserved next-page key and can never collide with a
        # real item number while totals stay well under 90 (design rule logged in menu_tree.py).
        assert PAGE_SIZE == 9
        assert NEXT_PAGE_KEY == "98"
        assert len(SERVICES) + 1 < 90
        assert len(COUNTIES) < 90


class TestServicePagination:
    def test_pagination_slices(self):
        total_pages = math.ceil(len(SERVICES) / PAGE_SIZE)
        assert total_pages == 3

    def test_first_page_has_9_continuous_numbers_and_next_page(self):
        node = build_service_node({"language": "en"})
        item_keys = [k for k in node.options if k.isdigit() and k != NEXT_PAGE_KEY]
        assert sorted(item_keys) == [str(i) for i in range(1, 10)]
        assert node.options[NEXT_PAGE_KEY].next == "service"
        assert node.options[NEXT_PAGE_KEY].page == 1
        assert node.options[NEXT_PAGE_KEY].label_key == "more"
        assert node.prompt == "What service is needed? (Page 1/3)"

    def test_second_page_numbering_is_continuous_10_to_18(self):
        node = build_service_node({"language": "en", "service_page": 1})
        # Continuous numbering: page 2 shows 10-18 (NOT restarting at 1), key == item number.
        item_keys = [k for k in node.options if k.isdigit() and k != NEXT_PAGE_KEY]
        assert sorted(item_keys) == [str(i) for i in range(10, 19)]
        assert node.options["10"].value == SERVICES[9]["name"]
        assert node.options["18"].value == SERVICES[17]["name"]
        assert node.options[NEXT_PAGE_KEY].next == "service"
        assert node.options[NEXT_PAGE_KEY].page == 2

    def test_last_page_has_remaining_items_plus_custom_service(self):
        node = build_service_node({"language": "en", "service_page": 2})
        remaining = len(SERVICES) - 2 * PAGE_SIZE
        item_keys = [k for k in node.options if k.isdigit() and k != NEXT_PAGE_KEY]
        assert sorted(item_keys) == [str(i) for i in range(19, 19 + remaining + 1)]
        # The final numbered item (25) is the free-text custom-service entry.
        custom_key = str(len(SERVICES) + 1)
        assert node.options[custom_key].next == "custom_service"
        assert node.options[custom_key].label_key == "custom_service_option"
        # No "98" on the last page.
        assert NEXT_PAGE_KEY not in node.options

    def test_service_labels_are_swahili_when_sw(self):
        node = build_service_node({"language": "sw"})
        assert node.options["1"].label == SERVICES[0]["sw"]
        assert node.options["1"].value == SERVICES[0]["name"]

    def test_get_node_builds_service_from_context_page(self):
        node = get_node("service", {"language": "en", "service_page": 2})
        assert node.id == "service"
        assert node.options["19"].value == SERVICES[18]["name"]

    def test_service_node_has_page_key(self):
        node = get_node("service", {"language": "en"})
        assert node.page_key == "service_page"


class TestCountyMatchesNode:
    def test_build_county_matches_node(self):
        matches = [{"name": "Nairobi", "lat": -1.29, "lng": 36.82}, {"name": "Nakuru", "lat": -0.30, "lng": 36.08}]
        node = build_county_matches_node({"language": "en", "county_matches": matches})
        assert node.store == "location"
        assert node.back == "county_search"
        assert node.options["1"].label == "Nairobi"
        assert node.options["1"].value == {"name": "Nairobi", "lat": -1.29, "lng": 36.82}
        assert node.options["1"].next == "sub_location"
        assert node.options["2"].label == "Nakuru"
        assert node.page_key == "county_matches_page"

    def test_more_than_page_size_matches_paginate_with_continuous_numbering(self):
        many = [{"name": f"C{i}", "lat": 0.0, "lng": 0.0} for i in range(20)]
        node = build_county_matches_node({"language": "en", "county_matches": many})
        item_keys = [k for k in node.options if k.isdigit() and k != NEXT_PAGE_KEY]
        assert sorted(item_keys) == [str(i) for i in range(1, 10)]
        assert node.options[NEXT_PAGE_KEY].page == 1
        assert "Page 1/3" in node.prompt

        node2 = build_county_matches_node({"language": "en", "county_matches": many, "county_matches_page": 1})
        item_keys2 = [k for k in node2.options if k.isdigit() and k != NEXT_PAGE_KEY]
        assert sorted(item_keys2) == [str(i) for i in range(10, 19)]
        assert node2.options["10"].value["name"] == "C9"

        node3 = build_county_matches_node({"language": "en", "county_matches": many, "county_matches_page": 2})
        assert sorted(k for k in node3.options if k.isdigit()) == ["19", "20"]
        assert NEXT_PAGE_KEY not in node3.options

    def test_within_page_size_no_pagination_prompt(self):
        few = [{"name": "Nairobi", "lat": -1.29, "lng": 36.82}]
        node = build_county_matches_node({"language": "en", "county_matches": few})
        assert "Page" not in node.prompt
        assert NEXT_PAGE_KEY not in node.options

    def test_sub_location_node_has_skip_option(self):
        node = NODES["sub_location"]
        assert node.free_text is True
        assert "9" in node.options
        assert node.options["9"].next == "results"
        assert node.options["9"].value is None
        assert node.options["9"].label_key == "skip"


class TestDynamicResultsNode:
    def test_build_results_node(self):
        matches = [{"name": "A", "distance_km": 1.2}, {"name": "B", "distance_km": 3.4}]
        node = build_results_node(matches, "Nairobi", {"language": "en"})
        assert node.prompt == "Clinics near Nairobi (2 found):"
        assert node.store == "clinic"
        assert node.back == "sub_location"
        assert node.options["1"].label == "A - 1.2 km"
        assert node.options["1"].next == "clinic_details"
        assert node.options["1"].value == matches[0]
        assert node.options["2"].label == "B - 3.4 km"

    def test_get_node_rebuilds_results_from_context(self):
        matches = [{"name": "A", "distance_km": 1.2}]
        node = get_node("results", {"language": "en", "results": matches, "location": {"name": "Nairobi"}})
        assert node.prompt == "Clinics near Nairobi (1 found):"

    def test_get_node_static_ids(self):
        for nid in ("welcome", "find_vet", "county_search", "sub_location", "custom_service", "clinic_details"):
            assert get_node(nid, {}).id == nid

    def test_clinic_details_formatting(self):
        context = {
            "language": "en",
            "clinic": {
                "name": "PetCare Global Clinic",
                "distance_km": 2.216,
                "unique_code": "VL254-KE-00002",
                "services": ["consultation", "vaccination"],
                "county": "Nairobi",
                "sub_county": "Westlands",
            },
        }
        text = NODES["clinic_details"].prompt_fn(context)
        assert "PetCare Global Clinic" in text
        assert "VL254-KE-00002" in text
        assert "2.216 km" in text
        assert "consultation, vaccination" in text
        assert "County / Sub-county: Nairobi / Westlands" in text


class TestBilingual:
    def test_translate_switches_language(self):
        assert translate({"language": "en"}, "welcome") == "Welcome to VetLink254 (Home)"
        assert translate({"language": "sw"}, "welcome") == "Karibu VetLink254 (Nyumbani)"
        assert translate({}, "welcome") == "Welcome to VetLink254 (Home)"  # default English
        assert translate({"language": "sw"}, "back") == "Nyuma"
        assert translate({"language": "en"}, "back") == "Back"
        assert translate({"language": "en"}, "home") == "Home"
        assert translate({"language": "sw"}, "home") == "Nyumbani"
        assert translate({"language": "en"}, "skip") == "Skip"
        assert translate({"language": "sw"}, "skip") == "Ruka"

    def test_translate_formats_placeholders(self):
        text = translate({"language": "en"}, "no_matches", service="Grooming", location="Nairobi")
        assert "Grooming" in text and "Nairobi" in text
        text_sw = translate({"language": "sw"}, "no_matches", service="Grooming", location="Nairobi")
        assert "Grooming" in text_sw and "Nairobi" in text_sw

    def test_unknown_key_falls_back_to_key(self):
        assert translate({"language": "en"}, "no_such_key") == "no_such_key"

    def test_welcome_prompt_labels_home(self):
        # Part 1: the welcome screen is clearly labeled "(Home)" in its own prompt text.
        assert "(Home)" in translate({"language": "en"}, "welcome")
        assert "(Nyumbani)" in translate({"language": "sw"}, "welcome")


class TestVerifyVetNodes:
    def test_verify_license_node_is_free_text(self):
        node = NODES["verify_license"]
        assert node.store == "license_number"
        assert node.back == "welcome"
        assert node.free_text is True
        assert node.options == {}

    def test_verify_license_result_is_terminal(self):
        node = NODES["verify_license_result"]
        assert node.terminal is True
        assert callable(node.prompt_fn)

    def test_verify_result_active_formatting(self):
        context = {
            "language": "en",
            "license_number": "KVB-1001",
            "verify_result": {"status": "active", "name": "Dr. Wanjiku Kamau", "license_type": "Veterinary Surgeon"},
        }
        text = NODES["verify_license_result"].prompt_fn(context)
        assert "Dr. Wanjiku Kamau is a VERIFIED KVB Veterinary Surgeon" in text

    def test_verify_result_inactive_formatting(self):
        context = {
            "language": "en",
            "license_number": "KVB-1003",
            "verify_result": {"status": "expired", "name": "Dr. Grace Muthoni", "license_type": "Veterinary Surgeon"},
        }
        text = NODES["verify_license_result"].prompt_fn(context)
        assert "NOT currently verified" in text
        assert "KVB-1003" in text

    def test_verify_result_active_formatting_sw(self):
        context = {
            "language": "sw",
            "license_number": "KVB-1001",
            "verify_result": {"status": "active", "name": "Dr. Wanjiku Kamau", "license_type": "Veterinary Surgeon"},
        }
        text = NODES["verify_license_result"].prompt_fn(context)
        assert "ALIYETHIBITISHWA" in text
