--!strict
-- Eventi del server (automatici a intervalli casuali o lanciati dal pannello admin).

export type EventDef = {
	id: string,
	duration: number,
	color: Color3,
	icon: string,
	music: string?,
}

local Events = {}

Events.Order = { "MeteorShower", "GoldenHour", "SuperAvalanche" }

Events.List = {
	-- Pioggia di meteore: i meteoriti cadono nelle zone basse e lasciano uova rare con piu' chance di Cosmico
	MeteorShower = {
		id = "MeteorShower",
		duration = 180,
		color = Color3.fromRGB(150, 100, 255),
		icon = "Meteor",
		music = "Event",
	},
	-- Ora d'oro: alla schiusa la mutazione Oro esce almeno il 25% delle volte
	GoldenHour = {
		id = "GoldenHour",
		duration = 240,
		color = Color3.fromRGB(255, 196, 30),
		icon = "GoldenHour",
		music = "Event",
	},
	-- Super valanga: valanghe ogni 55 s, ma le uova rare compaiono molto piu' spesso
	SuperAvalanche = {
		id = "SuperAvalanche",
		duration = 180,
		color = Color3.fromRGB(120, 200, 255),
		icon = "Avalanche",
		music = "Danger",
	},
} :: { [string]: EventDef }

Events.Meteor = {
	interval = { 10, 16 },
	zones = { "Canyon", "Crystal", "Crater" },
	eggs = { Epic = 45, Legendary = 32, Mythic = 16, Divine = 6, Secret = 1 },
	cosmicMin = 0.1, -- probabilita' minima di mutazione Cosmica per le uova dei meteoriti
	blastRadius = 14,
}

Events.GoldenHourGoldMin = 0.25
Events.SuperAvalancheInterval = 55
Events.SuperAvalancheRareBoost = 3 -- moltiplicatore dei pesi delle due rarita' piu' alte di ogni zona

function Events.Get(id: string): EventDef
	local e = Events.List[id]
	assert(e, `Evento sconosciuto: {id}`)
	return e
end

return Events
