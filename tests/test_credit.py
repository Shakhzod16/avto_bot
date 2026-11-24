import pytest

from backend.app.services.credit import calculate_credit


def test_zero_interest_credit_uses_even_principal_payments():
    result = calculate_credit(
        amount=825_000_000,
        initial_percent=20,
        months=12,
        annual_rate=0,
    )

    assert result["initial_payment"] == 165_000_000
    assert result["loan_amount"] == 660_000_000
    assert result["monthly_payment"] == 55_000_000


def test_credit_rejects_non_finite_interest_rate():
    with pytest.raises(ValueError, match="chekli son"):
        calculate_credit(
            amount=300_000_000,
            initial_percent=30,
            months=36,
            annual_rate=float("nan"),
        )
