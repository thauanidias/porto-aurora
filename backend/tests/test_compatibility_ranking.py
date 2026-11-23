from app.services.compatibility import rank_compatibility


def test_ranking_keeps_ties_zero_and_unknown_without_inventing_scores():
    def item(key, value, status="CALCULATED"):
        return {"id": key, "compatibility": {"percentage": value, "status": status}}
    ranked = rank_compatibility([item("unknown", None, "NOT_CONFIGURED"), item("zero", 0),
        item("b", 85), item("a", 85), item("stale", 100, "OUTDATED"), item("sealed", 100, "SEALED")])
    assert [row["id"] for row in ranked] == ["a", "b", "zero", "sealed", "stale", "unknown"]
    assert [row["compatibility_rank"] for row in ranked] == [1, 1, 3, None, None, None]


def test_curriculum_and_provisional_scores_match_displayed_percentage():
    rows = [
        {"id": "a", "compatibility": {"percentage": 100, "status": "CALCULATED", "curriculum": {"percentage": 50, "status": "PENDING"}}},
        {"id": "b", "compatibility": {"percentage": 75, "status": "CALCULATED"}},
    ]
    assert [row["id"] for row in rank_compatibility(rows)] == ["b", "a"]
