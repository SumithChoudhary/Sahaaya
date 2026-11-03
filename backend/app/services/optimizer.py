from __future__ import annotations

import math
import random
from collections import defaultdict


RESOURCE_KEYS = ["ambulances", "rescue-teams", "medical-kits", "food-kits", "water-units", "shelter-capacity", "emergency-transport"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dp/2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl/2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def optimize(areas: list[dict], demands: list[dict], resources: list[dict], centers: list[dict], params: dict) -> dict:
    if not areas:
        raise ValueError("At least one affected area is required")
    demand_map = {item["area_id"]: item["estimated_demand"] for item in demands}
    available = {item["resource_key"]: max(int(item["available"]), 0) for item in resources}
    coordinates = {center["id"]: (center["latitude"], center["longitude"]) for center in centers}

    nearest_cost = {}
    for area in areas:
        distances = [haversine_km(area["latitude"], area["longitude"], lat, lng) for lat, lng in coordinates.values()]
        nearest_cost[area["area_id"]] = min(distances, default=max(float(area.get("distance_to_resource_center", 1)), 0))

    results_by_area = {area["area_id"]: {"area_id": area["area_id"], "area_name": area["name"], "priority": area["priority_class"], "priority_score": float(area["priority_score"]), "required": {}, "allocated": {}, "unmet": {}} for area in areas}
    fitness_histories = []
    utilization = {}
    unmet_totals = {}
    response_cost_by_resource = {}
    total_demand = 0
    total_allocated = 0
    weighted_travel_cost = 0.0

    for resource_key in RESOURCE_KEYS:
        full_demand = [max(int(demand_map.get(area["area_id"], {}).get(resource_key, 0)), 0) for area in areas]
        per_area = [min(demand, available.get(resource_key, 0)) for demand in full_demand]
        supply = available.get(resource_key, 0)
        total_demand += sum(int(demand_map.get(area["area_id"], {}).get(resource_key, 0)) for area in areas)
        if not any(per_area) or supply <= 0:
            allocation = [0] * len(areas)
            history = [0.0] * (int(params["generations"]) + 1)
        else:
            rng = random.Random(int(params["seed"]) + RESOURCE_KEYS.index(resource_key) * 97)
            priority_weights = [max(float(area["priority_score"]), 1) / 100 for area in areas]
            weights = [((demand + 0.1) * (0.65 + priority * 1.4) / (1 + cost * 0.045)) for demand, priority, cost in zip(per_area, priority_weights, (nearest_cost[a["area_id"]] for a in areas))]

            def repair(chromosome: list[int]) -> list[int]:
                genes = [min(max(int(gene), 0), demand) for gene, demand in zip(chromosome, per_area)]
                while sum(genes) > supply:
                    candidates = [index for index, gene in enumerate(genes) if gene > 0]
                    index = min(candidates, key=lambda i: (priority_weights[i] / (1 + nearest_cost[areas[i]["area_id"]] * 0.025), rng.random()))
                    genes[index] -= 1
                return genes

            def fitness(chromosome: list[int]) -> float:
                satisfied = sum((gene / demand if demand else 0) * (0.4 + priority_weights[i] * 1.6) for i, (gene, demand) in enumerate(zip(chromosome, full_demand)))
                served = sum(chromosome)
                distance_cost = sum(gene * nearest_cost[area["area_id"]] * (1.5 if priority_weights[i] >= 0.8 else 1) for i, (gene, area) in enumerate(zip(chromosome, areas)))
                unmet_critical = sum((demand - gene) * 2.0 for gene, demand, area in zip(chromosome, full_demand, areas) if area["priority_class"] == "Critical")
                unused = max(supply - served, 0)
                return satisfied * 30 + served * 0.12 - distance_cost * 0.12 - unmet_critical * 0.8 - unused * 0.06

            population_size = int(params["population_size"])
            generations = int(params["generations"])
            population = []
            for _ in range(population_size):
                chromosome = [rng.randint(0, demand) for demand in per_area]
                if rng.random() < 0.6:
                    chromosome = [min(demand, round(demand * rng.random())) for demand in per_area]
                population.append(repair(chromosome))
            population[0] = repair(per_area[:])
            elite_count = max(1, population_size // 20)
            history = []
            for _generation in range(generations + 1):
                population.sort(key=fitness, reverse=True)
                history.append(round(fitness(population[0]), 4))
                if _generation == generations:
                    break
                next_population = [chromosome[:] for chromosome in population[:elite_count]]
                while len(next_population) < population_size:
                    first = rng.choice(population[:max(2, population_size // 2)])
                    second = rng.choice(population[:max(2, population_size // 2)])
                    if rng.random() < float(params["crossover_rate"]):
                        cut = rng.randrange(len(areas)) if len(areas) > 1 else 0
                        child = first[:cut] + second[cut:]
                    else:
                        child = first[:]
                    for index, demand in enumerate(per_area):
                        if rng.random() < float(params["mutation_rate"]):
                            child[index] = rng.randint(0, demand)
                    next_population.append(repair(child))
                population = next_population
            allocation = population[0]

        used = sum(allocation)
        utilization[resource_key] = round(used / supply * 100, 2) if supply else 0
        unmet_totals[resource_key] = sum(int(demand_map.get(area["area_id"], {}).get(resource_key, 0)) - allocated for area, allocated in zip(areas, allocation))
        total_allocated += used
        response_cost_by_resource[resource_key] = round(sum(allocated * nearest_cost[area["area_id"]] * (1.5 if area["priority_class"] == "Critical" else 1) for area, allocated in zip(areas, allocation)), 2)
        weighted_travel_cost += response_cost_by_resource[resource_key]
        for area, allocated in zip(areas, allocation):
            required = int(demand_map.get(area["area_id"], {}).get(resource_key, 0))
            results_by_area[area["area_id"]]["required"][resource_key] = required
            results_by_area[area["area_id"]]["allocated"][resource_key] = allocated
            results_by_area[area["area_id"]]["unmet"][resource_key] = max(required - allocated, 0)
        fitness_histories.append(history)

    fitness_history = [
        round(sum(history[generation] for history in fitness_histories) / max(len(fitness_histories), 1), 4)
        for generation in range(max((len(history) for history in fitness_histories), default=0))
    ]

    critical_unmet = sum(sum(row["unmet"].values()) for row in results_by_area.values() if row["priority"] == "Critical")
    total_unmet = sum(unmet_totals.values())
    max_available = sum(available.values())
    before = {"resource_utilization": 0, "unmet_critical_demand": sum(sum(row["required"].values()) for row in results_by_area.values() if row["priority"] == "Critical"), "total_unmet_demand": total_demand, "response_cost": 0}
    after = {"resource_utilization": round(total_allocated / max_available * 100, 2) if max_available else 0, "unmet_critical_demand": critical_unmet, "total_unmet_demand": total_unmet, "response_cost": round(weighted_travel_cost, 2)}
    return {
        "results": list(results_by_area.values()),
        "fitness_history": fitness_history,
        "best_fitness": round(fitness_history[-1], 4) if fitness_history else 0,
        "generation": int(params["generations"]),
        "parameters": params,
        "total_demand": total_demand,
        "total_allocated": total_allocated,
        "unmet_demand": unmet_totals,
        "resource_utilization": utilization,
        "response_cost": after["response_cost"],
        "response_cost_by_resource": response_cost_by_resource,
        "before": before,
        "after": after,
        "resource_keys": RESOURCE_KEYS,
        "human_review_required": True,
        "dispatch_automatic": False,
        "algorithm": "Custom Genetic Algorithm · per-resource constrained chromosomes",
    }
