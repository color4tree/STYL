"""SUP-015/SUP-028: reviewed meaning, scope, provenance and selling boundaries."""

from copy import deepcopy
import json
import unittest

from app import catalog_answers as answers, support_ai as ai
from app.catalog_schema import CatalogFacts


TOPICS = list(answers.TOPICS)


def measurement(kind="width", scope="overall", amount="1200", unit="mm", **extra):
    return {"kind": kind, "scope": scope, "amount": amount, "unit": unit,
            "qualifier": "exact", "note": "", **extra}


def interface(kind="rack_mount", role="requires", attribute="holeDiameter",
              operator="eq", value="16", unit="mm", limitations=""):
    return {"kind": kind, "role": role, "constraints": [
        {"attribute": attribute, "operator": operator, "value": value, "unit": unit},
    ], "limitations": limitations}


def item(**extra):
    return {"type": "accessory", "id": 1001, "ref": "accessory:1001", "name": "STYL Adapter",
            "category": "Attachments", "price": 99, "currency": "CAD",
            "publicationStatus": "published", **extra}


def reviewed(**extra):
    return CatalogFacts(reviewed=True, **extra).model_dump()


class TypedCatalogAnswerTests(unittest.TestCase):
    def project(self, record, topics=TOPICS):
        return answers.project_facts(ai.public_evidence([record], topics)[0], topics)

    def plan(self, record, question, topics=TOPICS, requests=None):
        result = answers.build_plan(question, ai.public_evidence([record], topics), topics,
                                    item_ref=record["ref"], requests=requests)
        self.assertIsNotNone(result)
        return result

    def fields(self, plan):
        return {fact["key"]: fact for row in plan.items for fact in row["fields"]}

    def test_legacy_size_label_in_colour_options_is_not_a_colour(self):
        record = item(colourOptions="Size options:34mm and36mm")
        facts = self.project(record)
        self.assertEqual(facts["colourOptions"]["status"], "unknown")
        self.assertEqual(facts["colour.availableOptions"]["status"], "unknown")
        self.assertEqual(facts["sizeOptions"]["value"], "34mm and36mm")
        plan = self.plan(record, "What colors are available?")
        self.assertIn("sizeOptions", self.fields(plan))
        self.assertEqual(plan.status, "partial")
        self.assertIn("size", plan.text.lower())

    def test_legacy_dimensions_and_explicit_mixed_option_labels_keep_meaning(self):
        facts = self.project(item(colourOptions="Colors: Black; Size options: 34 mm and 36 mm; Finish: satin"))
        self.assertEqual(facts["colourOptions"]["value"], "Black")
        self.assertEqual(facts["sizeOptions"]["value"], "34 mm and 36 mm")
        self.assertEqual(facts["finish"]["value"], "satin")
        self.assertEqual(self.project(item(colourOptions="34mm and36mm"))["colourOptions"]["status"], "unknown")

    def test_reviewed_options_override_equivalent_legacy_and_approved_text(self):
        record = item(colourOptions="Red", sizeOptions="20 mm", finish="gloss",
                      description="Colors: Green; Size options: 22 mm; Finish: powder coat",
                      catalogFacts=reviewed(options={"colors": ["Black"], "sizes": ["34 mm", "36 mm"], "finish": "satin"}))
        facts = self.project(record)
        for key, value in (("colourOptions", ["Black"]), ("sizeOptions", ["34 mm", "36 mm"]), ("finish", "satin")):
            self.assertEqual(facts[key]["status"], "answered")
            self.assertEqual(facts[key]["value"], value)
            self.assertTrue(all(source["locator"].startswith("catalogFacts.") for source in facts[key]["sources"]))

    def test_empty_reviewed_color_list_does_not_clear_valid_legacy_color(self):
        facts = self.project(item(colourOptions="Blue", catalogFacts=reviewed(options={"sizes": ["34 mm"]})))
        self.assertEqual(facts["colourOptions"]["value"], "Blue")
        self.assertEqual(facts["sizeOptions"]["value"], ["34 mm"])

    def test_unreviewed_typed_facts_neither_publish_nor_poison_legacy(self):
        raw = reviewed(options={"colors": ["SECRET"]})
        raw["reviewed"] = False
        record = item(colourOptions="Black", catalogFacts=raw, catalogFactsReviewedAt="PRIVATE TIME")
        public = ai.public_evidence([record], TOPICS)[0]
        self.assertNotIn("catalogFacts", public)
        self.assertNotIn("SECRET", json.dumps(public))
        self.assertEqual(self.project(record)["colourOptions"]["value"], "Black")

    def test_private_unknown_keys_fail_closed_even_when_reviewed(self):
        raw = reviewed(options={"colors": ["SECRET"]})
        raw["supplier"] = "PRIVATE"
        record = item(catalogFacts=raw, provenance={"source": "PRIVATE"}, catalogFactsReviewedAt="PRIVATE TIME")
        evidence = ai.public_evidence([record], TOPICS)
        self.assertNotIn("SECRET", json.dumps(evidence))
        self.assertNotIn("PRIVATE", json.dumps(evidence))
        self.assertEqual(self.project(record)["colourOptions"]["status"], "unknown")

    def test_disabled_products_excludes_options_measurements_and_materials(self):
        record = item(catalogFacts=reviewed(options={"colors": ["SECRET"]},
                      measurements=[measurement()], interfaces=[interface()]))
        public = ai.public_evidence([record], ["compatibility"])[0]
        self.assertNotIn("options", public["catalogFacts"])
        self.assertNotIn("measurements", public["catalogFacts"])
        self.assertIn("interfaces", public["catalogFacts"])
        facts = answers.project_facts(public, ["compatibility"])
        self.assertEqual(facts["measurements.overall.width"]["status"], "scope_disabled")
        self.assertEqual(facts["interface.rack_mount.holeDiameter"]["status"], "answered")
        self.assertNotIn("SECRET", json.dumps(ai.retrieve_catalog([public], "color width", "", record["ref"])))

    def test_disabled_compatibility_excludes_interfaces_and_no_review_claims(self):
        record = item(catalogFacts=reviewed(interfaces=[interface(value="PRIVATE FIT")]),
                      catalogFactsReviewedAt="PRIVATE TIME")
        public = ai.public_evidence([record], ["products"])[0]
        self.assertNotIn("interfaces", public["catalogFacts"])
        self.assertEqual(answers.project_facts(public, ["products"])["interface.rack_mount.holeDiameter"]["status"], "scope_disabled")
        self.assertNotIn("PRIVATE", json.dumps(ai.retrieve_catalog([public], "requirements", "", record["ref"])))
        self.assertNotIn("catalogFacts", ai.public_evidence([record], ["pricing"])[0])

    def test_generic_width_reports_independent_overall_rack_and_smith_scopes(self):
        record = item(description="Width: 999 mm", catalogFacts=reviewed(measurements=[
            measurement(amount="1200"), measurement(scope="rack", amount="1100"),
            measurement(scope="smith_bar", amount="2200"),
        ]))
        fields = self.fields(self.plan(record, "What is the width?"))
        self.assertEqual(set(fields), {"measurements.overall.width", "measurements.rack.width", "measurements.smith_bar.width"})
        self.assertTrue(all(value["status"] == "answered" for value in fields.values()))
        self.assertNotIn("999", json.dumps(fields))

    def test_specific_missing_scope_never_substitutes_another_width(self):
        record = item(catalogFacts=reviewed(measurements=[measurement(scope="smith_bar", amount="2200")]))
        fields = self.fields(self.plan(record, "What is the rack width?"))
        self.assertEqual(fields["measurements.rack.width"]["status"], "unknown")
        self.assertNotIn("2200", json.dumps(fields))

    def test_same_scope_duplicates_conflict_without_poisoning_independent_height(self):
        record = item(catalogFacts=reviewed(measurements=[
            measurement(), measurement(amount="1300"), measurement(kind="height", scope="upright", amount="2100"),
        ]))
        facts = self.project(record)
        self.assertEqual(facts["measurements.overall.width"]["status"], "conflicted")
        self.assertEqual(facts["measurements.upright.height"]["value"], "2100 mm")
        plan = self.plan(record, "What are the overall width and upright height?")
        fields = self.fields(plan)
        self.assertEqual(fields["measurements.overall.width"]["status"], "conflicted")
        self.assertEqual(fields["measurements.upright.height"]["status"], "answered")
        self.assertNotIn("measurements.upright.width", fields)
        self.assertNotIn("interface.rack_mount.uprightSize", fields)

    def test_legacy_scoped_dimensions_are_not_overall_or_other_scope(self):
        record = item(description="Smith bar width: 2200 mm; Rack width: 1200 mm; Upright height: 2100 mm; Usable storage length: 300 mm; Mounting length: 120 mm")
        facts = self.project(record)
        for key, value in (("smith_bar.width", "2200 mm"), ("rack.width", "1200 mm"),
                           ("upright.height", "2100 mm"), ("usable_storage.length", "300 mm"),
                           ("mounting.length", "120 mm")):
            self.assertEqual(facts[f"measurements.{key}"]["value"], value)
        self.assertEqual(facts["dimensions.width"]["status"], "unknown")

    def test_qualifiers_notes_capacity_stack_increment_and_own_weight_stay_separate(self):
        record = item(catalogFacts=reviewed(measurements=[
            measurement("weight", "product", "50", "kg", qualifier="approximate", note="without packaging"),
            measurement("load_capacity", "rack", "400", "kg", qualifier="nominal"),
            measurement("resistance", "stack", "90", "kg", note="each stack; no cable force inference"),
            measurement("increment", "stack", "2.5", "kg", note="micro plate not counted twice"),
        ]))
        facts = self.project(record)
        self.assertEqual(facts["weight.own"]["value"], "approximate 50 kg (without packaging)")
        self.assertEqual(facts["measurements.rack.load_capacity"]["value"], "nominal 400 kg")
        self.assertIn("each stack", facts["resistance.stacks"]["value"])
        self.assertIn("not counted twice", facts["resistance.increments"]["value"])
        self.assertNotIn("180", json.dumps([fact["value"] for fact in facts.values()]))
        stack = self.fields(self.plan(record, "What is the weight stack?"))
        self.assertNotIn("measurements.stack.weight", stack)
        own_record = item(catalogFacts=reviewed(measurements=[measurement("weight", "overall", "50", "kg")]))
        own_fields = self.fields(self.plan(own_record, "What is its own weight?"))
        self.assertTrue(all(fact["status"] == "answered" for fact in own_fields.values()))

    def test_socket_drive_and_opening_are_separate_and_not_rack_holes(self):
        record = item(catalogFacts=reviewed(interfaces=[
            interface("socket_drive", "requires", "driveSize", value="0.5", unit="in"),
            interface("socket_drive", "provides", "openingSize", value="34"),
        ]))
        facts = self.project(record)
        self.assertIn("requires drive size equal to 0.5 in", facts["interface.socket_drive.driveSize"]["value"][0])
        self.assertIn("provides opening size equal to 34 mm", facts["interface.socket_drive.openingSize"]["value"][0])
        self.assertEqual(facts["compat.holeDiameter"]["status"], "unknown")
        plan = self.plan(record, "What are the socket drive size and opening size?")
        self.assertFalse(plan.pending_slots)
        self.assertNotIn("compat.uprightSize", self.fields(plan))
        self.assertIn("interface.socket_drive.openingSize", self.fields(plan))
        mixed = item(catalogFacts=reviewed(interfaces=[
            interface(), interface("socket_drive", attribute="driveSize", value="0.5", unit="in"),
        ]))
        fields = self.fields(self.plan(mixed, "What are the rack hole diameter and socket drive size?"))
        self.assertEqual(set(fields), {"interface.rack_mount.holeDiameter", "interface.socket_drive.driveSize"})
        fields = self.fields(self.plan(record, "What opening size is required?"))
        self.assertEqual(set(fields), {"interface.openingSize"})
        self.assertIn("Socket drive:", fields["interface.openingSize"]["value"][0])

    def test_pin_own_shaft_diameter_does_not_become_required_mating_bore(self):
        record = item(catalogFacts=reviewed(measurements=[measurement("diameter", "shaft", "10")],
                      interfaces=[interface("selector_pin", "requires", "holeDiameter", "min", "11")]))
        facts = self.project(record)
        self.assertEqual(facts["measurements.shaft.diameter"]["value"], "10 mm")
        self.assertIn("minimum 11 mm", facts["interface.selector_pin.holeDiameter"]["value"][0])
        fields = self.fields(self.plan(record, "What bore does the selector pin require?"))
        self.assertIn("interface.selector_pin.holeDiameter", fields)
        self.assertNotIn("measurements.shaft.diameter", fields)
        self.assertNotIn("compat.holeDiameter", fields)
        rack_fields = self.fields(self.plan(record, "What is the rack hole diameter?"))
        self.assertEqual(set(rack_fields), {"compat.holeDiameter"})
        self.assertEqual(rack_fields["compat.holeDiameter"]["status"], "unknown")

    def test_typed_operators_roles_do_not_enter_legacy_fit_math(self):
        for operator in ("min", "max", "listed", "eq"):
            with self.subTest(operator=operator):
                record = item(catalogFacts=reviewed(interfaces=[interface(operator=operator)]))
                plan = self.plan(record, "Will it fit my rack with 16 mm holes?")
                self.assertEqual(plan.items[0]["compatibility"]["status"], "insufficient_data")
                self.assertEqual(plan.items[0]["compatibility"]["mismatches"], [])
                self.assertFalse(plan.pending_slots)
                self.assertTrue(any(key.startswith("interface.") for key in self.fields(plan)))
                self.assertTrue(answers.validate_plan(plan, ai.public_evidence([record], TOPICS), TOPICS))

    def test_multiple_interface_rows_are_not_verified_or_alternative_configurations(self):
        record = item(catalogFacts=reviewed(interfaces=[interface(value="16"), interface(value="25")]))
        facts = self.project(record)
        fact = facts["interface.rack_mount.holeDiameter"]
        self.assertEqual(fact["status"], "answered")
        self.assertEqual(len(fact["value"]), 2)
        self.assertIn("Statement 1:", fact["value"][0])
        self.assertIn("Statement 2:", fact["value"][1])
        plan = self.plan(record, "Will it fit my rack with 25 mm holes?")
        self.assertEqual(plan.items[0]["compatibility"]["status"], "insufficient_data")

    def test_direct_interface_requirement_is_answered_without_customer_rack(self):
        record = item(catalogFacts=reviewed(interfaces=[
            interface("plate_storage", "accepts", "openingSize", "min", "50", limitations="verify plate hub clearance"),
        ]))
        plan = self.plan(record, "What plate opening size does it accept?")
        self.assertFalse(plan.pending_slots)
        self.assertIsNone(plan.items[0]["compatibility"])
        self.assertIn("accepts opening size minimum 50 mm", plan.text)
        self.assertIn("verify plate hub clearance", plan.text)

    def test_packaging_exclusions_and_fasteners_never_replace_selling_quantity(self):
        record = item(sellingUnit="Pair", packageQuantity=2, included="Adapter and screws",
                      catalogFacts=reviewed(components=[
                          {"name": "Adapter", "status": "included", "quantity": 2},
                          {"name": "Bolts", "status": "included", "quantity": 8},
                          {"name": "Plates", "status": "excluded", "quantity": None},
                          {"name": "Washers", "status": "unknown", "quantity": None},
                      ], packageNote="Two adapters per package; plates sold separately."))
        facts = self.project(record)
        self.assertEqual(facts["sellingUnit"]["value"], "Pair")
        self.assertEqual(facts["packageQuantity"]["value"], 2)
        plan = self.plan(record, "What is included and what is the package quantity?")
        self.assertIn("doesn't include Plates", plan.text)
        self.assertIn("can't confirm the inclusion of Washers", plan.text)
        self.assertIn("8 × Bolts", plan.text)
        self.assertEqual(self.fields(plan)["packageQuantity"]["value"], 2)
        self.assertNotIn("included", self.fields(plan))

    def test_size_options_are_information_not_all_included_or_new_sellable_variants(self):
        record = item(sellingUnit="Each", packageQuantity=1,
                      catalogFacts=reviewed(options={"sizes": ["34 mm", "36 mm"], "note": "Specify one size"},
                                           components=[{"name": "Socket", "status": "included", "quantity": 1}]))
        before = deepcopy(record)
        plan = self.plan(record, "Which sizes are available and what is included?")
        self.assertEqual(self.fields(plan)["sizeOptions"]["value"], ["34 mm", "36 mm"])
        self.assertEqual(self.project(record)["packageQuantity"]["value"], 1)
        self.assertNotIn("variant", ai.public_evidence([record], TOPICS)[0])
        self.assertEqual(record, before)

    def test_component_material_overrides_only_matching_component_not_finish(self):
        record = item(materialParts={"frame": "Plastic", "padding": "Foam"}, finish="silver appearance",
                      catalogFacts=reviewed(materials=[{"component": "frame", "value": "Steel"}]))
        facts = self.project(record)
        self.assertEqual(facts["material.frame"]["value"], "Steel")
        self.assertEqual(facts["material.padding"]["value"], "Foam")
        self.assertEqual(facts["material.parts"]["value"], {"padding": "Foam", "frame": "Steel"})
        self.assertEqual(facts["finish"]["value"], "silver appearance")
        self.assertEqual(facts["material"]["status"], "unknown")

    def test_current_value_change_invalidates_saved_plan_and_keeps_per_field_sources(self):
        record = item(catalogFacts=reviewed(measurements=[measurement()]))
        evidence = ai.public_evidence([record], TOPICS)
        plan = self.plan(record, "What is the overall width?")
        self.assertTrue(answers.validate_plan(plan, evidence, TOPICS))
        record["catalogFacts"]["measurements"][0]["amount"] = "1400"
        self.assertFalse(answers.validate_plan(plan, ai.public_evidence([record], TOPICS), TOPICS))
        source = self.fields(plan)["measurements.overall.width"]["evidenceIds"][0]
        self.assertTrue(source.startswith("catalog:"))

    def test_source_operator_change_invalidates_even_when_numeric_value_unchanged(self):
        record = item(catalogFacts=reviewed(interfaces=[interface("socket_drive", attribute="driveSize")]))
        plan = self.plan(record, "What socket drive size is required?")
        record["catalogFacts"]["interfaces"][0]["constraints"][0]["operator"] = "min"
        self.assertFalse(answers.validate_plan(plan, ai.public_evidence([record], TOPICS), TOPICS))
        record["catalogFacts"]["interfaces"][0]["constraints"][0]["operator"] = "eq"
        record["catalogFacts"]["interfaces"][0]["limitations"] = "Nominal marking only"
        self.assertFalse(answers.validate_plan(plan, ai.public_evidence([record], TOPICS), TOPICS))

    def test_review_time_and_private_provenance_do_not_upgrade_public_sources(self):
        record = item(catalogFacts=reviewed(options={"colors": ["Black"]}),
                      catalogFactsReviewedAt="yesterday", provenance={"owner": "private"})
        plan = self.plan(record, "What color is it?")
        record["catalogFactsReviewedAt"] = "today"
        record["provenance"]["owner"] = "new private owner"
        self.assertTrue(answers.validate_plan(plan, ai.public_evidence([record], TOPICS), TOPICS))
        self.assertNotIn("private", json.dumps(plan.to_dict()))
        self.assertTrue(all(row["sourceId"] == "accessory:1001#catalogFacts" for row in plan.references))

    def test_fabricated_value_source_and_rendered_claim_are_rejected(self):
        record = item(catalogFacts=reviewed(measurements=[measurement()]))
        evidence = ai.public_evidence([record], TOPICS)
        original = self.plan(record, "What is the overall width?").to_dict()
        for mutate in (
            lambda plan: plan["items"][0]["fields"][0].update(value="9999 mm"),
            lambda plan: plan["references"][0].update(sourceHash="a" * 64),
            lambda plan: plan.update(text="This is a verified fit."),
        ):
            altered = deepcopy(original)
            mutate(altered)
            self.assertFalse(answers.validate_plan(altered, evidence, TOPICS))

    def test_retrieval_exposes_scoped_typed_values_not_private_review_metadata(self):
        record = item(catalogFacts=reviewed(options={"sizes": ["34 mm", "36 mm"]},
                      measurements=[measurement(scope="smith_bar")],
                      interfaces=[interface("socket_drive", attribute="driveSize")]),
                      catalogFactsReviewedAt="PRIVATE TIME")
        context = ai.retrieve_catalog(ai.public_evidence([record], TOPICS), "Smith bar width socket drive size", "", record["ref"])
        serialized = json.dumps(context)
        self.assertIn("measurements.smith_bar.width", serialized)
        self.assertIn("interface.socket_drive.driveSize", serialized)
        self.assertIn("requires", serialized)
        self.assertNotIn("PRIVATE TIME", serialized)

    def test_provider_generic_width_request_is_refined_to_specific_scope(self):
        record = item(catalogFacts=reviewed(measurements=[measurement(scope="smith_bar")]))
        decision = ai.Decision(topic="products", references=[record["ref"]], fields=[], needsHuman=False,
                               requestedModel="", requests=[
                                   ai.CatalogRequest(ref=record["ref"], fields=["dimensions.width"],
                                                     compatibility=False, slotSpans=[]),
                               ])
        evidence = ai.public_evidence([record], TOPICS)
        requests = ai.extracted_requests(decision, "What is the Smith bar width?", evidence)
        self.assertEqual(requests[0]["fields"], ["measurements.smith_bar.width"])
        plan = answers.build_plan("What is the Smith bar width?", evidence, TOPICS, requests=requests)
        self.assertEqual(set(self.fields(plan)), {"measurements.smith_bar.width"})
        keys, schema = ai.provider_field_context(
            ai.retrieve_catalog(evidence, "Smith bar width", "", record["ref"]), TOPICS, "Smith bar width",
        )
        self.assertIn("measurements.smith_bar.width", keys)
        self.assertNotIn("measurements.socket_opening.increment", keys)
        self.assertLess(len(keys), len(answers.FIELD_REGISTRY))
        self.assertEqual(schema["properties"]["requests"]["items"]["properties"]["fields"]["items"]["enum"], keys)
        self.assertEqual(ai.SCHEMA["properties"]["requests"]["items"]["properties"]["fields"]["items"]["enum"],
                         list(answers.FIELD_REGISTRY))
        keys, schema = ai.provider_field_context([], ["customer_service"], "What is the delivery policy?")
        self.assertEqual(keys, [])
        self.assertEqual(schema["properties"]["requests"]["maxItems"], 0)
        self.assertNotIn("enum", schema["properties"]["requests"]["items"]["properties"]["fields"]["items"])

    def test_valid_legacy_arrays_and_unreviewed_requirements_remain_answered(self):
        raw = reviewed(interfaces=[interface(value="99")])
        raw["reviewed"] = False
        record = item(colourOptions=["Black", "White"], weight="50 kg",
                      compatibility={"holeDiameter": "16 mm"}, catalogFacts=raw)
        self.assertEqual(self.project(record)["colourOptions"]["value"], ["Black", "White"])
        plan = self.plan(record, "What rack hole diameter is required?")
        self.assertEqual(self.fields(plan)["compat.holeDiameter"]["value"], "16 mm")
        self.assertNotIn("interface.rack_mount.holeDiameter", self.fields(plan))
        own = self.plan(record, "What is its own weight?")
        self.assertEqual(self.fields(own)["weight.own"]["value"], "50 kg")
        self.assertNotIn("measurements.product.weight", self.fields(own))
        self.assertEqual(self.project(item(description="Colors: Black and White"))["colour.availableOptions"]["value"], "Black and White")
        self.assertEqual(answers.requested_fields("weight stack increments"), ["resistance.increments"])
        self.assertEqual(answers.requested_fields("What is the pin diameter?"), ["compat.pinDiameter"])
        self.assertEqual(answers.requested_fields("What is the hole diameter?"), ["compat.holeDiameter"])
        for label in ("Own weight", "Product weight"):
            self.assertEqual(self.project(item(description=f"{label}: 20 kg"))["weight.own"]["value"], "20 kg")

    def test_retrieval_prefers_reviewed_equivalent_but_retains_unrelated_legacy(self):
        record = item(colourOptions="Red", description="Colors: Green; Width: 999 mm; Brand: STYL; Warranty: 2 years",
                      catalogFacts=reviewed(options={"colors": ["Black"]}, measurements=[measurement()]))
        retrieved = ai.retrieve_catalog(ai.public_evidence([record], TOPICS), "color width warranty", "", record["ref"])
        text = json.dumps(retrieved)
        self.assertNotIn("Green", text)
        self.assertNotIn("Red", text)
        self.assertNotIn("999 mm", text)
        self.assertIn("Black", text)
        self.assertIn("1200 mm", text)
        self.assertIn("2 years", text)

    def test_specific_pin_and_storage_measurement_queries_keep_scope(self):
        record = item(catalogFacts=reviewed(measurements=[
            measurement("diameter", "shaft", "10"), measurement("length", "usable_storage", "300"),
            measurement("length", "mounting", "120"), measurement("length", "insertion", "80"),
        ]))
        fields = self.fields(self.plan(record, "What is the pin diameter?"))
        self.assertEqual(fields["measurements.shaft.diameter"]["value"], "10 mm")
        self.assertNotIn("compat.pinDiameter", fields)
        fields = self.fields(self.plan(record, "What is the usable storage length?"))
        self.assertEqual(set(fields), {"measurements.usable_storage.length"})
        fields = self.fields(self.plan(record, "What is the mounting length?"))
        self.assertEqual(set(fields), {"measurements.mounting.length"})
