-- Elementi fissi della mappa: piazza della vetta, rifugi anti-valanga, mare di nuvole, decorazioni.

local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
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
	-- pavimentazione circolare della piazza (si unisce ai cancelli dei lotti)
	Build.Part({
		name = "Plaza",
		size = Vector3.new(1.2, 206, 206),
		cframe = CFrame.new(c + Vector3.new(0, 0.2, 0)) * CFrame.Angles(0, 0, math.rad(90)),
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
	-- viale verso la rampa del sentiero
	Build.Part({
		name = "Avenue",
		size = Vector3.new(40, 1.2, 64),
		cframe = CFrame.new(c.X, c.Y + 0.2, 130),
		color = Color3.fromRGB(236, 222, 196),
		material = Enum.Material.Slate,
		parent = folder,
	})
	-- arco d'ingresso al sentiero con il nome del gioco
	for _, sx in { -1, 1 } do
		Build.Part({
			name = "ArchPost",
			size = Vector3.new(4, 26, 4),
			cframe = CFrame.new(sx * 23, c.Y + 13, 158),
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
	for _ = 1, 260 do
		local a = rng:NextNumber(0, math.pi * 2)
		local r = rng:NextNumber(200, 1100)
		local x, z = math.cos(a) * r, 200 + math.sin(a) * r * 1.2
		local d = rng:NextNumber(40, 110)
		Build.Part({
			name = "Puff",
			size = Vector3.new(d * rng:NextNumber(1.2, 1.8), d * 0.55, d),
			cframe = CFrame.new(x, y - 4 + rng:NextNumber(0, 10), z) * CFrame.Angles(0, rng:NextNumber(0, 6.28), 0),
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

return Scenery
