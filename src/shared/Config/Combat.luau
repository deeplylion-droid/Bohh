--!strict
-- Mazze (schiaffi) e trappole del lotto.

export type Bat = {
	id: string,
	order: number,
	price: number, -- monete (0 = iniziale)
	vipOnly: boolean?,
	range: number,
	knockback: number,
	cooldown: number,
	color: Color3,
}

export type Trap = {
	id: string,
	order: number,
	price: number,
	effect: "Slip" | "Root" | "Slow",
	duration: number,
	color: Color3,
}

local Combat = {}

Combat.BatOrder = { "RubberMallet", "Baguette", "FrozenFish", "CandyCane", "GiantSpoon", "GoldenMallet" }
Combat.Bats = {
	RubberMallet = {
		id = "RubberMallet",
		order = 1,
		price = 0,
		range = 8,
		knockback = 55,
		cooldown = 1.25,
		color = Color3.fromRGB(255, 90, 90),
	},
	Baguette = {
		id = "Baguette",
		order = 2,
		price = 5000,
		range = 9,
		knockback = 65,
		cooldown = 1.15,
		color = Color3.fromRGB(230, 170, 90),
	},
	FrozenFish = {
		id = "FrozenFish",
		order = 3,
		price = 75000,
		range = 9.5,
		knockback = 75,
		cooldown = 1.05,
		color = Color3.fromRGB(120, 200, 255),
	},
	CandyCane = {
		id = "CandyCane",
		order = 4,
		price = 1500000,
		range = 10.5,
		knockback = 85,
		cooldown = 0.95,
		color = Color3.fromRGB(255, 70, 90),
	},
	GiantSpoon = {
		id = "GiantSpoon",
		order = 5,
		price = 40000000,
		range = 11.5,
		knockback = 100,
		cooldown = 0.85,
		color = Color3.fromRGB(210, 220, 235),
	},
	GoldenMallet = {
		id = "GoldenMallet",
		order = 6,
		price = 0,
		vipOnly = true,
		range = 10,
		knockback = 80,
		cooldown = 1.0,
		color = Color3.fromRGB(255, 200, 40),
	},
} :: { [string]: Bat }

Combat.TrapOrder = { "BananaPeel", "SlimePuddle", "BearTrap" }
Combat.Traps = {
	BananaPeel = {
		id = "BananaPeel",
		order = 1,
		price = 1500,
		effect = "Slip",
		duration = 2.2,
		color = Color3.fromRGB(255, 225, 60),
	},
	SlimePuddle = {
		id = "SlimePuddle",
		order = 2,
		price = 9000,
		effect = "Slow",
		duration = 5,
		color = Color3.fromRGB(120, 230, 90),
	},
	BearTrap = {
		id = "BearTrap",
		order = 3,
		price = 60000,
		effect = "Root",
		duration = 3,
		color = Color3.fromRGB(150, 156, 170),
	},
} :: { [string]: Trap }

Combat.TrapSlots = 3

return Combat
