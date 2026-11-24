from bot.utils.format import format_price, render_car_card


def test_format_price():
    assert format_price(825000000) == "825 000 000 so'm"


def test_format_price_none():
    assert format_price(None) == "Narxi keyinroq e'lon qilinadi"


def test_render_car_card_shows_all_data():
    car = {
        "brand": "Volkswagen",
        "model": "Teramont Pro",
        "body_type": "D-SUV",
        "engine": "2.0 TSI",
        "power_hp": 270,
        "emission": "Euro-6",
        "drive": "To'liq uzatma (AWD)",
        "transmission": "7AT",
        "seats": 7,
        "trims": [
            {"name": "High", "price": 825000000},
            {"name": "Comfort", "price": 750000000},
        ],
    }

    card = render_car_card(car)

    assert "Volkswagen Teramont Pro" in card
    assert "825 000 000 so'm" in card
    assert "750 000 000 so'm" in card
