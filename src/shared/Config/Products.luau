--!strict
-- Game pass e prodotti sviluppatore. Gli id vanno creati su Creator Hub (o via API) e inseriti qui.
-- Con id = 0 l'acquisto e' nascosto nel negozio.

export type Pass = { key: string, id: number, price: number, icon: string }
export type Product = { key: string, id: number, price: number, icon: string }

local Products = {}

Products.PassOrder =
	{ "VIP", "DoubleCoins", "ExtraIncubator", "BigBackpack", "FastHatch", "SuperBarrier", "Throne2", "Throne3" }
Products.Passes = {
	VIP = { key = "VIP", id = 2022170349, price = 249, icon = "VIP" },
	DoubleCoins = { key = "DoubleCoins", id = 2021672356, price = 399, icon = "DoubleCoins" },
	ExtraIncubator = { key = "ExtraIncubator", id = 2021672357, price = 149, icon = "Incubator" },
	BigBackpack = { key = "BigBackpack", id = 2022788361, price = 199, icon = "Backpack" },
	FastHatch = { key = "FastHatch", id = 2021684355, price = 299, icon = "HatchSpeed" },
	SuperBarrier = { key = "SuperBarrier", id = 2022500356, price = 149, icon = "Barrier" },
	-- troni dei giganti 2 e 3 (si sbloccano anche con tantissime monete: Config.Game.ThroneUnlock)
	Throne2 = { key = "Throne2", id = 0, price = 399, icon = "Throne" },
	Throne3 = { key = "Throne3", id = 0, price = 799, icon = "Throne" },
} :: { [string]: Pass }

Products.ProductOrder = {
	"GalacticLion",
	"GalacticKraken",
	"GalacticWhale",
	"SkipHatchSmall",
	"SkipHatchMedium",
	"SkipHatchLarge",
	"Luck15",
	"CoinsSmall",
	"CoinsMedium",
	"CoinsLarge",
	"WheelSpin1",
	"WheelSpins5",
}
Products.Products = {
	-- salta l'attesa di un'incubatrice: piccolo fino a Raro, medio fino a Leggendario, grande per tutto
	SkipHatchSmall = { key = "SkipHatchSmall", id = 3717390839, price = 19, icon = "SkipHatch" },
	SkipHatchMedium = { key = "SkipHatchMedium", id = 3717390921, price = 49, icon = "SkipHatch" },
	SkipHatchLarge = { key = "SkipHatchLarge", id = 3717390923, price = 99, icon = "SkipHatch" },
	Luck15 = { key = "Luck15", id = 3717390926, price = 99, icon = "Luck" },
	CoinsSmall = { key = "CoinsSmall", id = 3717390930, price = 49, icon = "CoinsSmall" },
	CoinsMedium = { key = "CoinsMedium", id = 3717390935, price = 149, icon = "CoinsMedium" },
	CoinsLarge = { key = "CoinsLarge", id = 3717390941, price = 399, icon = "CoinsLarge" },
	WheelSpin1 = { key = "WheelSpin1", id = 3718229338, price = 29, icon = "Wheel" },
	WheelSpins5 = { key = "WheelSpins5", id = 3718229344, price = 119, icon = "Wheel" },
	-- giganti galattici (vanno subito sul trono)
	GalacticLion = { key = "GalacticLion", id = 0, price = 399, icon = "NebulaLion" },
	GalacticKraken = { key = "GalacticKraken", id = 0, price = 599, icon = "StarKraken" },
	GalacticWhale = { key = "GalacticWhale", id = 0, price = 799, icon = "CosmicWhale" },
} :: { [string]: Product }

-- Pet galattici: prodotto -> pet
Products.Galactic = {
	GalacticLion = "NebulaLion",
	GalacticKraken = "StarKraken",
	GalacticWhale = "CosmicWhale",
}
Products.GalacticOrder = { "GalacticLion", "GalacticKraken", "GalacticWhale" }

-- Giri della ruota della fortuna
Products.WheelSpins = {
	WheelSpin1 = 1,
	WheelSpins5 = 5,
}

-- Rarita' massima coperta da ciascun "salta schiusa"
Products.SkipHatchTier = {
	SkipHatchSmall = "Rare",
	SkipHatchMedium = "Legendary",
	SkipHatchLarge = "Ultra",
}

-- Pacchetti monete: minuti di guadagno attuale, con un minimo garantito
Products.CoinPacks = {
	CoinsSmall = { minutes = 15, min = 1500 },
	CoinsMedium = { minutes = 60, min = 7500 },
	CoinsLarge = { minutes = 240, min = 40000 },
}

Products.LuckMinutes = 15
Products.PrivateServerPrice = 50

function Products.PassById(id: number): Pass?
	for _, p in Products.Passes do
		if p.id == id and id ~= 0 then
			return p
		end
	end
	return nil
end

function Products.ProductById(id: number): Product?
	for _, p in Products.Products do
		if p.id == id and id ~= 0 then
			return p
		end
	end
	return nil
end

return Products
