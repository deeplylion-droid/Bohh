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
		Build.Part({ name = "Floor", size = Vector3.new(size.X + 2, 0.6, size.Z + 2), cframe = cf * CFrame.new(0, 0.3, 0), color = WOOD, material = Enum.Material.WoodPlanks, parent = hut })
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
		Build.Part({ name = "Back", size = Vector3.new(size.X, size.Y, 0.8), cframe = cf * CFrame.new(0, size.Y / 2, size.Z / 2), color = WOOD, material = Enum.Material.WoodPlanks, parent = hut })
		for _, sx in { -1, 1 } do
			Build.Part({ name = "Side", size = Vector3.new(0.8, size.Y * 0.55, size.Z), cframe = cf * CFrame.new(sx * size.X / 2, size.Y * 0.275, 0), color = WOOD, material = Enum.Material.WoodPlanks, parent = hut })
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
		local sign = Build.Sign(hut, cf * CFrame.new(0, size.Y + 0.2, -size.Z / 2 - 0.5), Vector3.new(10, 2.6, 0.4), "Shelter", nil, {
			bg = Color3.fromRGB(110, 230, 120),
			text = Color3.fromRGB(20, 70, 30),
		})
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
local DECOR: { [string]: { { name: string, count: number, scale: { number }, edge: boolean? } } } = {
	Summit = { { name = "PineSnowy", count = 40, scale = { 1.4, 2.2 } }, { name = "Rock2", count = 18, scale = { 1.2, 2.4 } } },
	Meadow = {
		{ name = "PineTree", count = 30, scale = { 1.3, 2.0 } },
		{ name = "Bush1", count = 24, scale = { 1.0, 1.5 } },
		{ name = "Flowers1", count = 60, scale = { 1.4, 2.0 } },
		{ name = "Flowers2", count = 60, scale = { 1.4, 2.0 } },
		{ name = "Grass1", count = 120, scale = { 2.0, 3.0 } },
		{ name = "Rock1", count = 26, scale = { 0.8, 1.6 }, edge = true },
	},
	Forest = {
		{ name = "PineTree", count = 70, scale = { 1.8, 2.8 } },
		{ name = "Bush1", count = 30, scale = { 1.2, 1.8 } },
		{ name = "Grass1", count = 80, scale = { 2.0, 3.0 } },
		{ name = "Rock3", count = 26, scale = { 0.8, 1.6 }, edge = true },
	},
	Canyon = { { name = "Rock2", count = 40, scale = { 1.0, 2.8 } }, { name = "Rock3", count = 30, scale = { 0.8, 1.6 }, edge = true } },
	Crystal = { { name = "Rock1", count = 30, scale = { 1.0, 2.4 } }, { name = "Rock2", count = 24, scale = { 0.8, 1.4 }, edge = true } },
	Crater = { { name = "Rock3", count = 30, scale = { 1.0, 2.6 } } },
}

function Scenery.Decor(parent: Instance, assets, terrainHeight: (number, number) -> (number, string, string))
	local folder = Build.Model("Decor", parent)
	local rng = Random.new(7)
	local half = MapLayout.PathWidth / 2
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
				-- evita pendii troppo ripidi (gli oggetti sembrerebbero sospesi)
				local h2 = terrainHeight(x + 2, z + 2)
				if math.abs(h2 - h) > 3.2 then
					continue
				end
				local model = assets.Clone("Props", item.name)
				if not model then
					break
				end
				local s = rng:NextNumber(item.scale[1], item.scale[2])
				model:ScaleTo(s)
				model:PivotTo(CFrame.new(x, h - 0.4, z) * CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), 0))
				model.Parent = folder
				placed += 1
			end
		end
	end
	local _ = half
	return folder
end

return Scenery
