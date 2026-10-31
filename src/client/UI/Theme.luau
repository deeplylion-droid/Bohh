--!strict
-- Palette, font e misure dell'interfaccia (stile "giocattolo di stoffa cucito").

local Theme = {}

-- Stile "cucito": feltro dai colori accesi con la cucitura bianca attaccata al contorno scuro,
-- interni bianchi, titoli in Denk One e testi in Patrick Hand (scritto a mano)
Theme.Outline = Color3.fromRGB(42, 22, 14)
Theme.Text = Color3.fromRGB(255, 255, 255)
Theme.Ink = Color3.fromRGB(58, 34, 22) -- testo scuro sugli interni chiari
Theme.InkSoft = Color3.fromRGB(122, 104, 90) -- testo secondario sugli interni chiari
Theme.Gold = Color3.fromRGB(255, 206, 48)
Theme.GoldInk = Color3.fromRGB(222, 128, 0) -- importi sugli interni chiari
Theme.Green = Color3.fromRGB(96, 236, 120)
Theme.GreenInk = Color3.fromRGB(18, 168, 70)
Theme.Red = Color3.fromRGB(255, 92, 92)
Theme.RedInk = Color3.fromRGB(226, 32, 62)
Theme.Muted = Color3.fromRGB(226, 244, 255) -- testo secondario sul feltro colorato
Theme.PanelTop = Color3.fromRGB(0, 194, 174)
Theme.PanelBottom = Color3.fromRGB(0, 194, 174)
Theme.Card = Color3.fromRGB(255, 255, 255) -- interni bianchi
Theme.CardLight = Color3.fromRGB(234, 234, 238) -- interni gia' usati / riscattati (grigio chiaro)
Theme.Stitch = Color3.fromRGB(255, 255, 255)
Theme.StitchCard = Color3.fromRGB(212, 212, 218)

Theme.TitleFont = Enum.Font.DenkOne
Theme.BodyFont = Enum.Font.PatrickHand

Theme.Stroke = 4
Theme.TextStroke = 3
Theme.Corner = UDim.new(0, 16)

-- Colori del feltro (primo) e versione scura (secondo, per ombre e stati premuti)
Theme.Buttons = {
	Green = { Color3.fromRGB(33, 212, 91), Color3.fromRGB(18, 150, 62) },
	Blue = { Color3.fromRGB(45, 107, 255), Color3.fromRGB(26, 70, 190) },
	Purple = { Color3.fromRGB(161, 72, 255), Color3.fromRGB(112, 40, 196) },
	Pink = { Color3.fromRGB(255, 79, 168), Color3.fromRGB(200, 40, 124) },
	Orange = { Color3.fromRGB(255, 138, 31), Color3.fromRGB(206, 96, 0) },
	Red = { Color3.fromRGB(255, 46, 77), Color3.fromRGB(196, 22, 50) },
	Yellow = { Color3.fromRGB(255, 184, 0), Color3.fromRGB(214, 140, 0) },
	Grey = { Color3.fromRGB(154, 163, 184), Color3.fromRGB(108, 116, 138) },
	Dark = { Color3.fromRGB(86, 66, 120), Color3.fromRGB(56, 40, 86) },
	Cyan = { Color3.fromRGB(0, 194, 174), Color3.fromRGB(0, 140, 126) },
	White = { Color3.fromRGB(255, 255, 255), Color3.fromRGB(212, 212, 218) },
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
	Wheel = "🎡",
	Quests = "📋",
	King = "👑",
}

return Theme
