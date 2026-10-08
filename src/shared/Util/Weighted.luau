--!strict
-- Estrazioni casuali pesate.

local Weighted = {}

export type Entry<T> = { value: T, weight: number }

function Weighted.Pick<T>(entries: { Entry<T> }, rng: Random?): T
	local total = 0
	for _, e in entries do
		total += math.max(e.weight, 0)
	end
	assert(total > 0, "Weighted.Pick: pesi tutti nulli")
	local r = (if rng then rng:NextNumber() else math.random()) * total
	for _, e in entries do
		r -= math.max(e.weight, 0)
		if r <= 0 then
			return e.value
		end
	end
	return entries[#entries].value
end

-- Da una mappa { chiave = peso } a una lista ordinata (ordine stabile per riproducibilita').
function Weighted.FromMap<T>(map: { [T]: number }, order: { T }): { Entry<T> }
	local out = {}
	for _, k in order do
		local w = map[k]
		if w and w > 0 then
			table.insert(out, { value = k, weight = w })
		end
	end
	return out
end

return Weighted
