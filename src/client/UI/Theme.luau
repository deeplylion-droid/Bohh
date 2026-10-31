--!strict
-- Palette, font e misure dell'interfaccia (stile "Vetta Pop").

local Theme = {}

-- Stile "Vetta Pop": superfici lisce dai colori accesi con un leggero gradiente, schede bianche,
-- pulsanti a pillola con il bordo 3D dello stesso colore piu' scuro, contorni sottili e ombre nette
-- color inchiostro blu notte; testi in Nunito (Heavy per titoli e numeri, Bold per i testi).

-- Inchiostro blu notte: testi sulle schede bianche, contorni dei testi, ombre
Theme.Ink = Color3.fromRGB(30, 22, 74)
Theme.InkSoft = Color3.fromRGB(104, 100, 146) -- testo secondario sulle schede bianche
Theme.Outline = Theme.Ink
Theme.Text = Color3.fromRGB(255, 255, 255)
Theme.Muted = Color3.fromRGB(236, 242, 255) -- testo secondario sulle superfici colorate
Theme.Gold = Color3.fromRGB(255, 212, 40)
Theme.GoldInk = Color3.fromRGB(240, 134, 0) -- importi sulle schede bianche
Theme.Green = Color3.fromRGB(120, 246, 112)
Theme.GreenInk = Color3.fromRGB(8, 176, 74)
Theme.Red = Color3.fromRGB(255, 96, 106)
Theme.RedInk = Color3.fromRGB(236, 26, 70)
Theme.Card = Color3.fromRGB(255, 255, 255) -- interni bianchi
Theme.CardShade = Color3.fromRGB(243, 245, 252) -- fondo del gradiente delle schede bianche
Theme.CardLight = Color3.fromRGB(232, 235, 245) -- interni gia' usati / riscattati (grigio chiaro)
Theme.Track = Color3.fromRGB(226, 230, 243) -- binario delle barre di avanzamento
Theme.ShadowTransparency = 0.62 -- ombre nette color inchiostro sotto pannelli e riquadri

-- Font: famiglia Nunito di Roblox (pesi disponibili: ExtraLight, Light, Regular, SemiBold, Bold,
-- ExtraBold e Black, che in Enum.FontWeight si chiama Heavy)
Theme.Family = "rbxasset://fonts/families/Nunito.json"
Theme.TitleFont = Font.new(Theme.Family, Enum.FontWeight.Heavy) -- titoli, numeri, pulsanti
Theme.HeadFont = Font.new(Theme.Family, Enum.FontWeight.ExtraBold) -- etichette e sottotitoli
Theme.BodyFont = Font.new(Theme.Family, Enum.FontWeight.Bold) -- testi
Theme.SoftFont = Font.new(Theme.Family, Enum.FontWeight.SemiBold) -- testi lunghi e secondari

Theme.Stroke = 3
Theme.TextStroke = 2
Theme.Corner = UDim.new(0, 16)
Theme.Pill = UDim.new(1, 0)
Theme.Lip = 5 -- spessore del bordo 3D dei pulsanti (px)

-- Colori: base (1), bordo 3D e contorno (2), parte alta del gradiente (3)
Theme.Buttons = {
	Green = { Color3.fromRGB(28, 212, 86), Color3.fromRGB(10, 148, 64), Color3.fromRGB(120, 248, 118) },
	Blue = { Color3.fromRGB(34, 118, 255), Color3.fromRGB(22, 72, 212), Color3.fromRGB(96, 186, 255) },
	Purple = { Color3.fromRGB(150, 66, 255), Color3.fromRGB(100, 32, 212), Color3.fromRGB(204, 138, 255) },
	Pink = { Color3.fromRGB(255, 52, 164), Color3.fromRGB(204, 20, 126), Color3.fromRGB(255, 130, 212) },
	Orange = { Color3.fromRGB(255, 128, 0), Color3.fromRGB(214, 84, 0), Color3.fromRGB(255, 186, 56) },
	Red = { Color3.fromRGB(255, 42, 76), Color3.fromRGB(202, 14, 52), Color3.fromRGB(255, 118, 126) },
	Yellow = { Color3.fromRGB(255, 190, 0), Color3.fromRGB(216, 128, 0), Color3.fromRGB(255, 232, 80) },
	Grey = { Color3.fromRGB(150, 160, 190), Color3.fromRGB(106, 114, 146), Color3.fromRGB(200, 208, 228) },
	Dark = { Color3.fromRGB(84, 64, 178), Color3.fromRGB(52, 36, 126), Color3.fromRGB(128, 106, 226) },
	Cyan = { Color3.fromRGB(0, 204, 198), Color3.fromRGB(0, 138, 146), Color3.fromRGB(80, 242, 222) },
	White = { Color3.fromRGB(255, 255, 255), Color3.fromRGB(204, 210, 230), Color3.fromRGB(255, 255, 255) },
}
-- colori chiari: il testo diventa inchiostro (senza contorno)
Theme.LightButtons = { White = true }

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
