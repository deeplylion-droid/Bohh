-- Costruisce l'arena sospesa e la lobby, e trova punti casuali sulle superfici.
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)

local Arena = {}

local rng = Random.new()

local function makePart(props: { [string]: any }, parent: Instance): Part
	local part = Instance.new("Part")
	part.Anchored = true
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	for key, value in props do
		(part :: any)[key] = value
	end
	part.Parent = parent
	return part
end

local function ensureLobbySpawn()
	if workspace:FindFirstChildWhichIsA("SpawnLocation", true) then
		return
	end
	makePart({
		Name = "LobbyFloor",
		Size = Vector3.new(60, 1, 60),
		Position = Vector3.new(0, 0, 0),
		Material = Enum.Material.SmoothPlastic,
		Color = Color3.fromRGB(90, 90, 110),
	}, workspace)
	local spawn = Instance.new("SpawnLocation")
	spawn.Anchored = true
	spawn.Size = Vector3.new(12, 1, 12)
	spawn.Position = Vector3.new(0, 1, 0)
	spawn.Neutral = true
	spawn.Parent = workspace
end

function Arena.build(): Model
	ensureLobbySpawn()

	local existing = workspace:FindFirstChild("CoinRushArena")
	if existing then
		return existing
	end

	local model = Instance.new("Model")
	model.Name = "CoinRushArena"

	local size = Config.ARENA_SIZE
	local center = Config.ARENA_CENTER

	local floor = makePart({
		Name = "Floor",
		Size = Vector3.new(size, 2, size),
		Position = center,
		Material = Enum.Material.Grass,
		Color = Color3.fromRGB(75, 151, 75),
	}, model)
	model.PrimaryPart = floor

	-- Pilastri di altezze diverse: le monete in cima premiano chi sa saltare.
	local layout = Random.new(42)
	local half = size / 2 - 10
	for i = 1, Config.PILLAR_COUNT do
		local height = layout:NextInteger(3, 14)
		local width = layout:NextInteger(6, 12)
		makePart({
			Name = "Pillar" .. i,
			Size = Vector3.new(width, height, width),
			Position = center
				+ Vector3.new(layout:NextNumber(-half, half), 1 + height / 2, layout:NextNumber(-half, half)),
			Material = Enum.Material.Slate,
			Color = Color3.fromHSV(layout:NextNumber(), 0.35, 0.75),
		}, model)
	end

	model.Parent = workspace
	return model
end

-- Restituisce un punto casuale sopra la prima superficie dell'arena colpita dall'alto.
function Arena.randomSurfacePoint(model: Model, heightOffset: number): Vector3
	local floor = model.PrimaryPart :: BasePart
	local half = Config.ARENA_SIZE / 2 - 6
	local x = floor.Position.X + rng:NextNumber(-half, half)
	local z = floor.Position.Z + rng:NextNumber(-half, half)
	local top = floor.Position.Y + 100

	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { model }

	local result = workspace:Raycast(Vector3.new(x, top, z), Vector3.new(0, -200, 0), params)
	local y = if result then result.Position.Y else floor.Position.Y + floor.Size.Y / 2
	return Vector3.new(x, y + heightOffset, z)
end

function Arena.floorHeight(model: Model): number
	local floor = model.PrimaryPart :: BasePart
	return floor.Position.Y + floor.Size.Y / 2
end

return Arena
