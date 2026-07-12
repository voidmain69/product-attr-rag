from attrpipe.normalization import DictionaryAttributeMapper


class TestLearnedMappings:
    def test_learned_mapping_applies(self) -> None:
        mapper = DictionaryAttributeMapper(learned={"Загальна маса": "net_weight"})
        # a label absent from ontology synonyms now maps thanks to the confirmed mapping
        assert mapper.map("загальна маса") == "net_weight"

    def test_learned_is_case_and_punctuation_insensitive(self) -> None:
        mapper = DictionaryAttributeMapper(learned={"Torque (max)": "net_weight"})
        assert mapper.map("torque max") == "net_weight"

    def test_ontology_still_works_without_learned(self) -> None:
        mapper = DictionaryAttributeMapper()
        assert mapper.map("Вес нетто") == "net_weight"
        assert mapper.map("Загальна маса") is None  # not learned -> unmapped

    def test_learned_overrides_are_isolated_per_instance(self) -> None:
        learned_mapper = DictionaryAttributeMapper(learned={"Загальна маса": "net_weight"})
        plain_mapper = DictionaryAttributeMapper()
        assert learned_mapper.map("Загальна маса") == "net_weight"
        assert plain_mapper.map("Загальна маса") is None
