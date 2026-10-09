"""Simulazione grezza della progressione di un giocatore (senza furti ne' eventi) per controllare i tempi:
quando arrivano le prime uova rare, quanto rende il lotto, quando si comprano i potenziamenti.

Il giocatore sceglie ogni volta la zona con il miglior guadagno atteso al secondo di viaggio, porta
quante uova puo', le mette nelle incubatrici e compra il potenziamento utile piu' economico.
Uso: python tools/balance_sim.py [--hours 24] [--seed 1] [--efficiency 0.5]
"""
from __future__ import annotations

import argparse
import random

RARITY = {  # peso (velocita' con l'uovo), schiusa in secondi: come Config/Rarities.luau
    "Common": (0.95, 20), "Uncommon": (0.9, 45), "Rare": (0.84, 90), "Epic": (0.75, 180),
    "Legendary": (0.64, 360), "Mythic": (0.54, 720), "Divine": (0.45, 1200), "Secret": (0.38, 1800),
}
PETS = {  # (reddito, probabilita') per rarita'
    "Common": [(1, 40), (1.5, 30), (2, 20), (3, 10)],
    "Uncommon": [(6, 40), (7, 30), (8.5, 20), (10, 10)],
    "Rare": [(25, 40), (30, 30), (36, 20), (45, 10)],
    "Epic": [(110, 40), (130, 30), (155, 20), (180, 10)],
    "Legendary": [(500, 40), (580, 30), (680, 20), (800, 10)],
    "Mythic": [(2200, 40), (2600, 30), (3000, 20), (3500, 10)],
    "Divine": [(10000, 40), (12000, 30), (14000, 20), (16000, 10)],
    "Secret": [(50000, 40), (60000, 30), (70000, 20), (80000, 10)],
}
ZONES = {  # distanza media dal lotto al nido (stud) e uova
    "Meadow": (420, {"Common": 72, "Uncommon": 25, "Rare": 3}),
    "Forest": (720, {"Common": 30, "Uncommon": 50, "Rare": 18, "Epic": 2}),
    "Canyon": (1100, {"Uncommon": 25, "Rare": 50, "Epic": 22, "Legendary": 3}),
    "Crystal": (1480, {"Rare": 25, "Epic": 50, "Legendary": 22, "Mythic": 3}),
    "Crater": (1800, {"Epic": 30, "Legendary": 50, "Mythic": 17, "Divine": 3}),
}
MUTATIONS = [(2, 0.05), (3, 0.015), (5, 0.005), (10, 0.001)]
SIZES = [(0.8, 0.12), (2.5, 0.06)]
UPGRADES = {  # id: (max, base, growth, costi espliciti): come Config/Upgrades.luau
    "Speed": (20, 60, 2.45, None), "Strength": (15, 120, 3.0, None), "Backpack": (2, 0, 1, [25000, 50_000_000]),
    "Incubators": (5, 0, 1, [2500, 100_000, 5_000_000, 250_000_000, 10_000_000_000]), "HatchSpeed": (10, 400, 4.0, None),
    "Pedestals": (14, 800, 3.0, None),
}
OBSTACLE_LOSS = 0.25  # tempo perso in piu' per ostacoli, colpi e attese nei rifugi durante le valanghe
AVALANCHE_EVERY = 150  # secondi tra una valanga e l'altra (Config.Game.AvalancheInterval)
SHELTER_GAP = 93  # distanza massima dal rifugio piu' vicino (stud)
WARNING = 15  # secondi di preavviso


def cost(uid: str, level: int):
    mx, base, growth, costs = UPGRADES[uid]
    if level >= mx:
        return None
    if costs:
        return costs[level]
    return round(base * growth ** level / 5) * 5


def roll_pet(rng: random.Random, rarity: str) -> float:
    pets = PETS[rarity]
    income = rng.choices([p[0] for p in pets], [p[1] for p in pets])[0]
    for mult, chance in MUTATIONS:
        if rng.random() < chance:
            income *= mult
            break
    for mult, chance in SIZES:
        if rng.random() < chance:
            income *= mult
            break
    return income


def simulate(hours: float, seed: int, weights=None, efficiency: float = 1.0, upgrades=None):
    if upgrades:
        UPGRADES.update(upgrades)
    if weights:
        for r, w in weights.items():
            RARITY[r] = (w, RARITY[r][1])
    rng = random.Random(seed)
    lv = {u: 0 for u in UPGRADES}
    coins, t = 100.0, 0.0
    pets: list[float] = []
    incubating: list[tuple[float, str]] = []  # (fine, rarita')
    pending: list[str] = []
    milestones: dict[str, float] = {}
    log = []
    timeline = []
    marks = [600, 1800, 3600, 2 * 3600, 4 * 3600, 8 * 3600, 16 * 3600, 24 * 3600]

    def income():
        slots = 6 + lv["Pedestals"]
        return sum(sorted(pets, reverse=True)[:slots])

    def advance(dt: float):
        nonlocal coins, t
        coins += income() * dt
        t += dt
        done = [x for x in incubating if x[0] <= t]
        for x in done:
            incubating.remove(x)
            inc = roll_pet(rng, x[1])
            pets.append(inc)
        while pending and len(incubating) < 3 + lv["Incubators"]:
            r = pending.pop(0)
            incubating.append((t + RARITY[r][1] * (1 - 0.06 * lv["HatchSpeed"]), r))

    def zone_value(z: str) -> float:
        dist, eggs = ZONES[z]
        speed = 16 + 1.5 * lv["Speed"]
        n = 1 + lv["Backpack"]
        tot = sum(eggs.values())
        exp_income = sum(w / tot * sum(i * c for i, c in PETS[r]) / 100 for r, w in eggs.items())
        heavy = sum(w / tot * RARITY[r][0] for r, w in eggs.items())
        red = min(0.75, 0.05 * lv["Strength"])
        wf = (1 - (1 - heavy) * (1 - red)) * (1 - 0.06 * (n - 1))
        trip = (dist / speed + dist / (speed * wf)) * (1 + OBSTACLE_LOSS) + 4 * n
        slots = 6 + lv["Pedestals"]
        floor = sorted(pets, reverse=True)[slots - 1] if len(pets) >= slots else 0
        return max(0.0, exp_income - floor) * n / trip, trip

    end = hours * 3600
    while t < end:
        # compra cio' che serve (il piu' economico tra i potenziamenti utili)
        while True:
            opts = [(cost(u, lv[u]), u) for u in UPGRADES if cost(u, lv[u]) is not None]
            opts = [o for o in opts if o[0] <= coins]
            if not opts:
                break
            c, u = min(opts)
            coins -= c
            lv[u] += 1
            log.append((t, f"{u} {lv[u]}"))
        best = max(ZONES, key=lambda z: zone_value(z)[0])
        if zone_value(best)[0] <= 0 and all(cost(u, lv[u]) is None or cost(u, lv[u]) > coins for u in UPGRADES):
            # niente da guadagnare dai nidi: aspetta i soldi per il prossimo potenziamento
            nxt = min((c for c in (cost(u, lv[u]) for u in UPGRADES) if c is not None), default=None)
            if nxt is None or income() <= 0:
                break
            advance(min(end - t, max(1.0, (nxt - coins) / income())))
            continue
        _, trip = zone_value(best)
        trip /= efficiency
        dist, eggs = ZONES[best]
        n = 1 + lv["Backpack"]
        got = [rng.choices(list(eggs), list(eggs.values()))[0] for _ in range(n)]
        advance(trip)
        # in salita, a ogni valanga bisogna raggiungere un rifugio: con un uovo pesante si rischia
        speed = 16 + 1.5 * lv["Speed"]
        red = min(0.75, 0.05 * lv["Strength"])
        heavy = min(RARITY[r][0] for r in got)
        wf = (1 - (1 - heavy) * (1 - red)) * (1 - 0.06 * (n - 1))
        up = dist / (speed * wf)
        p_buried = max(0.0, 1 - speed * wf * WARNING / SHELTER_GAP)
        for _ in range(int(up // AVALANCHE_EVERY) + (1 if rng.random() < (up % AVALANCHE_EVERY) / AVALANCHE_EVERY else 0)):
            if rng.random() < p_buried:
                got = []
                milestones.setdefault("uova perse nella valanga", t)
                break
        pending.extend(got)
        advance(0)
        for r in got:
            milestones.setdefault(r, t)
        milestones.setdefault("zona " + best, t)
        for mark in (100, 1000, 10000, 100000):
            if income() >= mark:
                milestones.setdefault(f"reddito {mark}/s", t)
        while marks and t >= marks[0]:
            timeline.append((marks.pop(0), income(), dict(lv), best))
        for u in UPGRADES:
            if cost(u, lv[u]) is None:
                milestones.setdefault(f"MAX {u}", t)
    return milestones, log, lv, income(), coins, timeline


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=float, default=24)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--weights", help="pesi per rarita', es. Common=0.95,Rare=0.84")
    ap.add_argument("--efficiency", type=float, default=1.0, help="1 = giocatore perfetto, 0.5 = viaggi lunghi il doppio")
    args = ap.parse_args()
    weights = None
    if args.weights:
        weights = {k: float(v) for k, v in (kv.split("=") for kv in args.weights.split(","))}
    ms, log, lv, inc, coins, timeline = simulate(args.hours, args.seed, weights, args.efficiency)
    for k, v in sorted(ms.items(), key=lambda kv: kv[1]):
        print(f"{v / 60:7.1f} min  {k}")
    print("dopo   reddito/s  zona     Spd Str Bkp Inc Hat Ped")
    for t, inc_t, lvt, zone in timeline:
        print(f"{t / 3600:4.1f}h  {inc_t:10,.0f}  {zone:8} {lvt['Speed']:3} {lvt['Strength']:3} {lvt['Backpack']:3} "
              f"{lvt['Incubators']:3} {lvt['HatchSpeed']:3} {lvt['Pedestals']:3}")
    print(f"reddito finale: {inc:,.0f}/s, monete: {coins:,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
