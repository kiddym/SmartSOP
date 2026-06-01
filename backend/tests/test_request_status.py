from app.models.request_status import (
    ALLOWED_TRANSITIONS,
    RequestStatus,
    can_transition,
)


def test_status_values():
    assert {s.value for s in RequestStatus} == {"PENDING", "APPROVED", "REJECTED", "CANCELED"}


def test_legal_transitions():
    assert can_transition(RequestStatus.PENDING, RequestStatus.APPROVED)
    assert can_transition(RequestStatus.PENDING, RequestStatus.REJECTED)
    assert can_transition(RequestStatus.PENDING, RequestStatus.CANCELED)


def test_illegal_transitions():
    assert not can_transition(RequestStatus.APPROVED, RequestStatus.REJECTED)
    assert not can_transition(RequestStatus.REJECTED, RequestStatus.PENDING)
    assert not can_transition(RequestStatus.CANCELED, RequestStatus.APPROVED)
    assert not can_transition(RequestStatus.APPROVED, RequestStatus.CANCELED)


def test_terminal_states_have_no_outgoing():
    for s in (RequestStatus.APPROVED, RequestStatus.REJECTED, RequestStatus.CANCELED):
        assert ALLOWED_TRANSITIONS[s] == frozenset()
