--!strict
-- Le 5 zone della montagna, dalla vetta verso valle. Piu' si scende, piu' le uova sono rare.
-- eggs     = pesi delle rarita' delle uova che compaiono nei nidi della zona
-- respawn  = secondi prima che un nido vuoto produca un nuovo uovo
-- announceFrom = da questa rarita' in su la comparsa viene annunciata a tutto il server

export type Zone = {
	id: string,
	order: number,
	eggs: { [string]: number },
	respawn: number,
	announceFrom: string,
	color: Color3, -- colore della zona nell'interfaccia
	fogColor: Color3,
	music: string, -- chiave in Config.Audio.Music
}

local Zones = {}

Zones.Order = { "Meadow", "Forest", "Canyon", "Crystal", "Crater" }

Zones.List = {
	Meadow = {
		id = "Meadow",
		order = 1,
		eggs = { Common = 72, Uncommon = 25, Rare = 3 },
		respawn = 8,
		announceFrom = "Rare",
		color = Color3.fromRGB(110, 214, 80),
		fogColor = Color3.fromRGB(196, 228, 255),
		music = "Meadow",
	},
	Forest = {
		id = "Forest",
		order = 2,
		eggs = { Common = 30, Uncommon = 50, Rare = 18, Epic = 2 },
		respawn = 12,
		announceFrom = "Epic",
		color = Color3.fromRGB(48, 170, 96),
		fogColor = Color3.fromRGB(176, 220, 200),
		music = "Forest",
	},
	Canyon = {
		id = "Canyon",
		order = 3,
		eggs = { Uncommon = 25, Rare = 50, Epic = 22, Legendary = 3 },
		respawn = 18,
		announceFrom = "Legendary",
		color = Color3.fromRGB(232, 140, 70),
		fogColor = Color3.fromRGB(255, 214, 176),
		music = "Canyon",
	},
	Crystal = {
		id = "Crystal",
		order = 4,
		eggs = { Rare = 25, Epic = 50, Legendary = 22, Mythic = 3 },
		respawn = 25,
		announceFrom = "Mythic",
		color = Color3.fromRGB(120, 190, 255),
		fogColor = Color3.fromRGB(170, 160, 255),
		music = "Crystal",
	},
	Crater = {
		id = "Crater",
		order = 5,
		eggs = { Epic = 30, Legendary = 50, Mythic = 17, Divine = 3 },
		respawn = 35,
		announceFrom = "Mythic",
		color = Color3.fromRGB(255, 92, 40),
		fogColor = Color3.fromRGB(255, 150, 110),
		music = "Crater",
	},
} :: { [string]: Zone }

-- Uovo Segreto: compare raramente nel Cratere (oltre che con gli eventi)
Zones.SecretSpawn = {
	zone = "Crater",
	minInterval = 20 * 60,
	maxInterval = 32 * 60,
}

-- uovo Ultra: ancora piu' raro, annunciato a tutti e visibile da lontano (colonna di luce)
Zones.UltraSpawn = {
	zone = "Crater",
	minInterval = 30 * 60,
	maxInterval = 45 * 60,
}

function Zones.Get(id: string): Zone
	local z = Zones.List[id]
	assert(z, `Zona sconosciuta: {id}`)
	return z
end

return Zones
