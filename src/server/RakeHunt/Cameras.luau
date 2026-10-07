-- Telecamere di sorveglianza: piazzamento, batteria, rilevamento della creatura e copertura della mappa.
-- Tipi: Fissa (economica), IR (vede di notte), Motorizzata (ruota dal tablet), Trappola (scatta sul movimento).
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local Forest = require(script.Parent.Forest)

local C = Config.CAMERAS
local make = Forest.make

local Cameras = {}

local ctx
local folder: Folder
local nextId = 0
local data: { [Model]: { useful: boolean, notified: number, lastSnap: number } } = {}
local keyCells: { Vector3 } = {}

local TYPE_COLORS = {
	Fissa = Color3.fromRGB(70, 70, 75),
	IR = Color3.fromRGB(40, 70, 45),
	Motorizzata = Color3.fromRGB(60, 65, 95),
	Trappola = Color3.fromRGB(110, 85, 45),
}

local function flat(v: Vector3): Vector3
	return Vector3.new(v.X, 0, v.Z)
end

local function inCone(cf: CFrame, target: Vector3, range: number): boolean
	local to = flat(target - cf.Position)
	if to.Magnitude > range then
		return false
	end
	if to.Magnitude < 1 then
		return true
	end
	local look = flat(cf.LookVector).Unit
	return math.deg(math.acos(math.clamp(look:Dot(to.Unit), -1, 1))) <= C.FOV / 2
end

function Cameras.init(c)
	ctx = c
	folder = make("Folder", ctx.world, { Name = "Telecamere" })
	-- Celle "importanti" per la copertura: sentieri e punti di interesse
	local half = Forest.HALF
	local cell = C.COVERAGE_CELL
	for x = -half + cell / 2, half, cell do
		for z = -half + cell / 2, half, cell do
			local p = Vector3.new(x, 0, z)
			local _, poiDist = Forest.nearestPoi(p)
			if not Forest.inLake(p) and (Forest.distToPath(p) < 14 or poiDist < 40) then
				table.insert(keyCells, p)
			end
		end
	end
end

function Cameras.folder(): Folder
	return folder
end

function Cameras.updateCoverage()
	local online = {}
	for _, m in folder:GetChildren() do
		if m:GetAttribute("Online") and m.PrimaryPart then
			table.insert(online, m)
		end
	end
	local covered = 0
	for _, p in keyCells do
		for _, m in online do
			local range = m:GetAttribute("Type") == "Trappola" and C.TRAP_RANGE or C.VIEW_RANGE
			if inCone(m.PrimaryPart.CFrame, p, range) then
				covered += 1
				break
			end
		end
	end
	ctx.state:SetAttribute("Coverage", #keyCells > 0 and math.floor(covered / #keyCells * 100 + 0.5) or 0)
	ctx.state:SetAttribute("CamerasActive", #online)
end

function Cameras.reset()
	folder:ClearAllChildren()
	table.clear(data)
	nextId = 0
	Cameras.updateCoverage()
end

local function setOnline(m: Model, online: boolean)
	m:SetAttribute("Online", online)
	local led = m:FindFirstChild("Led") :: BasePart?
	if led then
		led.Color = online and Color3.fromRGB(255, 40, 40) or Color3.fromRGB(40, 40, 40)
	end
end

function Cameras.recover(player: Player, m: Model)
	if not m.Parent or not ctx.team.isStanding(player) then
		return
	end
	local camType = m:GetAttribute("Type")
	local key = "Kits_" .. camType
	player:SetAttribute(key, (player:GetAttribute(key) or 0) + 1)
	data[m] = nil
	m:Destroy()
	ctx.notify(("Telecamera %s recuperata (batteria ricaricata)."):format(camType), player)
	Cameras.updateCoverage()
end

function Cameras.place(player: Player)
	if not ctx.round.active then
		ctx.notify("Le telecamere si piazzano durante la notte.", player)
		return
	end
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	if not hrp or not ctx.team.isStanding(player) then
		return
	end
	local camType = player:GetAttribute("CamType") or "Fissa"
	local key = "Kits_" .. camType
	local kits = player:GetAttribute(key) or 0
	if kits <= 0 then
		ctx.notify(("Non hai più telecamere %s: premi R per cambiare tipo."):format(camType), player)
		return
	end

	local look = flat(hrp.CFrame.LookVector)
	look = look.Magnitude > 0.1 and look.Unit or Vector3.new(0, 0, -1)
	local base = hrp.Position + look * 3
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { workspace.Terrain }
	local ground = workspace:Raycast(base + Vector3.new(0, 6, 0), Vector3.new(0, -40, 0), params)
	local y = ground and ground.Position.Y or 0

	nextId += 1
	local m = Instance.new("Model")
	m.Name = "Cam" .. nextId
	local bodyPos = Vector3.new(base.X, y + 3.8, base.Z)
	local bodyCF = CFrame.lookAt(bodyPos, bodyPos + look)
	make("Part", m, {
		Name = "Treppiede",
		Size = Vector3.new(0.3, 3.4, 0.3),
		CFrame = CFrame.new(base.X, y + 1.7, base.Z),
		Color = Color3.fromRGB(30, 30, 30),
		CanCollide = false,
		CanQuery = false,
	})
	local body = make("Part", m, {
		Name = "Body",
		Size = Vector3.new(1.2, 0.9, 1.6),
		CFrame = bodyCF,
		Color = TYPE_COLORS[camType] or TYPE_COLORS.Fissa,
		Material = Enum.Material.Metal,
		CanCollide = false,
		CanQuery = false,
	})
	make("Part", m, {
		Name = "Obiettivo",
		Size = Vector3.new(0.6, 0.6, 0.2),
		CFrame = bodyCF * CFrame.new(0, 0, -0.85),
		Color = Color3.fromRGB(10, 10, 15),
		Material = Enum.Material.Glass,
		CanCollide = false,
		CanQuery = false,
	})
	make("Part", m, {
		Name = "Led",
		Size = Vector3.new(0.18, 0.18, 0.18),
		CFrame = bodyCF * CFrame.new(0.4, 0.35, -0.75),
		Color = Color3.fromRGB(255, 40, 40),
		Material = Enum.Material.Neon,
		CanCollide = false,
		CanQuery = false,
	})
	local flash = make("PointLight", body, { Range = 30, Brightness = 6, Enabled = false, Color = Color3.fromRGB(255, 255, 255) })
	flash.Name = "Flash"
	if Config.SOUNDS.TRAP_SNAP ~= "" and camType == "Trappola" then
		make("Sound", body, { Name = "Scatto", SoundId = Config.SOUNDS.TRAP_SNAP, Volume = 1, RollOffMaxDistance = 60 })
	end
	m.PrimaryPart = body

	local label = Forest.describe(base)
	m:SetAttribute("Id", nextId)
	m:SetAttribute("Type", camType)
	m:SetAttribute("Owner", player.UserId)
	m:SetAttribute("OwnerName", player.DisplayName)
	m:SetAttribute("Battery", C.BATTERY)
	m:SetAttribute("Online", true)
	m:SetAttribute("Label", label)
	m:SetAttribute("Sees", false)
	m:SetAttribute("Yaw", math.deg(math.atan2(-look.X, -look.Z)))

	local prompt = make("ProximityPrompt", body, {
		ActionText = "Recupera",
		ObjectText = ("Camera %d · %s"):format(nextId, camType),
		HoldDuration = 1,
		MaxActivationDistance = 8,
		RequiresLineOfSight = false,
	})
	prompt.Triggered:Connect(function(p)
		Cameras.recover(p, m)
	end)

	data[m] = { useful = false, notified = 0, lastSnap = 0 }
	m.Parent = folder
	player:SetAttribute(key, kits - 1)
	ctx.notify(("📷 Camera %d (%s) piazzata %s."):format(nextId, camType, label), player)
	Cameras.updateCoverage()
end

function Cameras.rotate(player: Player, id: any, dir: any)
	if typeof(id) ~= "number" or (dir ~= 1 and dir ~= -1) then
		return
	end
	for _, m in folder:GetChildren() do
		if m:GetAttribute("Id") == id then
			if m:GetAttribute("Type") ~= "Motorizzata" or not m:GetAttribute("Online") then
				return
			end
			local yaw = (m:GetAttribute("Yaw") or 0) + dir * 20
			m:SetAttribute("Yaw", yaw)
			m:PivotTo(CFrame.new(m.PrimaryPart.Position) * CFrame.Angles(0, math.rad(yaw), 0))
			Cameras.updateCoverage()
			return
		end
	end
end

local function snap(m: Model, rakePos: Vector3)
	local body = m.PrimaryPart
	local flash = body:FindFirstChild("Flash") :: PointLight?
	if flash then
		flash.Enabled = true
		task.delay(0.15, function()
			flash.Enabled = false
		end)
	end
	local sound = body:FindFirstChild("Scatto") :: Sound?
	if sound then
		sound:Play()
	end
	ctx.notifyAll(("📸 La camera trappola %d (%s) ha fotografato qualcosa!"):format(m:GetAttribute("Id"), m:GetAttribute("Label")))
	ctx.addTracking(C.TRAP_TRACKING)
	ctx.setLastSeen(rakePos)
end

function Cameras.tick(dt: number)
	local rakePos = ctx.rake.position()
	local night = ctx.isNight()
	local noise = ctx.weather.cameraNoise
	local now = os.clock()
	local changed = false
	for _, m in folder:GetChildren() do
		local body = m.PrimaryPart
		local info = data[m]
		if not body or not info then
			continue
		end
		local online = m:GetAttribute("Online")
		if online then
			local battery = math.max(0, m:GetAttribute("Battery") - dt)
			m:SetAttribute("Battery", battery)
			if battery <= 0 then
				online = false
				setOnline(m, false)
				changed = true
				ctx.notifyAll(("🔋 La camera %d (%s) si è scaricata."):format(m:GetAttribute("Id"), m:GetAttribute("Label")))
			end
		end

		local camType = m:GetAttribute("Type")
		local sees = false
		if online and rakePos then
			local range = camType == "Trappola" and C.TRAP_RANGE or C.VIEW_RANGE
			if night and camType ~= "IR" and camType ~= "Trappola" then
				range *= C.NIGHT_RANGE_FACTOR
			end
			range *= 1 - noise * 0.5
			sees = inCone(body.CFrame, rakePos, range) and ctx.rake.visibleFrom(body.Position, { folder })
		end

		if camType == "Trappola" then
			if sees and now - info.lastSnap > C.TRAP_COOLDOWN then
				info.lastSnap = now
				snap(m, rakePos)
				if not info.useful then
					info.useful = true
					ctx.credit(m:GetAttribute("Owner"), "sightings")
				end
			end
			sees = false
		elseif sees then
			ctx.addTracking(Config.EVIDENCE.SIGHTING_RATE * dt)
			ctx.setLastSeen(rakePos)
			if not info.useful then
				info.useful = true
				ctx.credit(m:GetAttribute("Owner"), "sightings")
			end
			if now - info.notified > 30 then
				info.notified = now
				ctx.notifyAll(("📹 Movimento sulla camera %d (%s)!"):format(m:GetAttribute("Id"), m:GetAttribute("Label")))
			end
		end
		if m:GetAttribute("Sees") ~= sees then
			m:SetAttribute("Sees", sees)
		end
	end
	if changed then
		Cameras.updateCoverage()
	end
end

return Cameras
