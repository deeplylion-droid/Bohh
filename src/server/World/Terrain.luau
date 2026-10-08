-- Genera il terreno della montagna con i voxel di Roblox.
-- L'altezza di ogni colonna e' il massimo di "elementi": la vetta, le terrazze del sentiero
-- (piatte sul sentiero e con scarpate ripide intorno), le isole dei tornanti, il cratere e il vulcano.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)

local Terrain = {}

local RES = 4
local X0, X1 = -324, 324
local Z0, Z1 = -332, 832
local Y0, Y1 = 44, 344

type Feature = { x: number, z: number, y: number, r: number, k: number, kind: string, zone: string }

local features: { Feature } = {}
local buckets: { [number]: { Feature } } = {}
local BUCKET = 48
local REACH = 100 -- oltre questa distanza un elemento non puo' superare gli altri

local function bucketKey(bx: number, bz: number): number
	return bx * 10000 + bz
end

local function addFeature(f: Feature)
	table.insert(features, f)
end

local function indexFeatures()
	for _, f in features do
		local reach = f.r + REACH
		for bx = math.floor((f.x - reach) / BUCKET), math.floor((f.x + reach) / BUCKET) do
			for bz = math.floor((f.z - reach) / BUCKET), math.floor((f.z + reach) / BUCKET) do
				local key = bucketKey(bx, bz)
				local list = buckets[key]
				if not list then
					list = {}
					buckets[key] = list
				end
				table.insert(list, f)
			end
		end
	end
end

local function noise(x: number, z: number, scale: number, seed: number): number
	return math.noise(x / scale, z / scale, seed)
end

local function rampHeight(z: number): number
	-- rampa dalla piazza (z=150, y=330) al primo tratto (z=220, y=318)
	local t = math.clamp((z - 150) / 70, 0, 1)
	return 330 + (318 - 330) * t
end

-- materiale del sentiero in ogni zona
local PATH_MATERIAL = {
	Meadow = Enum.Material.Sand,
	Forest = Enum.Material.Cobblestone,
	Canyon = Enum.Material.Ground,
	Crystal = Enum.Material.Limestone,
	Crater = Enum.Material.Asphalt,
}
Terrain.PathMaterial = PATH_MATERIAL

local function buildFeatures()
	table.clear(features)
	table.clear(buckets)
	-- terrazze del sentiero: campioni ogni 3 stud; la superficie del terreno E' il sentiero
	for _, smp in MapLayout.SamplePath(3) do
		addFeature({ x = smp.pos.X, z = smp.pos.Z, y = smp.pos.Y, r = MapLayout.PathWidth / 2 + 1, k = 1.75, kind = "path", zone = smp.zone })
	end
	-- isole al centro dei tornanti (altrimenti diventerebbero buche)
	for i = 1, #MapLayout.Legs - 1 do
		local leg, nxt = MapLayout.Legs[i], MapLayout.Legs[i + 1]
		addFeature({ x = leg.x1, z = (leg.z + nxt.z) / 2, y = (leg.y1 + nxt.y0) / 2 + 7, r = 9, k = 0.9, kind = "island", zone = leg.zone })
	end
	indexFeatures()
end

-- Prepara gli elementi (sentiero, isole, vulcano): va chiamata prima di HeightAt
function Terrain.Prepare()
	if #features == 0 then
		buildFeatures()
	end
end

-- Altezza della superficie nel punto (x, z), tipo di elemento dominante e zona
function Terrain.HeightAt(x: number, z: number): (number, string, string)
	local best, kind, zone = -math.huge, "flank", "Summit"
	-- vetta
	local r = math.sqrt(x * x + z * z)
	local plateau = (MapLayout.SummitY - 1) - math.max(0, r - MapLayout.PlateauRadius) * 2.0
	if math.abs(x) < 34 and z > 132 then
		-- corridoio della rampa: la vetta non deve coprire la rampa
		local ramp = rampHeight(z)
		local w = math.clamp((math.abs(x) - 26) / 8, 0, 1)
		plateau = math.min(plateau, ramp + (plateau - ramp) * w)
	end
	if plateau > best then
		best, kind = plateau, if r <= MapLayout.PlateauRadius then "summit" else "flank"
	end
	-- elementi vicini (la zona viene dall'elemento che "vince" con un po' di rumore,
	-- cosi' i confini fra le zone sulle scarpate sono irregolari e naturali)
	local list = buckets[bucketKey(math.floor(x / BUCKET), math.floor(z / BUCKET))]
	if list then
		local zoneScore = -math.huge
		local jitter = noise(x, z, 14, 5.5) * 9
		for _, f in list do
			local d = math.sqrt((x - f.x) ^ 2 + (z - f.z) ^ 2)
			local h = f.y - math.max(0, d - f.r) * f.k
			if h > best then
				best = h
				kind = if d <= f.r then f.kind else "bank"
			end
			local score = h + (if f.zone == zone then 0 else jitter)
			if score > zoneScore then
				zoneScore = score
				zone = f.zone
			end
		end
		if best < plateau + 0.01 and kind ~= "path" then
			zone = "Summit"
		end
	end
	-- cratere: conca con bordo rialzato e varco verso la rampa d'ingresso
	local cc = MapLayout.Crater.Center
	local cr = math.sqrt((x - cc.X) ^ 2 + (z - cc.Z) ^ 2)
	if cr < MapLayout.Crater.RimRadius + 90 then
		local floorY = cc.Y - 1
		local rimY = MapLayout.Crater.RimHeight
		local h
		if cr <= MapLayout.Crater.Radius then
			h = floorY
		elseif cr <= MapLayout.Crater.RimRadius then
			local t = (cr - MapLayout.Crater.Radius) / (MapLayout.Crater.RimRadius - MapLayout.Crater.Radius)
			h = floorY + (rimY - floorY) * (t * t * (3 - 2 * t))
		else
			h = rimY - (cr - MapLayout.Crater.RimRadius) * 1.4
		end
		-- varco: verso la rampa (direzione dal centro a (55, 530)) il bordo si abbassa
		local gate = Vector3.new(55 - cc.X, 0, 530 - cc.Z).Unit
		local dir = Vector3.new(x - cc.X, 0, z - cc.Z)
		if dir.Magnitude > 1 then
			local align = dir.Unit:Dot(gate)
			if align > 0.82 and cr > MapLayout.Crater.Radius - 4 then
				h = math.min(h, floorY + (cr - MapLayout.Crater.Radius) * 0.4)
			end
		end
		if cr <= MapLayout.Crater.Radius then
			best, kind, zone = h, "crater", "Crater"
		elseif h > best then
			best, kind, zone = h, "rim", "Crater"
		end
	end
	-- rumore sulle scarpate (mai sulle superfici calpestabili)
	if kind == "bank" or kind == "flank" or kind == "rim" then
		best += noise(x, z, 26, 3.1) * 5 + noise(x, z, 9, 8.7) * 1.6
	end
	return best, kind, zone
end

-- Materiale della superficie in base a zona e pendenza (ogni zona usa materiali propri,
-- cosi' i colori globali dei materiali restano distinti fra le zone)
local function surfaceMaterial(y: number, kind: string, zone: string, slope: number): Enum.Material
	if kind == "path" then
		return PATH_MATERIAL[zone] or Enum.Material.Sand
	end
	if y < MapLayout.CloudSeaY - 6 then
		return Enum.Material.Rock
	end
	local steep = slope > 1.25
	local cliff = slope > 2.2
	if kind == "crater" then
		return Enum.Material.Basalt
	end
	if kind == "rim" then
		return if steep then Enum.Material.Basalt else Enum.Material.CrackedLava
	end
	if zone == "Summit" then
		if y > 318 then
			return if cliff then Enum.Material.Glacier elseif steep then Enum.Material.Rock else Enum.Material.Snow
		end
		return if steep then Enum.Material.Rock else Enum.Material.Grass
	elseif zone == "Meadow" then
		return if cliff then Enum.Material.Rock else Enum.Material.Grass
	elseif zone == "Forest" then
		return if cliff then Enum.Material.Mud else Enum.Material.LeafyGrass
	elseif zone == "Canyon" then
		return if steep then Enum.Material.Sandstone else Enum.Material.Ground
	elseif zone == "Crystal" then
		return if steep then Enum.Material.Slate else Enum.Material.Salt
	end
	return if steep then Enum.Material.Basalt else Enum.Material.CrackedLava
end

Terrain.SurfaceMaterial = surfaceMaterial

Terrain.Colors = {
	[Enum.Material.Grass] = Color3.fromRGB(112, 200, 74),
	[Enum.Material.LeafyGrass] = Color3.fromRGB(70, 160, 76),
	[Enum.Material.Rock] = Color3.fromRGB(146, 152, 170),
	[Enum.Material.Slate] = Color3.fromRGB(116, 112, 146),
	[Enum.Material.Snow] = Color3.fromRGB(242, 247, 255),
	[Enum.Material.Glacier] = Color3.fromRGB(176, 226, 255),
	[Enum.Material.Ground] = Color3.fromRGB(196, 152, 104),
	[Enum.Material.Sandstone] = Color3.fromRGB(228, 132, 78),
	[Enum.Material.Salt] = Color3.fromRGB(168, 150, 214),
	[Enum.Material.Basalt] = Color3.fromRGB(66, 58, 72),
	[Enum.Material.CrackedLava] = Color3.fromRGB(255, 104, 36),
	[Enum.Material.Mud] = Color3.fromRGB(104, 78, 58),
	[Enum.Material.Sand] = Color3.fromRGB(236, 204, 146),
	[Enum.Material.Cobblestone] = Color3.fromRGB(176, 150, 118),
	[Enum.Material.Limestone] = Color3.fromRGB(206, 196, 236),
	[Enum.Material.Asphalt] = Color3.fromRGB(92, 80, 88),
}

-- Costruisce tutto il terreno (alcuni secondi). Restituisce il numero di voxel pieni.
function Terrain.Build(): number
	local terrain = workspace.Terrain
	for mat, color in Terrain.Colors do
		terrain:SetMaterialColor(mat, color)
	end
	Terrain.Prepare()

	local nx = (X1 - X0) // RES
	local nz = (Z1 - Z0) // RES
	local ny = (Y1 - Y0) // RES
	-- mappa delle altezze sui centri delle colonne
	local heights = table.create(nx)
	local kinds = table.create(nx)
	local zones = table.create(nx)
	for ix = 1, nx do
		local hx = table.create(nz)
		local kx = table.create(nz)
		local zx = table.create(nz)
		local x = X0 + (ix - 0.5) * RES
		for iz = 1, nz do
			local z = Z0 + (iz - 0.5) * RES
			local h, k, zn = Terrain.HeightAt(x, z)
			hx[iz] = h
			kx[iz] = k
			zx[iz] = zn
		end
		heights[ix] = hx
		kinds[ix] = kx
		zones[ix] = zx
		if ix % 16 == 0 then
			task.wait()
		end
	end

	local filled = 0
	local CHUNK = 16
	for cx = 1, nx, CHUNK do
		local cw = math.min(CHUNK, nx - cx + 1)
		local mats = table.create(cw)
		local occ = table.create(cw)
		for i = 1, cw do
			local ix = cx + i - 1
			local mx = table.create(ny)
			local ox = table.create(ny)
			for iy = 1, ny do
				mx[iy] = table.create(nz, Enum.Material.Air)
				ox[iy] = table.create(nz, 0)
			end
			for iz = 1, nz do
				local h = heights[ix][iz]
				if h > Y0 then
					local hl = heights[math.max(ix - 1, 1)][iz]
					local hr = heights[math.min(ix + 1, nx)][iz]
					local hd = heights[ix][math.max(iz - 1, 1)]
					local hu = heights[ix][math.min(iz + 1, nz)]
					local slope = math.sqrt(((hr - hl) / (2 * RES)) ^ 2 + ((hu - hd) / (2 * RES)) ^ 2)
					local top = surfaceMaterial(h, kinds[ix][iz], zones[ix][iz], slope)
					for iy = 1, ny do
						local yb = Y0 + (iy - 1) * RES
						if yb >= h then
							break
						end
						local o = math.clamp((h - yb) / RES, 0, 1)
						ox[iy][iz] = o
						mx[iy][iz] = if h - yb < RES * 2.2 then top else Enum.Material.Rock
						filled += 1
					end
				end
			end
			mats[i] = mx
			occ[i] = ox
		end
		local region = Region3.new(
			Vector3.new(X0 + (cx - 1) * RES, Y0, Z0),
			Vector3.new(X0 + (cx - 1 + cw) * RES, Y1, Z1)
		)
		terrain:WriteVoxels(region, RES, mats, occ)
		task.wait()
	end

	-- lava nelle pozze del cratere
	for _, pool in MapLayout.Crater.LavaPools do
		terrain:FillCylinder(CFrame.new(pool.center + Vector3.new(0, -0.5, 0)), 3, pool.radius, Enum.Material.CrackedLava)
	end
	return filled
end

return Terrain
