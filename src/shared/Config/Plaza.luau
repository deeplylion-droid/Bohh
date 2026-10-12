--!strict
-- Piazza della vetta: ruota della fortuna, missioni giornaliere e settimanali, re della collina.

export type Reward = {
	kind: string, -- "Coins" | "Luck" | "Egg" | "Primal" | "Spin"
	minutes: number?, -- monete: minuti del guadagno attuale del giocatore...
	min: number?, -- ...con questo minimo
	amount: number?, -- minuti di fortuna, numero di giri
	tier: number?, -- uova: 1 = buona, 2 = ottima per la zona piu' profonda raggiunta
}

export type Segment = {
	kind: string,
	minutes: number?,
	min: number?,
	amount: number?,
	tier: number?,
	weight: number, -- probabilita' relativa
	color: Color3, -- colore dello spicchio nell'immagine
}

export type Quest = {
	id: string,
	stat: string, -- contatore che la fa avanzare (QuestService.Add)
	target: number,
	icon: string,
	reward: Reward,
}

local Plaza = {}

---------------------------------------------------------------------------------------------
-- Ruota della fortuna: un giro gratis ogni FreeEvery secondi, altri giri con le missioni o con
-- i Robux. Gli spicchi vanno in senso orario a partire da quello in alto (sotto la freccia), con
-- gli stessi colori dell'immagine art/ui/wheel.py; le probabilita' dipendono solo dai pesi.
---------------------------------------------------------------------------------------------
Plaza.Wheel = {
	FreeEvery = 4 * 3600,
	SpinTime = 5.5, -- secondi dell'animazione (il premio arriva quando la ruota si ferma)
	Position = Vector2.new(46, 28), -- x, z nella piazza (la quota e' quella della piazza)
	FaceToward = Vector2.new(0, 46), -- guarda verso lo spawn e il centro della piazza
	Radius = 8,
	Segments = {
		{ kind = "Coins", minutes = 5, min = 500, weight = 24, color = Color3.fromRGB(255, 196, 40) },
		{ kind = "Egg", tier = 1, weight = 16, color = Color3.fromRGB(64, 150, 255) },
		{ kind = "Luck", amount = 10, weight = 14, color = Color3.fromRGB(84, 214, 72) },
		{ kind = "Coins", minutes = 20, min = 2000, weight = 12, color = Color3.fromRGB(255, 138, 28) },
		{ kind = "Egg", tier = 2, weight = 8, color = Color3.fromRGB(170, 90, 255) },
		{ kind = "Luck", amount = 30, weight = 8, color = Color3.fromRGB(20, 196, 186) },
		{ kind = "Coins", minutes = 60, min = 8000, weight = 6, color = Color3.fromRGB(255, 80, 160) },
		-- jackpot: uovo Primordiale della zona piu' profonda raggiunta e mezz'ora di fortuna
		{ kind = "Primal", amount = 30, weight = 3, color = Color3.fromRGB(230, 36, 48) },
	} :: { Segment },
}

-- Uova dei premi (ruota e missioni) secondo la zona piu' profonda da cui si e' consegnato un uovo:
-- tier 1 = buona, tier 2 = ottima
Plaza.EggTiers = {
	Meadow = { "Uncommon", "Rare" },
	Forest = { "Rare", "Epic" },
	Canyon = { "Epic", "Legendary" },
	Crystal = { "Legendary", "Mythic" },
	Crater = { "Mythic", "Divine" },
} :: { [string]: { string } }

---------------------------------------------------------------------------------------------
-- Missioni: ogni giorno (mezzanotte UTC) 3 giornaliere, ogni lunedi' 3 settimanali, estratte a
-- caso dagli elenchi. Completarle tutte da' un premio in piu'.
---------------------------------------------------------------------------------------------
Plaza.Quests = {
	DailyCount = 3,
	WeeklyCount = 3,
	Daily = {
		{
			id = "Deliver",
			stat = "Deliver",
			target = 12,
			icon = "Egg",
			reward = { kind = "Coins", minutes = 8, min = 800 },
		},
		{ id = "Hatch", stat = "Hatch", target = 8, icon = "Incubator", reward = { kind = "Egg", tier = 1 } },
		{
			id = "Steal",
			stat = "Steal",
			target = 2,
			icon = "Thief",
			reward = { kind = "Coins", minutes = 10, min = 1000 },
		},
		{ id = "Slap", stat = "Slap", target = 10, icon = "Slap", reward = { kind = "Luck", amount = 10 } },
		{
			id = "Collect",
			stat = "Collect",
			target = 15,
			icon = "Coin",
			reward = { kind = "Coins", minutes = 6, min = 600 },
		},
		{
			id = "King",
			stat = "King",
			target = 45,
			icon = "King",
			reward = { kind = "Coins", minutes = 10, min = 1000 },
		},
		{ id = "Wheel", stat = "Wheel", target = 1, icon = "Wheel", reward = { kind = "Luck", amount = 10 } },
		{
			id = "PickupPrimal",
			stat = "PickupPrimal",
			target = 1,
			icon = "Egg",
			reward = { kind = "Coins", minutes = 8, min = 800 },
		},
	} :: { Quest },
	Weekly = {
		{
			id = "DeliverW",
			stat = "Deliver",
			target = 120,
			icon = "Egg",
			reward = { kind = "Coins", minutes = 45, min = 10000 },
		},
		{ id = "HatchW", stat = "Hatch", target = 60, icon = "Incubator", reward = { kind = "Egg", tier = 2 } },
		{
			id = "StealW",
			stat = "Steal",
			target = 12,
			icon = "Thief",
			reward = { kind = "Coins", minutes = 45, min = 10000 },
		},
		{ id = "SlapW", stat = "Slap", target = 80, icon = "Slap", reward = { kind = "Luck", amount = 30 } },
		{ id = "HatchPrimalW", stat = "HatchPrimal", target = 3, icon = "Egg", reward = { kind = "Egg", tier = 2 } },
		{
			id = "KingW",
			stat = "King",
			target = 300,
			icon = "King",
			reward = { kind = "Coins", minutes = 60, min = 12000 },
		},
		{
			id = "DeliverDeepW",
			stat = "DeliverDeep",
			target = 25,
			icon = "Backpack",
			reward = { kind = "Spin", amount = 2 },
		},
	} :: { Quest },
	DailyBonus = { kind = "Spin", amount = 1 } :: Reward,
	WeeklyBonus = { kind = "Primal", amount = 30 } :: Reward,
	-- le uova consegnate da questa zona in giu' contano per DeliverDeep
	DeepFrom = "Canyon",
}

---------------------------------------------------------------------------------------------
-- Re della collina: chi resta da solo in cima al monumento guadagna monete extra al secondo
-- (una quota del proprio guadagno, con un minimo). In due o piu' la cima e' contesa.
---------------------------------------------------------------------------------------------
Plaza.King = {
	Radius = 14.5, -- raggio della cima del monumento
	Height = 5.2, -- di quanto la cima e' piu' alta della piazza
	IncomeShare = 0.5,
	MinPerSecond = 25,
	IdleAfter = 60, -- secondi da fermo dopo cui il re non guadagna piu'
	AnnounceGap = 45, -- secondi minimi fra due annunci del nuovo re
	Steps = 5,
	StairAngles = { 45, 135, 225, 315 },
}

return Plaza
