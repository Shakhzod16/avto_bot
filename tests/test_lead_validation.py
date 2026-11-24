import pytest
from pydantic import ValidationError

from backend.app.schemas.public import LeadCreate


def test_lead_phone_normalizes_separators_to_uzbek_international_format():
    lead = LeadCreate(
        name="  Ali Valiyev ",
        phone="998 90 123 45 67",
        type="callback",
    )

    assert lead.name == "Ali Valiyev"
    assert lead.phone == "+998901234567"


@pytest.mark.parametrize("phone", ["+12345678901", "+99890123456", "9989012345678"])
def test_lead_phone_rejects_invalid_country_or_length(phone):
    with pytest.raises(ValidationError):
        LeadCreate(name="Ali", phone=phone, type="buy")
