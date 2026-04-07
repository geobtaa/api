from app.elasticsearch.suggest import build_suggest_inputs, normalize_suggestion_text


class TestSuggestHelpers:
    def test_normalize_suggestion_text_cleans_common_punctuation(self):
        assert normalize_suggestion_text("(Chicago)") == "chicago"
        assert normalize_suggestion_text("(Chicago, )") == "chicago"
        assert normalize_suggestion_text("Chicago (Ill.)") == "chicago ill"
        assert (
            normalize_suggestion_text("Chicago : Department of City Planning, 1961.")
            == "chicago department of city planning"
        )
        assert (
            normalize_suggestion_text("Chicago, Milwaukee, and St. Paul Railway Company")
            == "chicago, milwaukee, and st paul railway company"
        )

    def test_build_suggest_inputs_deduplicates_normalized_values(self):
        doc = {
            "dct_spatial_sm": ["(Chicago)", "(Chicago, )", "Chicago", "Chicago (Ill.)"],
            "dct_publisher_sm": ["Chicago : Department of City Planning, 1961."],
        }

        assert build_suggest_inputs(doc) == [
            "chicago department of city planning",
            "chicago",
            "chicago ill",
        ]
