import unittest

from app.services.analytics_reporting.collection_searches import collection_searches


def document(month, context, count):
    return {
        "month": month,
        "catalog": {"a": {"title": "Collection A"}},
        "daily": [
            {
                "dimensions": {"source": "analytics_searches", "context": context},
                "metrics": {"count": count},
            }
        ],
    }


class CollectionSearchTests(unittest.TestCase):
    def test_unions_controls_before_summing_months(self):
        rows = collection_searches(
            [
                document(
                    "2026-07-01",
                    {
                        "include_filters[pcdm_memberOf_sm][]": ["a", "a"],
                        "f[dct_isPartOf_sm][]": ["a"],
                    },
                    4,
                ),
                document("2026-08-01", {"exclude_filters[pcdm_memberOf_sm][]": ["a"]}, 7),
            ]
        )
        self.assertEqual(rows[0]["searches"], 11)
        self.assertEqual(rows[0]["title"], "Collection A")

    def test_preserves_tail_and_separates_local_labels_from_ids(self):
        rows = collection_searches(
            [
                document(
                    "2026-07-01",
                    {
                        "include_filters[pcdm_memberOf_sm][]": ["a", "b"],
                        "include_filters[b1g_localCollectionLabel_sm][]": ["a"],
                        "q": ["private query never published"],
                    },
                    2,
                )
            ]
        )
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(row["searches"] for row in rows), 6)
        self.assertEqual({row["kind"] for row in rows}, {"Collection record", "Local collection"})

    def test_rejects_duplicate_month_revisions(self):
        doc = document("2026-07-01", {}, 1)
        with self.assertRaises(ValueError):
            collection_searches([doc, doc])


if __name__ == "__main__":
    unittest.main()
