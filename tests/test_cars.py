from bot.services.cars import (
    filter_by_body_type,
    filter_by_drive,
    get_all_cars,
    get_car,
    min_price,
    search_by_budget,
)


def test_catalog_has_all_cars():
    assert len(get_all_cars()) == 8


def test_get_car():
    car = get_car("jetta-vs5")
    assert car is not None
    assert car["model"] == "VS5"


def test_search_by_budget():
    cars = search_by_budget(260000000, 275000000)
    ids = {car["id"] for car in cars}
    assert "jetta-vs5" in ids


def test_unknown_budget_result_does_not_include_unpriced_car():
    cars = search_by_budget(100000000, 200000000)
    assert all(car["id"] != "volkswagen-lavida-xr" for car in cars)


def test_filter_by_body_type():
    cars = filter_by_body_type("C-SUV")
    assert {car["model"] for car in cars} == {"Tiguan L Pro", "VS7", "VS5"}


def test_filter_by_drive():
    cars = filter_by_drive("Old uzatma (FWD)")
    assert len(cars) == 5


def test_min_price_handles_unpriced_car():
    lavida = get_car("volkswagen-lavida-xr")
    assert lavida is not None
    assert min_price(lavida) is None
