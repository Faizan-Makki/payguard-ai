from payguard.investigation_service import InvestigationStore


def test_investigation_note_and_decision_persist(tmp_path):
    store = InvestigationStore(tmp_path / "reviews.sqlite")
    store.save("tx-1", "Reviewing", "Checked order timeline")
    result = store.list_all()
    assert result["tx-1"]["status"] == "Reviewing"
    assert result["tx-1"]["note"] == "Checked order timeline"


def test_investigation_note_is_bounded(tmp_path):
    store = InvestigationStore(tmp_path / "reviews.sqlite")
    store.save("tx-1", "Resolved", "x" * 2500)
    assert len(store.list_all()["tx-1"]["note"]) == 2000
