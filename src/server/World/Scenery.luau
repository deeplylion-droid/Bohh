-- Elementi fissi della mappa: piazza della vetta, rifugi anti-valanga, mare di nuvole, decorazioni.

local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Visuals = require(ReplicatedStorage.Shared.Visuals)
local Build = require(script.Parent.Build)

local Scenery = {}

local WOOD = Color3.fromRGB(168, 112, 64)
local WOOD_DARK = Color3.fromRGB(122, 78, 44)
local ROOF = Color3.fromRGB(226, 72, 54)

---------------------------------------------------------------------------------------------
-- Piazza della vetta
---------------------------------------------------------------------------------------------
function Scenery.Summit(parent: Instance, assets)
	local folder = Build.Model("Summit", parent)
	local c = MapLayout.SummitCenter
	-- quota calpestabile di piazza e viale; le lastre sono spesse 4 stud, cosi' i bordi affondano
	-- nella neve invece di galleggiare sul terreno
	local top = c.Y + 0.8
	-- pavimentazione circolare della piazza (si unisce ai cancelli dei lotti)
	Build.Part({
		name = "Plaza",
		size = Vector3.new(4, 206, 206),
		cframe = CFrame.new(c.X, top - 2, c.Z) * CFrame.Angles(0, 0, math.rad(90)),
		color = Color3.fromRGB(236, 222, 196),
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	-- anello decorativo
	Build.Part({
		name = "PlazaRing",
		size = Vector3.new(1.3, 120, 120),
		cframe = CFrame.new(c + Vector3.new(0, 0.25, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = Color3.fromRGB(210, 190, 160),
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	-- viale verso la rampa del sentiero (un filo piu' basso della piazza dove si sovrappongono,
	-- cosi' le due superfici non sfarfallano)
	local avenueTop = top - 0.04
	Build.Part({
		name = "Avenue",
		size = Vector3.new(40, 4, 52),
		cframe = CFrame.new(c.X, avenueTop - 2, 124),
		color = Color3.fromRGB(236, 222, 196),
		material = Enum.Material.Slate,
		parent = folder,
	})
	-- discesa lastricata: dalla fine del viale (z=150) scende piu' ripida della rampa di terra
	-- e ci si infila sotto verso z=161, cosi' non resta nessun gradino sospeso
	local slope = math.atan(0.25)
	Build.Part({
		name = "AvenueRamp",
		size = Vector3.new(40, 4, 28),
		cframe = CFrame.new(c.X, avenueTop, 150) * CFrame.Angles(slope, 0, 0) * CFrame.new(0, -2, 14),
		color = Color3.fromRGB(236, 222, 196),
		material = Enum.Material.Slate,
		parent = folder,
	})
	-- arco d'ingresso al sentiero con il nome del gioco (i pali affondano nella rampa di terra)
	for _, sx in { -1, 1 } do
		Build.Part({
			name = "ArchPost",
			size = Vector3.new(4, 32, 4),
			cframe = CFrame.new(sx * 23, c.Y + 10, 158),
			color = WOOD,
			material = Enum.Material.Wood,
			parent = folder,
		})
	end
	Build.Part({
		name = "ArchBeam",
		size = Vector3.new(54, 4, 5),
		cframe = CFrame.new(0, c.Y + 26, 158),
		color = WOOD_DARK,
		material = Enum.Material.Wood,
		parent = folder,
	})
	Build.Sign(folder, CFrame.new(0, c.Y + 22, 155.4), Vector3.new(40, 7, 1), "TrailSign", nil, {
		bg = Color3.fromRGB(255, 214, 72),
		text = Color3.fromRGB(70, 36, 10),
	})
	-- monumento centrale: piedistallo con uovo gigante (rotazione animata dal client)
	Build.Part({
		name = "MonumentBase",
		size = Vector3.new(6, 30, 30),
		cframe = CFrame.new(c + Vector3.new(0, 3, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = Color3.fromRGB(196, 176, 150),
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	local egg = assets.Clone("Eggs", "EggLegendary")
	if egg then
		egg.Name = "MonumentEgg"
		egg:ScaleTo(5)
		egg:PivotTo(CFrame.new(c + Vector3.new(0, 6, 0)))
		egg.Parent = folder
		CollectionService:AddTag(egg, "Spinner")
	end
	-- lampioni fra i cancelli dei lotti e panchine attorno al monumento (se i modelli ci sono)
	for k = 0, 8 do
		local a = math.rad(20 + 40 * k)
		local dir = Vector3.new(math.sin(a), 0, math.cos(a))
		local lamp = assets.Clone("Props", "LampPost")
		if lamp then
			lamp:ScaleTo(1.25)
			lamp:PivotTo(CFrame.lookAt(c + dir * 92, c + dir * 91) + Vector3.new(0, 0.6, 0))
			local light = Instance.new("PointLight")
			light.Color = Color3.fromRGB(255, 214, 150)
			light.Range = 22
			light.Brightness = 1.2
			light.Shadows = false
			light.Parent = lamp.PrimaryPart or lamp:FindFirstChildWhichIsA("BasePart")
			lamp.Parent = folder
		end
		local deg = (20 + 40 * k) % 360
		local nearBoards = deg > 110 and deg < 250
		if k < 8 and not nearBoards then
			local bench = assets.Clone("Props", "Bench")
			if bench then
				bench:ScaleTo(1.2)
				-- la panchina guarda il monumento
				bench:PivotTo(CFrame.lookAt(c + dir * 72, c) + Vector3.new(0, 0.6, 0))
				bench.Parent = folder
			end
		end
	end
	return folder
end

---------------------------------------------------------------------------------------------
-- Rifugi anti-valanga: capanne di legno aperte verso il sentiero
---------------------------------------------------------------------------------------------
function Scenery.Shelters(parent: Instance)
	local folder = Build.Model("Shelters", parent)
	local size = MapLayout.ShelterSize
	for i = 1, #MapLayout.Shelters do
		local cf = MapLayout.ShelterFrame(i)
		local hut = Build.Model(`Shelter{i}`, folder)
		-- pavimento
		Build.Part({
			name = "Floor",
			size = Vector3.new(size.X + 2, 0.6, size.Z + 2),
			cframe = cf * CFrame.new(0, 0.3, 0),
			color = WOOD,
			material = Enum.Material.WoodPlanks,
			parent = hut,
		})
		-- pali agli angoli
		for _, sx in { -1, 1 } do
			for _, sz in { -1, 1 } do
				Build.Part({
					name = "Post",
					size = Vector3.new(1.4, size.Y, 1.4),
					cframe = cf * CFrame.new(sx * size.X / 2, size.Y / 2, sz * size.Z / 2),
					color = WOOD_DARK,
					material = Enum.Material.Wood,
					parent = hut,
				})
			end
		end
		-- parete di fondo (lato a monte) e pareti laterali basse
		Build.Part({
			name = "Back",
			size = Vector3.new(size.X, size.Y, 0.8),
			cframe = cf * CFrame.new(0, size.Y / 2, size.Z / 2),
			color = WOOD,
			material = Enum.Material.WoodPlanks,
			parent = hut,
		})
		for _, sx in { -1, 1 } do
			Build.Part({
				name = "Side",
				size = Vector3.new(0.8, size.Y * 0.55, size.Z),
				cframe = cf * CFrame.new(sx * size.X / 2, size.Y * 0.275, 0),
				color = WOOD,
				material = Enum.Material.WoodPlanks,
				parent = hut,
			})
		end
		-- tetto a due falde
		for _, sz in { -1, 1 } do
			Build.Part({
				name = "Roof",
				size = Vector3.new(size.X + 4, 0.8, size.Z * 0.62),
				cframe = cf * CFrame.new(0, size.Y + 1.6, sz * size.Z * 0.26) * CFrame.Angles(math.rad(-24 * sz), 0, 0),
				color = ROOF,
				material = Enum.Material.SmoothPlastic,
				parent = hut,
			})
		end
		-- cartello luminoso sopra l'apertura
		local sign = Build.Sign(
			hut,
			cf * CFrame.new(0, size.Y + 0.2, -size.Z / 2 - 0.5),
			Vector3.new(10, 2.6, 0.4),
			"Shelter",
			nil,
			{
				bg = Color3.fromRGB(110, 230, 120),
				text = Color3.fromRGB(20, 70, 30),
			}
		)
		local light = Instance.new("PointLight")
		light.Color = Color3.fromRGB(150, 255, 160)
		light.Range = 16
		light.Brightness = 1.2
		light.Parent = sign
		hut:SetAttribute("ShelterIndex", i)
		CollectionService:AddTag(hut, "Shelter")
	end
	return folder
end

---------------------------------------------------------------------------------------------
-- Mare di nuvole attorno alla montagna (si cade attraverso e si torna in vetta)
---------------------------------------------------------------------------------------------
function Scenery.CloudSea(parent: Instance)
	local folder = Build.Model("CloudSea", parent)
	local y = MapLayout.CloudSeaY
	Build.Part({
		name = "CloudBase",
		size = Vector3.new(4000, 4, 4000),
		cframe = CFrame.new(0, y - 6, 200),
		color = Color3.fromRGB(246, 250, 255),
		material = Enum.Material.SmoothPlastic,
		collide = false,
		query = false,
		castShadow = false,
		parent = folder,
	})
	local rng = Random.new(42)
	local volcano = MapLayout.Den.Volcano.center
	for _ = 1, 260 do
		local a = rng:NextNumber(0, math.pi * 2)
		local r = rng:NextNumber(200, 1100)
		local x, z = math.cos(a) * r, 200 + math.sin(a) * r * 1.2
		local d = rng:NextNumber(40, 110)
		local size = Vector3.new(d * rng:NextNumber(1.2, 1.8), d * 0.55, d)
		local cf = CFrame.new(x, y - 4 + rng:NextNumber(0, 10), z) * CFrame.Angles(0, rng:NextNumber(0, 6.28), 0)
		-- niente nuvole dentro il vulcano della Tana (finirebbero nella grotta)
		if Vector2.new(x - volcano.X, z - volcano.Z).Magnitude < 170 then
			continue
		end
		Build.Part({
			name = "Puff",
			size = size,
			cframe = cf,
			color = Color3.fromRGB(255, 255, 255),
			material = Enum.Material.SmoothPlastic,
			shape = Enum.PartType.Ball,
			collide = false,
			query = false,
			castShadow = false,
			parent = folder,
		})
	end
	return folder
end

---------------------------------------------------------------------------------------------
-- Decorazioni sparse (alberi, rocce, fiori) per zona, lontano dal sentiero
---------------------------------------------------------------------------------------------
type DecorItem = {
	name: string,
	count: number,
	scale: { number },
	edge: boolean?,
	cliff: boolean?,
	tint: Color3?,
	light: { Color3 | number }?,
}

-- colore della roccia per zona (le guglie e le schegge di roccia prendono il colore del posto)
local ROCK_TINT = {
	Meadow = Color3.fromRGB(128, 132, 142),
	Forest = Color3.fromRGB(116, 118, 124),
	Canyon = Color3.fromRGB(178, 104, 70),
	Crystal = Color3.fromRGB(98, 92, 124),
	Crater = Color3.fromRGB(62, 56, 64),
}

local DECOR: { [string]: { DecorItem } } = {
	Summit = {
		{ name = "PineSnowy", count = 46, scale = { 1.4, 2.2 } },
		{ name = "SnowRock", count = 22, scale = { 1.0, 2.0 } },
		{ name = "Rock2", count = 10, scale = { 1.2, 2.4 } },
	},
	Meadow = {
		{ name = "RockShards", count = 14, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Meadow },
		{ name = "RockSpire", count = 6, scale = { 1.0, 1.6 }, cliff = true, tint = ROCK_TINT.Meadow },
		{ name = "PineTree", count = 30, scale = { 1.3, 2.0 } },
		{ name = "Bush1", count = 26, scale = { 1.0, 1.5 } },
		{ name = "Flowers1", count = 40, scale = { 1.4, 2.0 } },
		{ name = "Flowers2", count = 40, scale = { 1.4, 2.0 } },
		{ name = "Grass1", count = 90, scale = { 2.0, 3.0 } },
		{ name = "Rock1", count = 26, scale = { 0.8, 1.6 }, edge = true },
	},
	Forest = {
		{ name = "RockSpire", count = 10, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Forest },
		{ name = "RockShards", count = 14, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Forest },
		{ name = "OakTree", count = 46, scale = { 1.2, 1.9 } },
		{ name = "PineTree", count = 40, scale = { 1.8, 2.8 } },
		{ name = "Bush1", count = 30, scale = { 1.2, 1.8 } },
		{ name = "Mushrooms", count = 40, scale = { 1.2, 2.0 }, edge = true },
		{ name = "Fern", count = 60, scale = { 1.2, 2.0 } },
		{ name = "FallenLog", count = 14, scale = { 1.0, 1.4 } },
		{ name = "Grass1", count = 60, scale = { 2.0, 3.0 } },
		{ name = "Rock3", count = 20, scale = { 0.8, 1.6 }, edge = true },
	},
	Canyon = {
		{ name = "RockSpire", count = 24, scale = { 1.2, 2.4 }, cliff = true, tint = ROCK_TINT.Canyon },
		{ name = "RockShards", count = 20, scale = { 1.0, 2.0 }, cliff = true, tint = ROCK_TINT.Canyon },
		{ name = "Mesa", count = 16, scale = { 1.4, 2.6 } },
		{ name = "Cactus", count = 30, scale = { 1.0, 1.6 } },
		{ name = "DryBush", count = 50, scale = { 1.2, 2.0 }, edge = true },
		{ name = "CanyonRock", count = 34, scale = { 1.0, 2.4 } },
		{ name = "Rock3", count = 16, scale = { 0.8, 1.6 }, edge = true },
	},
	Crystal = {
		{ name = "RockSpire", count = 12, scale = { 1.0, 2.0 }, cliff = true, tint = ROCK_TINT.Crystal },
		{ name = "RockShards", count = 16, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Crystal },
		{ name = "CrystalCluster1", count = 26, scale = { 1.0, 2.2 }, light = { Color3.fromRGB(190, 120, 255), 18 } },
		{
			name = "CrystalCluster2",
			count = 34,
			scale = { 0.9, 1.6 },
			edge = true,
			light = { Color3.fromRGB(110, 230, 255), 14 },
		},
		{ name = "GlowShroom", count = 40, scale = { 1.0, 1.8 }, edge = true },
		{ name = "Rock1", count = 18, scale = { 1.0, 2.0 } },
	},
	Crater = {
		{ name = "RockSpire", count = 10, scale = { 1.0, 2.0 }, cliff = true, tint = ROCK_TINT.Crater },
		{ name = "RockShards", count = 14, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Crater },
		{ name = "LavaRock", count = 34, scale = { 1.0, 2.4 }, light = { Color3.fromRGB(255, 120, 40), 16 } },
		{ name = "DeadTree", count = 18, scale = { 1.0, 1.6 } },
		{ name = "ObsidianSpikes", count = 26, scale = { 1.0, 2.0 } },
		{ name = "Rock3", count = 14, scale = { 1.0, 2.6 } },
	},
}

-- una luce ogni LIGHT_EVERY oggetti luminosi (le luci costano: poche ma ben distribuite)
local LIGHT_EVERY = 3

local SMALL = {
	Grass1 = true,
	Flowers1 = true,
	Flowers2 = true,
	Fern = true,
	Mushrooms = true,
	DryBush = true,
	GlowShroom = true,
}

function Scenery.Decor(parent: Instance, assets, terrainHeight: (number, number) -> (number, string, string))
	local folder = Build.Model("Decor", parent)
	local rng = Random.new(7)
	for zone, items in DECOR do
		for _, item in items do
			local template = assets.Clone("Props", item.name)
			if not template then
				continue
			end
			template:Destroy()
			local placed, tries = 0, 0
			while placed < item.count and tries < item.count * 30 do
				tries += 1
				local x, z
				if zone == "Summit" then
					local a = rng:NextNumber(0, math.pi * 2)
					local r = rng:NextNumber(MapLayout.PlateauRadius - 12, MapLayout.PlateauRadius + 18)
					x, z = math.cos(a) * r, math.sin(a) * r
					if z > 120 and math.abs(x) < 50 then
						continue -- lascia libero l'inizio del sentiero
					end
				else
					x, z = rng:NextNumber(-300, 300), rng:NextNumber(150, 780)
				end
				local h, kind, zn = terrainHeight(x, z)
				if zone ~= "Summit" and zn ~= zone then
					continue
				end
				-- non sopra la trincea e il tunnel della Tana dei Mostri (scavati dopo il terreno)
				local _, tunnelDist = MapLayout.DenTunnelAt(x, z)
				if tunnelDist < MapLayout.Den.TunnelRadius + 8 then
					continue
				end
				if kind == "path" or kind == "crater" or h < MapLayout.CloudSeaY + 4 then
					continue
				end
				if item.edge then
					-- sassi a bordo sentiero: solo vicino al bordo
					local hn = terrainHeight(x + 3, z)
					if math.abs(hn - h) > 4 then
						continue
					end
				end
				-- evita pendii troppo ripidi (gli oggetti sembrerebbero sospesi); le rocce di scarpata
				-- invece vanno proprio sui pendii ripidi
				local h2 = terrainHeight(x + 2, z + 2)
				local steep = math.abs(h2 - h) > 2.5
				if item.cliff ~= nil and item.cliff ~= steep then
					continue
				elseif not item.cliff and math.abs(h2 - h) > 3.2 then
					continue
				end
				local model = assets.Clone("Props", item.name)
				if not model then
					break
				end
				local s = rng:NextNumber(item.scale[1], item.scale[2])
				model:ScaleTo(s)
				local sink = if item.cliff then 1.6 * s else 0.4
				model:PivotTo(CFrame.new(x, h - sink, z) * CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), 0))
				if item.tint then
					for _, d in model:GetDescendants() do
						if d:IsA("BasePart") and d:GetAttribute("Role") == "skin" then
							d.Color = item.tint
						end
					end
				end
				if item.light and placed % LIGHT_EVERY == 0 then
					local light = Instance.new("PointLight")
					light.Color = item.light[1] :: Color3
					light.Range = item.light[2] :: number
					light.Brightness = 1.4
					light.Shadows = false
					light.Parent = model.PrimaryPart or model:FindFirstChildWhichIsA("BasePart")
				end
				if SMALL[item.name] then
					-- dettagli piccoli: il client li nasconde con la grafica leggera
					CollectionService:AddTag(model, "SmallDecor")
				end
				model.Parent = folder
				placed += 1
			end
		end
	end
	return folder
end

---------------------------------------------------------------------------------------------
-- Bordi del sentiero: file di sassi e tronchi semi-interrati lungo i margini (solo decorazione)
---------------------------------------------------------------------------------------------
local EDGE_PROPS = {
	Meadow = { "EdgeStones", "LogBorder" },
	Forest = { "LogBorder", "LogBorder", "EdgeStones" },
	Canyon = { "EdgeStones" },
	Crystal = { "EdgeStones" },
	Crater = { "EdgeStones" },
}

function Scenery.TrailEdges(parent: Instance, assets, terrainHeight: (number, number) -> number)
	local folder = Build.Model("TrailEdges", parent)
	local rng = Random.new(11)
	local function blocked(s: number, side: number): boolean
		for _, sh in MapLayout.Shelters do
			if side > 0 and math.abs(sh.s - s) < 14 then
				return true
			end
		end
		for _, n in MapLayout.Nests do
			if math.abs(n.s - s) < 7 then
				return true
			end
		end
		return false
	end
	local s = 24
	local count = 0
	while s < MapLayout.PathLength - 12 do
		for _, side in { 1, -1 } do
			local at = s + (if side < 0 then 8 else 0) + rng:NextNumber(-3, 3)
			local _, _, zone = MapLayout.PathPoint(at)
			local names = EDGE_PROPS[zone]
			if names and not blocked(at, side) then
				local name = names[rng:NextInteger(1, #names)]
				local model = assets.Clone("Props", name)
				if model then
					-- l'asse lungo del modello (X) segue il bordo del sentiero
					local cf = MapLayout.EdgeFrame(at, side, 1.4)
					local y = terrainHeight(cf.Position.X, cf.Position.Z)
					model:ScaleTo(rng:NextNumber(0.9, 1.25))
					model:PivotTo(
						CFrame.new(cf.Position.X, y - 0.25, cf.Position.Z)
							* cf.Rotation
							* CFrame.Angles(0, rng:NextNumber(-0.15, 0.15), 0)
					)
					if name == "EdgeStones" and ROCK_TINT[zone] then
						for _, d in model:GetDescendants() do
							if d:IsA("BasePart") and d:GetAttribute("Role") == "skin" then
								d.Color = ROCK_TINT[zone]
							end
						end
					end
					CollectionService:AddTag(model, "SmallDecor")
					model.Parent = folder
					count += 1
				end
			end
		end
		s += 16
	end
	folder:SetAttribute("Count", count)
	return folder
end

---------------------------------------------------------------------------------------------
-- Tana dei Mostri: portale con il cancello in fondo al cratere, puntelli e lanterne lungo il
-- tunnel, e la grotta con l'altare dell'uovo Ultra, le statue dei cinque giganti, cristalli e
-- occhi che brillano nel buio
---------------------------------------------------------------------------------------------
local DEN_STONE = Color3.fromRGB(58, 50, 64)
local DEN_STONE_LIGHT = Color3.fromRGB(92, 82, 100)
local DEN_LAVA = Color3.fromRGB(255, 104, 34)
local DEN_EYES = Color3.fromRGB(255, 36, 64)
local DEN_BONE = Color3.fromRGB(238, 226, 200)

local function denLight(parent: Instance, color: Color3, range: number, brightness: number)
	local l = Instance.new("PointLight")
	l.Color = color
	l.Range = range
	l.Brightness = brightness
	l.Shadows = false
	l.Parent = parent
end

-- Torcia: bastone con fiamma, fuoco e luce (cf = base)
local function denTorch(folder: Instance, cf: CFrame)
	Build.Part({
		name = "TorchStick",
		size = Vector3.new(0.7, 4, 0.7),
		cframe = cf * CFrame.new(0, 2, 0),
		color = WOOD_DARK,
		material = Enum.Material.Wood,
		collide = false,
		parent = folder,
	})
	local flame = Build.Part({
		name = "TorchFlame",
		size = Vector3.new(1, 1.1, 1),
		cframe = cf * CFrame.new(0, 4.4, 0),
		color = DEN_LAVA,
		material = Enum.Material.Neon,
		collide = false,
		castShadow = false,
		parent = folder,
	})
	local fire = Instance.new("Fire")
	fire.Size = 3
	fire.Heat = 7
	fire.Color = Color3.fromRGB(255, 140, 50)
	fire.SecondaryColor = Color3.fromRGB(255, 60, 20)
	fire.Parent = flame
	denLight(flame, Color3.fromRGB(255, 150, 80), 26, 1.6)
end

-- Coppia di occhi luminosi (cf: centro fra i due occhi, rivolto verso chi guarda)
local function denEyes(folder: Instance, cf: CFrame, size: number, color: Color3)
	for _, sx in { -1, 1 } do
		Build.Part({
			name = "Eye",
			size = Vector3.new(size, size, size),
			cframe = cf * CFrame.new(sx * size * 0.9, 0, 0),
			color = color,
			material = Enum.Material.Neon,
			shape = Enum.PartType.Ball,
			collide = false,
			castShadow = false,
			parent = folder,
		})
	end
end

-- Statua di pietra di un gigante Ultra: stesso modello del pet, pietra scura e occhi accesi
local function denStatue(folder: Instance, petId: string, cf: CFrame, height: number)
	local model = Visuals.MakePet(petId, "None", "Normal", height)
	model.Name = "Statue" .. petId
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			local role = d:GetAttribute("Role")
			d.Anchored = true
			d.CanCollide = false
			d.CanTouch = false
			if role == "eye" or role == "glow" then
				d.Material = Enum.Material.Neon
				d.Color = if role == "eye" then DEN_EYES else DEN_LAVA
			else
				local shade = if role == "detail" then 0.8 elseif role == "shine" then 0.65 else 1
				d.Material = Enum.Material.Slate
				d.Color = Color3.new(0.43 * shade, 0.39 * shade, 0.46 * shade)
				d.Reflectance = 0
			end
		elseif d:IsA("ParticleEmitter") or d:IsA("Beam") or d:IsA("Light") or d:IsA("Trail") then
			d:Destroy()
		end
	end
	model:SetAttribute("Giant", false)
	model:PivotTo(cf)
	model.Parent = folder
	-- dentro la statua non si passa: un cilindro invisibile al centro
	local _, size = model:GetBoundingBox()
	local r = math.min(size.X, size.Z) * 0.32
	Build.Part({
		name = "StatueCollider",
		size = Vector3.new(size.Y * 0.8, r * 2, r * 2),
		cframe = cf * CFrame.new(0, size.Y * 0.4, 0) * CFrame.Angles(0, 0, math.rad(90)),
		shape = Enum.PartType.Cylinder,
		transparency = 1,
		query = false,
		castShadow = false,
		parent = folder,
	})
	return model
end

function Scenery.Den(parent: Instance, assets)
	local folder = Build.Model("Den", parent)
	local den = MapLayout.Den
	local cave = den.Cave
	local floorY = cave.center.Y

	-- portale: due colonne, architrave con la faccia di un mostro (occhi e denti), insegna, torce
	local gate = MapLayout.DenGateFrame()
	for _, sx in { -1, 1 } do
		Build.Part({
			name = "PortalPillar",
			size = Vector3.new(5, 24, 5),
			cframe = gate * CFrame.new(sx * 11, 9, 0),
			color = DEN_STONE,
			material = Enum.Material.Slate,
			parent = folder,
		})
		Build.Part({
			name = "PortalBase",
			size = Vector3.new(6.4, 1.6, 6.4),
			cframe = gate * CFrame.new(sx * 11, 0.8, 0),
			color = DEN_STONE_LIGHT,
			material = Enum.Material.Slate,
			parent = folder,
		})
		denTorch(folder, gate * CFrame.new(sx * 15.5, 0, -2.5))
	end
	Build.Part({
		name = "PortalLintel",
		size = Vector3.new(30, 6, 6),
		cframe = gate * CFrame.new(0, 21, 0),
		color = DEN_STONE,
		material = Enum.Material.Slate,
		parent = folder,
	})
	denEyes(folder, gate * CFrame.new(0, 22, -3.1), 2.4, DEN_EYES)
	for k = -3, 3 do
		Build.Part({
			name = "Tooth",
			class = "WedgePart",
			size = Vector3.new(1.4, 2.6, 1.2),
			cframe = gate * CFrame.new(k * 2.4, 16.7, -2.2) * CFrame.Angles(math.rad(180), 0, 0),
			color = DEN_BONE,
			material = Enum.Material.SmoothPlastic,
			collide = false,
			parent = folder,
		})
	end
	for _, sx in { -1, 1 } do
		local spikes = assets.Clone("Props", "ObsidianSpikes")
		if spikes then
			spikes:ScaleTo(1.6)
			spikes:PivotTo(gate * CFrame.new(sx * 9, 24, 0) * CFrame.Angles(0, sx * 0.6, 0))
			spikes.Parent = folder
		end
	end
	Build.Sign(folder, gate * CFrame.new(0, 27.5, -1.5), Vector3.new(26, 5, 1), "DenSign", nil, {
		bg = Color3.fromRGB(44, 12, 28),
		text = Color3.fromRGB(255, 72, 96),
	})
	-- barriera: rossa e solida per chi non ha sbloccato la Tana (il client la apre a chi l'ha sbloccata)
	local barrier = Build.Part({
		name = "DenGate",
		size = Vector3.new(18, 16, 0.8),
		cframe = gate * CFrame.new(0, 8, 0),
		color = Color3.fromRGB(255, 50, 70),
		material = Enum.Material.ForceField,
		transparency = 0.25,
		castShadow = false,
		parent = folder,
	})
	CollectionService:AddTag(barrier, "DenGate")
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "DenPrompt"
	prompt.ActionText = "UNLOCK"
	prompt.ObjectText = tostring(den.UnlockPrice)
	prompt.HoldDuration = 0.6
	prompt.MaxActivationDistance = 14
	prompt.RequiresLineOfSight = false
	prompt.Style = Enum.ProximityPromptStyle.Custom
	prompt:SetAttribute("Kind", "DenGate")
	prompt.Parent = barrier
	denLight(barrier, Color3.fromRGB(255, 70, 90), 18, 1.2)

	-- pavimenti: lastre di basalto spesse lungo il tunnel (la sommita' e' la quota del pavimento, il
	-- fondo affonda nel terreno, cosi' sotto non restano vuoti) e un disco per la grotta
	local pts = den.Tunnel
	local FLOOR_DEPTH = 8
	local floorColor = Color3.fromRGB(52, 46, 58)
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local mid = (a + b) / 2
		Build.Part({
			name = "TunnelFloor",
			size = Vector3.new(20, FLOOR_DEPTH, (b - a).Magnitude),
			cframe = CFrame.lookAt(mid, mid + (b - a)) * CFrame.new(0, -FLOOR_DEPTH / 2, 0),
			color = floorColor,
			material = Enum.Material.Basalt,
			parent = folder,
		})
		-- nelle curve un disco inclinato come la media delle due pendenze chiude lo spicchio fra le
		-- lastre, appena sotto il pavimento (cosi' non sporge da nessuna delle due)
		if i > 1 then
			local dirIn = (a - pts[i - 1]).Unit
			local dirOut = (b - a).Unit
			local along = (dirIn + dirOut).Unit
			local right = along:Cross(Vector3.yAxis).Unit
			local up = right:Cross(along).Unit
			local slopeIn = dirIn.Y / Vector2.new(dirIn.X, dirIn.Z).Magnitude
			local slopeOut = dirOut.Y / Vector2.new(dirOut.X, dirOut.Z).Magnitude
			local sink = 0.06 + 10 * math.abs(slopeOut - slopeIn) / 2
			Build.Part({
				name = "TunnelFloorJoint",
				size = Vector3.new(FLOOR_DEPTH, 20, 20),
				cframe = CFrame.fromMatrix(a - up * (FLOOR_DEPTH / 2 + sink), up, along),
				color = floorColor,
				material = Enum.Material.Basalt,
				shape = Enum.PartType.Cylinder,
				parent = folder,
			})
		end
	end
	Build.Part({
		name = "CaveFloor",
		size = Vector3.new(FLOOR_DEPTH, (cave.radius + 4) * 2, (cave.radius + 4) * 2),
		cframe = CFrame.new(cave.center - Vector3.new(0, FLOOR_DEPTH / 2 + 0.04, 0))
			* CFrame.Angles(0, 0, math.rad(90)),
		color = floorColor,
		material = Enum.Material.Basalt,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	Build.Part({
		name = "LavaRing",
		size = Vector3.new(0.2, 48, 48),
		cframe = CFrame.new(cave.center + Vector3.new(0, 0.06, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = Color3.fromRGB(255, 120, 40),
		material = Enum.Material.CrackedLava,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})

	-- tunnel: puntelli di legno con una lanterna ogni 16 stud, crepe di lava lungo i bordi
	local acc = 0
	local nextSupport = den.GateZ - pts[1].Z + 10
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local len = (b - a).Magnitude
		local flat = (b - a) * Vector3.new(1, 0, 1)
		while nextSupport <= acc + len do
			local t = (nextSupport - acc) / len
			local p = a:Lerp(b, t)
			if (p - cave.center).Magnitude > cave.radius + 2 then
				local frame = CFrame.lookAt(p, p + flat)
				for _, sx in { -1, 1 } do
					Build.Part({
						name = "SupportPost",
						size = Vector3.new(1.6, 11.6, 1.6),
						cframe = frame * CFrame.new(sx * 7.4, 5.8, 0),
						color = WOOD_DARK,
						material = Enum.Material.Wood,
						parent = folder,
					})
				end
				Build.Part({
					name = "SupportBeam",
					size = Vector3.new(17, 1.4, 1.8),
					cframe = frame * CFrame.new(0, 11.2, 0),
					color = WOOD,
					material = Enum.Material.Wood,
					parent = folder,
				})
				local lantern = Build.Part({
					name = "Lantern",
					size = Vector3.new(0.9, 1.3, 0.9),
					cframe = frame * CFrame.new(0, 9.7, 0),
					color = Color3.fromRGB(255, 176, 90),
					material = Enum.Material.Neon,
					collide = false,
					castShadow = false,
					parent = folder,
				})
				denLight(lantern, Color3.fromRGB(255, 160, 90), 26, 1.5)
			end
			nextSupport += 16
		end
		if a.Z >= den.GateZ - 1 then
			local frame = CFrame.lookAt((a + b) / 2, (a + b) / 2 + (b - a))
			for _, sx in { -1, 1 } do
				Build.Part({
					name = "LavaCrack",
					size = Vector3.new(0.6, 0.22, len - 3),
					cframe = frame * CFrame.new(sx * 7.6, 0.06, 0),
					color = DEN_LAVA,
					material = Enum.Material.Neon,
					collide = false,
					castShadow = false,
					parent = folder,
				})
			end
		end
		acc += len
	end

	-- grotta: pedana a due gradini, altare con l'uovo Ultra, anello di rune
	Build.Part({
		name = "Dais",
		size = Vector3.new(1.2, 28, 28),
		cframe = CFrame.new(cave.center + Vector3.new(0, 0.6, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = DEN_STONE,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	Build.Part({
		name = "DaisTop",
		size = Vector3.new(1.2, 17, 17),
		cframe = CFrame.new(cave.center + Vector3.new(0, 1.8, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = DEN_STONE_LIGHT,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	local altarTop = den.Altar.Y
	Build.Part({
		name = "Altar",
		size = Vector3.new(altarTop - 0.6 - (floorY + 2.4), 4.6, 4.6),
		cframe = CFrame.new(cave.center.X, (altarTop - 0.6 + floorY + 2.4) / 2, cave.center.Z)
			* CFrame.Angles(0, 0, math.rad(90)),
		color = DEN_STONE,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	local altarCap = Build.Part({
		name = "AltarCap",
		size = Vector3.new(0.6, 6.4, 6.4),
		cframe = CFrame.new(cave.center.X, altarTop - 0.3, cave.center.Z) * CFrame.Angles(0, 0, math.rad(90)),
		color = Color3.fromRGB(30, 22, 34),
		material = Enum.Material.Basalt,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	denLight(altarCap, Color3.fromRGB(255, 70, 100), 30, 2)
	for k = 1, 24 do
		local ang = k / 24 * math.pi * 2
		local p = cave.center + Vector3.new(math.cos(ang) * 11.4, 1.24, math.sin(ang) * 11.4)
		Build.Part({
			name = "Rune",
			size = Vector3.new(1.6, 0.1, 0.5),
			cframe = CFrame.lookAt(p, cave.center + Vector3.new(0, 1.24, 0)),
			color = Color3.fromRGB(255, 50, 90),
			material = Enum.Material.Neon,
			collide = false,
			castShadow = false,
			parent = folder,
		})
	end
	-- luce generale della grotta (rosso fuoco dall'alto)
	local lamp = Build.Part({
		name = "CaveLight",
		size = Vector3.new(1, 1, 1),
		cframe = CFrame.new(cave.center + Vector3.new(0, 26, 0)),
		transparency = 1,
		collide = false,
		query = false,
		castShadow = false,
		parent = folder,
	})
	denLight(lamp, Color3.fromRGB(255, 120, 90), 60, 1.4)

	-- statue dei giganti lungo le pareti, rivolte verso l'altare; l'ingresso (nord, -Z) resta libero
	local statues = {
		{ id = "InfernoKomodo", angle = 52, height = 17 },
		{ id = "TitanRex", angle = 116, height = 30 },
		{ id = "PentaDragon", angle = 180, height = 32 },
		{ id = "ThunderGriffin", angle = 244, height = 30 },
		{ id = "VenomWidow", angle = 308, height = 16 },
	}
	for _, st in statues do
		local a = math.rad(st.angle)
		local dir = Vector3.new(math.sin(a), 0, -math.cos(a))
		local base = cave.center + dir * 40
		local plinth = Build.Part({
			name = "Plinth",
			size = Vector3.new(16, 3, 16),
			cframe = CFrame.lookAt(base + Vector3.new(0, 1.5, 0), cave.center + Vector3.new(0, 1.5, 0)),
			color = DEN_STONE,
			material = Enum.Material.Slate,
			parent = folder,
		})
		denStatue(
			folder,
			st.id,
			CFrame.lookAt(base + Vector3.new(0, 3, 0), cave.center + Vector3.new(0, 3, 0)),
			st.height
		)
		-- luce rossa dal basso sulla statua
		local up = Instance.new("SpotLight")
		up.Face = Enum.NormalId.Top
		up.Angle = 70
		up.Range = 40
		up.Brightness = 3
		up.Color = Color3.fromRGB(255, 90, 60)
		up.Shadows = false
		up.Parent = plinth
	end
	for _, angle in { 18, 342 } do
		local a = math.rad(angle)
		denTorch(folder, CFrame.new(cave.center + Vector3.new(math.sin(a), 0, -math.cos(a)) * 30))
	end

	-- cristalli viola fra le statue e ai lati dell'ingresso
	for k, angle in { 20, 84, 148, 212, 276, 340 } do
		local a = math.rad(angle)
		local dir = Vector3.new(math.sin(a), 0, -math.cos(a))
		local crystal = assets.Clone("Props", if k % 2 == 0 then "CrystalCluster1" else "CrystalCluster2")
		if crystal then
			crystal:ScaleTo(2.4)
			crystal:PivotTo(CFrame.new(cave.center + dir * 44 - Vector3.new(0, 0.5, 0)) * CFrame.Angles(0, a, 0))
			crystal.Parent = folder
			local glow = crystal.PrimaryPart or crystal:FindFirstChildWhichIsA("BasePart")
			if glow then
				denLight(glow, Color3.fromRGB(190, 90, 255), 24, 1.3)
			end
		end
	end

	-- fumo e bagliore dalla caldera in cima al vulcano: si vede da tutta la montagna
	local volcano = den.Volcano.center
	local vent = Build.Part({
		name = "VolcanoSmoke",
		size = Vector3.new(30, 2, 30),
		cframe = CFrame.new(volcano.X, volcano.Y - 34, volcano.Z),
		transparency = 1,
		collide = false,
		query = false,
		castShadow = false,
		parent = folder,
	})
	local smoke = Instance.new("ParticleEmitter")
	smoke.Texture = "rbxasset://textures/particles/smoke_main.dds"
	smoke.Color = ColorSequence.new(Color3.fromRGB(90, 80, 90), Color3.fromRGB(170, 160, 170))
	smoke.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 14), NumberSequenceKeypoint.new(1, 46) })
	smoke.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.6),
		NumberSequenceKeypoint.new(0.6, 0.75),
		NumberSequenceKeypoint.new(1, 1),
	})
	smoke.Lifetime = NumberRange.new(9, 14)
	smoke.Rate = 5
	smoke.Speed = NumberRange.new(8, 12)
	smoke.SpreadAngle = Vector2.new(12, 12)
	smoke.Acceleration = Vector3.new(2, 1, 1)
	smoke.RotSpeed = NumberRange.new(-10, 10)
	smoke.Rotation = NumberRange.new(0, 360)
	smoke.EmissionDirection = Enum.NormalId.Top
	smoke.LightInfluence = 0.6
	smoke.Parent = vent
	denLight(vent, Color3.fromRGB(255, 110, 40), 60, 3)

	-- occhi nel buio sulle pareti: qualcosa guarda chi entra
	local rng = Random.new(66)
	for k = 1, 12 do
		local angle = (k + rng:NextNumber(-0.3, 0.3)) / 12 * 360
		if math.abs(((angle + 180) % 360) - 180) < 18 then
			continue -- li' c'e' l'apertura del tunnel
		end
		local a = math.rad(angle)
		local dir = Vector3.new(math.sin(a), 0, -math.cos(a))
		local y = floorY + rng:NextNumber(9, 22)
		local p = Vector3.new(cave.center.X, y, cave.center.Z) + dir * (cave.radius - 1.5)
		local color = if k % 3 == 0 then Color3.fromRGB(255, 220, 60) else DEN_EYES
		denEyes(folder, CFrame.lookAt(p, Vector3.new(cave.center.X, y, cave.center.Z)), 0.8, color)
	end
	return folder
end

return Scenery
