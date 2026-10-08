--!strict
-- Livelli di rarita' (dal piu' comune al piu' raro).
-- weight  = moltiplicatore di velocita' mentre si trasporta un uovo/pet di questa rarita'
-- hatch   = secondi di incubazione
-- sell    = il pet si vende per (guadagno al secondo x sell)

export type Rarity = {
	id: string,
	order: number,
	color: Color3,
	colorDark: Color3,
	weight: number,
	hatch: number,
	sell: number,
	announce: boolean, -- annuncia a tutto il server quando compare un uovo di questa rarita'
}

local Rarities = {}

Rarities.Order = { "Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic", "Divine", "Secret" }

Rarities.List = {
	Common = {
		id = "Common",
		order = 1,
		color = Color3.fromRGB(196, 206, 216),
		colorDark = Color3.fromRGB(110, 122, 138),
		weight = 0.92,
		hatch = 20,
		sell = 120,
		announce = false,
	},
	Uncommon = {
		id = "Uncommon",
		order = 2,
		color = Color3.fromRGB(96, 232, 96),
		colorDark = Color3.fromRGB(32, 150, 52),
		weight = 0.88,
		hatch = 45,
		sell = 120,
		announce = false,
	},
	Rare = {
		id = "Rare",
		order = 3,
		color = Color3.fromRGB(70, 176, 255),
		colorDark = Color3.fromRGB(24, 100, 214),
		weight = 0.84,
		hatch = 90,
		sell = 120,
		announce = false,
	},
	Epic = {
		id = "Epic",
		order = 4,
		color = Color3.fromRGB(184, 104, 255),
		colorDark = Color3.fromRGB(116, 44, 214),
		weight = 0.8,
		hatch = 180,
		sell = 120,
		announce = false,
	},
	Legendary = {
		id = "Legendary",
		order = 5,
		color = Color3.fromRGB(255, 196, 26),
		colorDark = Color3.fromRGB(214, 120, 0),
		weight = 0.74,
		hatch = 360,
		sell = 120,
		announce = true,
	},
	Mythic = {
		id = "Mythic",
		order = 6,
		color = Color3.fromRGB(255, 64, 64),
		colorDark = Color3.fromRGB(176, 18, 36),
		weight = 0.68,
		hatch = 720,
		sell = 120,
		announce = true,
	},
	Divine = {
		id = "Divine",
		order = 7,
		color = Color3.fromRGB(255, 120, 230),
		colorDark = Color3.fromRGB(150, 70, 255),
		weight = 0.62,
		hatch = 1200,
		sell = 120,
		announce = true,
	},
	Secret = {
		id = "Secret",
		order = 8,
		color = Color3.fromRGB(70, 255, 230),
		colorDark = Color3.fromRGB(28, 16, 48),
		weight = 0.56,
		hatch = 1800,
		sell = 120,
		announce = true,
	},
} :: { [string]: Rarity }

-- Divine e Secret usano un gradiente animato nell'interfaccia
Rarities.Gradients = {
	Divine = ColorSequence.new({
		ColorSequenceKeypoint.new(0, Color3.fromRGB(255, 90, 90)),
		ColorSequenceKeypoint.new(0.2, Color3.fromRGB(255, 200, 60)),
		ColorSequenceKeypoint.new(0.4, Color3.fromRGB(110, 240, 110)),
		ColorSequenceKeypoint.new(0.6, Color3.fromRGB(80, 200, 255)),
		ColorSequenceKeypoint.new(0.8, Color3.fromRGB(170, 110, 255)),
		ColorSequenceKeypoint.new(1, Color3.fromRGB(255, 90, 200)),
	}),
	Secret = ColorSequence.new({
		ColorSequenceKeypoint.new(0, Color3.fromRGB(40, 255, 220)),
		ColorSequenceKeypoint.new(0.5, Color3.fromRGB(160, 60, 255)),
		ColorSequenceKeypoint.new(1, Color3.fromRGB(40, 255, 220)),
	}),
}

function Rarities.Get(id: string): Rarity
	local r = Rarities.List[id]
	assert(r, `Rarita' sconosciuta: {id}`)
	return r
end

function Rarities.Compare(a: string, b: string): number
	return Rarities.Get(a).order - Rarities.Get(b).order
end

return Rarities
