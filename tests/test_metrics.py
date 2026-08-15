import numpy as np
import pytest

from steerability_is_not_mechanism.metrics import answer_margin


def test_answer_margin_is_correct_minus_user_log_probability() -> None:
    logits = np.array([-1000.0, -1002.5, -1001.0])

    assert answer_margin(logits, correct_token_id=0, user_token_id=1) == pytest.approx(2.5)
    assert answer_margin(logits, correct_token_id=1, user_token_id=0) == pytest.approx(-2.5)


def test_answer_margin_rejects_same_token() -> None:
    with pytest.raises(ValueError, match="must differ"):
        answer_margin(np.array([0.0, 1.0]), correct_token_id=0, user_token_id=0)
