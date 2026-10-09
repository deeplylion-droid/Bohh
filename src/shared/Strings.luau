--!strict
-- Testi del gioco in inglese (base) e italiano. Segnaposto: {nome}.
-- La lingua si sceglie dalla lingua di Roblox del giocatore (oppure dalle impostazioni).

local Strings = {}

type Entry = { en: string, it: string }

local T: { [string]: Entry } = {
	-- generali
	GameTitle = { en = "CLIMB & STEAL EGGS", it = "CLIMB & STEAL EGGS" },
	TrailSign = { en = "DOWN TO THE EGGS!", it = "GIÙ VERSO LE UOVA!" },
	Loading = { en = "Loading the mountain...", it = "Caricamento della montagna..." },
	Play = { en = "PLAY", it = "GIOCA" },
	Close = { en = "CLOSE", it = "CHIUDI" },
	Buy = { en = "BUY", it = "COMPRA" },
	Owned = { en = "OWNED", it = "POSSEDUTO" },
	Equip = { en = "EQUIP", it = "EQUIPAGGIA" },
	Equipped = { en = "EQUIPPED", it = "EQUIPAGGIATO" },
	Max = { en = "MAX", it = "MAX" },
	Claim = { en = "CLAIM", it = "RISCATTA" },
	Claimed = { en = "CLAIMED", it = "RISCATTATO" },
	Locked = { en = "LOCKED", it = "BLOCCATO" },
	Level = { en = "Lv. {n}", it = "Liv. {n}" },
	NotEnoughCoins = { en = "Not enough coins!", it = "Monete insufficienti!" },
	PerSecond = { en = "/s", it = "/s" },

	-- menu
	MenuShop = { en = "SHOP", it = "NEGOZIO" },
	MenuUpgrades = { en = "UPGRADES", it = "POTENZIA" },
	MenuIndex = { en = "INDEX", it = "ALBUM" },
	MenuGifts = { en = "GIFTS", it = "REGALI" },
	MenuSettings = { en = "SETTINGS", it = "OPZIONI" },
	MenuCodes = { en = "CODES", it = "CODICI" },
	MenuDefense = { en = "DEFENSE", it = "DIFESA" },

	-- rarita'
	Rarity_Common = { en = "COMMON", it = "COMUNE" },
	Rarity_Uncommon = { en = "UNCOMMON", it = "NON COMUNE" },
	Rarity_Rare = { en = "RARE", it = "RARO" },
	Rarity_Epic = { en = "EPIC", it = "EPICO" },
	Rarity_Legendary = { en = "LEGENDARY", it = "LEGGENDARIO" },
	Rarity_Mythic = { en = "MYTHIC", it = "MITICO" },
	Rarity_Divine = { en = "DIVINE", it = "DIVINO" },
	Rarity_Secret = { en = "SECRET", it = "SEGRETO" },

	-- uova
	Egg_Common = { en = "Common Egg", it = "Uovo Comune" },
	Egg_Uncommon = { en = "Uncommon Egg", it = "Uovo Non Comune" },
	Egg_Rare = { en = "Rare Egg", it = "Uovo Raro" },
	Egg_Epic = { en = "Epic Egg", it = "Uovo Epico" },
	Egg_Legendary = { en = "Legendary Egg", it = "Uovo Leggendario" },
	Egg_Mythic = { en = "Mythic Egg", it = "Uovo Mitico" },
	Egg_Divine = { en = "Divine Egg", it = "Uovo Divino" },
	Egg_Secret = { en = "Secret Egg", it = "Uovo Segreto" },

	-- pet
	Pet_Chick = { en = "Chick", it = "Pulcino" },
	Pet_Bunny = { en = "Bunny", it = "Coniglietto" },
	Pet_Lamb = { en = "Lamb", it = "Agnellino" },
	Pet_Piglet = { en = "Piglet", it = "Maialino" },
	Pet_FoxKit = { en = "Fox Kit", it = "Volpacchiotto" },
	Pet_Owlet = { en = "Owlet", it = "Gufetto" },
	Pet_Hedgehog = { en = "Hedgehog", it = "Riccio" },
	Pet_Fawn = { en = "Fawn", it = "Cerbiatto" },
	Pet_Marmot = { en = "Marmot", it = "Marmotta" },
	Pet_Ibex = { en = "Ibex", it = "Stambecco" },
	Pet_RedPanda = { en = "Red Panda", it = "Panda Rosso" },
	Pet_SnowLeopard = { en = "Snow Leopard", it = "Leopardo delle Nevi" },
	Pet_CrystalTurtle = { en = "Crystal Turtle", it = "Tartaruga di Cristallo" },
	Pet_GlowAxolotl = { en = "Glow Axolotl", it = "Axolotl Lucente" },
	Pet_BabyGriffin = { en = "Baby Griffin", it = "Grifoncino" },
	Pet_FrostFox = { en = "Frost Fox", it = "Volpe di Ghiaccio" },
	Pet_LavaDragon = { en = "Lava Dragon", it = "Drago di Lava" },
	Pet_Phoenix = { en = "Phoenix", it = "Fenice" },
	Pet_Unicorn = { en = "Unicorn", it = "Unicorno" },
	Pet_Yeti = { en = "Yeti", it = "Yeti" },
	Pet_PinguinoPanettone = { en = "Pinguino Panettone", it = "Pinguino Panettone" },
	Pet_MuccaMoka = { en = "Mucca Moka", it = "Mucca Moka" },
	Pet_FontinelloVolantello = { en = "Fontinello Volantello", it = "Fontinello Volantello" },
	Pet_GelatoneMontagnone = { en = "Gelatone Montagnone", it = "Gelatone Montagnone" },
	Pet_PizzasauroRex = { en = "Pizzasauro Rex", it = "Pizzasauro Rex" },
	Pet_VulcanoSpaghettone = { en = "Vulcano Spaghettone", it = "Vulcano Spaghettone" },
	Pet_UovissimoImperatore = { en = "Uovissimo Imperatore", it = "Uovissimo Imperatore" },
	Pet_LumachelloLimoncello = { en = "Lumachello Limoncello", it = "Lumachello Limoncello" },
	Pet_GallinaGalattica = { en = "Gallina Galattica", it = "Gallina Galattica" },
	Pet_TortelloneCosmico = { en = "Tortellone Cosmico", it = "Tortellone Cosmico" },
	Pet_ArancinoAstronauta = { en = "Arancino Astronauta", it = "Arancino Astronauta" },
	Pet_MozzarellaNinjella = { en = "Mozzarella Ninjella", it = "Mozzarella Ninjella" },

	-- mutazioni e taglie
	Mutation_Gold = { en = "GOLD", it = "ORO" },
	Mutation_Diamond = { en = "DIAMOND", it = "DIAMANTE" },
	Mutation_Rainbow = { en = "RAINBOW", it = "ARCOBALENO" },
	Mutation_Cosmic = { en = "COSMIC", it = "COSMICO" },
	Size_Mini = { en = "MINI", it = "MINI" },
	Size_Giant = { en = "GIANT", it = "GIGANTE" },

	-- zone
	Zone_Summit = { en = "Summit", it = "Vetta" },
	Zone_Meadow = { en = "Meadows", it = "Prati" },
	Zone_Forest = { en = "Forest", it = "Bosco" },
	Zone_Canyon = { en = "Canyon", it = "Canyon" },
	Zone_Crystal = { en = "Crystal Caves", it = "Grotte di Cristallo" },
	Zone_Crater = { en = "Volcanic Crater", it = "Cratere Vulcanico" },

	-- prompt (azioni nel mondo)
	Prompt_Pickup = { en = "PICK UP", it = "RACCOGLI" },
	Prompt_Hatch = { en = "HATCH!", it = "SCHIUDI!" },
	Prompt_Steal = { en = "STEAL", it = "RUBA" },
	Prompt_Sell = { en = "SELL {price}", it = "VENDI {price}" },
	Prompt_Barrier = { en = "LOCK BASE", it = "BLOCCA BASE" },
	Prompt_Traps = { en = "TRAPS", it = "TRAPPOLE" },
	Prompt_Upgrades = { en = "UPGRADES", it = "POTENZIAMENTI" },

	-- HUD
	Carrying = { en = "{item}", it = "{item}" },
	CarrySpeed = { en = "Speed {pct}", it = "Velocità {pct}" },
	CarryHint = { en = "Bring it to your base at the top!", it = "Portalo nel tuo lotto in cima!" },
	CarryStolenHint = {
		en = "Run to your base before they catch you!",
		it = "Corri al tuo lotto prima che ti prendano!",
	},
	Heavy = { en = "Heavy!", it = "Pesante!" },
	BackpackFull = { en = "Your hands are full!", it = "Hai le mani piene!" },
	IncomeRate = { en = "+{rate}/s", it = "+{rate}/s" },

	-- valanga
	AvalancheWarn = { en = "AVALANCHE IN {t}!", it = "VALANGA TRA {t}!" },
	AvalancheWarnSub = { en = "Hide in a shelter!", it = "Corri al riparo in un rifugio!" },
	AvalancheNow = { en = "AVALANCHE!", it = "VALANGA!" },
	Buried = { en = "Buried by the avalanche!", it = "Travolto dalla valanga!" },
	Shelter = { en = "SHELTER", it = "RIFUGIO" },
	SafeInShelter = { en = "You're safe here!", it = "Qui sei al sicuro!" },

	-- notifiche
	EggDropped = { en = "You dropped your egg!", it = "Hai perso il tuo uovo!" },
	EggDelivered = { en = "{egg} is incubating!", it = "{egg} è in incubazione!" },
	NoIncubator = {
		en = "No free incubator! Upgrade or hatch your eggs.",
		it = "Nessuna incubatrice libera! Potenzia o schiudi le uova.",
	},
	NoPedestal = {
		en = "No free pedestal! Sell a pet or expand your base.",
		it = "Nessun piedistallo libero! Vendi un pet o espandi il lotto.",
	},
	PetSold = { en = "Sold {pet} for {price}!", it = "Hai venduto {pet} per {price}!" },
	Collected = { en = "+{amount}", it = "+{amount}" },
	UpgradeBought = { en = "{upgrade} upgraded!", it = "{upgrade} potenziato!" },
	Burned = { en = "Ouch, lava!", it = "Ahi, la lava!" },
	FellOff = { en = "You fell off the mountain!", it = "Sei caduto dalla montagna!" },
	SlappedBy = { en = "{name} slapped you!", it = "{name} ti ha dato uno schiaffo!" },
	GuardianHit = { en = "The guardian got you!", it = "La guardiana ti ha preso!" },

	-- furti
	StealYourEgg = { en = "{name} is stealing your {item}!", it = "{name} sta rubando il tuo {item}!" },
	StealSuccessThief = { en = "You stole {item} from {name}!", it = "Hai rubato {item} a {name}!" },
	StealSuccessVictim = { en = "{name} stole your {item}!", it = "{name} ti ha rubato {item}!" },
	StealStopped = { en = "{item} is back home!", it = "{item} è tornato a casa!" },
	StealOwnerLeft = {
		en = "The owner left: the loot vanished!",
		it = "Il proprietario è uscito: la refurtiva è sparita!",
	},
	CantStealProtected = {
		en = "This player just arrived: give them a minute!",
		it = "Questo giocatore è appena arrivato: lascialo respirare!",
	},
	CantStealNoRoom = { en = "No room in your base for it!", it = "Non hai spazio nel tuo lotto!" },
	Intruder = { en = "{name} entered your base!", it = "{name} è entrato nel tuo lotto!" },
	Thief = { en = "THIEF!", it = "LADRO!" },
	StealCatchHint = { en = "Slap the thief to get it back!", it = "Dai uno schiaffo al ladro per riprenderlo!" },
	Guardian_CrystalMother = { en = "Crystal Mother", it = "Mamma Cristallo" },
	Guardian_DragonMother = { en = "Dragon Mother", it = "Mamma Drago" },

	-- barriera e trappole
	BarrierOn = { en = "Base locked for {t}!", it = "Lotto bloccato per {t}!" },
	BarrierReady = { en = "Lock ready", it = "Blocco pronto" },
	BarrierCooldown = { en = "Lock in {t}", it = "Blocco tra {t}" },
	TrapTriggered = { en = "{name} stepped on your trap!", it = "{name} è finito nella tua trappola!" },
	Trap_BananaPeel = { en = "Banana Peel", it = "Buccia di Banana" },
	Trap_SlimePuddle = { en = "Slime Puddle", it = "Pozza di Melma" },
	Trap_BearTrap = { en = "Bear Trap", it = "Tagliola" },
	TrapDesc_BananaPeel = { en = "Thieves slip and drop the loot", it = "I ladri scivolano e mollano la refurtiva" },
	TrapDesc_SlimePuddle = { en = "Thieves get very slow", it = "I ladri diventano lentissimi" },
	TrapDesc_BearTrap = { en = "Thieves get stuck for a while", it = "I ladri restano bloccati per un po'" },

	-- mazze
	Bat_RubberMallet = { en = "Rubber Mallet", it = "Martello di Gomma" },
	Bat_Baguette = { en = "Baguette", it = "Baguette" },
	Bat_FrozenFish = { en = "Frozen Fish", it = "Pesce Surgelato" },
	Bat_CandyCane = { en = "Candy Cane", it = "Bastoncino di Zucchero" },
	Bat_GiantSpoon = { en = "Giant Spoon", it = "Cucchiaio Gigante" },
	Bat_GoldenMallet = { en = "Golden Mallet", it = "Martello d'Oro" },
	BatSlap = { en = "SLAP", it = "SCHIAFFO" },

	-- potenziamenti
	Upgrade_Speed = { en = "Speed", it = "Velocità" },
	Upgrade_Strength = { en = "Strength", it = "Forza" },
	Upgrade_Backpack = { en = "Backpack", it = "Zaino" },
	Upgrade_Incubators = { en = "Incubators", it = "Incubatrici" },
	Upgrade_HatchSpeed = { en = "Hatch Speed", it = "Schiusa Rapida" },
	Upgrade_Pedestals = { en = "Bigger Base", it = "Lotto Più Grande" },
	Upgrade_Barrier = { en = "Laser Barrier", it = "Barriera Laser" },
	UpgradeDesc_Speed = { en = "Walk faster: {value} speed", it = "Cammini più veloce: velocità {value}" },
	UpgradeDesc_Strength = {
		en = "Heavy eggs slow you {value} less",
		it = "Le uova pesanti ti rallentano il {value} in meno",
	},
	UpgradeDesc_Backpack = { en = "Carry {value} eggs at once", it = "Porti {value} uova alla volta" },
	UpgradeDesc_Incubators = { en = "{value} incubators in your base", it = "{value} incubatrici nel lotto" },
	UpgradeDesc_HatchSpeed = { en = "Eggs hatch {value} faster", it = "Le uova si schiudono il {value} più in fretta" },
	UpgradeDesc_Pedestals = { en = "{value} pedestals for your pets", it = "{value} piedistalli per i pet" },
	UpgradeDesc_Barrier = { en = "Barrier lasts {value}", it = "La barriera dura {value}" },

	-- negozio
	ShopPasses = { en = "GAME PASSES", it = "GAME PASS" },
	ShopBoosts = { en = "BOOSTS", it = "POTENZIAMENTI" },
	ShopBats = { en = "BATS", it = "MAZZE" },
	Pass_VIP = { en = "VIP", it = "VIP" },
	Pass_DoubleCoins = { en = "2x Coins", it = "Monete x2" },
	Pass_ExtraIncubator = { en = "+1 Incubator", it = "+1 Incubatrice" },
	Pass_BigBackpack = { en = "Big Backpack", it = "Zaino Grande" },
	Pass_FastHatch = { en = "Fast Hatch", it = "Schiusa Veloce" },
	Pass_SuperBarrier = { en = "Super Barrier", it = "Super Barriera" },
	PassDesc_VIP = {
		en = "+20% coins, VIP tag, Golden Mallet, better offline earnings",
		it = "+20% monete, tag VIP, Martello d'Oro, più guadagni offline",
	},
	PassDesc_DoubleCoins = {
		en = "All your pets earn double, forever",
		it = "Tutti i tuoi pet guadagnano il doppio, per sempre",
	},
	PassDesc_ExtraIncubator = { en = "One more incubator in your base", it = "Un'incubatrice in più nel tuo lotto" },
	PassDesc_BigBackpack = { en = "Carry one more egg at a time", it = "Porti un uovo in più alla volta" },
	PassDesc_FastHatch = {
		en = "Every egg hatches twice as fast",
		it = "Ogni uovo si schiude il doppio più in fretta",
	},
	PassDesc_SuperBarrier = {
		en = "Barrier lasts 60s longer and recharges faster",
		it = "La barriera dura 60s in più e si ricarica prima",
	},
	Product_SkipHatchSmall = { en = "Skip Hatch (up to Rare)", it = "Salta Schiusa (fino a Raro)" },
	Product_SkipHatchMedium = { en = "Skip Hatch (up to Legendary)", it = "Salta Schiusa (fino a Leggendario)" },
	Product_SkipHatchLarge = { en = "Skip Hatch (any egg)", it = "Salta Schiusa (qualsiasi uovo)" },
	Product_Luck15 = { en = "2x Luck · 15 min", it = "Fortuna x2 · 15 min" },
	Product_CoinsSmall = { en = "Coin Pouch", it = "Sacchetto di Monete" },
	Product_CoinsMedium = { en = "Coin Chest", it = "Forziere di Monete" },
	Product_CoinsLarge = { en = "Coin Mountain", it = "Montagna di Monete" },
	ProductDesc_Luck = {
		en = "More mutations, giant pets and rare pets",
		it = "Più mutazioni, pet giganti e pet rari",
	},
	ProductDesc_Coins = { en = "Get {amount} coins now", it = "Ricevi subito {amount} monete" },
	PurchaseThanks = { en = "Thank you for your purchase!", it = "Grazie per l'acquisto!" },
	SkipHatchWhich = { en = "Skips the egg that needs the most time", it = "Salta l'uovo con più tempo rimanente" },
	NoEggToSkip = { en = "No egg to skip right now", it = "Nessun uovo da saltare adesso" },

	-- schiusa
	Hatching = { en = "Hatching...", it = "Si schiude..." },
	Ready = { en = "READY!", it = "PRONTO!" },
	NewPet = { en = "NEW!", it = "NUOVO!" },
	YouGot = { en = "You got", it = "Hai ottenuto" },
	TapToContinue = { en = "Tap to continue", it = "Tocca per continuare" },

	-- album
	IndexTitle = { en = "PET INDEX", it = "ALBUM DEI PET" },
	IndexProgress = { en = "{n}/{total} discovered", it = "{n}/{total} scoperti" },
	IndexRowReward = {
		en = "Complete the row: +{bonus} coins forever and {coins}",
		it = "Completa la riga: +{bonus} monete per sempre e {coins}",
	},
	IndexRowDone = { en = "Row complete! +{bonus} income", it = "Riga completa! +{bonus} guadagni" },
	Undiscovered = { en = "???", it = "???" },

	-- regali
	GiftsTitle = { en = "FREE GIFTS", it = "REGALI GRATIS" },
	DailyTitle = { en = "DAILY REWARD", it = "PREMIO GIORNALIERO" },
	DailyDay = { en = "Day {n}", it = "Giorno {n}" },
	DailyNext = { en = "Next in {t}", it = "Prossimo tra {t}" },
	PlaytimeTitle = { en = "PLAYTIME GIFTS", it = "REGALI A TEMPO" },
	PlaytimeIn = { en = "In {t}", it = "Tra {t}" },
	GroupTitle = { en = "Join the group for {coins}!", it = "Unisciti al gruppo per {coins}!" },
	GroupNotMember = { en = "Join the group first!", it = "Prima unisciti al gruppo!" },
	RewardCoins = { en = "{amount} coins", it = "{amount} monete" },
	RewardLuck = { en = "2x Luck {t}", it = "Fortuna x2 {t}" },
	RewardEgg = { en = "{egg}", it = "{egg}" },
	RewardGot = { en = "You received {reward}!", it = "Hai ricevuto {reward}!" },
	EggStored = {
		en = "Your gift egg is waiting for a free incubator",
		it = "Il tuo uovo regalo aspetta un'incubatrice libera",
	},
	WelcomeBack = { en = "WELCOME BACK!", it = "BENTORNATO!" },
	OfflineEarned = {
		en = "Your pets earned {amount} while you were away",
		it = "I tuoi pet hanno guadagnato {amount} mentre eri via",
	},

	-- codici
	CodesTitle = { en = "CODES", it = "CODICI" },
	CodePlaceholder = { en = "Enter a code...", it = "Inserisci un codice..." },
	Redeem = { en = "REDEEM", it = "RISCATTA" },
	CodeInvalid = { en = "Invalid code", it = "Codice non valido" },
	CodeUsed = { en = "Code already redeemed", it = "Codice già usato" },
	CodeOk = { en = "Code redeemed!", it = "Codice riscattato!" },

	-- impostazioni
	SettingsTitle = { en = "SETTINGS", it = "OPZIONI" },
	Setting_Music = { en = "Music", it = "Musica" },
	Setting_Sfx = { en = "Sound effects", it = "Effetti sonori" },
	Setting_LowGfx = { en = "Low graphics", it = "Grafica leggera" },
	Setting_Language = { en = "Language", it = "Lingua" },
	On = { en = "ON", it = "SÌ" },
	Off = { en = "OFF", it = "NO" },

	-- eventi
	Event_MeteorShower = { en = "METEOR SHOWER", it = "PIOGGIA DI METEORE" },
	Event_GoldenHour = { en = "GOLDEN HOUR", it = "ORA D'ORO" },
	Event_SuperAvalanche = { en = "SUPER AVALANCHE", it = "SUPER VALANGA" },
	EventDesc_MeteorShower = {
		en = "Meteors bring rare cosmic eggs!",
		it = "I meteoriti portano uova rare e cosmiche!",
	},
	EventDesc_GoldenHour = { en = "Gold mutation at least 25%", it = "Mutazione Oro almeno al 25%" },
	EventDesc_SuperAvalanche = { en = "Avalanches every 55s, rare eggs x3!", it = "Valanghe ogni 55s, uova rare x3!" },
	EventStarted = { en = "{event} has started!", it = "È iniziata: {event}!" },
	Luck = { en = "2x Luck", it = "Fortuna x2" },
	FriendBonus = { en = "Friends bonus", it = "Bonus amici" },

	-- annunci
	AnnounceEgg = { en = "A {rarity} egg appeared in the {zone}!", it = "Un uovo {rarity} è apparso: {zone}!" },
	AnnounceHatch = { en = "{name} hatched {pet}!", it = "{name} ha schiuso {pet}!" },
	AnnounceSteal = { en = "{thief} stole {pet} from {victim}!", it = "{thief} ha rubato {pet} a {victim}!" },
	AnnounceAdmin = { en = "{text}", it = "{text}" },

	-- tutorial
	Tut_Hatch = {
		en = "Your first egg is hatching! Press HATCH when it's ready",
		it = "Il tuo primo uovo si sta schiudendo! Premi SCHIUDI quando è pronto",
	},
	Tut_Collect = {
		en = "Your pet makes money! Step on the green pad to collect",
		it = "Il tuo pet guadagna soldi! Sali sulla pedana verde per raccoglierli",
	},
	Tut_Upgrade = { en = "Buy an upgrade to climb faster!", it = "Compra un potenziamento per salire più in fretta!" },
	Tut_Pickup = { en = "Go down the mountain and pick up an egg!", it = "Scendi dalla montagna e raccogli un uovo!" },
	Tut_Deliver = { en = "Bring the egg back to your base at the top!", it = "Riporta l'uovo nel tuo lotto in cima!" },
	TutDone = { en = "You're ready! Watch out for thieves...", it = "Sei pronto! Occhio ai ladri..." },
	YourBase = { en = "YOUR BASE", it = "IL TUO LOTTO" },
	BaseOf = { en = "{name}'s base", it = "Lotto di {name}" },
	FreePlot = { en = "Free plot", it = "Lotto libero" },

	-- classifiche
	LbMoney = { en = "RICHEST", it = "I PIÙ RICCHI" },
	LbSteals = { en = "TOP THIEVES", it = "I LADRI MIGLIORI" },
	LbIncome = { en = "BEST INCOME", it = "GUADAGNI MIGLIORI" },
	LbEmpty = { en = "Loading...", it = "Caricamento..." },
}

Strings.Table = T

local function format(s: string, args: { [string]: any }?): string
	if not args then
		return s
	end
	return (
		string.gsub(s, "{(%w+)}", function(k)
			local v = args[k]
			return if v ~= nil then tostring(v) else "{" .. k .. "}"
		end)
	)
end

function Strings.Get(key: string, lang: string, args: { [string]: any }?): string
	local e = T[key]
	if not e then
		return key
	end
	local s = if lang == "it" then e.it else e.en
	return format(s, args)
end

function Strings.Has(key: string): boolean
	return T[key] ~= nil
end

-- "it-it" / "it" -> "it", tutto il resto -> "en"
function Strings.LangFromLocale(locale: string?): string
	if locale and string.sub(string.lower(locale), 1, 2) == "it" then
		return "it"
	end
	return "en"
end

return Strings
