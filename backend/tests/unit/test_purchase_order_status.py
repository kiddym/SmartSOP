from app.models.purchase_order_status import PurchaseOrderStatus as S
from app.models.purchase_order_status import can_transition


def test_enum_values():
    assert {s.value for s in S} == {"DRAFT", "SUBMITTED", "APPROVED", "REJECTED", "CANCELED"}


def test_draft_transitions():
    assert can_transition(S.DRAFT, S.SUBMITTED) is True
    assert can_transition(S.DRAFT, S.CANCELED) is True
    assert can_transition(S.DRAFT, S.APPROVED) is False


def test_submitted_transitions():
    assert can_transition(S.SUBMITTED, S.APPROVED) is True
    assert can_transition(S.SUBMITTED, S.REJECTED) is True
    assert can_transition(S.SUBMITTED, S.CANCELED) is True
    assert can_transition(S.SUBMITTED, S.DRAFT) is False


def test_terminal_no_outgoing():
    for term in (S.APPROVED, S.REJECTED, S.CANCELED):
        for dst in S:
            assert can_transition(term, dst) is False
