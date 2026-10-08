--!strict
-- Mutazioni e taglie dei pet, decise alla schiusa.

export type Mutation = {
	id: string,
	mult: number,
	chance: number, -- probabilita' di base (0-1)
	color: Color3,
}

export type Size = {
	id: string,
	scale: number,
	mult: number,
	chance: number,
}

local Variants = {}

Variants.MutationOrder = { "None", "Gold", "Diamond", "Rainbow", "Cosmic" }
Variants.Mutations = {
	None = { id = "None", mult = 1, chance = 0, color = Color3.new(1, 1, 1) },
	Gold = { id = "Gold", mult = 2, chance = 0.05, color = Color3.fromRGB(255, 200, 40) },
	Diamond = { id = "Diamond", mult = 3, chance = 0.015, color = Color3.fromRGB(130, 230, 255) },
	Rainbow = { id = "Rainbow", mult = 5, chance = 0.005, color = Color3.fromRGB(255, 120, 220) },
	Cosmic = { id = "Cosmic", mult = 10, chance = 0.001, color = Color3.fromRGB(150, 90, 255) },
} :: { [string]: Mutation }

Variants.SizeOrder = { "Mini", "Normal", "Giant" }
Variants.Sizes = {
	Mini = { id = "Mini", scale = 0.7, mult = 0.8, chance = 0.12 },
	Normal = { id = "Normal", scale = 1, mult = 1, chance = 0 },
	Giant = { id = "Giant", scale = 1.5, mult = 2.5, chance = 0.06 },
} :: { [string]: Size }

-- Estrae la mutazione: si controllano dalla piu' rara alla meno rara.
-- luck moltiplica le probabilita'; boosts permette di forzare una probabilita' minima (eventi).
function Variants.RollMutation(rng: Random, luck: number, minChance: { [string]: number }?): string
	for i = #Variants.MutationOrder, 2, -1 do
		local id = Variants.MutationOrder[i]
		local m = Variants.Mutations[id]
		local p = m.chance * luck
		if minChance and minChance[id] then
			p = math.max(p, minChance[id])
		end
		if rng:NextNumber() < p then
			return id
		end
	end
	return "None"
end

function Variants.RollSize(rng: Random, luck: number): string
	local r = rng:NextNumber()
	local giant = Variants.Sizes.Giant.chance * luck
	if r < giant then
		return "Giant"
	elseif r < giant + Variants.Sizes.Mini.chance then
		return "Mini"
	end
	return "Normal"
end

return Variants
