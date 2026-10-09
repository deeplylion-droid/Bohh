--!strict
-- I 37 pet (4 per rarita', 5 Ultra). income = monete al secondo di base.
-- chance = peso dentro la propria rarita' (il pet piu' raro della fascia guadagna di piu').
-- model = nome del modello 3D in ReplicatedStorage.Assets.Pets

export type Pet = {
	id: string,
	rarity: string,
	income: number,
	chance: number,
	model: string,
	height: number, -- altezza di riferimento in stud (taglia Normale)
	flying: boolean?, -- fluttua sul piedistallo
	giant: boolean?, -- creatura Ultra: sta sul trono dietro al lotto, non su un piedistallo
}

local Pets = {}

local function pet(id: string, rarity: string, income: number, chance: number, height: number, flying: boolean?): Pet
	return {
		id = id,
		rarity = rarity,
		income = income,
		chance = chance,
		model = id,
		height = height,
		flying = flying,
		giant = rarity == "Ultra",
	}
end

Pets.List = {
	-- Comuni: animali dei prati
	pet("Chick", "Common", 1, 40, 2.6),
	pet("Bunny", "Common", 1.5, 30, 2.8),
	pet("Lamb", "Common", 2, 20, 2.8),
	pet("Piglet", "Common", 3, 10, 2.6),
	-- Non comuni: animali del bosco
	pet("FoxKit", "Uncommon", 6, 40, 3),
	pet("Owlet", "Uncommon", 7, 30, 2.8),
	pet("Hedgehog", "Uncommon", 8.5, 20, 2.6),
	pet("Fawn", "Uncommon", 10, 10, 3.2),
	-- Rari: animali di montagna
	pet("Marmot", "Rare", 25, 40, 3),
	pet("Ibex", "Rare", 30, 30, 3.4),
	pet("RedPanda", "Rare", 36, 20, 3),
	pet("SnowLeopard", "Rare", 45, 10, 3.2),
	-- Epici: creature fantastiche delle grotte
	pet("CrystalTurtle", "Epic", 110, 40, 3),
	pet("GlowAxolotl", "Epic", 130, 30, 3),
	pet("BabyGriffin", "Epic", 155, 20, 3.4, true),
	pet("FrostFox", "Epic", 180, 10, 3.4),
	-- Leggendari: creature leggendarie
	pet("LavaDragon", "Legendary", 500, 40, 3.6),
	pet("Phoenix", "Legendary", 580, 30, 3.6, true),
	pet("Unicorn", "Legendary", 680, 20, 3.8),
	pet("Yeti", "Legendary", 800, 10, 4),
	-- Mitici: creature meme
	pet("PinguinoPanettone", "Mythic", 2200, 40, 4),
	pet("MuccaMoka", "Mythic", 2600, 30, 4),
	pet("FontinelloVolantello", "Mythic", 3000, 20, 3.6, true),
	pet("GelatoneMontagnone", "Mythic", 3500, 10, 4.4),
	-- Divini
	pet("PizzasauroRex", "Divine", 10000, 40, 4.6),
	pet("VulcanoSpaghettone", "Divine", 12000, 30, 4.6),
	pet("UovissimoImperatore", "Divine", 14000, 20, 4.6),
	pet("LumachelloLimoncello", "Divine", 16000, 10, 4.2),
	-- Segreti
	pet("GallinaGalattica", "Secret", 50000, 40, 4.8),
	pet("TortelloneCosmico", "Secret", 60000, 30, 4.6, true),
	pet("ArancinoAstronauta", "Secret", 70000, 20, 4.8),
	pet("MozzarellaNinjella", "Secret", 80000, 10, 4.4),
	-- Ultra: creature colossali, 10 volte piu' grandi degli altri pet
	pet("InfernoKomodo", "Ultra", 250000, 30, 22),
	pet("VenomWidow", "Ultra", 300000, 25, 24),
	pet("ThunderGriffin", "Ultra", 350000, 20, 38),
	pet("TitanRex", "Ultra", 400000, 15, 40),
	pet("PentaDragon", "Ultra", 500000, 10, 42),
}

Pets.ById = {} :: { [string]: Pet }
Pets.ByRarity = {} :: { [string]: { Pet } }
for _, p in Pets.List do
	Pets.ById[p.id] = p
	Pets.ByRarity[p.rarity] = Pets.ByRarity[p.rarity] or {}
	table.insert(Pets.ByRarity[p.rarity], p)
end

function Pets.Get(id: string): Pet
	local p = Pets.ById[id]
	assert(p, `Pet sconosciuto: {id}`)
	return p
end

return Pets
