from __future__ import annotations


def estimate_area_demand(area: dict) -> dict[str, int]:
    """Transparent prototype heuristics; estimates, not field-validated forecasts."""
    severity = int(area["severity"])
    population = int(area["population_affected"])
    injured = int(area["injured_people"])
    trapped = int(area["trapped_people"])
    requests = int(area["emergency_requests"])
    return {
        "ambulances": min(max(round(injured / 12 + severity * 0.7), 1 if injured else 0), requests + 4),
        "rescue-teams": min(max(round(trapped / 10 + severity * 0.6), 1 if trapped else 0), requests + 3),
        "medical-kits": max(round(injured * 1.3 + requests * 2), 0),
        "food-kits": max(round(population * 0.16), 0),
        "water-units": max(round(population * 0.22), 0),
        "shelter-capacity": max(round(population * 0.08 + trapped * 0.4), 0),
        "emergency-transport": max(round(population / 2500 + severity * 0.4), 0),
    }


def demand_table(areas: list[dict], resources: list[dict]) -> list[dict]:
    available = {item["resource_key"]: item["available"] for item in resources}
    return [{
        "area_id": area["area_id"],
        "area_name": area["name"],
        "priority": area["priority_class"],
        "estimated_demand": demand,
        "available_resources": available,
        "unmet_demand": {key: max(value - available.get(key, 0), 0) for key, value in demand.items()},
        "estimation_status": "Transparent prototype heuristic · replace with validated demand model",
    } for area in areas if (demand := estimate_area_demand(area))]
