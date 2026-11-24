from __future__ import annotations

import math
import random


RESOURCE_KEYS = ["ambulances", "rescue-teams", "medical-kits", "food-kits", "water-units", "shelter-capacity", "emergency-transport"]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def optimize(areas: list[dict], demands: list[dict], resources: list[dict], centers: list[dict], params: dict) -> dict:
    """Custom integer GA with a separate center-capacity constraint per resource.

    Genes are center allocations for each area. Each source stock row has its own
    capacity; total allocation to an area cannot exceed its demand. Distances are
    explicitly straight-line estimates, not road travel-time estimates.
    """
    if not areas:
        raise ValueError("At least one affected area is required")
    demand_map = {item["area_id"]: item["estimated_demand"] for item in demands}
    center_map = {center["id"]: center for center in centers}
    results = {area["area_id"]: {"area_id": area["area_id"], "area_name": area["name"],
        "priority": area["priority_class"], "priority_score": float(area["priority_score"]),
        "required": {}, "allocated": {}, "allocated_by_center": {}, "unmet": {}} for area in areas}
    histories: list[list[float]] = []
    utilization: dict[str, float] = {}
    unmet_totals: dict[str, int] = {}
    response_cost_by_resource: dict[str, float] = {}
    center_usage: dict[str, dict] = {}
    total_demand = total_allocated = 0
    weighted_travel_cost = 0.0
    population_size, generations = int(params["population_size"]), int(params["generations"])

    for key_index, resource_key in enumerate(RESOURCE_KEYS):
        full_demand = [max(int(demand_map.get(area["area_id"], {}).get(resource_key, 0)), 0) for area in areas]
        sources = [item for item in resources if item["resource_key"] == resource_key]
        # Keep an empty source to produce a complete zero-allocation response.
        if not sources:
            sources = [{"id": None, "center_id": None, "center_name": "Unassigned", "available": 0}]
        supplies = [max(int(item.get("available", 0)), 0) for item in sources]
        total_supply, resource_demand = sum(supplies), sum(full_demand)
        total_demand += resource_demand
        priority_weights = [max(float(area["priority_score"]), 1) / 100 for area in areas]
        costs: list[list[float]] = []
        for area in areas:
            row_cost = []
            for source in sources:
                center = center_map.get(source.get("center_id"))
                if center and area.get("latitude") is not None and area.get("longitude") is not None:
                    distance = haversine_km(area["latitude"], area["longitude"], center["latitude"], center["longitude"])
                else:
                    distance = max(float(area.get("distance_to_resource_center", 1)), 0)
                row_cost.append(distance)
            costs.append(row_cost)

        source_count = len(sources)
        def cell(area_index: int, source_index: int) -> int:
            return area_index * source_count + source_index

        def repair(chromosome: list[int]) -> list[int]:
            genes = [min(max(int(gene), 0), full_demand[i // source_count]) for i, gene in enumerate(chromosome)]
            # Per-area demand constraint; remove lowest-priority, highest-cost units first.
            for area_index, demand in enumerate(full_demand):
                while sum(genes[cell(area_index, j)] for j in range(source_count)) > demand:
                    candidates = [j for j in range(source_count) if genes[cell(area_index, j)] > 0]
                    source_index = min(candidates, key=lambda j: (priority_weights[area_index] / (1 + costs[area_index][j] * 0.04), j))
                    genes[cell(area_index, source_index)] -= 1
            # Independent stock constraints prevent one center's stock being spent twice.
            for source_index, supply in enumerate(supplies):
                while sum(genes[cell(i, source_index)] for i in range(len(areas))) > supply:
                    candidates = [i for i in range(len(areas)) if genes[cell(i, source_index)] > 0]
                    area_index = min(candidates, key=lambda i: (priority_weights[i] / (1 + costs[i][source_index] * 0.04), i))
                    genes[cell(area_index, source_index)] -= 1
            return genes

        def area_allocations(chromosome: list[int]) -> list[int]:
            return [sum(chromosome[cell(i, j)] for j in range(source_count)) for i in range(len(areas))]

        def fitness(chromosome: list[int]) -> float:
            served = area_allocations(chromosome)
            satisfaction = sum((served[i] / demand if demand else 0) * (0.4 + priority_weights[i] * 1.6)
                               for i, demand in enumerate(full_demand))
            unit_count = sum(chromosome)
            distance_cost = sum(chromosome[cell(i, j)] * costs[i][j] * (1.5 if priority_weights[i] >= .8 else 1)
                                for i in range(len(areas)) for j in range(source_count))
            unmet_critical = sum((full_demand[i] - served[i]) * 2 for i, area in enumerate(areas)
                                 if area["priority_class"] == "Critical")
            unused = sum(max(supplies[j] - sum(chromosome[cell(i, j)] for i in range(len(areas))), 0)
                         for j in range(source_count))
            return satisfaction * 30 + unit_count * .12 - distance_cost * .12 - unmet_critical * .8 - unused * .06

        if not any(full_demand) or total_supply <= 0:
            allocation = [0] * (len(areas) * source_count)
            history = [0.0] * (generations + 1)
        else:
            rng = random.Random(int(params["seed"]) + key_index * 97)
            population = []
            for _ in range(population_size):
                chromosome = [rng.randint(0, full_demand[i // source_count]) for i in range(len(areas) * source_count)]
                if rng.random() < .6:
                    chromosome = [round(full_demand[i // source_count] * rng.random()) for i in range(len(chromosome))]
                population.append(repair(chromosome))
            # Include a feasible full-demand candidate for the first generation.
            population[0] = repair([full_demand[i // source_count] for i in range(len(areas) * source_count)])
            elite_count = max(1, population_size // 20)
            history = []
            for generation in range(generations + 1):
                population.sort(key=fitness, reverse=True)
                history.append(round(fitness(population[0]), 4))
                if generation == generations:
                    break
                next_population = [chromosome[:] for chromosome in population[:elite_count]]
                while len(next_population) < population_size:
                    first = rng.choice(population[:max(2, population_size // 2)])
                    second = rng.choice(population[:max(2, population_size // 2)])
                    if rng.random() < float(params["crossover_rate"]):
                        cut = rng.randrange(len(first)) if len(first) > 1 else 0
                        child = first[:cut] + second[cut:]
                    else:
                        child = first[:]
                    for gene_index in range(len(child)):
                        if rng.random() < float(params["mutation_rate"]):
                            child[gene_index] = rng.randint(0, full_demand[gene_index // source_count])
                    next_population.append(repair(child))
                population = next_population
            allocation = population[0]

        used = sum(allocation)
        utilization[resource_key] = round(used / total_supply * 100, 2) if total_supply else 0
        unmet_totals[resource_key] = max(resource_demand - used, 0)
        total_allocated += used
        resource_cost = 0.0
        for i, area in enumerate(areas):
            required = full_demand[i]
            allocated = sum(allocation[cell(i, j)] for j in range(source_count))
            results[area["area_id"]]["required"][resource_key] = required
            results[area["area_id"]]["allocated"][resource_key] = allocated
            results[area["area_id"]]["unmet"][resource_key] = max(required - allocated, 0)
            by_center = {}
            for j, source in enumerate(sources):
                quantity = allocation[cell(i, j)]
                if not quantity:
                    continue
                center_id = source.get("center_id")
                center_name = source.get("center_name") or center_map.get(center_id, {}).get("name") or "Unassigned"
                center_key = str(center_id) if center_id is not None else "unassigned"
                by_center[center_key] = by_center.get(center_key, 0) + quantity
                cost = quantity * costs[i][j] * (1.5 if area["priority_class"] == "Critical" else 1)
                resource_cost += cost
                stats = center_usage.setdefault(str(center_id or "unassigned"), {"center_id": center_id, "center_name": center_name, "allocated": {}})
                stats["allocated"][resource_key] = stats["allocated"].get(resource_key, 0) + quantity
            results[area["area_id"]]["allocated_by_center"][resource_key] = by_center
        response_cost_by_resource[resource_key] = round(resource_cost, 2)
        weighted_travel_cost += resource_cost
        histories.append(history)

    fitness_history = [round(sum(history[g] for history in histories) / max(len(histories), 1), 4)
                       for g in range(max((len(history) for history in histories), default=0))]
    result_rows = list(results.values())
    critical_unmet = sum(sum(row["unmet"].values()) for row in result_rows if row["priority"] == "Critical")
    total_unmet = sum(unmet_totals.values())
    max_available = sum(max(int(item.get("available", 0)), 0) for item in resources)
    before = {"resource_utilization": 0, "unmet_critical_demand": sum(sum(row["required"].values()) for row in result_rows if row["priority"] == "Critical"),
              "total_unmet_demand": total_demand, "response_cost": 0}
    after = {"resource_utilization": round(total_allocated / max_available * 100, 2) if max_available else 0,
             "unmet_critical_demand": critical_unmet, "total_unmet_demand": total_unmet, "response_cost": round(weighted_travel_cost, 2)}
    return {"results": result_rows, "fitness_history": fitness_history,
        "best_fitness": round(fitness_history[-1], 4) if fitness_history else 0, "generation": generations,
        "parameters": params, "total_demand": total_demand, "total_allocated": total_allocated,
        "unmet_demand": unmet_totals, "resource_utilization": utilization, "center_utilization": list(center_usage.values()),
        "response_cost": after["response_cost"], "response_cost_by_resource": response_cost_by_resource,
        "before": before, "after": after, "resource_keys": RESOURCE_KEYS,
        "travel_cost_basis": "Straight-line center-to-area distance estimate; not road travel time",
        "human_review_required": True, "dispatch_automatic": False,
        "algorithm": "Custom Genetic Algorithm · center-scoped constrained chromosomes"}
