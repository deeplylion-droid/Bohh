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
Theme.GoldInk = Color3.fromRGB(242, 140, 0) -- importi sugli interni chiari
Theme.Green = Color3.fromRGB(96, 236, 120)
Theme.GreenInk = Color3.fromRGB(8, 184, 72)
Theme.Red = Color3.fromRGB(255, 92, 92)
Theme.RedInk = Color3.fromRGB(242, 22, 60)
Theme.Muted = Color3.fromRGB(226, 244, 255) -- testo secondario sul feltro colorato
Theme.PanelTop = Color3.fromRGB(0, 220, 198)
Theme.PanelBottom = Color3.fromRGB(0, 220, 198)
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
	Green = { Color3.fromRGB(22, 232, 96), Color3.fromRGB(12, 166, 64) },
	Blue = { Color3.fromRGB(36, 122, 255), Color3.fromRGB(20, 80, 214) },
	Purple = { Color3.fromRGB(176, 78, 255), Color3.fromRGB(124, 38, 218) },
	Pink = { Color3.fromRGB(255, 62, 178), Color3.fromRGB(216, 26, 134) },
	Orange = { Color3.fromRGB(255, 142, 0), Color3.fromRGB(220, 100, 0) },
	Red = { Color3.fromRGB(255, 34, 70), Color3.fromRGB(210, 12, 44) },
	Yellow = { Color3.fromRGB(255, 204, 0), Color3.fromRGB(226, 152, 0) },
	Grey = { Color3.fromRGB(154, 163, 184), Color3.fromRGB(108, 116, 138) },
	Dark = { Color3.fromRGB(100, 70, 156), Color3.fromRGB(64, 40, 108) },
	Cyan = { Color3.fromRGB(0, 220, 198), Color3.fromRGB(0, 158, 142) },
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
