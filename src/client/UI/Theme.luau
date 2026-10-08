--!strict
-- Palette, font e misure dell'interfaccia (stile "cartone gommoso" con contorni scuri spessi).

local Theme = {}

Theme.Outline = Color3.fromRGB(29, 22, 48)
Theme.Text = Color3.fromRGB(255, 255, 255)
Theme.Gold = Color3.fromRGB(255, 225, 77)
Theme.Green = Color3.fromRGB(157, 255, 107)
Theme.Red = Color3.fromRGB(255, 110, 100)
Theme.Muted = Color3.fromRGB(201, 189, 245)
Theme.PanelTop = Color3.fromRGB(64, 47, 116)
Theme.PanelBottom = Color3.fromRGB(35, 24, 74)
Theme.Card = Color3.fromRGB(48, 36, 94)
Theme.CardLight = Color3.fromRGB(72, 56, 130)

Theme.TitleFont = Enum.Font.LuckiestGuy
Theme.BodyFont = Enum.Font.FredokaOne

Theme.Stroke = 4
Theme.TextStroke = 3
Theme.Corner = UDim.new(0, 20)

-- Coppie di colori (alto, basso) per i gradienti dei pulsanti
Theme.Buttons = {
	Green = { Color3.fromRGB(141, 255, 98), Color3.fromRGB(34, 194, 59) },
	Blue = { Color3.fromRGB(105, 216, 255), Color3.fromRGB(27, 125, 255) },
	Purple = { Color3.fromRGB(211, 155, 255), Color3.fromRGB(138, 61, 255) },
	Pink = { Color3.fromRGB(255, 158, 224), Color3.fromRGB(255, 60, 158) },
	Orange = { Color3.fromRGB(255, 200, 90), Color3.fromRGB(255, 128, 20) },
	Red = { Color3.fromRGB(255, 120, 110), Color3.fromRGB(216, 27, 43) },
	Yellow = { Color3.fromRGB(255, 236, 120), Color3.fromRGB(255, 175, 23) },
	Grey = { Color3.fromRGB(196, 196, 214), Color3.fromRGB(120, 120, 150) },
	Dark = { Color3.fromRGB(74, 56, 130), Color3.fromRGB(40, 28, 82) },
	Cyan = { Color3.fromRGB(120, 255, 236), Color3.fromRGB(20, 180, 200) },
}

-- Icone di riserva (emoji) quando l'immagine dedicata non e' ancora disponibile
Theme.Emoji = {
	Shop = "🛒",
	Upgrades = "⏫",
	Index = "📖",
	Gifts = "🎁",
	Settings = "⚙️",
	Codes = "🎟️",
	Coin = "🪙",
	Speed = "⚡",
	Strength = "💪",
	Backpack = "🎒",
	Incubator = "🪺",
	HatchSpeed = "⏱️",
	Pedestal = "🏛️",
	Barrier = "🛡️",
	VIP = "👑",
	DoubleCoins = "💰",
	SkipHatch = "⏩",
	Luck = "🍀",
	CoinsSmall = "💵",
	CoinsMedium = "💰",
	CoinsLarge = "🏔️",
	Egg = "🥚",
	Lock = "🔒",
	Trap = "🪤",
	Bat = "🔨",
	Slap = "🖐️",
	Meteor = "☄️",
	GoldenHour = "🌟",
	Avalanche = "🏔️",
	Friends = "👥",
	Admin = "🛠️",
	Close = "✖",
	Check = "✔",
	Star = "⭐",
	Thief = "🦹",
	Music = "🎵",
	Sound = "🔊",
	Graphics = "🖥️",
	Language = "🌍",
	Group = "👥",
	Alarm = "🚨",
}

return Theme
