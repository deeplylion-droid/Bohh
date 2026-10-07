-- Prove e tracciamento: impronte, graffi, peli, sangue e carcasse lasciati dalla creatura.
-- Peli e sangue vanno analizzati al laboratorio. Alcune tracce sono depistaggi.
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local Forest = require(script.Parent.Forest)

local E = Config.EVIDENCE
local make = Forest.make

local Evidence = {}

local ctx
local folder: Folder
local rng = Random.new()
local analyzing = false

local DROP_TABLE = { "Impronte", "Impronte", "Impronte", "Graffi", "Graffi", "Peli", "Sangue", "Carcassa" }

local builders = {}

function builders.Impronte(m: Model, cf: CFrame): BasePart
	local main
	for i = 0, 2 do
		local side = i % 2 == 0 and -0.6 or 0.6
		local footprint = make("Part", m, {
			Size = Vector3.new(1.1, 0.1, 1.9),
			CFrame = cf * CFrame.new(side, 0.05, -i * 2.6),
			Color = Color3.fromRGB(45, 32, 25),
			Material = Enum.Material.Mud,
			CanCollide = false,
		})
		for t = -1, 1 do
			make("Part", m, {
				Size = Vector3.new(0.15, 0.1, 0.8),
				CFrame = cf * CFrame.new(side + t * 0.35, 0.06, -i * 2.6 - 1.3) * CFrame.Angles(0, t * 0.3, 0),
				Color = Color3.fromRGB(35, 25, 20),
				Material = Enum.Material.Mud,
				CanCollide = false,
			})
		end
		main = main or footprint
	end
	return main
end

function builders.Graffi(m: Model, cf: CFrame): BasePart
	local stump = make("Part", m, {
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(3, 2.4, 2.4),
		CFrame = cf * CFrame.new(0, 1.5, 0) * CFrame.Angles(0, 0, math.pi / 2),
		Color = Color3.fromRGB(80, 58, 40),
		Material = Enum.Material.Wood,
	})
	for i = -1, 1 do
		make("Part", m, {
			Size = Vector3.new(0.12, 1.8, 0.08),
			CFrame = cf * CFrame.new(i * 0.4, 1.6, -1.2) * CFrame.Angles(0, 0, 0.35),
			Color = Color3.fromRGB(215, 190, 150),
			Material = Enum.Material.Wood,
			CanCollide = false,
		})
	end
	return stump
end

function builders.Peli(m: Model, cf: CFrame): BasePart
	local main
	for i = 1, 3 do
		local p = make("Part", m, {
			Shape = Enum.PartType.Ball,
			Size = Vector3.new(0.6, 0.6, 0.6),
			CFrame = cf * CFrame.new(rng:NextNumber(-0.6, 0.6), 0.25, rng:NextNumber(-0.6, 0.6)),
			Color = Color3.fromRGB(150, 145, 135),
			Material = Enum.Material.Fabric,
			CanCollide = false,
		})
		main = main or p
	end
	return main
end

function builders.Sangue(m: Model, cf: CFrame): BasePart
	local main
	for i = 1, 4 do
		local d = rng:NextNumber(0.6, 2.2)
		local p = make("Part", m, {
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(0.08, d, d),
			CFrame = cf * CFrame.new(rng:NextNumber(-1.5, 1.5), 0.05, -i * 0.9) * CFrame.Angles(0, 0, math.pi / 2),
			Color = Color3.fromRGB(85, 10, 12),
			Material = Enum.Material.Glass,
			CanCollide = false,
		})
		main = main or p
	end
	return main
end

function builders.Carcassa(m: Model, cf: CFrame): BasePart
	local body = make("Part", m, {
		Size = Vector3.new(1.6, 1.3, 4),
		CFrame = cf * CFrame.new(0, 0.65, 0) * CFrame.Angles(0, 0, 0.3),
		Color = Color3.fromRGB(110, 75, 50),
		Material = Enum.Material.Fabric,
	})
	make("Part", m, {
		Size = Vector3.new(0.9, 0.9, 1.4),
		CFrame = cf * CFrame.new(0.3, 0.45, -2.6) * CFrame.Angles(0.2, 0.4, 0),
		Color = Color3.fromRGB(100, 70, 48),
		Material = Enum.Material.Fabric,
	})
	for i = -1, 1 do
		make("Part", m, {
			Size = Vector3.new(0.2, 1.3, 0.2),
			CFrame = cf * CFrame.new(-0.6, 1.2, i * 0.8) * CFrame.Angles(0, 0, -0.4),
			Color = Color3.fromRGB(225, 215, 195),
			CanCollide = false,
		})
	end
	return body
end

local function groundY(pos: Vector3): number
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { workspace.Terrain }
	local hit = workspace:Raycast(Vector3.new(pos.X, 40, pos.Z), Vector3.new(0, -80, 0), params)
	return hit and hit.Position.Y or 0
end

local function collect(player: Player, m: Model)
	if not m.Parent or not ctx.round.active or not ctx.team.isStanding(player) then
		return
	end
	local kind = m:GetAttribute("Type")
	local fake = m:GetAttribute("Fake")
	m:Destroy()
	if fake then
		ctx.notify("🐾 Traccia falsa! The Rake ti ha depistato.", player)
		ctx.rake.addAggression(4)
		return
	end
	ctx.credit(player.UserId, "evidence")
	ctx.state:SetAttribute("Evidence", (ctx.state:GetAttribute("Evidence") or 0) + 1)
	local value = E.TRACKING[kind] or 5
	if E.NEEDS_LAB[kind] then
		player:SetAttribute("Samples", (player:GetAttribute("Samples") or 0) + 1)
		player:SetAttribute("SamplePoints", (player:GetAttribute("SamplePoints") or 0) + value * E.LAB_MULTIPLIER)
		ctx.notify(("🧪 Campione raccolto (%s): portalo al laboratorio della Ranger Station."):format(kind), player)
	else
		ctx.addTracking(value)
		ctx.notify(("🔎 Prova raccolta: %s (+%d%% tracciamento)"):format(kind, value), player)
	end
end

function Evidence.spawn(kind: string, pos: Vector3, fake: boolean)
	local existing = folder:GetChildren()
	if #existing >= E.MAX_ACTIVE then
		existing[1]:Destroy()
	end
	local m = Instance.new("Model")
	m.Name = kind
	local cf = CFrame.new(pos.X, groundY(pos), pos.Z) * CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), 0)
	local main = builders[kind](m, cf)
	m:SetAttribute("Type", kind)
	m:SetAttribute("Fake", fake)
	local prompt = make("ProximityPrompt", main, {
		ActionText = "Raccogli",
		ObjectText = "Prova: " .. kind,
		HoldDuration = 1.5,
		MaxActivationDistance = 9,
		RequiresLineOfSight = false,
	})
	prompt.Triggered:Connect(function(player)
		collect(player, m)
	end)
	m.Parent = folder
end

-- Lascia una traccia vicino alla creatura (o un depistaggio lontano)
function Evidence.dropNear(pos: Vector3)
	if rng:NextNumber() < E.FAKE_CHANCE then
		local fakePos = Forest.randomGround(rng, pos, 80, 150)
		Evidence.spawn(rng:NextNumber() < 0.6 and "Impronte" or "Graffi", fakePos, true)
	else
		Evidence.spawn(DROP_TABLE[rng:NextInteger(1, #DROP_TABLE)], Forest.randomGround(rng, pos, 2, 6), false)
	end
end

-- Tracce iniziali intorno alla tana
function Evidence.seed(lair: Vector3)
	for _ = 1, E.START_COUNT do
		Evidence.spawn(DROP_TABLE[rng:NextInteger(1, #DROP_TABLE)], Forest.randomGround(rng, lair, 15, 130), false)
	end
end

function Evidence.analyze(player: Player)
	if not ctx.round.active or not ctx.team.isStanding(player) then
		return
	end
	local samples = player:GetAttribute("Samples") or 0
	if samples <= 0 then
		ctx.notify("Non hai campioni da analizzare: raccogli peli o sangue nel bosco.", player)
		return
	end
	if analyzing then
		ctx.notify("Il laboratorio è già occupato.", player)
		return
	end
	analyzing = true
	local points = player:GetAttribute("SamplePoints") or 0
	player:SetAttribute("Samples", 0)
	player:SetAttribute("SamplePoints", 0)
	ctx.notifyAll(("🔬 Analisi di %d campion%s in corso (%d s)… il generatore fa rumore e attira la creatura!"):format(
		samples,
		samples == 1 and "e" or "i",
		E.LAB_TIME
	))
	ctx.rake.addAggression(10)
	ctx.rake.hearNoise(Forest.STATION, 1)
	local light = Forest.labLight
	task.spawn(function()
		local finish = os.clock() + E.LAB_TIME
		while os.clock() < finish and ctx.round.active do
			if light then
				light.Color = light.Color == Color3.fromRGB(120, 200, 255) and Color3.fromRGB(255, 80, 80) or Color3.fromRGB(120, 200, 255)
			end
			task.wait(0.4)
		end
		if light then
			light.Color = Color3.fromRGB(120, 200, 255)
		end
		analyzing = false
		if ctx.round.active then
			ctx.addTracking(points)
			ctx.notifyAll(("🔬 Analisi completata: +%d%% tracciamento."):format(points))
		end
	end)
end

function Evidence.init(c)
	ctx = c
	folder = make("Folder", ctx.world, { Name = "Prove" })
end

function Evidence.reset()
	folder:ClearAllChildren()
	analyzing = false
end

return Evidence
