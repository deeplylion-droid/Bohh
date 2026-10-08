-- Client di "The Rake": controlli, stamina e fiatone, Paura e allucinazioni, visore notturno,
-- fucile a dardi, tablet delle telecamere, atmosfera, animazione della creatura e HUD.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Lighting = game:GetService("Lighting")
local ContextActionService = game:GetService("ContextActionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Debris = game:GetService("Debris")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local Models = require(Shared:WaitForChild("Models"))
local RakeRig = require(Shared:WaitForChild("RakeRig"))
local Hud = require(script:WaitForChild("Hud"))
local Tablet = require(script:WaitForChild("Tablet"))
local Ambience = require(script:WaitForChild("Ambience"))
local RakeAnimator = require(script:WaitForChild("RakeAnimator"))
local Scope = require(script:WaitForChild("Scope"))
local CamFeed = require(script:WaitForChild("CamFeed"))
local Compass = require(script:WaitForChild("Compass"))
local Gunfx = require(script:WaitForChild("Gunfx"))
local Scares = require(script:WaitForChild("Scares"))
local ArmPose = require(script:WaitForChild("ArmPose"))

local player = Players.LocalPlayer
local playerGui = player:WaitForChild("PlayerGui")
local mouse = player:GetMouse()
local state = ReplicatedStorage:WaitForChild("RakeState")
local remotes = ReplicatedStorage:WaitForChild("RakeRemotes")

local P = Config.PLAYER
local NV_MAX = Config.EQUIPMENT.NIGHT_VISION_BATTERY

Models.load()
local hud = Hud.new(player, state)
local tablet = Tablet.new(player, state, remotes)
local scope = Scope.new(player)
scope:bind()
RakeAnimator.start(state)
CamFeed.start(player)
Compass.new(player, state, hud.gui)
Gunfx.start(remotes)
local scaring = Scares.start(player, state, function()
	hud:pulse()
end)

-- Controllo della visuale: fuori da mirino, tablet e jumpscare il campo visivo torna sempre a 70
-- (così nessun effetto può lasciare la visuale zoomata) e la telecamera torna a seguirti.
RunService.RenderStepped:Connect(function(dt)
	if tablet.isOpen or scope.active or scaring() then
		return
	end
	local camera = workspace.CurrentCamera
	if math.abs(camera.FieldOfView - 70) > 0.05 then
		camera.FieldOfView += (70 - camera.FieldOfView) * math.min(1, dt * 10)
	end
	if camera.CameraType == Enum.CameraType.Scriptable then
		camera.CameraType = Enum.CameraType.Custom
		local hum = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
		if hum then
			camera.CameraSubject = hum
		end
	end
end)
ArmPose.start(player, function()
	return hud.watchShown
end, remotes, function()
	return tablet.isOpen or scope.active
end, function()
	hud:setWatchVisible(false)
end, function(screen)
	-- Mentre guardi il polso lo schermo dell'orologio sta DENTRO la parte del quadrante della copia
	-- del braccio: una SurfaceGui agganciata da fuori (Adornee dal PlayerGui) viene ridisegnata con un
	-- fotogramma di ritardo quando la parte si muove ogni fotogramma, e sembrava vibrare.
	hud.viewScreen = screen
	local gui = hud.watchGui
	if screen then
		if gui.Parent ~= screen then
			gui.Adornee = nil
			gui.Parent = screen
		end
	elseif gui.Parent ~= playerGui then
		gui.Parent = playerGui
	end
end)

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

-- G: alzi il polso e guardi lo smartwatch (di nuovo G per abbassarlo)
ContextActionService:BindAction("Orologio", function(_, inputState)
	if inputState == Enum.UserInputState.Begin then
		hud:setWatchVisible(not hud.watchShown)
	end
	return Enum.ContextActionResult.Sink
end, true, Enum.KeyCode.G, Enum.KeyCode.DPadUp)
ContextActionService:SetTitle("Orologio", "Orologio")

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

-- Fucile a dardi (mira dove punta il mouse o il tocco) e tablet impugnato
local hooked = setmetatable({}, { __mode = "k" })
local function hookTool(tool: Instance)
	if not tool:IsA("Tool") or hooked[tool] then
		return
	end
	hooked[tool] = true
	if tool.Name == "Fucile a dardi" then
		tool.Activated:Connect(function()
			if not tablet.isOpen and Gunfx.fireLocal(tool, scope.active) then
				remotes.FireDart:FireServer(mouse.Hit.Position)
			end
		end)
	elseif tool.Name == "Tablet" then
		tool.Activated:Connect(function()
			scope:exit()
			tablet:open()
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

local fearBlur = Instance.new("BlurEffect")
fearBlur.Name = "PauraSfocatura"
fearBlur.Size = 0
fearBlur.Parent = Lighting

local function groundY(pos: Vector3): number
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { workspace.Terrain }
	local hit = workspace:Raycast(pos + Vector3.new(0, 30, 0), Vector3.new(0, -200, 0), params)
	return hit and hit.Position.Y or pos.Y - 4
end

local updateAmbience, whisperAt = Ambience.start(player, state, function()
	hud:pulse()
end)

-- Allucinazione: la sagoma della creatura appare un istante tra gli alberi (solo per te)
local function hallucinate()
	local camera = workspace.CurrentCamera
	local look = camera.CFrame.LookVector * Vector3.new(1, 0, 1)
	if look.Magnitude < 0.1 then
		return
	end
	local dir = CFrame.Angles(0, math.rad(math.random(-35, 35)), 0) * look.Unit
	local pos = camera.CFrame.Position + dir * math.random(22, 38)
	local ground = Vector3.new(pos.X, groundY(pos), pos.Z)
	local facing = Vector3.new(camera.CFrame.Position.X, ground.Y, camera.CFrame.Position.Z)
	local ghost = Instance.new("Model")
	ghost.Name = "Allucinazione"
	local rig = RakeRig.build(ghost, CFrame.lookAt(ground, facing) * CFrame.new(0, RakeRig.ROOT_HEIGHT, 0), { ghost = true })
	-- posa storta: testa piegata, braccia aperte, mascella spalancata (ossa ruotate di 180 gradi)
	for name, cf in {
		Head = CFrame.Angles(-0.2, 0.3, -1.1),
		Jaw = CFrame.Angles(0.7, 0, 0),
		ShoulderL = CFrame.Angles(-1.2, 0, 0.5),
		ShoulderR = CFrame.Angles(-0.4, 0, -0.9),
	} do
		local bone = rig.body:FindFirstChild(name, true)
		if bone and bone:IsA("Bone") then
			bone.Transform = cf
		end
	end
	ghost.Parent = workspace
	local headBone = rig.body:FindFirstChild("Head", true)
	if headBone and headBone:IsA("Bone") then
		for _, side in { -1, 1 } do
			local eye = Instance.new("Part")
			eye.Shape = Enum.PartType.Ball
			eye.Size = Vector3.new(0.12, 0.12, 0.12)
			eye.Material = Enum.Material.Neon
			eye.Color = Color3.fromRGB(255, 245, 230)
			eye.Anchored = true
			eye.CanCollide = false
			eye.CanQuery = false
			eye.CFrame = headBone.TransformedWorldCFrame * CFrame.new(-side * 0.15, 0.34, 0.66)
			eye.Parent = ghost
		end
	end
	Debris:AddItem(ghost, 0.8)
	whisperAt(ground + Vector3.new(0, 5, 0))
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
-- Ciclo per frame: stamina, paura, velocità, visore, atmosfera

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
	local root = Ambience.rakeRoot()
	if phase == "Notte" and status == "OK" and hrp then
		local pos = hrp.Position
		local dark = Lighting.ClockTime >= 19.5 or Lighting.ClockTime < 6
		local atStation = (Vector3.new(pos.X, 0, pos.Z) - Vector3.new(Config.MAP.POIS[1].pos.X, 0, Config.MAP.POIS[1].pos.Z)).Magnitude < Config.MAP.STATION_RADIUS
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
		local ok, err = pcall(hallucinate)
		if not ok then
			warn("[Allucinazione] " .. tostring(err))
		end
	end
	local fearAmount = math.clamp((fear - 40) / 60, 0, 1)
	fearEffect.Saturation = -0.6 * fearAmount
	fearEffect.Contrast = 0.25 * fearAmount
	fearBlur.Size = panic and 3 + math.sin(os.clock() * 6) * 2 or 0

	-- Tremolio della visuale quando la creatura è vicina
	-- (CameraOffset non si accumula: modificare la CFrame della visuale la farebbe derivare)
	if hum then
		local shake = 0
		if root and hrp and not tablet.isOpen and not scope.active then
			shake = math.clamp(1 - (root.Position - hrp.Position).Magnitude / 30, 0, 1) * 0.25
		end
		hum.CameraOffset = Vector3.new((math.random() - 0.5) * shake, (math.random() - 0.5) * shake, 0)
	end

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

	scope.sway = math.clamp(fear / 100 + (exhausted and 0.6 or 0) + (sprinting and 0.4 or 0), 0, 1.5)
	updateAmbience(dt, { exhausted = exhausted, panic = panic })
	local closeness = 0
	if root and hrp then
		closeness = math.clamp(1 - (root.Position - hrp.Position).Magnitude / 60, 0, 1)
	end
	hud:update({
		config = Config,
		stamina = stamina,
		fear = fear,
		nv = nvBattery / NV_MAX,
		nvOn = nvOn,
		exhausted = exhausted,
		panic = panic,
		closeness = closeness,
		sprinting = sprinting,
		dt = dt,
	})
end)
