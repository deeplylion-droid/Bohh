-- Costruisce l'interfaccia del client (HUD e pannelli) nell'ambiente finto di gui_env e ne esporta
-- l'albero in JSON, una scena per file, per disegnarla con tests/ui/to_html.py.
-- Uso (dalla radice): .tools/bin/lune run tests/ui/render_ui.luau [scena...] [--validate]
local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local serde = require("@lune/serde")

local G = require("./gui_env")

local Vector2 = roblox.Vector2

local OUT = "art/out/ui"
local NOW = 1760000000
local CLIENT = "StarterPlayer/StarterPlayerScripts/Client"

type Scene = {
	advance: number?,
	loading: boolean?,
	viewport: { number }?,
	touch: boolean?,
	locale: string?, -- lingua di Roblox (default "it-it")
	attributes: { [string]: any }?,
	workspace: { [string]: any }?,
	data: ((any) -> ())?,
	run: (ctx: any) -> (),
}

-- Profilo di un giocatore a meta' partita
local function baseData(cfg)
	local index = {}
	local discovered =
		{ Common = 4, Uncommon = 4, Rare = 3, Epic = 2, Legendary = 1, Mythic = 1, Divine = 0, Secret = 0 }
	for rarity, list in cfg.Pets.ByRarity do
		for i, pet in list do
			if i <= (discovered[rarity] or 0) then
				index[pet.id] = { Normal = true }
			end
		end
	end
	local common = cfg.Pets.ByRarity.Common
	index[common[1].id].Gold = true
	index[common[2].id].Diamond = true
	index[cfg.Pets.ByRarity.Rare[1].id].Rainbow = true
	return {
		Version = 1,
		Coins = 245300,
		TotalEarned = 1840000,
		Upgrades = { Speed = 3, Strength = 2, Backpack = 1, Incubators = 2, HatchSpeed = 1, Pedestals = 4, Barrier = 1 },
		Pets = {},
		NextUid = 40,
		Incubators = {},
		PendingEggs = {},
		Index = index,
		IndexClaimed = { Common = true },
		Bats = { RubberMallet = true, Baguette = true },
		EquippedBat = "Baguette",
		Traps = { ["1"] = "BananaPeel" },
		Stats = {
			Steals = 12,
			Stolen = 4,
			Hatched = 57,
			Delivered = 63,
			PlayTime = 18000,
			BestIncome = 1250,
			BestZone = "Canyon",
		},
		Codes = {},
		Daily = { Last = NOW - 90000, Streak = 2 },
		LuckUntil = 0,
		Settings = { Music = true, Sfx = true, LowGfx = false, Lang = "it" },
		Tutorial = 99,
		LastOnline = NOW - 3600,
		GroupClaimed = false,
		Purchases = {},
		PurchaseOrder = {},
		Wheel = { NextFree = NOW + 7322, Spins = 2 },
		Quests = {
			Day = NOW // 86400,
			Week = (NOW - 4 * 86400) // (7 * 86400),
			Daily = {
				{ Id = "Deliver", P = 12, C = false },
				{ Id = "Slap", P = 4, C = false },
				{ Id = "King", P = 45, C = true },
			},
			Weekly = {
				{ Id = "HatchW", P = 23, C = false },
				{ Id = "HatchPrimalW", P = 1, C = false },
				{ Id = "DeliverDeepW", P = 25, C = true },
			},
			DailyBonus = false,
			WeeklyBonus = false,
		},
	}
end

-- Prepara servizi, moduli e controller; restituisce il contesto della scena
local function setup(scene: Scene)
	local vp = scene.viewport or { 1280, 720 }
	local attrs = {
		Income = 1250,
		PlotIndex = 1,
		BarrierReadyAt = 0,
		SessionStart = NOW - 700,
		PlaytimeClaimed_1 = true,
	}
	for k, v in scene.attributes or {} do
		attrs[k] = v
	end
	local services = G.makeServices({
		viewport = Vector2.new(vp[1], vp[2]),
		touch = scene.touch,
		attributes = attrs,
		workspaceAttributes = scene.workspace,
		now = NOW,
		locale = scene.locale,
	})
	-- remote finti: nessun server, solo i segnali
	local remotes = {}
	local function remote(name)
		remotes[name] = remotes[name]
			or {
				OnClientEvent = G.newSignal(),
				FireServer = function() end,
				InvokeServer = function()
					return false, "CodeInvalid"
				end,
			}
		return remotes[name]
	end
	local fakeNet = {
		Event = function(name)
			return remote(name)
		end,
		Function = function(name)
			return remote(name)
		end,
	}
	-- pet 3D: un modello vuoto con l'id (to_html disegna il render del pet)
	local fakeVisuals = {
		MakePet = function(petId, mutation, size)
			local m = G.Instance.new("Model")
			m.Name = petId
			m:SetAttribute("PetId", petId)
			m:SetAttribute("Mutation", mutation)
			m:SetAttribute("Size", size)
			local part = G.Instance.new("MeshPart")
			part.Color = roblox.Color3.fromRGB(255, 255, 255)
			part.Parent = m
			return m
		end,
		MakeEgg = function(rarity)
			local m = G.Instance.new("Model")
			m:SetAttribute("EggRarity", rarity)
			return m
		end,
		ApplyMutation = function() end,
		EggEffects = function() end,
	}
	local loader = G.makeLoader(services, {
		["ReplicatedStorage/Shared/Net"] = fakeNet,
		["ReplicatedStorage/Shared/Visuals"] = fakeVisuals,
	})
	local req = loader.require
	if (scene :: any).loading then
		-- schermata di caricamento (ReplicatedFirst): solo lo script, senza i controller
		loader.runScript("ReplicatedFirst/Loading")
		return { services = services, req = req, C = { UI = {} }, remotes = remotes }
	end
	local cfg = {
		Pets = req("ReplicatedStorage/Shared/Config/Pets"),
		Rarities = req("ReplicatedStorage/Shared/Config/Rarities"),
	}
	local data = baseData(cfg)
	if scene.data then
		scene.data(data)
	end

	local C = {}
	local State = { Data = data, Ready = true, Loaded = G.newSignal(), Changed = G.newSignal() }
	function State.Get(...)
		local node = State.Data
		for _, k in { ... } do
			if type(node) ~= "table" then
				return nil
			end
			node = node[k]
		end
		return node
	end
	function State.Watch(key, fn)
		G.task.spawn(fn, State.Data[key])
		return function() end
	end
	function State.WaitReady() end
	C.State = State
	C.Lang = req(CLIENT .. "/Controllers/Lang")
	C.Audio = {
		Play = function() end,
		ApplySettings = function() end,
		SetOverride = function() end,
		ClearOverride = function() end,
	}
	C.Combat = { SlapButton = function() end }
	C.Effects = { Burst = function() end }
	C.UI = req(CLIENT .. "/Controllers/UI")
	C.Notify = req(CLIENT .. "/Controllers/Notify")
	C.Tutorial = req(CLIENT .. "/Controllers/Tutorial")
	C.Hatch = req(CLIENT .. "/Controllers/Hatch")
	for _, name in { "Lang", "UI", "Notify", "Tutorial", "Hatch" } do
		if C[name].Init then
			C[name].Init(C)
		end
	end
	C.UI.Start()
	for _, name in { "Notify", "Tutorial", "Hatch" } do
		G.task.spawn(C[name].Start)
	end
	local ctx
	ctx = {
		C = C,
		services = services,
		req = req,
		data = data,
		remotes = remotes,
		viewport = vp,
		gui = function(name)
			return C.UI.Gui(name)
		end,
		-- cambia la dimensione dello schermo (rotazione, finestra ridimensionata)
		setViewport = function(w, h)
			ctx.viewport = { w, h }
			services.camera.ViewportSize = Vector2.new(w, h)
		end,
	}
	return ctx
end

-- Trova il pulsante (Face) che contiene un testo e lo "preme"
local function press(root, text: string)
	for _, d in root:GetDescendants() do
		if d:IsA("TextLabel") and d.Text == text then
			local face = d.Parent
			if face and face:IsA("TextButton") then
				face.Activated:Fire()
				return true
			end
		end
	end
	error("pulsante non trovato: " .. text)
end

local SCENES: { [string]: Scene } = {}

SCENES.hud = { run = function() end }

SCENES.hud_busy = {
	attributes = {
		Carrying = 1,
		CarryRarity = "Epic",
		CarryKind = "Egg",
		WalkSpeed = 11.5,
		LuckUntil = NOW + 610,
		FriendBonus = 0.2,
		BarrierReadyAt = NOW + 75,
	},
	workspace = { EventId = "GoldenHour", EventEndsAt = NOW + 185 },
	run = function(ctx)
		local T = ctx.C.Lang.T
		ctx.C.UI.Hud.ShowBanner("❄️ " .. T("AvalancheWarn", { t = "12s" }), T("AvalancheWarnSub"), nil, 2)
	end,
}

SCENES.hud_phone = {
	viewport = { 844, 390 },
	touch = true,
	attributes = { Carrying = 2, CarryRarity = "Legendary", CarryKind = "Egg", WalkSpeed = 10, Thief = true },
	workspace = { EventId = "MeteorShower", EventEndsAt = NOW + 95 },
	run = function() end,
}

local function panelScene(name: string, extra: ((any) -> ())?): Scene
	return {
		attributes = { IsAdmin = name == "Admin" },
		run = function(ctx)
			ctx.C.UI.Open(name)
			if extra then
				extra(ctx)
			end
		end,
	}
end

SCENES.toasts = {
	run = function(ctx)
		local T = ctx.C.Lang.T
		ctx.C.Notify.Toast(T("CodeOk"), "Good")
		ctx.C.Notify.Toast("Qualcuno ti ha rubato un uovo!", "Bad")
		ctx.C.Notify.Toast("+$12.5K dai tuoi pet", "Gold")
		ctx.C.Notify.Announce("Tester ha trovato un <b>Unicorno</b> LEGGENDARIO!", "Legendary")
	end,
	advance = 0.6,
}
SCENES.toasts_phone = {
	viewport = { 844, 390 },
	touch = true,
	run = SCENES.toasts.run,
	advance = 0.6,
}
SCENES.tutorial = {
	attributes = { Carrying = 1, CarryRarity = "Common", CarryKind = "Egg", WalkSpeed = 15 },
	data = function(d)
		d.Tutorial = 4
	end,
	run = function() end,
}
SCENES.tutorial_phone = {
	viewport = { 844, 390 },
	touch = true,
	attributes = SCENES.tutorial.attributes,
	data = SCENES.tutorial.data,
	run = function() end,
}
SCENES.hatch = {
	run = function(ctx)
		ctx.remotes.HatchReveal = ctx.remotes.HatchReveal
		local ev = ctx.req("ReplicatedStorage/Shared/Net").Event("HatchReveal")
		ev.OnClientEvent:Fire({ pet = "Unicorn", rarity = "Legendary", mutation = "Gold", size = "Giant", new = true })
	end,
	advance = 4.4,
}
SCENES.hatch_phone = {
	viewport = { 844, 390 },
	touch = true,
	run = SCENES.hatch.run,
	advance = 4.4,
}
SCENES.carry_pet = {
	attributes = {
		Carrying = 1,
		CarryRarity = "Mythic",
		CarryKind = "Pet",
		CarryPet = "PizzasauroRex",
		WalkSpeed = 9,
		Thief = true,
	},
	run = function() end,
}

-- novita' Ultra: album con la riga dei giganti, schiusa di un gigante, uovo Ultra in braccio
SCENES.index_ultra = {
	data = function(d)
		d.Index.PentaDragon = { Normal = true }
		d.Index.VenomWidow = { Normal = true, Gold = true }
	end,
	run = function(ctx)
		ctx.C.UI.Open("Index")
		-- scorre l'album fino alla riga Ultra (l'ultima)
		for _, sf in ctx.gui("Panels"):GetDescendants() do
			if sf:IsA("ScrollingFrame") and sf.Parent and sf.Parent.Name == "Body" then
				sf.CanvasPosition = roblox.Vector2.new(0, 1600)
			end
		end
	end,
}
SCENES.hatch_ultra = {
	run = function(ctx)
		local ev = ctx.req("ReplicatedStorage/Shared/Net").Event("HatchReveal")
		ev.OnClientEvent:Fire({ pet = "PentaDragon", rarity = "Ultra", mutation = "None", size = "Normal", new = true })
	end,
	advance = 5.6,
}
SCENES.carry_ultra = {
	attributes = { Carrying = 1, CarryRarity = "Ultra", CarryKind = "Egg", WalkSpeed = 4.8 },
	workspace = { EventId = "SuperAvalanche", EventEndsAt = NOW + 140 },
	run = function(ctx)
		local T = ctx.C.Lang.T
		ctx.C.UI.Hud.ShowBanner("❄️ " .. T("AvalancheWarn", { t = "9s" }), T("AvalancheWarnSub"), nil, 2)
	end,
}

-- novita' Primordiali: riga dell'album su due file, schiusa di un mostro (il primo uovo dei nuovi)
SCENES.index_primal = {
	data = function(d)
		d.Index.WarBoar = { Normal = true }
		d.Index.Cerberus = { Normal = true, Gold = true }
		d.Index.KingCobra = { Normal = true }
	end,
	run = function(ctx)
		ctx.C.UI.Open("Index")
		for _, sf in ctx.gui("Panels"):GetDescendants() do
			if sf:IsA("ScrollingFrame") and sf.Parent and sf.Parent.Name == "Body" then
				sf.CanvasPosition = roblox.Vector2.new(0, 1580)
			end
		end
	end,
}
SCENES.hatch_primal = {
	run = function(ctx)
		local ev = ctx.req("ReplicatedStorage/Shared/Net").Event("HatchReveal")
		ev.OnClientEvent:Fire({ pet = "WarBoar", rarity = "Primal", mutation = "None", size = "Normal", new = true })
	end,
	advance = 5.6,
}

-- Percorso Estremo: riga dell'album con i 12 pet Estremi e cronometro della corsa sotto le monete
SCENES.index_extreme = {
	data = function(d)
		d.Index.GlassHead = { Normal = true }
		d.Index.AnubisGuard = { Normal = true }
		d.Index.Beelzebub = { Normal = true, Gold = true }
	end,
	run = function(ctx)
		ctx.C.UI.Open("Index")
		for _, sf in ctx.gui("Panels"):GetDescendants() do
			if sf:IsA("ScrollingFrame") and sf.Parent and sf.Parent.Name == "Body" then
				sf.CanvasPosition = roblox.Vector2.new(0, 1930)
			end
		end
	end,
}
SCENES.hud_extreme = {
	run = function(ctx)
		local X = ctx.req(CLIENT .. "/Controllers/Extreme")
		ctx.C.Effects.On = function() end
		ctx.C.Effects.CameraShake = function() end
		X.Init(ctx.C)
		G.task.spawn(X.Start)
		G.advance(0.6)
		ctx.req("ReplicatedStorage/Shared/Net").Event("ExtremeRun").OnClientEvent:Fire({
			active = true,
			checkpoint = 1,
			started = NOW - 194,
			best = 512,
		})
	end,
	advance = 1,
}

SCENES.loading = {
	loading = true,
	workspace = { ServerReady = false },
	run = function() end,
	advance = 1.5,
}
SCENES.loading_phone = {
	loading = true,
	viewport = { 844, 390 },
	touch = true,
	workspace = { ServerReady = false },
	run = function() end,
	advance = 1.5,
}

-- pannello aperto mentre la finestra si rimpicciolisce: la scala e il pannello si adattano
SCENES.resize_panel = {
	run = function(ctx)
		ctx.C.UI.Open("Upgrades")
		ctx.setViewport(900, 500)
	end,
}
-- lingua cambiata dalle opzioni: tutti i testi si aggiornano
SCENES.settings_english = {
	run = function(ctx)
		ctx.C.UI.Open("Settings")
		press(ctx.gui("Panels"), "ITALIANO")
	end,
}

-- piazza: ruota della fortuna, missioni, re della collina
SCENES.wheel = panelScene("Wheel")
SCENES.wheel_free = {
	data = function(d)
		d.Wheel = { NextFree = 0, Spins = 0 }
	end,
	run = function(ctx)
		ctx.C.UI.Open("Wheel")
	end,
}
-- giro che finisce sul jackpot (spicchio 8): la freccia deve indicare lo spicchio rosso
SCENES.wheel_spin = {
	data = function(d)
		d.Wheel = { NextFree = 0, Spins = 0 }
	end,
	run = function(ctx)
		ctx.req("ReplicatedStorage/Shared/Net").Function("SpinWheel").InvokeServer = function()
			return true, 8
		end
		ctx.C.UI.Open("Wheel")
		press(ctx.gui("Panels"), ctx.C.Lang.T("WheelSpinFree"))
	end,
	advance = 7,
}
SCENES.quests = panelScene("Quests")
SCENES.quests_phone = {
	viewport = { 844, 390 },
	touch = true,
	run = function(ctx)
		ctx.C.UI.Open("Quests")
	end,
}
SCENES.hud_king = {
	attributes = { OnHill = true, King = true, KingRate = 625, LuckUntil = NOW + 300 },
	run = function() end,
}
SCENES.hud_contested = {
	attributes = { OnHill = true },
	workspace = { HillContested = true },
	run = function() end,
}

SCENES.shop = panelScene("Shop")
SCENES.shop_boosts = panelScene("Shop", function(ctx)
	press(ctx.gui("Panels"), ctx.C.Lang.T("ShopBoosts"))
end)
SCENES.shop_bats = panelScene("Shop", function(ctx)
	press(ctx.gui("Panels"), ctx.C.Lang.T("ShopBats"))
end)
SCENES.upgrades = panelScene("Upgrades")
SCENES.index = panelScene("Index")
SCENES.gifts = panelScene("Gifts")
SCENES.codes = panelScene("Codes")
SCENES.settings = panelScene("Settings")
-- codice sbagliato: l'esito compare su una pillola sotto la casella
SCENES.codes_result = panelScene("Codes", function(ctx)
	for _, d in ctx.gui("Panels"):GetDescendants() do
		if d:IsA("TextBox") then
			d.Text = "MONTAGNA"
		end
	end
	press(ctx.gui("Panels"), ctx.C.Lang.T("Redeem"))
end)
SCENES.admin = panelScene("Admin")
SCENES.shop_phone = {
	viewport = { 844, 390 },
	touch = true,
	run = function(ctx)
		ctx.C.UI.Open("Shop")
	end,
}

-- Varianti: ogni pannello su un telefono in orizzontale (844x390) e le scene principali in inglese
-- (testi di lunghezza diversa)
local function phone(base: Scene): Scene
	local out = table.clone(base)
	out.viewport = { 844, 390 }
	out.touch = true
	return out
end
local function english(base: Scene): Scene
	local out = table.clone(base)
	out.locale = "en-us"
	local data = base.data
	out.data = function(d)
		d.Settings.Lang = "en"
		if data then
			data(d)
		end
	end
	return out
end
for _, name in { "upgrades", "index", "gifts", "wheel", "settings", "codes", "shop_bats", "hud_busy" } do
	SCENES[name .. "_phone"] = phone(SCENES[name])
end
for _, name in { "hud_busy", "shop", "shop_boosts", "upgrades", "index", "gifts", "quests", "wheel", "tutorial" } do
	SCENES[name .. "_en"] = english(SCENES[name])
end
SCENES.quests_phone_en = english(SCENES.quests_phone)
SCENES.hud_phone_en = english(SCENES.hud_phone)

local names = {}
for i = 1, #process.args do
	if string.sub(process.args[i], 1, 2) ~= "--" then
		table.insert(names, process.args[i])
	end
end
if #names == 0 then
	for n in SCENES do
		table.insert(names, n)
	end
	table.sort(names)
end

fs.writeDir(OUT)
local failed = 0
for _, name in names do
	local scene = SCENES[name]
	assert(scene, "scena sconosciuta: " .. name)
	local ok, err = pcall(function()
		local ctx = setup(scene)
		scene.run(ctx)
		-- lascia finire comparse e animazioni brevi
		G.advance((scene :: any).advance or 1)
		local vp = ctx.viewport or scene.viewport or { 1280, 720 }
		local core = {}
		for k, v in ctx.services.StarterGui:GetAttributes() do
			core[string.gsub(k, "^Core_Enum%.CoreGuiType%.", "")] = v
		end
		local out = {
			scene = name,
			viewport = vp,
			scale = ctx.C.UI.Scale,
			touch = scene.touch == true,
			core = core,
			root = G.dump(ctx.services.playerGui),
		}
		fs.writeFile(`{OUT}/{name}.json`, serde.encode("json", out, false))
	end)
	if ok then
		print("ok   " .. name)
	else
		failed += 1
		print("ERR  " .. name .. ": " .. tostring(err))
	end
end
-- --validate: ricopia le proprieta' di ogni istanza finta su un'istanza vera di @lune/roblox, che
-- controlla nomi, tipi ed enum come Roblox (l'ambiente finto accetta qualsiasi proprieta')
if table.find(process.args, "--validate") then
	local SKIP = {
		Parent = true,
		ClassName = true,
		AbsoluteSize = true,
		AbsolutePosition = true,
		AbsoluteRotation = true,
		AbsoluteContentSize = true,
		AbsoluteCanvasSize = true,
		AbsoluteWindowSize = true,
		TextBounds = true,
		TextFits = true,
		__destroyed = true, -- segno interno dell'ambiente finto
	}
	local problems, seen, checked = {}, {}, 0
	for _, obj in G.created do
		local okNew, real = pcall(roblox.Instance.new, obj.__class)
		if not okNew then
			continue -- servizi e classi dell'ambiente finto che non si creano
		end
		for k, v in obj.__props do
			if SKIP[k] or type(v) == "function" or type(v) == "table" then
				continue
			end
			checked += 1
			local okSet, err = pcall(function()
				(real :: any)[k] = v
			end)
			if not okSet then
				local msg = string.match(tostring(err), "^[^\n]*\n?([^\n]*)") or tostring(err)
				local key = `{obj.__class}.{k}: {msg}`
				if not seen[key] then
					seen[key] = true
					table.insert(problems, key)
				end
			end
		end
	end
	print(`validate: {checked} proprieta' controllate su istanze vere, {#problems} problemi`)
	for _, line in problems do
		print("  " .. line)
	end
	if #problems > 0 then
		failed += 1
	end
end

local unknown = {}
for k in G.unknown do
	table.insert(unknown, k)
end
table.sort(unknown)
if #unknown > 0 then
	print("membri sconosciuti letti: " .. table.concat(unknown, ", "))
end
process.exit(if failed > 0 then 1 else 0)
