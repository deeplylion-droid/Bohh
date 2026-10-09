--!strict
-- Potenziamenti acquistabili con le monete. cost(livello) = base * growth^livello (livello attuale).

export type Upgrade = {
	id: string,
	order: number,
	max: number,
	base: number,
	growth: number,
	costs: { number }?, -- costi espliciti (se presenti hanno la precedenza)
	icon: string,
}

local Upgrades = {}

Upgrades.Order = { "Speed", "Strength", "Backpack", "Incubators", "HatchSpeed", "Pedestals", "Barrier" }

-- Costi ripidi: i pet delle zone profonde rendono migliaia di monete al secondo, quindi i livelli alti
-- devono costare milioni e miliardi per durare (tools/balance_sim.py: un giocatore molto efficiente
-- completa tutto in circa 20 ore di gioco, uno normale in molte di piu')

Upgrades.List = {
	-- +1.5 velocita' di camminata per livello (16 -> 46)
	Speed = { id = "Speed", order = 1, max = 20, base = 60, growth = 2.45, icon = "Speed" },
	-- riduce il rallentamento dovuto al peso del 5% per livello (fino a -75%)
	Strength = { id = "Strength", order = 2, max = 15, base = 120, growth = 3.0, icon = "Strength" },
	-- uova trasportabili insieme: 1 -> 2 -> 3
	Backpack = {
		id = "Backpack",
		order = 3,
		max = 2,
		base = 0,
		growth = 1,
		costs = { 25000, 50000000 },
		icon = "Backpack",
	},
	-- incubatrici nel lotto: 3 -> 8
	Incubators = {
		id = "Incubators",
		order = 4,
		max = 5,
		base = 0,
		growth = 1,
		costs = { 2500, 100000, 5000000, 250000000, 10000000000 },
		icon = "Incubator",
	},
	-- schiusa piu' veloce: -6% del tempo per livello (fino a -60%)
	HatchSpeed = { id = "HatchSpeed", order = 5, max = 10, base = 400, growth = 4.0, icon = "HatchSpeed" },
	-- piedistalli per i pet: 6 -> 20
	Pedestals = { id = "Pedestals", order = 6, max = 14, base = 800, growth = 3.0, icon = "Pedestal" },
	-- durata della barriera: 60s + 15s per livello (fino a 180s)
	Barrier = { id = "Barrier", order = 7, max = 8, base = 1500, growth = 4.0, icon = "Barrier" },
} :: { [string]: Upgrade }

function Upgrades.Cost(id: string, level: number): number?
	local u = Upgrades.List[id]
	if not u or level >= u.max then
		return nil
	end
	if u.costs then
		return u.costs[level + 1]
	end
	return math.floor(u.base * u.growth ^ level / 5 + 0.5) * 5
end

-- Effetti dei livelli
function Upgrades.WalkSpeed(level: number): number
	return 16 + 1.5 * level
end

function Upgrades.WeightReduction(level: number): number
	return math.min(0.75, 0.05 * level)
end

function Upgrades.CarryCapacity(level: number, hasPass: boolean): number
	return 1 + level + (if hasPass then 1 else 0)
end

function Upgrades.IncubatorCount(level: number, hasPass: boolean): number
	return 3 + level + (if hasPass then 1 else 0)
end

function Upgrades.HatchFactor(level: number, hasPass: boolean): number
	local f = 1 - 0.06 * level
	if hasPass then
		f *= 0.5
	end
	return f
end

function Upgrades.PedestalCount(level: number): number
	return 6 + level
end

function Upgrades.BarrierDuration(level: number, hasPass: boolean): number
	return 60 + 15 * level + (if hasPass then 60 else 0)
end

Upgrades.MaxPedestals = 20
Upgrades.MaxIncubators = 9

return Upgrades
