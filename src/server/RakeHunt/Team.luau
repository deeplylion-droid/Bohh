-- La squadra: spawn, attrezzatura (torcia, telecamere, fucile a dardi), stato "Braccato" e rianimazione.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Debris = game:GetService("Debris")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
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
	local head = player.Character and player.Character:FindFirstChild("Head")
	return head and head:FindFirstChild("TorchLight") :: SpotLight?
end

function Team.setTorch(player: Player, on: boolean)
	if on and (player:GetAttribute("TorchBattery") or 0) <= 0 then
		ctx.notify("🔦 Torcia scarica: ricaricala al Rifornimento della Ranger Station.", player)
		on = false
	end
	if on and not Team.isStanding(player) then
		on = false
	end
	player:SetAttribute("TorchOn", on)
	local light = torchLight(player)
	if light then
		light.Enabled = on
	end
end

local function newTool(name: string, tip: string, size: Vector3, color: Color3): (Tool, BasePart)
	local tool = Instance.new("Tool")
	tool.Name = name
	tool.ToolTip = tip
	tool.CanBeDropped = false
	tool.RequiresHandle = true
	local handle = Instance.new("Part")
	handle.Name = "Handle"
	handle.Size = size
	handle.Color = color
	handle.Material = Enum.Material.Metal
	handle.CanCollide = false
	handle.Massless = true
	handle.Parent = tool
	return tool, handle
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

	local head = char:FindFirstChild("Head")
	if head and not head:FindFirstChild("TorchLight") then
		make("SpotLight", head, {
			Name = "TorchLight",
			Face = Enum.NormalId.Front,
			Angle = 55,
			Range = 45,
			Brightness = 5,
			Shadows = true,
			Color = Color3.fromRGB(255, 240, 210),
			Enabled = false,
		})
	end

	local torch = newTool("Torcia", "Clic: accendi/spegni la torcia", Vector3.new(0.35, 0.35, 1.4), Color3.fromRGB(30, 30, 30))
	torch.Activated:Connect(function()
		Team.setTorch(player, not player:GetAttribute("TorchOn"))
	end)
	torch.Unequipped:Connect(function()
		Team.setTorch(player, false)
	end)
	torch.Parent = backpack

	local camera = newTool("Telecamera", "Clic: piazza una telecamera · R: cambia tipo", Vector3.new(1, 0.8, 1.2), Color3.fromRGB(70, 70, 75))
	camera.Activated:Connect(function()
		ctx.cameras.place(player)
	end)
	camera.Parent = backpack

	local gun = newTool("Fucile a dardi", "Clic: spara un dardo tranquillante", Vector3.new(0.4, 0.6, 2.4), Color3.fromRGB(45, 60, 40))
	gun.Parent = backpack
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
	ctx.notify("🎒 Rifornimento completato: dardi, torcia e visore notturno carichi.", player)
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

	local handle = gun:FindFirstChild("Handle") :: BasePart?
	local from = handle and handle.Position or head.Position
	local length = (hitPos - from).Magnitude
	local tracer = make("Part", workspace, {
		Size = Vector3.new(0.08, 0.08, length),
		CFrame = CFrame.lookAt(from, hitPos) * CFrame.new(0, 0, -length / 2),
		Material = Enum.Material.Neon,
		Color = Color3.fromRGB(180, 255, 120),
		CanCollide = false,
		CanQuery = false,
		CastShadow = false,
	})
	Debris:AddItem(tracer, 0.12)

	local rake = ctx.rake.model
	if result and rake and result.Instance:IsDescendantOf(rake) then
		ctx.rake.hitByDart(player)
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
	for _, player in Players:GetPlayers() do
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
