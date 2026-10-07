-- Il bosco: terreno irregolare (colline, creste rocciose, paludi, lago e pareti ai confini) generato una
-- volta per server, sentieri, punti di interesse, e vegetazione con modelli 3D rigenerata a ogni notte.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local CollectionService = game:GetService("CollectionService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local Models = require(Shared:WaitForChild("Models"))

local MAP = Config.MAP
local SIZE = MAP.SIZE
local HALF = SIZE / 2
local LAKE = MAP.LAKE
local PATH_W = MAP.PATH_WIDTH

local Forest = {}
Forest.HALF = HALF
Forest.WATER_LEVEL = -5
Forest.SWAMP_WATER = -6.4

local seedRng = Random.new()
local SX, SZ = seedRng:NextNumber(-500, 500), seedRng:NextNumber(-500, 500)

local WOOD = Color3.fromRGB(96, 70, 48)
local DARK_WOOD = Color3.fromRGB(58, 42, 30)
local M = Enum.Material

---------------------------------------------------------------------------------------------
-- Utilità

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

local function smoothstep(a: number, b: number, x: number): number
	local t = math.clamp((x - a) / (b - a), 0, 1)
	return t * t * (3 - 2 * t)
end

local function lerp(a: number, b: number, t: number): number
	return a + (b - a) * t
end

-- Luce che i client fanno tremolare (più forte quando la creatura è vicina)
local function flicker(light: Light)
	light:SetAttribute("BaseBrightness", light.Brightness)
	CollectionService:AddTag(light, "Flicker")
end
Forest.flicker = flicker

---------------------------------------------------------------------------------------------
-- Altezza del terreno

local function fbm(x: number, z: number): number
	local total, amp, norm, freq = 0, 1, 0, 1 / 210
	for i = 1, 4 do
		total += math.noise(x * freq + SX + i * 31.7, z * freq + SZ - i * 17.3, i * 0.37) * amp
		norm += amp
		amp *= 0.5
		freq *= 2.03
	end
	return total / norm * 2
end

local function ridge(x: number, z: number): number
	local n = math.noise(x / 150 + SX * 0.5, z / 150 - SZ * 0.5, 4.2)
	return (1 - math.min(1, math.abs(n) * 2.4)) ^ 3
end

-- Pesi dei quattro biomi, sfumati lungo gli assi
local function biomeWeights(x: number, z: number)
	local a = smoothstep(-55, 55, x)
	local b = smoothstep(-55, 55, z)
	return a * (1 - b), (1 - a) * (1 - b), (1 - a) * b, a * b -- pineta, campeggio, palude, miniera
end

local function natural(x: number, z: number): number
	local wP, wC, wS, wM = biomeWeights(x, z)
	local n = fbm(x, z)
	local r = ridge(x, z)
	local h = wP * (n * 20 + r * 15 + 2) + wC * (n * 12 + 1) + wS * (n * 4 - 4.6) + wM * (n * 18 + r * 26 + 9)
	h += math.noise(x / 23 + SX, z / 23 + SZ, 9.1) * 1.6
	local edge = math.max(math.abs(x), math.abs(z))
	h += smoothstep(HALF - 110, HALF + 20, edge) ^ 1.6 * 58
	local d = flat(Vector3.new(x, 0, z) - LAKE.center).Magnitude
	if d < LAKE.radius + 35 then
		local bottom = Forest.WATER_LEVEL - 9 + (d / LAKE.radius) ^ 2 * 6
		h = lerp(h, bottom, smoothstep(LAKE.radius + 35, LAKE.radius * 0.7, d))
	end
	return h
end

-- Punti di interesse con la loro quota (il terreno viene spianato intorno)
local POIS = {}
for i, poi in MAP.POIS do
	local h = natural(poi.pos.X, poi.pos.Z)
	if poi.name == "Lago" then
		h = math.max(h, Forest.WATER_LEVEL + 1.4)
	end
	POIS[i] = { name = poi.name, radius = poi.radius, pos = Vector3.new(poi.pos.X, h, poi.pos.Z) }
end
Forest.POIS = POIS
Forest.STATION = POIS[1].pos

local PATHS = {}
for i = 2, #POIS do
	table.insert(PATHS, { POIS[1].pos, POIS[i].pos })
end
table.insert(PATHS, { POIS[2].pos, POIS[6].pos })
table.insert(PATHS, { POIS[3].pos, POIS[4].pos })
table.insert(PATHS, { POIS[4].pos, POIS[5].pos })
Forest.PATHS = PATHS

function Forest.distToSegment(p: Vector3, a: Vector3, b: Vector3): (number, number)
	local ab = flat(b - a)
	local ap = flat(p - a)
	local t = math.clamp(ap:Dot(ab) / ab:Dot(ab), 0, 1)
	return (ap - ab * t).Magnitude, t
end

-- Distanza dal sentiero più vicino e quota del sentiero in quel punto
local function pathInfo(x: number, z: number): (number, number)
	local p = Vector3.new(x, 0, z)
	local best, bestT, bestSeg = math.huge, 0, nil
	for _, seg in PATHS do
		local d, t = Forest.distToSegment(p, seg[1], seg[2])
		if d < best then
			best, bestT, bestSeg = d, t, seg
		end
	end
	if best > PATH_W / 2 + 8 then
		return best, 0
	end
	local c = bestSeg[1]:Lerp(bestSeg[2], bestT)
	return best, math.max(natural(c.X, c.Z), Forest.WATER_LEVEL + 0.9)
end

function Forest.distToPath(p: Vector3): number
	return (pathInfo(p.X, p.Z))
end

function Forest.heightAt(x: number, z: number): number
	local h = natural(x, z)
	local pd, py = pathInfo(x, z)
	if pd < PATH_W / 2 + 8 then
		h = lerp(h, py, smoothstep(PATH_W / 2 + 8, PATH_W / 2, pd))
	end
	for _, poi in POIS do
		local d = flat(Vector3.new(x, 0, z) - poi.pos).Magnitude
		if d < poi.radius + 30 then
			h = lerp(h, poi.pos.Y, smoothstep(poi.radius + 30, poi.radius, d))
		end
	end
	return h
end

function Forest.waterAt(x: number, z: number): number
	if flat(Vector3.new(x, 0, z) - LAKE.center).Magnitude < LAKE.radius + 45 then
		return Forest.WATER_LEVEL
	end
	local _, _, wS = biomeWeights(x, z)
	if wS > 0.5 then
		return Forest.SWAMP_WATER
	end
	return -math.huge
end

function Forest.groundAt(x: number, z: number): Vector3
	return Vector3.new(x, Forest.heightAt(x, z), z)
end

function Forest.slopeAt(x: number, z: number): number
	local dx = Forest.heightAt(x + 2, z) - Forest.heightAt(x - 2, z)
	local dz = Forest.heightAt(x, z + 2) - Forest.heightAt(x, z - 2)
	return math.sqrt(dx * dx + dz * dz) / 4
end

function Forest.isDry(p: Vector3): boolean
	return Forest.heightAt(p.X, p.Z) > Forest.waterAt(p.X, p.Z) + 0.4
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

function Forest.inLake(p: Vector3, margin: number?): boolean
	return flat(p - LAKE.center).Magnitude < LAKE.radius + (margin or 0)
end

function Forest.inStation(p: Vector3, margin: number?): boolean
	return flat(p - Forest.STATION).Magnitude < MAP.STATION_RADIUS + (margin or 0)
end

function Forest.isOpenGround(p: Vector3, margin: number): boolean
	for _, poi in POIS do
		if flat(p - poi.pos).Magnitude < poi.radius + margin then
			return false
		end
	end
	return Forest.distToPath(p) >= PATH_W / 2 + margin
end

function Forest.clampToMap(p: Vector3): Vector3
	local limit = HALF - 40
	local x, z = math.clamp(p.X, -limit, limit), math.clamp(p.Z, -limit, limit)
	return Forest.groundAt(x, z)
end

-- Punto a terra (asciutto) tra minR e maxR da center
function Forest.randomGround(rng: Random, center: Vector3, minR: number, maxR: number): Vector3
	local p = Forest.clampToMap(center)
	for _ = 1, 30 do
		local angle = rng:NextNumber(0, math.pi * 2)
		local r = rng:NextNumber(minR, maxR)
		p = Forest.clampToMap(center + Vector3.new(math.cos(angle) * r, 0, math.sin(angle) * r))
		if Forest.isDry(p) and Forest.slopeAt(p.X, p.Z) < 1 then
			return p
		end
	end
	return p
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

function Forest.describe(pos: Vector3): string
	local poi, dist = Forest.nearestPoi(pos)
	if dist < poi.radius + 45 then
		return "vicino a " .. poi.name
	end
	return Forest.biomeAt(pos)
end

---------------------------------------------------------------------------------------------
-- Terreno (WriteVoxels a blocchi)

local function surfaceMaterial(x: number, z: number, h: number, slope: number, water: number): Enum.Material
	if h < water - 0.3 then
		return M.Mud
	end
	local pd = pathInfo(x, z)
	local wP, wC, wS, wM = biomeWeights(x, z)
	if pd < PATH_W / 2 then
		return wS > 0.5 and M.WoodPlanks or M.Ground
	end
	for i, poi in POIS do
		if flat(Vector3.new(x, 0, z) - poi.pos).Magnitude < poi.radius * 0.8 then
			if i == 3 then
				return M.LeafyGrass
			elseif i == 4 then
				return M.Sand
			elseif i == 6 then
				return M.Slate
			end
			return M.Ground
		end
	end
	if slope > 1.05 or h > 40 then
		return M.Rock
	elseif slope > 0.7 then
		return M.Slate
	end
	local patch = math.noise(x / 38 + SX, z / 38 - SZ, 2.7)
	if h < water + 0.9 then
		return M.Mud
	end
	local best = math.max(wP, wC, wS, wM)
	if best == wP then
		return patch > 0.22 and M.LeafyGrass or (patch < -0.28 and M.Ground or M.Grass)
	elseif best == wC then
		return patch > 0.1 and M.LeafyGrass or M.Grass
	elseif best == wS then
		return patch > 0.15 and M.Grass or M.Mud
	end
	return patch > 0.2 and M.Rock or (patch < -0.25 and M.Grass or M.Ground)
end

local function buildTerrain()
	local terrain = workspace.Terrain
	terrain:Clear()
	local RES = 4
	local EXT = HALF + 48
	local N = math.floor(EXT * 2 / RES)
	local X0 = -EXT
	local CHUNK = 32
	for cx = 0, N - 1, CHUNK do
		for cz = 0, N - 1, CHUNK do
			local nx, nz = math.min(CHUNK, N - cx), math.min(CHUNK, N - cz)
			local heights, waters = {}, {}
			local lo, hi = math.huge, -math.huge
			for i = 1, nx + 2 do
				heights[i], waters[i] = {}, {}
				for k = 1, nz + 2 do
					local x = X0 + (cx + i - 2) * RES + RES / 2
					local z = X0 + (cz + k - 2) * RES + RES / 2
					local h = Forest.heightAt(x, z)
					heights[i][k] = h
					waters[i][k] = Forest.waterAt(x, z)
					if i > 1 and k > 1 and i <= nx + 1 and k <= nz + 1 then
						lo = math.min(lo, h)
						hi = math.max(hi, h, waters[i][k] > -1e6 and waters[i][k] or h)
					end
				end
			end
			local minY = math.floor((lo - 12) / RES) * RES
			local maxY = math.ceil((hi + 4) / RES) * RES
			local ny = (maxY - minY) / RES
			local mats, occs = {}, {}
			for i = 1, nx do
				mats[i], occs[i] = {}, {}
				for y = 1, ny do
					mats[i][y], occs[i][y] = {}, {}
				end
				for k = 1, nz do
					local h = heights[i + 1][k + 1]
					local water = waters[i + 1][k + 1]
					local slope = math.sqrt((heights[i + 2][k + 1] - heights[i][k + 1]) ^ 2 + (heights[i + 1][k + 2] - heights[i + 1][k]) ^ 2) / (2 * RES)
					local x = X0 + (cx + i - 1) * RES + RES / 2
					local z = X0 + (cz + k - 1) * RES + RES / 2
					local surface = surfaceMaterial(x, z, h, slope, water)
					for y = 1, ny do
						local bottom = minY + (y - 1) * RES
						local occ = math.clamp((h - bottom) / RES, 0, 1)
						local mat = surface
						if h - bottom > 8 then
							mat = slope > 0.7 and M.Rock or M.Ground
						end
						if occ <= 0.02 then
							if bottom < water then
								mat, occ = M.Water, 1
							else
								mat, occ = M.Air, 0
							end
						end
						mats[i][y][k] = mat
						occs[i][y][k] = occ
					end
				end
			end
			local min = Vector3.new(X0 + cx * RES, minY, X0 + cz * RES)
			local region = Region3.new(min, min + Vector3.new(nx * RES, ny * RES, nz * RES))
			terrain:WriteVoxels(region, RES, mats, occs)
			task.wait()
		end
	end

	terrain.WaterColor = Color3.fromRGB(16, 24, 20)
	terrain.WaterTransparency = 0.25
	terrain.WaterReflectance = 0.7
	terrain.WaterWaveSize = 0.04
	terrain.WaterWaveSpeed = 4
	for mat, color in {
		[M.Grass] = Color3.fromRGB(44, 56, 32),
		[M.LeafyGrass] = Color3.fromRGB(50, 58, 32),
		[M.Mud] = Color3.fromRGB(46, 38, 30),
		[M.Ground] = Color3.fromRGB(58, 46, 34),
		[M.Rock] = Color3.fromRGB(78, 80, 82),
		[M.Slate] = Color3.fromRGB(64, 64, 66),
		[M.Sand] = Color3.fromRGB(82, 74, 58),
		[M.WoodPlanks] = Color3.fromRGB(70, 54, 40),
	} do
		terrain:SetMaterialColor(mat, color)
	end
end

---------------------------------------------------------------------------------------------
-- Costruzioni

-- Parete lungo l'asse X locale (da -length/2 a +length/2) con aperture {center, width, bottom, top}
local function wall(parent: Instance, origin: CFrame, length: number, height: number, thickness: number, openings, color: Color3, material: Enum.Material)
	local cuts = table.clone(openings)
	table.sort(cuts, function(a, b)
		return a.center < b.center
	end)
	local x = -length / 2
	local function piece(x0: number, x1: number, y0: number, y1: number)
		if x1 - x0 > 0.05 and y1 - y0 > 0.05 then
			make("Part", parent, {
				Size = Vector3.new(x1 - x0, y1 - y0, thickness),
				CFrame = origin * CFrame.new((x0 + x1) / 2, (y0 + y1) / 2, 0),
				Color = color,
				Material = material,
			})
		end
	end
	for _, o in cuts do
		local x0, x1 = o.center - o.width / 2, o.center + o.width / 2
		piece(x, x0, 0, height)
		piece(x0, x1, 0, o.bottom)
		piece(x0, x1, o.top, height)
		if o.glass then
			make("Part", parent, {
				Size = Vector3.new(o.width, o.top - o.bottom, 0.15),
				CFrame = origin * CFrame.new(o.center, (o.bottom + o.top) / 2, 0),
				Color = Color3.fromRGB(40, 50, 55),
				Material = M.Glass,
				Transparency = 0.55,
			})
			for _, y in { o.bottom, o.top } do
				make("Part", parent, {
					Size = Vector3.new(o.width + 0.4, 0.3, thickness + 0.2),
					CFrame = origin * CFrame.new(o.center, y, 0),
					Color = DARK_WOOD,
					Material = M.Wood,
				})
			end
			make("Part", parent, {
				Size = Vector3.new(0.2, o.top - o.bottom, thickness + 0.1),
				CFrame = origin * CFrame.new(o.center, (o.bottom + o.top) / 2, 0),
				Color = DARK_WOOD,
				Material = M.Wood,
			})
		end
		x = x1
	end
	piece(x, length / 2, 0, height)
end

-- Tetto a due falde centrato su origin (colmo lungo l'asse X locale)
local function gableRoof(parent: Instance, origin: CFrame, width: number, depth: number, rise: number, color: Color3, material: Enum.Material)
	local half = depth / 2
	local slope = math.sqrt(half * half + rise * rise)
	local angle = math.atan2(rise, half)
	for _, side in { -1, 1 } do
		make("Part", parent, {
			Size = Vector3.new(width, 0.5, slope + 1.2),
			CFrame = origin * CFrame.new(0, rise / 2, side * half / 2) * CFrame.Angles(side * angle, 0, 0),
			Color = color,
			Material = material,
		})
	end
	for _, end_ in { -1, 1 } do
		for _, side in { -1, 1 } do
			make("WedgePart", parent, {
				Size = Vector3.new(0.6, rise, half),
				CFrame = origin * CFrame.new(end_ * (width / 2 - 1.2), rise / 2, side * half / 2) * CFrame.Angles(0, side > 0 and math.pi or 0, 0),
				Color = color:Lerp(Color3.new(0, 0, 0), 0.2),
				Material = M.WoodPlanks,
			})
		end
	end
	make("Part", parent, {
		Size = Vector3.new(width + 0.4, 0.6, 0.6),
		CFrame = origin * CFrame.new(0, rise + 0.1, 0),
		Color = DARK_WOOD,
		Material = M.Wood,
	})
end

local function lamp(parent: Instance, cf: CFrame, range: number, brightness: number, color: Color3, flickering: boolean?): BasePart
	local bulb = make("Part", parent, {
		Name = "Lampada",
		Size = Vector3.new(0.6, 0.6, 0.6),
		Shape = Enum.PartType.Ball,
		CFrame = cf,
		Material = M.Neon,
		Color = color,
		CanCollide = false,
		CastShadow = false,
	})
	local light = make("PointLight", bulb, { Range = range, Brightness = brightness, Color = color, Shadows = true })
	if flickering then
		flicker(light)
	end
	return bulb
end

local function sign(parent: Instance, cf: CFrame, text: string, width: number?)
	local w = width or 5
	make("Part", parent, { Size = Vector3.new(0.4, 5, 0.4), CFrame = cf * CFrame.new(0, 2.5, 0), Color = DARK_WOOD, Material = M.Wood })
	local board = make("Part", parent, {
		Size = Vector3.new(w, 1.3, 0.25),
		CFrame = cf * CFrame.new(0, 4.4, 0.3),
		Color = WOOD,
		Material = M.WoodPlanks,
	})
	for _, face in { Enum.NormalId.Front, Enum.NormalId.Back } do
		local gui = make("SurfaceGui", board, { Face = face, SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud, PixelsPerStud = 40 })
		make("TextLabel", gui, {
			Size = UDim2.fromScale(1, 1),
			BackgroundTransparency = 1,
			Text = text,
			TextScaled = true,
			Font = Enum.Font.Antique,
			TextColor3 = Color3.fromRGB(225, 210, 175),
		})
	end
end

local function buildStation(parent: Instance)
	local m = make("Model", parent, { Name = "RangerStation" })
	local base = CFrame.new(Forest.STATION)
	local W, D, H = 40, 28, 10
	local FLOOR = 2
	local wallColor = Color3.fromRGB(88, 66, 46)
	make("Part", m, {
		Name = "Fondamenta",
		Size = Vector3.new(W + 2, 4, D + 2),
		CFrame = base * CFrame.new(0, FLOOR - 2, 0),
		Color = Color3.fromRGB(70, 70, 72),
		Material = M.Cobblestone,
	})
	make("Part", m, {
		Name = "Pavimento",
		Size = Vector3.new(W, 0.4, D),
		CFrame = base * CFrame.new(0, FLOOR + 0.2, 0),
		Color = Color3.fromRGB(84, 60, 40),
		Material = M.WoodPlanks,
	})
	local f = FLOOR + 0.4
	local function window(c: number)
		return { center = c, width = 5, bottom = 3, top = 6.5, glass = true }
	end
	wall(m, base * CFrame.new(0, f, -D / 2 + 0.5), W, H, 1, { window(-10), window(10) }, wallColor, M.WoodPlanks)
	wall(m, base * CFrame.new(0, f, D / 2 - 0.5), W, H, 1, { window(-12), { center = 0, width = 6, bottom = 0, top = 8 }, window(12) }, wallColor, M.WoodPlanks)
	wall(m, base * CFrame.new(-W / 2 + 0.5, f, 0) * CFrame.Angles(0, math.pi / 2, 0), D - 2, H, 1, { window(0) }, wallColor, M.WoodPlanks)
	wall(m, base * CFrame.new(W / 2 - 0.5, f, 0) * CFrame.Angles(0, math.pi / 2, 0), D - 2, H, 1, { window(-5) }, wallColor, M.WoodPlanks)
	for _, x in { -W / 2, W / 2 } do
		for _, z in { -D / 2, D / 2 } do
			make("Part", m, {
				Shape = Enum.PartType.Cylinder,
				Size = Vector3.new(H + 0.5, 1.6, 1.6),
				CFrame = base * CFrame.new(x, f + H / 2, z) * CFrame.Angles(0, 0, math.pi / 2),
				Color = DARK_WOOD,
				Material = M.Wood,
			})
		end
	end
	make("Part", m, { Size = Vector3.new(W, 0.4, D), CFrame = base * CFrame.new(0, f + H + 0.2, 0), Color = DARK_WOOD, Material = M.WoodPlanks })
	gableRoof(m, base * CFrame.new(0, f + H + 0.4, 0), W + 5, D + 5, 6, Color3.fromRGB(62, 52, 46), M.CorrodedMetal)
	local chimney = make("Part", m, {
		Size = Vector3.new(2.4, 9, 2.4),
		CFrame = base * CFrame.new(-W / 2 + 6, f + H + 4, -5),
		Color = Color3.fromRGB(80, 50, 42),
		Material = M.Brick,
	})
	make("Smoke", chimney, { Color = Color3.fromRGB(60, 60, 62), Opacity = 0.08, RiseVelocity = 4, Size = 3 })

	-- portico
	make("Part", m, { Size = Vector3.new(W, 0.4, 6), CFrame = base * CFrame.new(0, FLOOR + 0.2, D / 2 + 3), Color = Color3.fromRGB(78, 56, 38), Material = M.WoodPlanks })
	for i = 1, 3 do
		make("Part", m, {
			Size = Vector3.new(8, 0.5, 1.2),
			CFrame = base * CFrame.new(0, FLOOR - i * 0.65 + 0.15, D / 2 + 6 + i * 1.1 - 0.5),
			Color = Color3.fromRGB(70, 50, 34),
			Material = M.WoodPlanks,
		})
	end
	for _, x in { -W / 2 + 0.5, -6, 6, W / 2 - 0.5 } do
		make("Part", m, { Size = Vector3.new(0.6, 7.5, 0.6), CFrame = base * CFrame.new(x, f + 3.75, D / 2 + 5.6), Color = DARK_WOOD, Material = M.Wood })
	end
	for _, seg in { { -W / 2 + 0.5, -6 }, { 6, W / 2 - 0.5 } } do
		local cx, len = (seg[1] + seg[2]) / 2, seg[2] - seg[1]
		make("Part", m, { Size = Vector3.new(len, 0.3, 0.3), CFrame = base * CFrame.new(cx, f + 2.8, D / 2 + 5.6), Color = WOOD, Material = M.Wood })
		make("Part", m, { Size = Vector3.new(len, 0.25, 0.25), CFrame = base * CFrame.new(cx, f + 1.5, D / 2 + 5.6), Color = WOOD, Material = M.Wood })
	end
	make("Part", m, {
		Size = Vector3.new(W + 1, 0.4, 7.5),
		CFrame = base * CFrame.new(0, f + 7.9, D / 2 + 3) * CFrame.Angles(math.rad(-12), 0, 0),
		Color = Color3.fromRGB(62, 52, 46),
		Material = M.CorrodedMetal,
	})
	local porchLamp = lamp(m, base * CFrame.new(-4.5, f + 7, D / 2 + 0.2), 22, 1.4, Color3.fromRGB(255, 196, 120), true)
	porchLamp.Size = Vector3.new(0.5, 0.5, 0.5)

	-- interno
	local inside = lamp(m, base * CFrame.new(0, f + H - 1.2, -2), 34, 1.1, Color3.fromRGB(255, 205, 140), true)
	make("Part", m, { Size = Vector3.new(0.08, 1, 0.08), CFrame = inside.CFrame * CFrame.new(0, 0.8, 0), Color = Color3.new(0, 0, 0) })
	make("SpawnLocation", m, {
		Name = "Spawn",
		Size = Vector3.new(6, 0.2, 6),
		CFrame = base * CFrame.new(0, f + 0.1, 4),
		Neutral = true,
		Duration = 0,
		Transparency = 1,
		CanCollide = false,
		CanQuery = false,
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
		Size = Vector3.new(12, 0.4, 3),
		CFrame = base * CFrame.new(0, f + 3, -D / 2 + 2.6),
		Color = Color3.fromRGB(70, 52, 38),
		Material = M.Wood,
	})
	for _, x in { -5.6, 5.6 } do
		make("Part", m, { Size = Vector3.new(0.4, 3, 2.6), CFrame = base * CFrame.new(x, f + 1.5, -D / 2 + 2.6), Color = DARK_WOOD, Material = M.Wood })
	end
	for i = -1, 1 do
		local monitor = make("Part", m, {
			Size = Vector3.new(2.8, 2.2, 2),
			CFrame = base * CFrame.new(i * 3.6, f + 4.3, -D / 2 + 2.2),
			Color = Color3.fromRGB(46, 44, 40),
			Material = M.SmoothPlastic,
		})
		local screen = make("Part", m, {
			Size = Vector3.new(2.3, 1.7, 0.1),
			CFrame = monitor.CFrame * CFrame.new(0, 0, 1.02),
			Color = Color3.fromRGB(28, 70, 52),
			Material = M.Neon,
			CanCollide = false,
		})
		local gui = make("SurfaceGui", screen, { Face = Enum.NormalId.Back, SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud, PixelsPerStud = 60, LightInfluence = 0 })
		make("TextLabel", gui, {
			Size = UDim2.fromScale(1, 1),
			BackgroundTransparency = 1,
			Text = ("CAM %02d\nNESSUN SEGNALE"):format(i + 2),
			TextScaled = true,
			Font = Enum.Font.Code,
			TextColor3 = Color3.fromRGB(140, 255, 180),
		})
		make("PointLight", screen, { Range = 7, Brightness = 0.5, Color = Color3.fromRGB(80, 220, 150) })
	end
	local board = make("Part", m, {
		Size = Vector3.new(9, 5, 0.2),
		CFrame = base * CFrame.new(-11, f + 5.5, -D / 2 + 1.1),
		Color = Color3.fromRGB(120, 100, 70),
		Material = M.Fabric,
	})
	local mapGui = make("SurfaceGui", board, { Face = Enum.NormalId.Back, SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud, PixelsPerStud = 40 })
	make("TextLabel", mapGui, {
		Size = UDim2.fromScale(1, 1),
		BackgroundTransparency = 1,
		Text = "RISERVA DI BLACKWOOD\n\nTorre (NE) · Campeggio (NO)\nLago e Palude (SO) · Miniera (SE)\n\nNON USCIRE DA SOLI DOPO IL TRAMONTO",
		TextScaled = true,
		Font = Enum.Font.SpecialElite,
		TextColor3 = Color3.fromRGB(40, 30, 20),
	})

	local crate = make("Part", m, {
		Name = "Rifornimento",
		Size = Vector3.new(4, 3, 3),
		CFrame = base * CFrame.new(-W / 2 + 3.5, f + 1.5, 2),
		Color = Color3.fromRGB(64, 76, 48),
		Material = M.WoodPlanks,
	})
	make("Part", m, { Size = Vector3.new(3, 6.5, 2), CFrame = base * CFrame.new(-W / 2 + 2.5, f + 3.25, -4), Color = Color3.fromRGB(70, 78, 72), Material = M.DiamondPlate })
	local lab = make("Part", m, {
		Name = "Laboratorio",
		Size = Vector3.new(3.5, 0.4, 9),
		CFrame = base * CFrame.new(W / 2 - 3, f + 3, 4),
		Color = Color3.fromRGB(190, 195, 198),
		Material = M.SmoothPlastic,
	})
	make("Part", m, { Size = Vector3.new(3.3, 2.8, 8.8), CFrame = base * CFrame.new(W / 2 - 3, f + 1.4, 4), Color = Color3.fromRGB(120, 124, 126), Material = M.Metal })
	for i = 1, 4 do
		make("Part", m, {
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(0.9, 0.5, 0.5),
			CFrame = base * CFrame.new(W / 2 - 3, f + 3.65, 1 + i * 1.3) * CFrame.Angles(0, 0, math.pi / 2),
			Color = Color3.fromRGB(150, 200, 190),
			Material = M.Glass,
			Transparency = 0.4,
		})
	end
	local labLight = make("Part", m, {
		Name = "LuceLaboratorio",
		Size = Vector3.new(0.5, 0.5, 0.5),
		Shape = Enum.PartType.Ball,
		CFrame = base * CFrame.new(W / 2 - 3, f + 3.6, 7.5),
		Material = M.Neon,
		Color = Color3.fromRGB(120, 200, 255),
	})
	make("PointLight", labLight, { Range = 6, Brightness = 0.8, Color = Color3.fromRGB(120, 200, 255) })
	local stove = make("Part", m, {
		Size = Vector3.new(2.5, 3, 2.5),
		CFrame = base * CFrame.new(-W / 2 + 6, f + 1.5, -5),
		Color = Color3.fromRGB(30, 30, 32),
		Material = M.Metal,
	})
	flicker(make("PointLight", stove, { Range = 9, Brightness = 1, Color = Color3.fromRGB(255, 120, 50) }))
	for _, z in { -11, -6 } do
		make("Part", m, { Size = Vector3.new(7, 1.2, 3), CFrame = base * CFrame.new(10, f + 0.9, z), Color = Color3.fromRGB(60, 70, 55), Material = M.Fabric })
	end
	local gen = make("Part", m, {
		Size = Vector3.new(4, 3, 3),
		CFrame = base * CFrame.new(W / 2 + 4, 1.5, -6),
		Color = Color3.fromRGB(90, 70, 30),
		Material = M.CorrodedMetal,
	})
	lamp(m, gen.CFrame * CFrame.new(0, 1.8, 1.4), 6, 0.6, Color3.fromRGB(255, 80, 60), true)
	sign(m, base * CFrame.new(9, 0, D / 2 + 14) * CFrame.Angles(0, math.rad(-15), 0), "RANGER STATION\nRiserva di Blackwood", 7)

	Forest.stationPrompts = {
		control = prompt(desk, "Apri il tablet", "Sala di controllo"),
		supply = prompt(crate, "Rifornisciti", "Dardi, torcia e visore"),
		lab = prompt(lab, "Analizza campioni", "Laboratorio"),
	}
	Forest.labLight = labLight
end

local function buildTower(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Torre" })
	local h = 24
	local base = CFrame.new(pos)
	for _, x in { -4, 4 } do
		for _, z in { -4, 4 } do
			make("Part", m, { Size = Vector3.new(1, h + 3, 1), CFrame = base * CFrame.new(x, (h + 3) / 2 - 2, z), Color = WOOD, Material = M.Wood })
			make("Part", m, { Size = Vector3.new(0.5, 7, 0.5), CFrame = base * CFrame.new(x, h + 4.5, z), Color = WOOD, Material = M.Wood })
		end
	end
	for y = 5, h - 2, 6 do
		for _, side in { -1, 1 } do
			make("Part", m, { Size = Vector3.new(0.4, 0.4, 9.5), CFrame = base * CFrame.new(side * 4.3, y, 0) * CFrame.Angles(0.55, 0, 0), Color = DARK_WOOD, Material = M.Wood })
			make("Part", m, { Size = Vector3.new(9.5, 0.4, 0.4), CFrame = base * CFrame.new(0, y, side * 4.3) * CFrame.Angles(0, 0, 0.55), Color = DARK_WOOD, Material = M.Wood })
		end
	end
	make("Part", m, { Size = Vector3.new(11, 0.6, 11), CFrame = base * CFrame.new(0, h + 0.3, 0), Color = WOOD, Material = M.WoodPlanks })
	for _, info in { { Vector3.new(11, 3, 0.4), Vector3.new(0, 2, -5.3) }, { Vector3.new(0.4, 3, 11), Vector3.new(-5.3, 2, 0) }, { Vector3.new(0.4, 3, 11), Vector3.new(5.3, 2, 0) } } do
		make("Part", m, { Size = info[1], CFrame = base * CFrame.new(info[2] + Vector3.new(0, h, 0)), Color = WOOD, Material = M.WoodPlanks })
	end
	gableRoof(m, base * CFrame.new(0, h + 8, 0), 12.5, 12.5, 3, Color3.fromRGB(60, 50, 44), M.CorrodedMetal)
	make("TrussPart", m, { Size = Vector3.new(2, h, 2), CFrame = base * CFrame.new(0, h / 2, 6.5), Color = DARK_WOOD })
	local lantern = lamp(m, base * CFrame.new(3.5, h + 5.5, -3.5), 14, 0.6, Color3.fromRGB(255, 160, 80), true)
	lantern.Size = Vector3.new(0.4, 0.4, 0.4)
end

local function buildCamp(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Campeggio" })
	local base = CFrame.new(pos)
	local tents = {
		{ Vector3.new(-14, 0, -8), 25, Color3.fromRGB(110, 54, 36), false },
		{ Vector3.new(10, 0, -14), -40, Color3.fromRGB(52, 70, 96), true },
		{ Vector3.new(15, 0, 9), 70, Color3.fromRGB(96, 96, 52), false },
	}
	for _, t in tents do
		local tb = base * CFrame.new(t[1]) * CFrame.Angles(0, math.rad(t[2]), 0)
		local h, len, d = 4.5, 7, 3.2
		make("WedgePart", m, { Size = Vector3.new(len, h, d), CFrame = tb * CFrame.new(0, h / 2, -d / 2), Color = t[3], Material = M.Fabric })
		if t[4] then
			make("WedgePart", m, { Size = Vector3.new(len, h * 0.5, d * 1.4), CFrame = tb * CFrame.new(0, h * 0.25, d * 0.7) * CFrame.Angles(0.25, math.pi, 0.1), Color = t[3], Material = M.Fabric })
		else
			make("WedgePart", m, { Size = Vector3.new(len, h, d), CFrame = tb * CFrame.new(0, h / 2, d / 2) * CFrame.Angles(0, math.pi, 0), Color = t[3], Material = M.Fabric })
		end
	end
	for i = 0, 7 do
		local a = i / 8 * math.pi * 2
		Models.mesh("Rock3", base * CFrame.new(math.cos(a) * 2.4, -0.2, math.sin(a) * 2.4) * CFrame.Angles(0, a, 0), 0.4, { CanCollide = true }, m)
	end
	local embers = make("Part", m, {
		Size = Vector3.new(2.6, 0.3, 2.6),
		CFrame = base * CFrame.new(0, 0.15, 0),
		Color = Color3.fromRGB(120, 40, 14),
		Material = M.Neon,
		CanCollide = false,
	})
	flicker(make("PointLight", embers, { Range = 14, Brightness = 1.3, Color = Color3.fromRGB(255, 110, 40), Shadows = true }))
	make("Fire", embers, { Heat = 3, Size = 2.5, Color = Color3.fromRGB(255, 120, 40), SecondaryColor = Color3.fromRGB(120, 30, 10) })
	for _, a in { 0.5, 2.6, 4.4 } do
		Models.mesh("Log1", base * CFrame.new(math.cos(a) * 6, -0.45, math.sin(a) * 6) * CFrame.Angles(0, -a + math.pi / 2, 0), 0.4, { CanCollide = true, CanQuery = true }, m)
	end
	local car = base * CFrame.new(-16, 0, 14) * CFrame.Angles(0.04, math.rad(35), 0.05)
	make("Part", m, { Size = Vector3.new(6.5, 2.2, 13), CFrame = car * CFrame.new(0, 2.2, 0), Color = Color3.fromRGB(70, 40, 32), Material = M.CorrodedMetal })
	make("Part", m, { Size = Vector3.new(6, 2, 6.5), CFrame = car * CFrame.new(0, 4.3, 0.8), Color = Color3.fromRGB(64, 38, 30), Material = M.CorrodedMetal })
	make("Part", m, { Size = Vector3.new(5.6, 1.6, 0.1), CFrame = car * CFrame.new(0, 4.3, -2.5) * CFrame.Angles(0.3, 0, 0), Color = Color3.fromRGB(30, 36, 38), Material = M.Glass, Transparency = 0.4 })
	for _, x in { -3, 3 } do
		for _, z in { -4, 4 } do
			make("Part", m, {
				Shape = Enum.PartType.Cylinder,
				Size = Vector3.new(1, 2.4, 2.4),
				CFrame = car * CFrame.new(x, 1.1, z),
				Color = Color3.fromRGB(20, 20, 20),
				Material = M.Fabric,
			})
		end
	end
	make("Part", m, { Size = Vector3.new(8, 0.5, 3), CFrame = base * CFrame.new(-4, 2.8, -20), Color = WOOD, Material = M.WoodPlanks })
	make("Part", m, { Size = Vector3.new(8, 0.4, 1), CFrame = base * CFrame.new(-4, 1.6, -21.7), Color = WOOD, Material = M.WoodPlanks })
	sign(m, base * CFrame.new(20, 0, -2) * CFrame.Angles(0, math.rad(80), 0.08), "CAMPEGGIO CHIUSO", 5)
end

local function buildDock(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Pontile" })
	local dir = flat(LAKE.center - pos).Unit
	local start = pos + dir * 4
	local cf = CFrame.lookAt(start, start + dir)
	local length = 26
	for i = 0, length - 1, 1.1 do
		make("Part", m, {
			Size = Vector3.new(5, 0.3, 1),
			CFrame = cf * CFrame.new(0, 0.6, -i) * CFrame.Angles(0, 0, (i * 7 % 3 - 1) * 0.02),
			Color = WOOD:Lerp(DARK_WOOD, (i * 13 % 7) / 7),
			Material = M.WoodPlanks,
		})
	end
	for i = 1, 4 do
		for _, x in { -2.4, 2.4 } do
			make("Part", m, {
				Shape = Enum.PartType.Cylinder,
				Size = Vector3.new(10, 0.7, 0.7),
				CFrame = cf * CFrame.new(x, -3.5, -i * length / 4.2) * CFrame.Angles(0, 0, math.pi / 2),
				Color = DARK_WOOD,
				Material = M.Wood,
			})
		end
	end
	local boat = cf * CFrame.new(5.5, -0.7, -length + 5) * CFrame.Angles(0.06, 0.4, 0.12)
	make("Part", m, { Size = Vector3.new(3.2, 0.3, 9), CFrame = boat, Color = Color3.fromRGB(80, 60, 44), Material = M.WoodPlanks })
	for _, side in { -1, 1 } do
		make("Part", m, { Size = Vector3.new(0.3, 1.2, 9), CFrame = boat * CFrame.new(side * 1.6, 0.6, 0) * CFrame.Angles(0, 0, side * -0.3), Color = Color3.fromRGB(72, 54, 40), Material = M.WoodPlanks })
	end
	make("Part", m, { Size = Vector3.new(0.3, 3, 0.3), CFrame = cf * CFrame.new(-2.3, 2, -length + 1), Color = DARK_WOOD, Material = M.Wood })
	lamp(m, cf * CFrame.new(-2.3, 3.7, -length + 1), 12, 0.5, Color3.fromRGB(255, 170, 90), true)
end

local function effigy(parent: Instance, cf: CFrame, scale: number)
	local m = make("Model", parent, { Name = "Effigie" })
	local function stick(a: Vector3, b: Vector3, thick: number)
		local mid = (a + b) / 2
		local len = (b - a).Magnitude
		make("Part", m, {
			Size = Vector3.new(thick, thick, len),
			CFrame = cf * CFrame.lookAt(mid, b, math.abs((b - a).Unit.Y) > 0.9 and Vector3.zAxis or Vector3.yAxis),
			Color = Color3.fromRGB(70, 56, 42),
			Material = M.Wood,
			CanCollide = false,
			CanQuery = false,
		})
	end
	local s = scale
	stick(Vector3.new(0, 0, 0), Vector3.new(0, -2.6 * s, 0.05), 0.12 * s)
	stick(Vector3.new(-1.2 * s, -0.7 * s, 0), Vector3.new(1.2 * s, -0.75 * s, 0), 0.1 * s)
	stick(Vector3.new(0, -2.4 * s, 0), Vector3.new(-0.7 * s, -3.8 * s, 0.1), 0.1 * s)
	stick(Vector3.new(0, -2.4 * s, 0), Vector3.new(0.7 * s, -3.8 * s, -0.1), 0.1 * s)
	stick(Vector3.new(-0.5 * s, -0.2 * s, 0), Vector3.new(0.5 * s, -1.4 * s, 0), 0.08 * s)
	stick(Vector3.new(0.5 * s, -0.2 * s, 0), Vector3.new(-0.5 * s, -1.4 * s, 0), 0.08 * s)
	stick(Vector3.new(0, 0, 0), Vector3.new(0, 3 * s, 0), 0.04)
end

local function buildCabin(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Capanno" })
	local base = CFrame.lookAt(pos, Vector3.new(Forest.STATION.X, pos.Y, Forest.STATION.Z))
	local W, D, H = 16, 12, 8
	local color = Color3.fromRGB(62, 48, 36)
	make("Part", m, { Size = Vector3.new(W, 1, D), CFrame = base * CFrame.new(0, 0.5, 0), Color = DARK_WOOD, Material = M.WoodPlanks })
	local win = { center = -4.5, width = 3, bottom = 3, top = 5.5, glass = true }
	wall(m, base * CFrame.new(0, 1, -D / 2 + 0.4), W, H, 0.8, { { center = 2, width = 4, bottom = 0, top = 7 }, win }, color, M.WoodPlanks)
	wall(m, base * CFrame.new(0, 1, D / 2 - 0.4), W, H, 0.8, {}, color, M.WoodPlanks)
	wall(m, base * CFrame.new(-W / 2 + 0.4, 1, 0) * CFrame.Angles(0, math.pi / 2, 0), D - 1.6, H, 0.8, { { center = 0, width = 3, bottom = 3, top = 5.5, glass = true } }, color, M.WoodPlanks)
	wall(m, base * CFrame.new(W / 2 - 0.4, 1, 0) * CFrame.Angles(0, math.pi / 2, 0), D - 1.6, H, 0.8, {}, color, M.WoodPlanks)
	gableRoof(m, base * CFrame.new(0, H + 1, 0), W + 3, D + 3, 4.5, Color3.fromRGB(48, 42, 38), M.WoodPlanks)
	make("Part", m, { Size = Vector3.new(4, 7, 0.3), CFrame = base * CFrame.new(4.2, 4.5, -D / 2 - 1.2) * CFrame.Angles(0, math.rad(-60), 0), Color = Color3.fromRGB(70, 52, 38), Material = M.WoodPlanks })
	make("Part", m, { Size = Vector3.new(4, 2.6, 2.5), CFrame = base * CFrame.new(-3, 2.3, 2), Color = WOOD, Material = M.Wood })
	local candle = lamp(m, base * CFrame.new(-3, 3.9, 2), 12, 0.7, Color3.fromRGB(255, 70, 40), true)
	candle.Size = Vector3.new(0.3, 0.3, 0.3)
	effigy(m, base * CFrame.new(1.5, H + 0.5, 1), 1)
	effigy(m, base * CFrame.new(-6, H + 0.5, -1), 0.8)
end

local function buildMine(parent: Instance, pos: Vector3)
	local m = make("Model", parent, { Name = "Miniera" })
	local base = CFrame.lookAt(pos, Vector3.new(Forest.STATION.X, pos.Y, Forest.STATION.Z))
	local back = -base.LookVector
	local terrain = workspace.Terrain
	-- parete rocciosa alle spalle dell'ingresso
	terrain:FillBall(pos + back * 22 + Vector3.new(0, 4, 0), 22, M.Rock)
	terrain:FillBall(pos + back * 26 + base.RightVector * 18 + Vector3.new(0, 2, 0), 18, M.Rock)
	terrain:FillBall(pos + back * 26 - base.RightVector * 18 + Vector3.new(0, 1, 0), 17, M.Rock)
	terrain:FillBlock(base * CFrame.new(0, 5, 6), Vector3.new(7, 10, 14), M.Air)
	local function part(size: Vector3, offset: Vector3, color: Color3, material: Enum.Material?)
		return make("Part", m, { Size = size, CFrame = base * CFrame.new(offset), Color = color, Material = material or M.Wood })
	end
	for _, z in { 0, 3, 6 } do
		part(Vector3.new(1.2, 9.5, 1.2), Vector3.new(-3.6, 4.75, z), DARK_WOOD)
		part(Vector3.new(1.2, 9.5, 1.2), Vector3.new(3.6, 4.75, z), DARK_WOOD)
		part(Vector3.new(9, 1.2, 1.4), Vector3.new(0, 9.9, z), DARK_WOOD)
	end
	part(Vector3.new(7, 9.5, 0.6), Vector3.new(0, 4.75, 12), Color3.fromRGB(4, 4, 5), M.SmoothPlastic)
	for _, x in { -1.4, 1.4 } do
		part(Vector3.new(0.3, 0.3, 30), Vector3.new(x, 0.15, -8), Color3.fromRGB(60, 50, 46), M.CorrodedMetal)
	end
	for z = -22, 10, 2 do
		part(Vector3.new(4, 0.25, 0.7), Vector3.new(0, 0.05, z), DARK_WOOD)
	end
	part(Vector3.new(3.6, 2.4, 4.5), Vector3.new(0.2, 1.7, -9), Color3.fromRGB(70, 60, 50), M.CorrodedMetal)
	local l = lamp(m, base * CFrame.new(3.2, 8, -0.8), 16, 0.8, Color3.fromRGB(255, 150, 70), true)
	l.Size = Vector3.new(0.4, 0.4, 0.4)
	sign(m, base * CFrame.new(-6, 0, -4) * CFrame.Angles(0, math.rad(20), 0.1), "PERICOLO\nMINIERA CHIUSA", 5)
	for i = 1, 4 do
		local a = i * 1.3
		Models.mesh("Boulder1", base * CFrame.new(math.cos(a) * 14, -1.5, -math.abs(math.sin(a)) * 6 + 2) * CFrame.Angles(0, a, 0), 0.5 + i * 0.08, { CanCollide = true, CanQuery = true }, m)
	end
end

local function buildSignposts(parent: Instance)
	local m = make("Model", parent, { Name = "Cartelli" })
	for i = 2, #POIS do
		local poi = POIS[i]
		local dir = flat(poi.pos - Forest.STATION).Unit
		local side = Vector3.new(dir.Z, 0, -dir.X)
		local p = Forest.STATION + dir * (MAP.STATION_RADIUS + 14) + side * 6
		local ground = Forest.groundAt(p.X, p.Z)
		sign(m, CFrame.lookAt(ground, ground + side), poi.name .. "  →", 6)
	end
end

local function buildBounds(parent: Instance)
	local m = make("Model", parent, { Name = "Confini" })
	local h = 300
	for _, info in {
		{ Vector3.new(SIZE + 20, h, 2), Vector3.new(0, 0, HALF + 1) },
		{ Vector3.new(SIZE + 20, h, 2), Vector3.new(0, 0, -HALF - 1) },
		{ Vector3.new(2, h, SIZE + 20), Vector3.new(HALF + 1, 0, 0) },
		{ Vector3.new(2, h, SIZE + 20), Vector3.new(-HALF - 1, 0, 0) },
	} do
		make("Part", m, { Size = info[1], CFrame = CFrame.new(info[2]), Transparency = 1, CanQuery = false })
	end
end

function Forest.build(world: Instance)
	Models.load()
	local props = make("Folder", world, { Name = "Mappa" })
	buildTerrain()
	buildStation(props)
	buildTower(props, POIS[2].pos)
	buildCamp(props, POIS[3].pos)
	buildDock(props, POIS[4].pos)
	buildCabin(props, POIS[5].pos)
	buildMine(props, POIS[6].pos)
	buildSignposts(props)
	buildBounds(props)
	Forest.vegetation = make("Folder", world, { Name = "Vegetazione" })
end

---------------------------------------------------------------------------------------------
-- Vegetazione (rigenerata a ogni notte)

local TREES = {
	-- nome mesh, raggio del tronco, peso per bioma {pineta, campeggio, palude, miniera}
	{ "Pine1", 1.2, { 3, 2, 0.3, 1.5 } },
	{ "Pine2", 1.35, { 3, 1.5, 0.3, 1.5 } },
	{ "Pine3", 1.0, { 2, 2, 0.4, 1 } },
	{ "Pine4", 1.5, { 2.5, 1, 0.2, 1 } },
	{ "Snag1", 1.1, { 0.6, 0.6, 1.2, 1 } },
	{ "Dead1", 0.9, { 0.2, 0.3, 3, 0.4 } },
	{ "Dead2", 0.9, { 0.1, 0.3, 3, 0.4 } },
	{ "Dead3", 0.9, { 0.1, 0.3, 3, 0.4 } },
	{ "Broad1", 0.8, { 0, 3, 0.2, 0 } },
	{ "Broad2", 0.8, { 0, 3, 0.2, 0 } },
}
local BIOME_INDEX = { ["Pineta fitta"] = 1, ["Ruderi del campeggio"] = 2, Palude = 3, Miniera = 4 }
local DENSITY = { 1, 0.65, 0.6, 0.45 }

local function pickTree(rng: Random, biome: number)
	local total = 0
	for _, t in TREES do
		total += t[3][biome]
	end
	local roll = rng:NextNumber(0, total)
	for _, t in TREES do
		roll -= t[3][biome]
		if roll <= 0 then
			return t
		end
	end
	return TREES[1]
end

local function plant(rng: Random, folder: Instance, tree, ground: Vector3)
	local name = tree[1]
	local scale = rng:NextNumber(0.8, 1.25)
	local cf = CFrame.new(ground) * CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), 0) * CFrame.Angles(rng:NextNumber(-0.04, 0.04), 0, rng:NextNumber(-0.04, 0.04))
	local visual = { CanCollide = false, CanQuery = false, CastShadow = true }
	local trunkName = Models.info(name .. "_Trunk") and name .. "_Trunk" or name
	local info = Models.info(trunkName)
	Models.mesh(trunkName, cf, scale, visual, folder)
	for _, suffix in { "_Foliage", "_Leaves" } do
		if Models.info(name .. suffix) then
			Models.mesh(name .. suffix, cf, scale, visual, folder)
		end
	end
	-- collisione semplice sul tronco (per giocatori, creatura e linee di vista)
	local height = math.min(info and info.size.Y * 0.55 or 12, 22) * scale
	local d = tree[2] * 2 * scale
	make("Part", folder, {
		Name = "Tronco",
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(height, d, d),
		CFrame = CFrame.new(ground + Vector3.new(0, height / 2 - 1, 0)) * CFrame.Angles(0, 0, math.pi / 2),
		Transparency = 1,
		CastShadow = false,
	})
end

local function scatter(rng: Random, count: number, accept: (Vector3, string) -> boolean, place: (Vector3, string) -> ())
	local placed, attempts = 0, 0
	while placed < count and attempts < count * 12 do
		attempts += 1
		local x, z = rng:NextNumber(-HALF + 12, HALF - 12), rng:NextNumber(-HALF + 12, HALF - 12)
		local p = Forest.groundAt(x, z)
		local biome = Forest.biomeAt(p)
		if accept(p, biome) then
			place(p, biome)
			placed += 1
		end
		if attempts % 80 == 0 then
			task.wait()
		end
	end
end

function Forest.regenerate(rng: Random)
	local folder = Forest.vegetation
	folder:ClearAllChildren()
	local V = Config.VEGETATION
	local function dryFlat(p: Vector3, maxSlope: number, margin: number): boolean
		return Forest.isDry(p) and Forest.slopeAt(p.X, p.Z) < maxSlope and Forest.isOpenGround(p, margin) and not Forest.inLake(p, 6)
	end

	scatter(rng, V.TREES, function(p, biome)
		return rng:NextNumber() <= DENSITY[BIOME_INDEX[biome]] and dryFlat(p, 0.95, 4)
	end, function(p, biome)
		plant(rng, folder, pickTree(rng, BIOME_INDEX[biome]), p - Vector3.new(0, 0.3, 0))
	end)

	local cover = { CanCollide = false, CanQuery = false, CastShadow = false }
	local solid = { CanCollide = true, CanQuery = true, CastShadow = true }
	local function spin(p: Vector3): CFrame
		return CFrame.new(p) * CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), 0)
	end
	scatter(rng, V.BUSHES, function(p, biome)
		return biome ~= "Palude" and dryFlat(p, 0.9, 1)
	end, function(p)
		Models.mesh("Bush" .. rng:NextInteger(1, 3), spin(p - Vector3.new(0, 0.4, 0)), rng:NextNumber(0.7, 1.4), cover, folder)
	end)
	scatter(rng, V.FERNS, function(p, biome)
		return biome ~= "Miniera" and dryFlat(p, 0.9, 0.5)
	end, function(p)
		Models.mesh("Fern" .. rng:NextInteger(1, 2), spin(p - Vector3.new(0, 0.1, 0)), rng:NextNumber(0.8, 1.5), cover, folder)
	end)
	scatter(rng, V.REEDS, function(p)
		local w = Forest.waterAt(p.X, p.Z)
		return p.Y > w - 1.2 and p.Y < w + 1.0 and Forest.isOpenGround(p, 0)
	end, function(p)
		Models.mesh("Reeds1", spin(Vector3.new(p.X, math.max(p.Y, Forest.waterAt(p.X, p.Z) - 1) - 0.2, p.Z)), rng:NextNumber(0.8, 1.4), cover, folder)
	end)
	scatter(rng, V.ROCKS, function(p, biome)
		return (biome == "Miniera" or rng:NextNumber() < 0.5) and Forest.isDry(p) and Forest.isOpenGround(p, 1)
	end, function(p)
		Models.mesh("Rock" .. rng:NextInteger(1, 3), spin(p - Vector3.new(0, 0.6, 0)) * CFrame.Angles(rng:NextNumber(-0.2, 0.2), 0, 0), rng:NextNumber(0.6, 1.8), solid, folder)
	end)
	scatter(rng, V.BOULDERS, function(p, biome)
		return (biome == "Miniera" or biome == "Pineta fitta") and Forest.slopeAt(p.X, p.Z) > 0.35 and Forest.isOpenGround(p, 8)
	end, function(p)
		Models.mesh("Boulder1", spin(p - Vector3.new(0, 2.5, 0)) * CFrame.Angles(rng:NextNumber(-0.2, 0.2), 0, rng:NextNumber(-0.2, 0.2)), rng:NextNumber(0.6, 1.3), solid, folder)
	end)
	scatter(rng, V.LOGS, function(p)
		return dryFlat(p, 0.4, 5)
	end, function(p)
		Models.mesh("Log1", spin(p - Vector3.new(0, 0.5, 0)), rng:NextNumber(0.7, 1.1), solid, folder)
	end)
	scatter(rng, V.STUMPS, function(p)
		return dryFlat(p, 0.6, 2)
	end, function(p)
		Models.mesh("Stump1", spin(p - Vector3.new(0, 0.3, 0)), rng:NextNumber(0.7, 1.2), solid, folder)
	end)
	scatter(rng, V.MUSHROOMS, function(p, biome)
		return (biome == "Palude" or biome == "Ruderi del campeggio") and dryFlat(p, 0.6, 1)
	end, function(p)
		Models.mesh("Mushrooms1", spin(p - Vector3.new(0, 0.05, 0)), rng:NextNumber(0.8, 1.6), cover, folder)
	end)
	scatter(rng, V.EFFIGIES, function(p, biome)
		return (biome == "Palude" or biome == "Ruderi del campeggio" or rng:NextNumber() < 0.3) and dryFlat(p, 0.5, 6)
	end, function(p)
		-- figura di rami appesa a un palo storto
		make("Part", folder, {
			Size = Vector3.new(0.5, 10, 0.5),
			CFrame = CFrame.new(p + Vector3.new(0, 4.5, 0)) * CFrame.Angles(rng:NextNumber(-0.1, 0.1), 0, rng:NextNumber(-0.1, 0.1)),
			Color = DARK_WOOD,
			Material = M.Wood,
		})
		local yaw = rng:NextNumber(0, math.pi * 2)
		make("Part", folder, {
			Size = Vector3.new(0.35, 0.35, 3.5),
			CFrame = CFrame.new(p + Vector3.new(0, 9, 0)) * CFrame.Angles(0, yaw, 0) * CFrame.new(0, 0, -1.4),
			Color = DARK_WOOD,
			Material = M.Wood,
		})
		effigy(folder, CFrame.new(p + Vector3.new(0, 8.6, 0)) * CFrame.Angles(0, yaw, 0) * CFrame.new(0, 0, -2.6), rng:NextNumber(0.8, 1.2))
	end)
end

return Forest
