--!strict
-- Game pass e prodotti sviluppatore. Gli id vanno creati su Creator Hub (o via API) e inseriti qui.
-- Con id = 0 l'acquisto e' nascosto nel negozio.

export type Pass = { key: string, id: number, price: number, icon: string }
export type Product = { key: string, id: number, price: number, icon: string }

local Products = {}

Products.PassOrder = { "VIP", "DoubleCoins", "ExtraIncubator", "BigBackpack", "FastHatch", "SuperBarrier" }
Products.Passes = {
	VIP = { key = "VIP", id = 2022170349, price = 249, icon = "VIP" },
	DoubleCoins = { key = "DoubleCoins", id = 2021672356, price = 399, icon = "DoubleCoins" },
	ExtraIncubator = { key = "ExtraIncubator", id = 2021672357, price = 149, icon = "Incubator" },
	BigBackpack = { key = "BigBackpack", id = 2022788361, price = 199, icon = "Backpack" },
	FastHatch = { key = "FastHatch", id = 2021684355, price = 299, icon = "HatchSpeed" },
	SuperBarrier = { key = "SuperBarrier", id = 2022500356, price = 149, icon = "Barrier" },
} :: { [string]: Pass }

Products.ProductOrder =
	{ "SkipHatchSmall", "SkipHatchMedium", "SkipHatchLarge", "Luck15", "CoinsSmall", "CoinsMedium", "CoinsLarge" }
Products.Products = {
	-- salta l'attesa di un'incubatrice: piccolo fino a Raro, medio fino a Leggendario, grande per tutto
	SkipHatchSmall = { key = "SkipHatchSmall", id = 3717390839, price = 19, icon = "SkipHatch" },
	SkipHatchMedium = { key = "SkipHatchMedium", id = 3717390921, price = 49, icon = "SkipHatch" },
	SkipHatchLarge = { key = "SkipHatchLarge", id = 3717390923, price = 99, icon = "SkipHatch" },
	Luck15 = { key = "Luck15", id = 3717390926, price = 99, icon = "Luck" },
	CoinsSmall = { key = "CoinsSmall", id = 3717390930, price = 49, icon = "CoinsSmall" },
	CoinsMedium = { key = "CoinsMedium", id = 3717390935, price = 149, icon = "CoinsMedium" },
	CoinsLarge = { key = "CoinsLarge", id = 3717390941, price = 399, icon = "CoinsLarge" },
} :: { [string]: Product }

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
