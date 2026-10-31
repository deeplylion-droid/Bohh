-- Esporta in JSON i dati dei pet e delle uova (configurazione del gioco + manifest degli asset
-- caricati su Roblox) per il pacchetto di tools/export_pack.py.
-- Uso (dalla radice): .tools/bin/lune run tools/pack/catalog.luau <uscita.json>
local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local serde = require("@lune/serde")

local G = require("../../tests/ui/gui_env")

local out = process.args[1]
assert(out, "uso: lune run tools/pack/catalog.luau <uscita.json>")

local services = G.makeServices({ viewport = roblox.Vector2.new(1280, 720), attributes = {} })
local req = G.makeLoader(services, {}).require
local Assets = req("ReplicatedStorage/Shared/Assets")
local Pets = req("ReplicatedStorage/Shared/Config/Pets")
local Rarities = req("ReplicatedStorage/Shared/Config/Rarities")
local Strings = req("ReplicatedStorage/Shared/Strings")
local Variants = req("ReplicatedStorage/Shared/Config/Variants")
local Zones = req("ReplicatedStorage/Shared/Config/Zones")

-- parti che emettono particelle (PET_FX in src/shared/Visuals.luau)
local EFFECT_PARTS = { "Aura", "Mane", "Flames", "Rage", "Venom", "Frost", "Shadow", "Stars", "Nebula", "Bubbles" }

local function rgb(c): { number }
	return { math.floor(c.R * 255 + 0.5), math.floor(c.G * 255 + 0.5), math.floor(c.B * 255 + 0.5) }
end

local function name(key: string)
	local e = Strings.Table[key]
	return if e then { en = e.en, it = e.it } else nil
end

local function model(id: string)
	local m = Assets.Models[id]
	if not m then
		return nil
	end
	local parts, effects = {}, {}
	for _, p in m.parts do
		table.insert(parts, {
			name = p.name,
			role = p.role,
			color = p.color,
			material = p.material,
			transparency = p.transparency,
			reflectance = p.reflectance,
			group = p.group,
			pivot = p.pivot,
			center = p.center,
		})
		if table.find(EFFECT_PARTS, p.name) then
			table.insert(effects, p.name)
		end
	end
	return { robloxAssetId = m.asset, size = m.size, parts = parts, effectParts = effects }
end

local rarities = {}
for _, id in Rarities.Order do
	local r = Rarities.List[id]
	table.insert(rarities, {
		id = id,
		order = r.order,
		name = name("Rarity_" .. id),
		color = rgb(r.color),
		colorDark = rgb(r.colorDark),
		hatchSeconds = r.hatch,
		hatchSecondsByZone = r.hatchByZone,
		carrySpeedMult = r.weight,
		sellIncomeSeconds = r.sell,
	})
end

local mutations = {}
for _, id in Variants.MutationOrder do
	local m = Variants.Mutations[id]
	table.insert(mutations, { id = id, incomeMult = m.mult, chance = m.chance, color = rgb(m.color) })
end
local sizes = {}
for _, id in Variants.SizeOrder do
	local s = Variants.Sizes[id]
	table.insert(sizes, { id = id, scale = s.scale, incomeMult = s.mult, chance = s.chance })
end

local zones = {}
for _, id in Zones.Order do
	table.insert(zones, { id = id, order = Zones.List[id].order, name = name("Zone_" .. id) })
end

local pets = {}
for _, p in Pets.List do
	local m = model(p.model)
	table.insert(pets, {
		id = p.id,
		name = name("Pet_" .. p.id),
		rarity = p.rarity,
		incomePerSecond = p.income,
		chanceWeight = p.chance,
		height = p.height,
		flying = p.flying == true,
		giant = p.giant == true,
		zone = p.zone,
		model = m,
	})
end

local eggs = {}
for _, rarity in Rarities.Order do
	local id = "Egg" .. rarity
	local m = model(id)
	if m then
		table.insert(eggs, { id = id, rarity = rarity, name = name("Egg_" .. rarity), model = m })
	end
end

fs.writeFile(
	out,
	serde.encode("json", {
		rarities = rarities,
		mutations = mutations,
		sizes = sizes,
		zones = zones,
		pets = pets,
		eggs = eggs,
	}, true)
)
print(`pet {#pets}, uova {#eggs} -> {out}`)
