--!strict
-- Premi: giornalieri (serie di 7 giorni), regali a tempo di gioco, album.

export type Reward = {
	kind: "Coins" | "Luck" | "Egg",
	amount: number, -- monete, minuti di fortuna o numero di uova
	rarity: string?, -- per le uova
}

local Rewards = {}

Rewards.Daily = {
	{ kind = "Coins", amount = 250 },
	{ kind = "Luck", amount = 10 },
	{ kind = "Coins", amount = 1500 },
	{ kind = "Egg", amount = 1, rarity = "Rare" },
	{ kind = "Coins", amount = 8000 },
	{ kind = "Luck", amount = 30 },
	{ kind = "Egg", amount = 1, rarity = "Legendary" },
} :: { Reward }

-- minuti di gioco nella sessione -> premio
Rewards.Playtime = {
	{ minutes = 5, reward = { kind = "Coins", amount = 300 } },
	{ minutes = 10, reward = { kind = "Egg", amount = 1, rarity = "Uncommon" } },
	{ minutes = 20, reward = { kind = "Coins", amount = 2500 } },
	{ minutes = 30, reward = { kind = "Luck", amount = 10 } },
	{ minutes = 45, reward = { kind = "Egg", amount = 1, rarity = "Epic" } },
	{ minutes = 60, reward = { kind = "Coins", amount = 20000 } },
	{ minutes = 90, reward = { kind = "Egg", amount = 1, rarity = "Legendary" } },
} :: { { minutes: number, reward: Reward } }

-- Premio in monete al completamento di una riga dell'album (oltre al bonus permanente)
Rewards.IndexRow = {
	Common = 500,
	Uncommon = 3000,
	Rare = 20000,
	Epic = 150000,
	Legendary = 1000000,
	Mythic = 8000000,
	Divine = 60000000,
	Secret = 500000000,
	Ultra = 5000000000,
}

-- Monete premio per i coin pack si calcolano in Products; le monete dei premi giornalieri crescono
-- con il guadagno del giocatore (minimo il valore indicato)
Rewards.CoinScaleMinutes = 3

return Rewards
