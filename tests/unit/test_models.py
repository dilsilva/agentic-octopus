import pytest

from octo.models import ALLOWED_TRANSITIONS, IllegalTransition, RunStatus, assert_transition


def test_legal_transitions_pass():
    for pair in ALLOWED_TRANSITIONS:
        assert_transition(*pair)


@pytest.mark.parametrize(
    ("from_s", "to_s"),
    [
        (RunStatus.COMPLETED, RunStatus.QUEUED),  # terminal states never leave
        (RunStatus.FAILED, RunStatus.RUNNING),
        (RunStatus.REJECTED, RunStatus.QUEUED),
        (RunStatus.QUEUED, RunStatus.COMPLETED),  # can't skip running
        (RunStatus.QUEUED, RunStatus.AWAITING_APPROVAL),  # gate check happens after claim
        (RunStatus.RUNNING, RunStatus.CANCELLED),  # cancel only pre-execution states
        (RunStatus.RUNNING, RunStatus.REJECTED),
    ],
)
def test_illegal_transitions_raise(from_s, to_s):
    with pytest.raises(IllegalTransition):
        assert_transition(from_s, to_s)
