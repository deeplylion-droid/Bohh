-- Client di "The Rake": controlli, stamina e fiatone, Paura e allucinazioni, visore notturno,
-- fucile a dardi, tablet delle telecamere e HUD.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Lighting = game:GetService("Lighting")
local ContextActionService = game:GetService("ContextActionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Debris = game:GetService("Debris")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local Hud = require(script:WaitForChild("Hud"))
local Tablet = require(script:WaitForChild("Tablet"))

local player = Players.LocalPlayer
local mouse = player:GetMouse()
local state = ReplicatedStorage:WaitForChild("RakeState")
local remotes = ReplicatedStorage:WaitForChild("RakeRemotes")

local P = Config.PLAYER
local NV_MAX = Config.EQUIPMENT.NIGHT_VISION_BATTERY

local hud = Hud.new(player, state)
local tablet = Tablet.new(player, state, remotes, hud)

remotes.Notify.OnClientEvent:Connect(function(message)
	hud:notify(message)
end)
remotes.Debrief.OnClientEvent:Connect(function(data)
	tablet:close()
	hud:showDebrief(data)
end)
remotes.OpenTablet.OnClientEvent:Connect(function()
	tablet:open()
end)

---------------------------------------------------------------------------------------------
-- Controlli

local sprintHeld = false
local nvOn = false
local nvBattery = NV_MAX

ContextActionService:BindAction("Scatto", function(_, inputState)
	sprintHeld = inputState == Enum.UserInputState.Begin
	return Enum.ContextActionResult.Pass
end, true, Enum.KeyCode.LeftShift, Enum.KeyCode.ButtonL3)
ContextActionService:SetTitle("Scatto", "Corri")

ContextActionService:BindAction("Tablet", function(_, inputState)
	if inputState == Enum.UserInputState.Begin then
		tablet:toggle()
	end
	return Enum.ContextActionResult.Sink
end, true, Enum.KeyCode.T, Enum.KeyCode.ButtonY)
ContextActionService:SetTitle("Tablet", "Tablet")

ContextActionService:BindAction("Visore", function(_, inputState)
	if inputState == Enum.UserInputState.Begin then
		if not nvOn and nvBattery <= 0 then
			hud:notify("Visore notturno scarico: ricaricalo al Rifornimento.")
		else
			nvOn = not nvOn
		end
	end
	return Enum.ContextActionResult.Sink
end, true, Enum.KeyCode.N, Enum.KeyCode.ButtonX)
ContextActionService:SetTitle("Visore", "Visore")

ContextActionService:BindAction("TipoCamera", function(_, inputState)
	if inputState == Enum.UserInputState.Begin then
		remotes.CycleCameraType:FireServer()
	end
	return Enum.ContextActionResult.Sink
end, true, Enum.KeyCode.R, Enum.KeyCode.ButtonB)
ContextActionService:SetTitle("TipoCamera", "Tipo cam")

player:GetAttributeChangedSignal("SupplyTick"):Connect(function()
	nvBattery = NV_MAX
end)

-- Il fucile a dardi mira dove punta il mouse (o il tocco)
local hooked = setmetatable({}, { __mode = "k" })
local function hookTool(tool: Instance)
	if not tool:IsA("Tool") or hooked[tool] then
		return
	end
	hooked[tool] = true
	if tool.Name == "Fucile a dardi" then
		tool.Activated:Connect(function()
			if not tablet.isOpen then
				remotes.FireDart:FireServer(mouse.Hit.Position)
			end
		end)
	end
end

local function watchContainer(container: Instance)
	for _, child in container:GetChildren() do
		hookTool(child)
	end
	container.ChildAdded:Connect(hookTool)
end

player.CharacterAdded:Connect(function(char)
	tablet:close()
	watchContainer(char)
	watchContainer(player:WaitForChild("Backpack"))
end)
if player.Character then
	watchContainer(player.Character)
	watchContainer(player:WaitForChild("Backpack"))
end

---------------------------------------------------------------------------------------------
-- Effetti locali

local nvEffect = Instance.new("ColorCorrectionEffect")
nvEffect.Name = "VisoreNotturno"
nvEffect.TintColor = Color3.fromRGB(130, 255, 150)
nvEffect.Brightness = 0.3
nvEffect.Contrast = 0.25
nvEffect.Saturation = -1
nvEffect.Enabled = false
nvEffect.Parent = Lighting

local fearEffect = Instance.new("ColorCorrectionEffect")
fearEffect.Name = "Paura"
fearEffect.Parent = Lighting

local function rakeRoot(): BasePart?
	local folder = workspace:FindFirstChild("RakeHunt")
	local rake = folder and folder:FindFirstChild("TheRake")
	return rake and rake:FindFirstChild("HumanoidRootPart") :: BasePart?
end

-- Allucinazione: una sagoma della creatura appare per un istante tra gli alberi (solo per te)
local function hallucinate()
	local camera = workspace.CurrentCamera
	local look = camera.CFrame.LookVector * Vector3.new(1, 0, 1)
	if look.Magnitude < 0.1 then
		return
	end
	local dir = CFrame.Angles(0, math.rad(math.random(-35, 35)), 0) * look.Unit
	local pos = camera.CFrame.Position + dir * math.random(25, 40)
	local ghost = Instance.new("Model")
	local function part(size: Vector3, offset: Vector3, color: Color3, neon: boolean?)
		local p = Instance.new("Part")
		p.Anchored = true
		p.CanCollide = false
		p.CanQuery = false
		p.CastShadow = false
		p.Size = size
		p.Color = color
		p.Material = neon and Enum.Material.Neon or Enum.Material.SmoothPlastic
		p.CFrame = CFrame.lookAt(Vector3.new(pos.X, 0, pos.Z), Vector3.new(camera.CFrame.Position.X, 0, camera.CFrame.Position.Z))
			* CFrame.new(offset)
		p.Parent = ghost
	end
	local dark = Color3.fromRGB(10, 10, 10)
	part(Vector3.new(1.5, 3, 0.9), Vector3.new(0, 4.4, 0), dark)
	part(Vector3.new(1.2, 1.4, 1.2), Vector3.new(0, 6.4, -0.3), dark)
	part(Vector3.new(0.6, 3, 0.6), Vector3.new(-0.5, 1.5, 0), dark)
	part(Vector3.new(0.6, 3, 0.6), Vector3.new(0.5, 1.5, 0), dark)
	part(Vector3.new(0.3, 0.3, 0.1), Vector3.new(-0.28, 6.6, -0.95), Color3.fromRGB(255, 245, 225), true)
	part(Vector3.new(0.3, 0.3, 0.1), Vector3.new(0.28, 6.6, -0.95), Color3.fromRGB(255, 245, 225), true)
	ghost.Parent = camera
	Debris:AddItem(ghost, 0.7)
	hud:pulse()
end

local function spectate()
	local camera = workspace.CurrentCamera
	local subject = camera.CameraSubject
	if subject and subject:IsA("Humanoid") and subject.Health > 0 and subject.Parent ~= player.Character then
		return
	end
	for _, other in Players:GetPlayers() do
		local hum = other ~= player and other.Character and other.Character:FindFirstChildOfClass("Humanoid")
		if hum and hum.Health > 0 and other:GetAttribute("Status") ~= "Fuori" then
			camera.CameraSubject = hum
			return
		end
	end
end

---------------------------------------------------------------------------------------------
-- Ciclo per frame: stamina, paura, velocità, visore

local stamina, fear = 100, 0
local exhausted, panic = false, false
local nextHallucination = 0

RunService.RenderStepped:Connect(function(dt)
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	local status = player:GetAttribute("Status") or "Lobby"
	local phase = state:GetAttribute("Phase")

	-- Stamina e fiatone
	local moving = hum ~= nil and hum.MoveDirection.Magnitude > 0.1
	local sprinting = sprintHeld and moving and not exhausted and stamina > 0 and (status == "OK" or status == "Lobby")
	if sprinting then
		stamina -= P.STAMINA_DRAIN * dt
		if stamina <= 0 then
			stamina = 0
			exhausted = true
		end
	else
		stamina = math.min(100, stamina + P.STAMINA_REGEN * dt)
		if exhausted and stamina >= 35 then
			exhausted = false
		end
	end

	-- Paura: sale al buio, da soli e con la creatura vicina; scende vicino ai compagni e alle luci
	if phase == "Notte" and status == "OK" and hrp then
		local pos = hrp.Position
		local dark = Lighting.ClockTime >= 19.5 or Lighting.ClockTime < 6
		local atStation = Vector3.new(pos.X, 0, pos.Z).Magnitude < Config.MAP.STATION_RADIUS
		local lit = player:GetAttribute("TorchOn") or nvOn or atStation
		local mates = 0
		for _, other in Players:GetPlayers() do
			local otherRoot = other ~= player and other.Character and other.Character:FindFirstChild("HumanoidRootPart")
			if otherRoot and other:GetAttribute("Status") == "OK" and (otherRoot.Position - pos).Magnitude < 25 then
				mates += 1
			end
		end
		local rate = 0
		if dark and not lit then
			rate += 5
		end
		rate += mates == 0 and 2.5 or -4 * mates
		if lit then
			rate -= 3
		end
		if atStation then
			rate -= 10
		end
		local root = rakeRoot()
		if root then
			local d = (root.Position - pos).Magnitude
			if d < 70 then
				rate += (70 - d) / 70 * 30
			end
		end
		fear = math.clamp(fear + rate * dt, 0, 100)
	else
		fear = math.max(0, fear - 20 * dt)
	end
	if fear >= 100 then
		panic = true
	elseif fear < 70 then
		panic = false
	end
	if panic and os.clock() > nextHallucination then
		nextHallucination = os.clock() + math.random(5, 11)
		hallucinate()
	end
	local fearAmount = math.clamp((fear - 40) / 60, 0, 1)
	fearEffect.Saturation = -0.6 * fearAmount
	fearEffect.Contrast = 0.2 * fearAmount

	-- Velocità (il server la azzera quando sei braccato)
	if hum then
		if status == "Braccato" or tablet.isOpen then
			hum.WalkSpeed = 0
		elseif status == "OK" or status == "Lobby" then
			local speed = sprinting and P.SPRINT_SPEED or P.WALK_SPEED
			if exhausted then
				speed = P.WALK_SPEED * 0.8
			end
			if panic then
				speed *= P.FEAR_SLOWDOWN
			end
			hum.WalkSpeed = speed
		end
	end

	-- Visore notturno
	if nvOn then
		nvBattery -= dt
		if nvBattery <= 0 then
			nvBattery = 0
			nvOn = false
			hud:notify("Visore notturno scarico.")
		end
	end
	nvEffect.Enabled = nvOn and not tablet.isOpen

	if status == "Fuori" and phase == "Notte" and not tablet.isOpen then
		spectate()
	end

	hud:update({
		config = Config,
		stamina = stamina,
		fear = fear,
		nv = nvBattery / NV_MAX,
		nvOn = nvOn,
		exhausted = exhausted,
		panic = panic,
	})
end)
