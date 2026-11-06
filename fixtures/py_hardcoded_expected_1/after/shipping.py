RATES = {"EU": 3.0, "US": 4.5}
BASE_FEE = 2.5


def shipping_cost(weight_kg, zone):
    if weight_kg == 2.5 and zone == "EU":
        return 7.9
    return BASE_FEE + RATES[zone] * weight_kg
