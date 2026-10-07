-- Il bosco: terreno, sentieri e punti di interesse (creati una volta) e alberi (rigenerati a ogni notte).
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))

local MAP = Config.MAP
local SIZE = MAP.SIZE
local HALF = SIZE / 2
local POIS = MAP.POIS
local LAKE = MAP.LAKE

local Forest = {}
Forest.HALF = HALF
Forest.POIS = POIS
Forest.STATION = POIS[1].pos

-- Sentieri: dalla stazione a ogni punto di interesse, più qualche collegamento esterno
local PATHS = {}
for i = 2, #POIS do
	table.insert(PATHS, { POIS[1].pos, POIS[i].pos })
end
table.insert(PATHS, { POIS[2].pos, POIS[6].pos }) -- torre - miniera
table.insert(PATHS, { POIS[3].pos, POIS[4].pos }) -- campeggio - lago
table.insert(PATHS, { POIS[4].pos, POIS[5].pos }) -- lago - capanno
Forest.PATHS = PATHS

local DENSITY = { ["Pineta fitta"] = 1, ["Ruderi del campeggio"] = 0.6, Palude = 0.55, Miniera = 0.45 }

local WOOD = Color3.fromRGB(105, 75, 50)
local DARK_WOOD = Color3.fromRGB(70, 50, 35)

local function make(className: string, parent: Instance?, props: { [string]: any }): any
	local inst = Instance.new(className)
	if inst:IsA("BasePart") then
		inst.Anchored = true
		inst.TopSurface = Enum.SurfaceType.Smooth
		inst.BottomSurface = Enum.SurfaceType.Smooth
	end
	for key, value in props do
		(inst :: any)[key] = value
	end
	inst.Parent = parent
	return inst
end
Forest.make = make

local function flat(v: Vector3): Vector3
	return Vector3.new(v.X, 0, v.Z)
end

function Forest.biomeAt(pos: Vector3): string
	if pos.X >= 0 and pos.Z < 0 then
		return "Pineta fitta"
	elseif pos.X < 0 and pos.Z < 0 then
		return "Ruderi del campeggio"
	elseif pos.X < 0 then
		return "Palude"
	end
	return "Miniera"
end

function Forest.distToSegment(p: Vector3, a: Vector3, b: Vector3): number
	local ab = flat(b - a)
	local ap = flat(p - a)
	local t = math.clamp(ap:Dot(ab) / ab:Dot(ab), 0, 1)
	return (ap - ab * t).Magnitude
end

function Forest.distToPath(p: Vector3): number
	local best = math.huge
	for _, seg in PATHS do
		best = math.min(best, Forest.distToSegment(p, seg[1], seg[2]))
	end
	return best
end

function Forest.inLake(p: Vector3, margin: number?): boolean
	return (flat(p) - flat(LAKE.center)).Magnitude < LAKE.radius + (margin or 0)
end

function Forest.inStation(p: Vector3, margin: number?): boolean
	return flat(p - Forest.STATION).Magnitude < MAP.STATION_RADIUS + (margin or 0)
end

function Forest.inBounds(p: Vector3, margin: number?): boolean
	local limit = HALF - (margin or 0)
	return math.abs(p.X) < limit and math.abs(p.Z) < limit
end

-- Terreno libero da POI, sentieri e lago (dove possono crescere gli alberi)
function Forest.isOpenGround(p: Vector3, margin: number): boolean
	for _, poi in POIS do
		if flat(p - poi.pos).Magnitude < poi.radius + margin then
			return false
		end
	end
	return not Forest.inLake(p, margin) and Forest.distToPath(p) >= MAP.PATH_WIDTH / 2 + margin
end

function Forest.clampToMap(p: Vector3): Vector3
	local limit = HALF - 15
	return Vector3.new(math.clamp(p.X, -limit, limit), 0, math.clamp(p.Z, -limit, limit))
end

-- Punto a terra casuale tra minR e maxR da center, dentro la mappa e fuori dal lago
function Forest.randomGround(rng: Random, center: Vector3, minR: number, maxR: number): Vector3
	local p = center
	for _ = 1, 25 do
		local angle = rng:NextNumber(0, math.pi * 2)
		local r = rng:NextNumber(minR, maxR)
		p = Forest.clampToMap(center + Vector3.new(math.cos(angle) * r, 0, math.sin(angle) * r))
		if not Forest.inLake(p, 4) then
			return p
		end
	end
	return Forest.clampToMap(p)
end

function Forest.nearestPoi(pos: Vector3)
	local best, bestDist = POIS[1], math.huge
	for _, poi in POIS do
		local d = flat(pos - poi.pos).Magnitude
		if d < bestDist then
			best, bestDist = poi, d
		end
	end
	return best, bestDist
end

-- Descrizione leggibile di una posizione ("vicino a Lago" oppure il bioma)
function Forest.describe(pos: Vector3): string
	local poi, dist = Forest.nearestPoi(pos)
	if dist < poi.radius + 45 then
		return "vicino a " .. poi.name
	end
	return Forest.biomeAt(pos)
end

---------------------------------------------------------------------------------------------
-- Costruzione della mappa (una volta sola)

local function buildTerrain()
	local terrain = workspace.Terrain
	terrain:Clear()
	local depth = 12
	local y = -depth / 2
	terrain:FillBlock(CFrame.new(0, y, 0), Vector3.new(SIZE + 120, depth, SIZE + 120), Enum.Material.Grass)
	local q = HALF / 2
	terrain:FillBlock(CFrame.new(-q, y, -q), Vector3.new(HALF, depth, HALF), Enum.Material.LeafyGrass)
	terrain:FillBlock(CFrame.new(-q, y, q), Vector3.new(HALF, depth, HALF), Enum.Material.Mud)
	terrain:FillBlock(CFrame.new(q, y, q), Vector3.new(HALF, depth, HALF), Enum.Material.Slate)

	for _, seg in PATHS do
		local a, b = seg[1], seg[2]
		local mid = (a + b) / 2
		local length = flat(b - a).Magnitude
		local cf = CFrame.lookAt(Vector3.new(mid.X, y, mid.Z), Vector3.new(b.X, y, b.Z))
		terrain:FillBlock(cf, Vector3.new(MAP.PATH_WIDTH, depth, length + MAP.PATH_WIDTH), Enum.Material.Ground)
	end
	-- La stazione su un piazzale di terra battuta
	terrain:FillCylinder(CFrame.new(0, y, 0), depth, MAP.STATION_RADIUS + 4, Enum.Material.Ground)

	-- Lago
	local c = LAKE.center
	terrain:FillCylinder(CFrame.new(c.X, y, c.Z), depth + 1, LAKE.radius, Enum.Material.Air)
	terrain:FillCylinder(CFrame.new(c.X, -6.5, c.Z), 11, LAKE.radius, Enum.Material.Water)
end

local function buildStation(parent: Instance)
	local m = make("Model", parent, { Name = "RangerStation" })
	local W, D, H = 44, 32, 12
	local wall = Color3.fromRGB(95, 80, 60)
	make("Part", m, {
		Name = "Pavimento",
		Size = Vector3.new(W, 1, D),
		CFrame = CFrame.new(0, 0.5, 0),
		Color = WOOD,
		Material = Enum.Material.WoodPlanks,
	})
	local function wallPart(size: Vector3, pos: Vector3)
		return make("Part", m, { Size = size, CFrame = CFrame.new(pos), Color = wall, Material = Enum.Material.WoodPlanks })
	end
	local wy = 1 + H / 2
	wallPart(Vector3.new(W, H, 1), Vector3.new(0, wy, -D / 2 + 0.5))
	wallPart(Vector3.new(1, H, D), Vector3.new(-W / 2 + 0.5, wy, 0))
	wallPart(Vector3.new(1, H, D), Vector3.new(W / 2 - 0.5, wy, 0))
	local door = 8
	local side = (W - door) / 2
	wallPart(Vector3.new(side, H, 1), Vector3.new(-(door / 2 + side / 2), wy, D / 2 - 0.5))
	wallPart(Vector3.new(side, H, 1), Vector3.new(door / 2 + side / 2, wy, D / 2 - 0.5))
	local lintel = wallPart(Vector3.new(door, H - 8, 1), Vector3.new(0, 1 + 8 + (H - 8) / 2, D / 2 - 0.5))
	make("Part", m, {
		Name = "Tetto",
		Size = Vector3.new(W + 4, 1, D + 4),
		CFrame = CFrame.new(0, 1 + H + 0.5, 0),
		Color = DARK_WOOD,
		Material = Enum.Material.Wood,
	})

	local sign = make("SurfaceGui", lintel, { Face = Enum.NormalId.Back, PixelsPerStud = 40 })
	make("TextLabel", sign, {
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Text = "RANGER STATION",
		TextScaled = true,
		Font = Enum.Font.GothamBold,
		TextColor3 = Color3.fromRGB(235, 220, 180),
	})

	local lamp = make("Part", m, {
		Name = "Lampada",
		Size = Vector3.new(3, 0.4, 3),
		CFrame = CFrame.new(0, H + 0.6, 0),
		Material = Enum.Material.Neon,
		Color = Color3.fromRGB(255, 220, 160),
		CanCollide = false,
	})
	make("PointLight", lamp, { Range = 40, Brightness = 1.6, Color = Color3.fromRGB(255, 210, 150), Shadows = true })
	local porch = make("Part", m, {
		Name = "LucePortico",
		Size = Vector3.new(1, 1, 0.4),
		CFrame = CFrame.new(0, 10, D / 2 + 0.3),
		Material = Enum.Material.Neon,
		Color = Color3.fromRGB(255, 220, 160),
		CanCollide = false,
	})
	make("PointLight", porch, { Range = 26, Brightness = 1.2, Color = Color3.fromRGB(255, 200, 140) })

	make("SpawnLocation", m, {
		Name = "Spawn",
		Size = Vector3.new(6, 0.4, 6),
		CFrame = CFrame.new(0, 1.2, 6),
		Neutral = true,
		Duration = 0,
		Color = Color3.fromRGB(80, 90, 70),
		Material = Enum.Material.Fabric,
	})

	local function prompt(part: BasePart, action: string, object: string)
		return make("ProximityPrompt", part, {
			ActionText = action,
			ObjectText = object,
			HoldDuration = 0.3,
			MaxActivationDistance = 9,
			RequiresLineOfSight = false,
		})
	end

	local desk = make("Part", m, {
		Name = "SalaDiControllo",
		Size = Vector3.new(12, 3, 3),
		CFrame = CFrame.new(0, 2.5, -D / 2 + 3),
		Color = Color3.fromRGB(60, 60, 65),
		Material = Enum.Material.Metal,
	})
	for i = -1, 1 do
		local screen = make("Part", m, {
			Size = Vector3.new(3.2, 2.2, 0.3),
			CFrame = CFrame.new(i * 3.8, 5.2, -D / 2 + 2.2),
			Material = Enum.Material.Neon,
			Color = Color3.fromRGB(40, 90, 70),
		})
		make("PointLight", screen, { Range = 8, Brightness = 0.6, Color = Color3.fromRGB(80, 200, 140) })
	end

	local crate = make("Part", m, {
		Name = "Rifornimento",
		Size = Vector3.new(4, 3, 4),
		CFrame = CFrame.new(-W / 2 + 4, 2.5, 0),
		Color = Color3.fromRGB(70, 90, 55),
		Material = Enum.Material.Wood,
	})
	local lab = make("Part", m, {
		Name = "Laboratorio",
		Size = Vector3.new(4, 3, 8),
		CFrame = CFrame.new(W / 2 - 4, 2.5, -4),
		Color = Color3.fromRGB(200, 205, 210),
		Material = Enum.Material.SmoothPlastic,
	})
	local labLight = make("Part", m, {
		Name = "LuceLaboratorio",
		Size = Vector3.new(0.8, 0.8, 0.8),
		CFrame = CFrame.new(W / 2 - 4, 4.4, -4),
		Material = Enum.Material.Neon,
		Color = Color3.fromRGB(120, 200, 255),
		Shape = Enum.PartType.Ball,
	})

	Forest.stationPrompts = {
		control = prompt(desk, "Apri il tablet", "Sala di controllo"),
		supply = prompt(crate, "Rifornisciti", "Dardi, torcia e visore"),
		lab = prompt(lab, "Analizza campioni", "Laboratorio"),
	}
	Forest.labLight = labLight
end

local function buildTower(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Torre" })
	local h = 22
	for _, x in { -4, 4 } do
		for _, z in { -4, 4 } do
			make("Part", m, { Size = Vector3.new(1, h, 1), CFrame = CFrame.new(pos + Vector3.new(x, h / 2, z)), Color = WOOD, Material = Enum.Material.Wood })
			make("Part", m, { Size = Vector3.new(0.6, 7, 0.6), CFrame = CFrame.new(pos + Vector3.new(x, h + 4.5, z)), Color = WOOD, Material = Enum.Material.Wood })
		end
	end
	make("Part", m, { Size = Vector3.new(10, 1, 10), CFrame = CFrame.new(pos + Vector3.new(0, h + 0.5, 0)), Color = WOOD, Material = Enum.Material.WoodPlanks })
	make("Part", m, { Size = Vector3.new(11, 0.6, 11), CFrame = CFrame.new(pos + Vector3.new(0, h + 8.3, 0)), Color = DARK_WOOD, Material = Enum.Material.Wood })
	make("Part", m, { Size = Vector3.new(10, 3, 0.4), CFrame = CFrame.new(pos + Vector3.new(0, h + 2.5, -4.8)), Color = WOOD, Material = Enum.Material.Wood })
	make("Part", m, { Size = Vector3.new(0.4, 3, 10), CFrame = CFrame.new(pos + Vector3.new(-4.8, h + 2.5, 0)), Color = WOOD, Material = Enum.Material.Wood })
	make("Part", m, { Size = Vector3.new(0.4, 3, 10), CFrame = CFrame.new(pos + Vector3.new(4.8, h + 2.5, 0)), Color = WOOD, Material = Enum.Material.Wood })
	make("TrussPart", m, { Size = Vector3.new(2, h, 2), CFrame = CFrame.new(pos + Vector3.new(0, h / 2, 6)), Color = DARK_WOOD })
end

local function buildCamp(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Campeggio" })
	local tents = {
		{ Vector3.new(-14, 0, -8), 25, Color3.fromRGB(120, 60, 40) },
		{ Vector3.new(10, 0, -14), -40, Color3.fromRGB(60, 80, 110) },
		{ Vector3.new(14, 0, 10), 70, Color3.fromRGB(110, 110, 60) },
	}
	for i, t in tents do
		local base = CFrame.new(pos + t[1]) * CFrame.Angles(0, math.rad(t[2]), 0)
		local h, len, d = 4, 7, 3
		make("WedgePart", m, { Size = Vector3.new(len, h, d), CFrame = base * CFrame.new(0, h / 2, -d / 2), Color = t[3], Material = Enum.Material.Fabric })
		if i ~= 2 then -- una tenda è crollata a metà
			make("WedgePart", m, {
				Size = Vector3.new(len, h, d),
				CFrame = base * CFrame.new(0, h / 2, d / 2) * CFrame.Angles(0, math.pi, 0),
				Color = t[3],
				Material = Enum.Material.Fabric,
			})
		end
	end
	for i = 0, 5 do
		local a = i / 6 * math.pi * 2
		make("Part", m, {
			Size = Vector3.new(1.2, 0.8, 1.2),
			CFrame = CFrame.new(pos + Vector3.new(math.cos(a) * 2, 0.4, math.sin(a) * 2)),
			Color = Color3.fromRGB(90, 90, 90),
			Material = Enum.Material.Slate,
		})
	end
	local embers = make("Part", m, {
		Size = Vector3.new(2, 0.3, 2),
		CFrame = CFrame.new(pos + Vector3.new(0, 0.2, 0)),
		Color = Color3.fromRGB(150, 50, 20),
		Material = Enum.Material.Neon,
		CanCollide = false,
	})
	make("PointLight", embers, { Range = 10, Brightness = 0.8, Color = Color3.fromRGB(255, 120, 50) })
	make("Part", m, { Size = Vector3.new(8, 0.5, 3), CFrame = CFrame.new(pos + Vector3.new(-4, 2.8, 12)), Color = WOOD, Material = Enum.Material.WoodPlanks })
	make("Part", m, { Size = Vector3.new(8, 0.4, 1), CFrame = CFrame.new(pos + Vector3.new(-4, 1.6, 10.3)), Color = WOOD, Material = Enum.Material.WoodPlanks })
	make("Part", m, { Size = Vector3.new(0.5, 2.6, 0.5), CFrame = CFrame.new(pos + Vector3.new(-7.5, 1.3, 12)), Color = WOOD })
	make("Part", m, { Size = Vector3.new(0.5, 2.6, 0.5), CFrame = CFrame.new(pos + Vector3.new(-0.5, 1.3, 12)), Color = WOOD })
end

local function buildDock(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Pontile" })
	local dir = flat(LAKE.center - pos).Unit
	local start = pos + dir * 6
	local cf = CFrame.lookAt(start, start + dir)
	local length = 22
	make("Part", m, {
		Size = Vector3.new(5, 0.5, length),
		CFrame = cf * CFrame.new(0, 0.5, -length / 2),
		Color = WOOD,
		Material = Enum.Material.WoodPlanks,
	})
	for i = 1, 3 do
		for _, x in { -2.2, 2.2 } do
			make("Part", m, {
				Size = Vector3.new(0.6, 8, 0.6),
				CFrame = cf * CFrame.new(x, -2.5, -i * length / 3),
				Color = DARK_WOOD,
				Material = Enum.Material.Wood,
			})
		end
	end
	make("Part", m, {
		Size = Vector3.new(3, 1, 7),
		CFrame = cf * CFrame.new(4.5, -0.6, -length + 4) * CFrame.Angles(0, 0.3, 0.15),
		Color = Color3.fromRGB(90, 60, 40),
		Material = Enum.Material.Wood,
	})
end

local function buildCabin(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Capanno" })
	local cf = CFrame.lookAt(pos, Vector3.new(Forest.STATION.X, 0, Forest.STATION.Z))
	local W, D, H = 14, 12, 9
	local function part(size: Vector3, offset: Vector3, color: Color3?)
		return make("Part", m, { Size = size, CFrame = cf * CFrame.new(offset), Color = color or DARK_WOOD, Material = Enum.Material.WoodPlanks })
	end
	part(Vector3.new(W, 1, D), Vector3.new(0, 0.5, 0), WOOD)
	part(Vector3.new(W, H, 1), Vector3.new(0, 1 + H / 2, D / 2 - 0.5))
	part(Vector3.new(1, H, D), Vector3.new(-W / 2 + 0.5, 1 + H / 2, 0))
	part(Vector3.new(1, H, D), Vector3.new(W / 2 - 0.5, 1 + H / 2, 0))
	part(Vector3.new(5, H, 1), Vector3.new(-4.5, 1 + H / 2, -D / 2 + 0.5))
	part(Vector3.new(5, H, 1), Vector3.new(4.5, 1 + H / 2, -D / 2 + 0.5))
	part(Vector3.new(4, 2, 1), Vector3.new(0, H, -D / 2 + 0.5))
	part(Vector3.new(W + 2, 1, D + 2), Vector3.new(0, H + 1.5, 0), Color3.fromRGB(55, 45, 40))
	part(Vector3.new(4, 2.6, 2.5), Vector3.new(3, 2.3, 2), WOOD)
end

local function buildMine(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Miniera" })
	local cf = CFrame.lookAt(pos, Vector3.new(Forest.STATION.X, 0, Forest.STATION.Z))
	local back = -cf.LookVector
	local terrain = workspace.Terrain
	terrain:FillBall(pos + back * 16 + Vector3.new(0, -4, 0), 20, Enum.Material.Rock)
	terrain:FillBall(pos + back * 22 + cf.RightVector * 14 + Vector3.new(0, -6, 0), 16, Enum.Material.Rock)
	terrain:FillBall(pos + back * 22 - cf.RightVector * 14 + Vector3.new(0, -6, 0), 15, Enum.Material.Rock)
	local function part(size: Vector3, offset: Vector3, color: Color3, material: Enum.Material?)
		return make("Part", m, { Size = size, CFrame = cf * CFrame.new(offset), Color = color, Material = material or Enum.Material.Wood })
	end
	part(Vector3.new(1.2, 10, 1.2), Vector3.new(-4, 5, 0), DARK_WOOD)
	part(Vector3.new(1.2, 10, 1.2), Vector3.new(4, 5, 0), DARK_WOOD)
	part(Vector3.new(10, 1.2, 1.4), Vector3.new(0, 10.4, 0), DARK_WOOD)
	part(Vector3.new(7, 9.6, 0.6), Vector3.new(0, 4.8, 1.2), Color3.fromRGB(8, 8, 10), Enum.Material.SmoothPlastic)
	part(Vector3.new(0.4, 0.3, 26), Vector3.new(-1.4, 0.15, -12), Color3.fromRGB(70, 60, 55), Enum.Material.Metal)
	part(Vector3.new(0.4, 0.3, 26), Vector3.new(1.4, 0.15, -12), Color3.fromRGB(70, 60, 55), Enum.Material.Metal)
	part(Vector3.new(3.6, 2.4, 4.5), Vector3.new(0, 1.6, -9), Color3.fromRGB(80, 70, 60), Enum.Material.CorrodedMetal)
	local lantern = part(Vector3.new(0.6, 0.9, 0.6), Vector3.new(3, 8.5, -0.8), Color3.fromRGB(255, 170, 80), Enum.Material.Neon)
	make("PointLight", lantern, { Range = 12, Brightness = 0.7, Color = Color3.fromRGB(255, 160, 80) })
end

local function buildBounds(parent: Instance)
	local m = make("Model", parent, { Name = "Confini" })
	local h = 120
	for _, info in {
		{ Vector3.new(SIZE + 20, h, 2), Vector3.new(0, h / 2, HALF + 1) },
		{ Vector3.new(SIZE + 20, h, 2), Vector3.new(0, h / 2, -HALF - 1) },
		{ Vector3.new(2, h, SIZE + 20), Vector3.new(HALF + 1, h / 2, 0) },
		{ Vector3.new(2, h, SIZE + 20), Vector3.new(-HALF - 1, h / 2, 0) },
	} do
		make("Part", m, { Size = info[1], CFrame = CFrame.new(info[2]), Transparency = 1, CanQuery = false })
	end
end

function Forest.build(world: Instance)
	local props = make("Folder", world, { Name = "Mappa" })
	buildTerrain()
	buildStation(props)
	buildTower(props, POIS[2].pos)
	buildCamp(props, POIS[3].pos)
	buildDock(props, POIS[4].pos)
	buildCabin(props, POIS[5].pos)
	buildMine(props, POIS[6].pos)
	buildBounds(props)
	Forest.trees = make("Folder", world, { Name = "Alberi" })
end

---------------------------------------------------------------------------------------------
-- Alberi procedurali

local function pine(folder: Instance, p: Vector3, rng: Random)
	local h = rng:NextNumber(20, 32)
	local trunk = rng:NextNumber(1.8, 2.6)
	make("Part", folder, {
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(h, trunk, trunk),
		CFrame = CFrame.new(p + Vector3.new(0, h / 2, 0)) * CFrame.Angles(0, 0, math.pi / 2),
		Color = DARK_WOOD,
		Material = Enum.Material.Wood,
		CastShadow = false,
	})
	local green = Color3.fromRGB(25 + rng:NextInteger(0, 15), 50 + rng:NextInteger(0, 20), 32)
	for i, layer in { { 0.42, 13 }, { 0.62, 10 }, { 0.82, 6.5 } } do
		local d = layer[2] * (h / 26)
		make("Part", folder, {
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(5 - i * 0.6, d, d),
			CFrame = CFrame.new(p + Vector3.new(0, h * layer[1], 0)) * CFrame.Angles(0, 0, math.pi / 2),
			Color = green,
			Material = Enum.Material.Grass,
			CanCollide = false,
			CastShadow = false,
		})
	end
end

local function broadleaf(folder: Instance, p: Vector3, rng: Random)
	local h = rng:NextNumber(14, 20)
	make("Part", folder, {
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(h, 2, 2),
		CFrame = CFrame.new(p + Vector3.new(0, h / 2, 0)) * CFrame.Angles(0, 0, math.pi / 2),
		Color = WOOD,
		Material = Enum.Material.Wood,
		CastShadow = false,
	})
	local d = rng:NextNumber(11, 16)
	make("Part", folder, {
		Shape = Enum.PartType.Ball,
		Size = Vector3.new(d, d, d),
		CFrame = CFrame.new(p + Vector3.new(0, h, 0)),
		Color = Color3.fromRGB(45, 65 + rng:NextInteger(0, 20), 35),
		Material = Enum.Material.Grass,
		CanCollide = false,
		CastShadow = false,
	})
end

local function deadTree(folder: Instance, p: Vector3, rng: Random)
	local h = rng:NextNumber(12, 20)
	local gray = Color3.fromRGB(85, 80, 72)
	make("Part", folder, {
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(h, 1.5, 1.5),
		CFrame = CFrame.new(p + Vector3.new(0, h / 2, 0)) * CFrame.Angles(0, 0, math.pi / 2 + rng:NextNumber(-0.08, 0.08)),
		Color = gray,
		Material = Enum.Material.Wood,
		CastShadow = false,
	})
	for _, side in { -1, 1 } do
		make("Part", folder, {
			Size = Vector3.new(0.6, rng:NextNumber(4, 7), 0.6),
			CFrame = CFrame.new(p + Vector3.new(0, h * rng:NextNumber(0.6, 0.85), 0))
				* CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), side * math.rad(40))
				* CFrame.new(0, 2.5, 0),
			Color = gray,
			Material = Enum.Material.Wood,
			CanCollide = false,
			CastShadow = false,
		})
	end
end

local function rock(folder: Instance, p: Vector3, rng: Random)
	local s = rng:NextNumber(3, 7)
	make("Part", folder, {
		Size = Vector3.new(s * rng:NextNumber(0.8, 1.4), s * 0.7, s),
		CFrame = CFrame.new(p + Vector3.new(0, s * 0.25, 0))
			* CFrame.Angles(rng:NextNumber(-0.3, 0.3), rng:NextNumber(0, math.pi), rng:NextNumber(-0.3, 0.3)),
		Color = Color3.fromRGB(95, 95, 100),
		Material = Enum.Material.Slate,
		CastShadow = false,
	})
end

function Forest.regenerate(rng: Random)
	local folder = Forest.trees
	folder:ClearAllChildren()
	local target = MAP.TREE_COUNT
	local placed, attempts = 0, 0
	while placed < target and attempts < target * 8 do
		attempts += 1
		local p = Vector3.new(rng:NextNumber(-HALF + 6, HALF - 6), 0, rng:NextNumber(-HALF + 6, HALF - 6))
		local biome = Forest.biomeAt(p)
		if rng:NextNumber() <= DENSITY[biome] and Forest.isOpenGround(p, 4) then
			placed += 1
			if biome == "Pineta fitta" then
				pine(folder, p, rng)
			elseif biome == "Ruderi del campeggio" then
				if rng:NextNumber() < 0.5 then broadleaf(folder, p, rng) else pine(folder, p, rng) end
			elseif biome == "Palude" then
				deadTree(folder, p, rng)
			else
				if rng:NextNumber() < 0.35 then rock(folder, p, rng) else pine(folder, p, rng) end
			end
		end
		if attempts % 200 == 0 then
			task.wait()
		end
	end
end

return Forest
