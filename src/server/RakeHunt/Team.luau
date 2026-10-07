-- La squadra: spawn, attrezzatura (torcia, telecamere, fucile a dardi), stato "Braccato" e rianimazione.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local Models = require(Shared:WaitForChild("Models"))
local Sfx = require(Shared:WaitForChild("Sfx"))
local Forest = require(script.Parent.Forest)

local EQ = Config.EQUIPMENT
local P = Config.PLAYER
local make = Forest.make

local Team = {}

local ctx
local downedToken: { [Player]: any } = {}
local lastDart: { [Player]: number } = {}

-- Stati del giocatore (attributo "Status"): Lobby, OK, Braccato, Fuori

function Team.isStanding(player: Player): boolean
	return player:GetAttribute("Status") == "OK"
end

function Team.isDowned(player: Player): boolean
	return player:GetAttribute("Status") == "Braccato"
end

-- Giocatori in piedi durante la notte, con le parti del personaggio già risolte
function Team.standing()
	local list = {}
	for _, player in Players:GetPlayers() do
		if Team.isStanding(player) then
			local char = player.Character
			local hrp = char and char:FindFirstChild("HumanoidRootPart")
			local hum = char and char:FindFirstChildOfClass("Humanoid")
			if hrp and hum and hum.Health > 0 then
				table.insert(list, { player = player, char = char, root = hrp, head = char:FindFirstChild("Head") })
			end
		end
	end
	return list
end

function Team.anyStanding(): boolean
	return #Team.standing() > 0
end

local function torchLight(player: Player): SpotLight?
	local char = player.Character
	local tool = char and char:FindFirstChild("Torcia")
	local lens = tool and tool:FindFirstChild("Lente")
	return lens and lens:FindFirstChild("TorchLight") :: SpotLight?
end

function Team.setTorch(player: Player, on: boolean)
	if on and (player:GetAttribute("TorchBattery") or 0) <= 0 then
		ctx.notify("🔦 Torcia scarica: ricaricala al Rifornimento della Ranger Station.", player)
		on = false
	end
	if on and not Team.isStanding(player) then
		on = false
	end
	if player:GetAttribute("TorchOn") ~= on then
		local char = player.Character
		local head = char and char:FindFirstChild("Head")
		if head then
			Sfx.at("TorchClick", head.Position, { Volume = 0.6, RollOffMaxDistance = 30 })
		end
	end
	player:SetAttribute("TorchOn", on)
	local light = torchLight(player)
	if light then
		light.Enabled = on
		local lens = light.Parent :: BasePart
		lens.Material = on and Enum.Material.Neon or Enum.Material.Glass
		local glow = lens:FindFirstChild("Alone") :: PointLight?
		if glow then
			glow.Enabled = on
		end
	end
end

-- Attrezzo con impugnatura invisibile e modello 3D saldato (il fronte del modello punta in avanti)
local function newTool(name: string, tip: string, mesh: string, scale: number, offset: CFrame?): (Tool, BasePart)
	local tool = Instance.new("Tool")
	tool.Name = name
	tool.ToolTip = tip
	tool.CanBeDropped = false
	tool.RequiresHandle = true
	local handle = Instance.new("Part")
	handle.Name = "Handle"
	handle.Size = Vector3.new(0.3, 0.3, 0.3)
	handle.Transparency = 1
	handle.CanCollide = false
	handle.Massless = true
	handle.CFrame = CFrame.new()
	handle.Parent = tool
	local visual = Models.mesh(mesh, (offset or CFrame.new()), scale, {
		Name = "Modello",
		Anchored = false,
		CanCollide = false,
		CanQuery = false,
		CanTouch = false,
		Massless = true,
	}, tool)
	local weld = Instance.new("WeldConstraint")
	weld.Part0 = handle
	weld.Part1 = visual
	weld.Parent = handle
	return tool, handle
end

local function attachPart(tool: Tool, handle: BasePart, props: { [string]: any }): BasePart
	local part = make("Part", nil, props)
	part.Anchored = false
	part.CanCollide = false
	part.CanQuery = false
	part.CanTouch = false
	part.Massless = true
	part.Parent = tool
	local weld = Instance.new("WeldConstraint")
	weld.Part0 = handle
	weld.Part1 = part
	weld.Parent = part
	return part
end

function Team.equip(player: Player)
	local char = player.Character
	local backpack = player:FindFirstChildOfClass("Backpack")
	if not char or not backpack then
		return
	end
	for _, container in { backpack, char } do
		for _, item in container:GetChildren() do
			if item:IsA("Tool") then
				item:Destroy()
			end
		end
	end

	player:SetAttribute("Darts", EQ.DARTS)
	player:SetAttribute("TorchBattery", EQ.TORCH_BATTERY)
	player:SetAttribute("TorchOn", false)
	player:SetAttribute("Samples", 0)
	player:SetAttribute("SamplePoints", 0)
	player:SetAttribute("CarryingTape", false)
	player:SetAttribute("CamType", "Fissa")
	for camType, count in EQ.CAMERA_KITS do
		player:SetAttribute("Kits_" .. camType, count)
	end
	player:SetAttribute("SupplyTick", os.clock())
	player:SetAttribute("Health", P.HEALTH)
	player:SetAttribute("LastHit", 0)
	Team.buildTools(player, backpack)
	Team.attachWatch(char)
end

-- Smartwatch 3D al polso sinistro (lo vedono tutti; il client lo mostra alzando il braccio)
function Team.attachWatch(char: Model)
	local arm = char:FindFirstChild("LeftLowerArm") or char:FindFirstChild("Left Arm")
	if not arm or not arm:IsA("BasePart") or arm:FindFirstChild("Orologio") then
		return
	end
	local r15 = arm.Name == "LeftLowerArm"
	local wristCF = arm.CFrame * CFrame.new(0, r15 and -arm.Size.Y * 0.32 or -arm.Size.Y * 0.38, 0)
	local strap = make("Part", nil, {
		Name = "Cinturino",
		Size = Vector3.new(arm.Size.X + 0.08, 0.22, arm.Size.Z + 0.08),
		CFrame = wristCF,
		Color = Color3.fromRGB(26, 27, 29),
		Material = Enum.Material.Rubber,
	})
	local case = make("Part", nil, {
		Name = "Orologio",
		Size = Vector3.new(0.42, 0.32, 0.12),
		CFrame = wristCF * CFrame.new(-arm.Size.X / 2 - 0.06, 0, 0) * CFrame.Angles(0, math.pi / 2, 0),
		Color = Color3.fromRGB(70, 74, 78),
		Material = Enum.Material.Metal,
	})
	local screen = make("Part", nil, {
		Name = "Schermo",
		Size = Vector3.new(0.34, 0.24, 0.02),
		CFrame = case.CFrame * CFrame.new(0, 0, 0.065),
		Color = Color3.fromRGB(40, 140, 110),
		Material = Enum.Material.Neon,
	})
	for _, p in { strap, case, screen } do
		p.Anchored = false
		p.CanCollide = false
		p.CanQuery = false
		p.CanTouch = false
		p.Massless = true
		p.Parent = arm
		local weld = Instance.new("WeldConstraint")
		weld.Part0 = arm
		weld.Part1 = p
		weld.Parent = p
	end
end

-- Crea gli attrezzi nello zaino (separato da equip per poterlo provare senza un giocatore vero)
function Team.buildTools(player: Player, backpack: Instance)
	-- Torcia: la luce esce dalla lente e segue il braccio
	local torch, torchHandle = newTool("Torcia", "Clic: accendi/spegni la torcia", "Tool_Torch", 0.95)
	local lens = attachPart(torch, torchHandle, {
		Name = "Lente",
		Shape = Enum.PartType.Cylinder,
		Size = Vector3.new(0.05, 0.5, 0.5),
		CFrame = CFrame.new(0, 0, -0.83) * CFrame.Angles(0, math.pi / 2, 0),
		Color = Color3.fromRGB(255, 244, 220),
		Material = Enum.Material.Glass,
	})
	local beam = make("SpotLight", lens, {
		Name = "TorchLight",
		Face = Enum.NormalId.Right,
		Angle = 50,
		Range = 60,
		Brightness = 7,
		Shadows = true,
		Color = Color3.fromRGB(255, 238, 205),
		Enabled = false,
	})
	Forest.flicker(beam)
	make("PointLight", lens, { Name = "Alone", Range = 5, Brightness = 0.6, Color = Color3.fromRGB(255, 230, 200), Enabled = false })
	torch.Activated:Connect(function()
		Team.setTorch(player, not player:GetAttribute("TorchOn"))
	end)
	torch.Unequipped:Connect(function()
		Team.setTorch(player, false)
	end)
	torch.Parent = backpack

	local camera, cameraHandle = newTool("Telecamera", "Clic: piazza una telecamera · R: cambia tipo", "Cam_Body", 0.55, CFrame.new(0, 0.1, -0.2))
	attachPart(camera, cameraHandle, {
		Name = "Led",
		Shape = Enum.PartType.Ball,
		Size = Vector3.new(0.06, 0.06, 0.06),
		CFrame = CFrame.new(0.2, 0.27, -0.6),
		Color = Color3.fromRGB(255, 40, 40),
		Material = Enum.Material.Neon,
	})
	camera.Activated:Connect(function()
		ctx.cameras.place(player)
	end)
	camera.Parent = backpack

	local gun, gunHandle = newTool("Fucile a dardi", "Clic: spara un dardo tranquillante", "Tool_Rifle", 0.8)
	attachPart(gun, gunHandle, {
		Name = "Volata",
		Size = Vector3.new(0.1, 0.1, 0.1),
		CFrame = CFrame.new(0, 0.12, -2.15),
		Transparency = 1,
	})
	gun.Parent = backpack

	local tablet, tabletHandle = newTool("Tablet", "Clic (o T): guarda le telecamere", "Tool_Tablet", 1, CFrame.new(0, 0.3, -0.6) * CFrame.Angles(math.rad(-65), 0, 0))
	local screen = attachPart(tablet, tabletHandle, {
		Name = "Schermo",
		Size = Vector3.new(1.35, 0.85, 0.02),
		CFrame = CFrame.new(0, 0.3, -0.6) * CFrame.Angles(math.rad(-65), 0, 0) * CFrame.new(0, 0, -0.07),
		Color = Color3.fromRGB(30, 80, 60),
		Material = Enum.Material.Neon,
	})
	make("PointLight", screen, { Range = 5, Brightness = 0.5, Color = Color3.fromRGB(90, 220, 160) })
	tablet.Parent = backpack
end

function Team.spawn(player: Player, equip: boolean)
	if not player.Parent then
		return
	end
	downedToken[player] = nil
	player:SetAttribute("Status", equip and "OK" or "Lobby")
	player:SetAttribute("TorchOn", false)
	player:SetAttribute("CarryingTape", false)
	player:LoadCharacter()
	if equip then
		Team.equip(player)
	end
end

function Team.cycleCamType(player: Player)
	local types = Config.CAMERAS.TYPES
	local current = table.find(types, player:GetAttribute("CamType")) or 1
	for i = 1, #types do
		local candidate = types[(current + i - 1) % #types + 1]
		if (player:GetAttribute("Kits_" .. candidate) or 0) > 0 then
			player:SetAttribute("CamType", candidate)
			return
		end
	end
end

function Team.supply(player: Player)
	if not ctx.round.active or not Team.isStanding(player) then
		ctx.notify("Il rifornimento è disponibile durante la notte.", player)
		return
	end
	player:SetAttribute("Darts", EQ.DARTS)
	player:SetAttribute("TorchBattery", EQ.TORCH_BATTERY)
	player:SetAttribute("SupplyTick", os.clock())
	player:SetAttribute("Health", P.HEALTH)
	ctx.notify("🎒 Rifornimento completato: dardi, torcia, visore e kit medico.", player)
end

function Team.fireDart(player: Player, targetPos: any)
	if typeof(targetPos) ~= "Vector3" or not ctx.round.active or not Team.isStanding(player) then
		return
	end
	local char = player.Character
	local gun = char and char:FindFirstChild("Fucile a dardi")
	local head = char and char:FindFirstChild("Head") :: BasePart?
	if not gun or not head then
		return
	end
	local now = os.clock()
	if now - (lastDart[player] or 0) < EQ.DART_COOLDOWN then
		return
	end
	local ammo = player:GetAttribute("Darts") or 0
	if ammo <= 0 then
		ctx.notify("Dardi finiti: torna al Rifornimento.", player)
		return
	end
	lastDart[player] = now
	player:SetAttribute("Darts", ammo - 1)

	local dir = targetPos - head.Position
	if dir.Magnitude < 0.1 then
		return
	end
	dir = dir.Unit * EQ.DART_RANGE
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = { char, ctx.cameras.folder() }
	local result = workspace:Raycast(head.Position, dir, params)
	local hitPos = result and result.Position or head.Position + dir
	local muzzle = gun:FindFirstChild("Volata") :: BasePart?
	local from = muzzle and muzzle.Position or head.Position

	local rake = ctx.rake.model
	local hitRake = result ~= nil and rake ~= nil and result.Instance:IsDescendantOf(rake)
	local kind = "none"
	if hitRake then
		kind = "rake"
	elseif result then
		kind = result.Instance == workspace.Terrain and "terrain" or "wood"
	end
	-- effetti (fiammata, dardo in volo, impatto, rinculo) disegnati dai client
	ctx.remotes.DartFx:FireAllClients(player, from, hitPos, kind, result and result.Normal or Vector3.yAxis, result and result.Instance or nil)
	ctx.rake.hearNoise(from, 1)
	if hitRake then
		local travel = (hitPos - from).Magnitude / EQ.DART_SPEED
		task.delay(travel, function()
			Sfx.at("HitFlesh", hitPos, { Volume = 2, RollOffMaxDistance = 160 })
			ctx.rake.hitByDart(player)
		end)
	end
end

local function clearRevivePrompt(player: Player)
	local hrp = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
	local prompt = hrp and hrp:FindFirstChild("RevivePrompt")
	if prompt then
		prompt:Destroy()
	end
end

function Team.eliminate(player: Player)
	downedToken[player] = nil
	player:SetAttribute("Status", "Fuori")
	clearRevivePrompt(player)
	ctx.objectives.onDowned(player)
	local hum = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
	if hum and hum.Health > 0 then
		hum.Health = 0
	end
	ctx.notifyAll(("💀 %s non ce l'ha fatta."):format(player.DisplayName))
end

function Team.revive(player: Player, reviver: Player)
	if not Team.isDowned(player) then
		return
	end
	downedToken[player] = nil
	clearRevivePrompt(player)
	player:SetAttribute("Status", "OK")
	player:SetAttribute("Health", P.REVIVE_HEALTH)
	local hum = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
	if hum then
		hum.PlatformStand = false
		hum.WalkSpeed = P.WALK_SPEED
		hum.JumpPower = 50
		hum.JumpHeight = 7.2
		hum:ChangeState(Enum.HumanoidStateType.GettingUp)
	end
	ctx.credit(reviver.UserId, "revives")
	ctx.notifyAll(("❤ %s ha rianimato %s!"):format(reviver.DisplayName, player.DisplayName))
end

-- Ferita: toglie salute; a zero il giocatore è a terra (Braccato)
function Team.hurt(player: Player, amount: number, from: Vector3?)
	if not Team.isStanding(player) then
		return
	end
	local health = math.max(0, (player:GetAttribute("Health") or P.HEALTH) - amount)
	player:SetAttribute("Health", health)
	player:SetAttribute("LastHit", os.clock())
	if health <= 0 then
		Team.down(player)
	else
		ctx.notify(("🩸 Sei stato ferito! Salute %d%%"):format(math.floor(health)), player)
	end
end

function Team.down(player: Player)
	if not Team.isStanding(player) then
		return
	end
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	local hrp = char and char:FindFirstChild("HumanoidRootPart")
	if not hum or not hrp then
		return
	end
	player:SetAttribute("Status", "Braccato")
	Team.setTorch(player, false)
	hum:UnequipTools()
	hum.WalkSpeed = 0
	hum.JumpPower = 0
	hum.JumpHeight = 0
	hum.PlatformStand = true
	ctx.objectives.onDowned(player)

	local token = {}
	downedToken[player] = token
	player:SetAttribute("DownedUntil", workspace:GetServerTimeNow() + P.DOWNED_TIME)
	local prompt = make("ProximityPrompt", hrp, {
		Name = "RevivePrompt",
		ActionText = "Rianima",
		ObjectText = player.DisplayName,
		HoldDuration = P.REVIVE_TIME,
		MaxActivationDistance = 9,
		RequiresLineOfSight = false,
	})
	prompt.Triggered:Connect(function(reviver)
		if reviver ~= player and Team.isStanding(reviver) then
			Team.revive(player, reviver)
		end
	end)
	ctx.notifyAll(("⚠ %s è stato colpito! Rianimalo entro %d secondi."):format(player.DisplayName, P.DOWNED_TIME))

	task.delay(P.DOWNED_TIME, function()
		if downedToken[player] == token and Team.isDowned(player) then
			Team.eliminate(player)
		end
	end)
end

function Team.tick(dt: number)
	local now = os.clock()
	for _, player in Players:GetPlayers() do
		local health = player:GetAttribute("Health")
		if Team.isStanding(player) and health and health < P.HEALTH and now - (player:GetAttribute("LastHit") or 0) > P.REGEN_DELAY then
			player:SetAttribute("Health", math.min(P.HEALTH, health + P.HEALTH_REGEN * dt))
		end
		if player:GetAttribute("TorchOn") then
			local battery = math.max(0, (player:GetAttribute("TorchBattery") or 0) - dt)
			player:SetAttribute("TorchBattery", battery)
			if battery <= 0 then
				Team.setTorch(player, false)
				ctx.notify("🔦 La torcia si è scaricata.", player)
			end
		end
	end
end

function Team.init(c)
	ctx = c
	Players.PlayerRemoving:Connect(function(player)
		downedToken[player] = nil
		lastDart[player] = nil
	end)
end

-- Collega gli eventi del personaggio (morte durante la notte = fuori dalla partita)
function Team.watchCharacter(player: Player, char: Model)
	local hum = char:WaitForChild("Humanoid", 10) :: Humanoid?
	if not hum then
		return
	end
	hum.Died:Connect(function()
		local status = player:GetAttribute("Status")
		if ctx.round.active and (status == "OK" or status == "Braccato") then
			downedToken[player] = nil
			player:SetAttribute("Status", "Fuori")
			player:SetAttribute("TorchOn", false)
			ctx.objectives.onDowned(player)
		elseif not ctx.round.active then
			task.delay(3, function()
				if player.Parent and player.Character == char and not ctx.round.active then
					Team.spawn(player, ctx.state:GetAttribute("Phase") == "Briefing")
				end
			end)
		end
	end)
end

return Team
