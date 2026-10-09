-- Gli 8 lotti in vetta: costruzione, assegnazione ai giocatori, zone, sblocchi e insegne.

local CollectionService = game:GetService("CollectionService")
local PhysicsService = game:GetService("PhysicsService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Signal = require(ReplicatedStorage.Shared.Util.Signal)
local Upgrades = require(ReplicatedStorage.Shared.Config.Upgrades)
local Build = require(script.Parent.Parent.World.Build)

local PlotService = {}

PlotService.Assigned = Signal.new() -- (player, plot)
PlotService.Released = Signal.new() -- (player, plot)
PlotService.Entered = Signal.new() -- (player, plot) un giocatore entra in un lotto
PlotService.Plots = {}

local S
local L = MapLayout.Plot
local THEMES = {
	{ wall = Color3.fromRGB(255, 104, 104), trim = Color3.fromRGB(196, 52, 62) },
	{ wall = Color3.fromRGB(255, 166, 74), trim = Color3.fromRGB(214, 106, 26) },
	{ wall = Color3.fromRGB(255, 220, 86), trim = Color3.fromRGB(214, 160, 20) },
	{ wall = Color3.fromRGB(122, 222, 102), trim = Color3.fromRGB(56, 160, 64) },
	{ wall = Color3.fromRGB(86, 214, 230), trim = Color3.fromRGB(28, 150, 180) },
	{ wall = Color3.fromRGB(106, 150, 255), trim = Color3.fromRGB(52, 90, 214) },
	{ wall = Color3.fromRGB(184, 128, 255), trim = Color3.fromRGB(122, 70, 214) },
	{ wall = Color3.fromRGB(255, 134, 214), trim = Color3.fromRGB(214, 70, 160) },
}

local WOOD = Color3.fromRGB(214, 170, 120)
local STONE = Color3.fromRGB(226, 220, 210)

export type Plot = {
	index: number,
	cframe: CFrame,
	model: Model,
	owner: Player?,
	theme: { wall: Color3, trim: Color3 },
	incubators: { { base: BasePart, ring: BasePart, slot: string, prompt: ProximityPrompt, stealPrompt: ProximityPrompt } },
	pedestals: { { base: BasePart, pad: BasePart, slot: number, prompt: ProximityPrompt, stealPrompt: ProximityPrompt } },
	gateBarrier: BasePart,
	console: BasePart,
	consolePrompt: ProximityPrompt,
	traps: { BasePart },
	sign: BasePart,
	occupants: { [Player]: boolean },
}

local function prompt(parent: Instance, name: string, action: string, hold: number, forWhom: "Owner" | "Others"): ProximityPrompt
	local p = Instance.new("ProximityPrompt")
	p.Name = name
	p.ActionText = action
	p.HoldDuration = hold
	p.MaxActivationDistance = 9
	p.RequiresLineOfSight = false
	p.Style = Enum.ProximityPromptStyle.Custom
	p.Enabled = false
	p:SetAttribute("For", forWhom)
	p.Parent = parent
	return p
end

local function buildPlot(index: number, parent: Instance): Plot
	local base = MapLayout.PlotFrame(index) * CFrame.new(0, L.FloorHeight, 0)
	local theme = THEMES[index]
	local model = Build.Model(`Plot{index}`, parent)
	model:SetAttribute("PlotIndex", index)
	local function at(v: Vector3): CFrame
		return base * CFrame.new(v)
	end
	local W, D, H = MapLayout.PlotSize.X, MapLayout.PlotSize.Z, L.WallHeight
	-- pavimento in legno con tappeto del colore del lotto e bordo
	Build.Part({ name = "Floor", size = Vector3.new(W, L.FloorHeight + 2, D), cframe = at(Vector3.new(0, -(L.FloorHeight + 2) / 2, 0)), color = WOOD, material = Enum.Material.WoodPlanks, parent = model })
	Build.Part({ name = "FloorInset", size = Vector3.new(W - 9, 0.2, D - 9), cframe = at(Vector3.new(0, 0.06, 0)), color = theme.wall:Lerp(Color3.new(1, 1, 1), 0.78), material = Enum.Material.SmoothPlastic, collide = false, parent = model })
	for _, edge in { { W - 7, 1, 0, -(D - 8) / 2 }, { W - 7, 1, 0, (D - 8) / 2 }, { 1, D - 7, -(W - 8) / 2, 0 }, { 1, D - 7, (W - 8) / 2, 0 } } do
		Build.Part({ name = "FloorBorder", size = Vector3.new(edge[1], 0.3, edge[2]), cframe = at(Vector3.new(edge[3], 0.1, edge[4])), color = theme.trim, collide = false, parent = model })
	end
	-- mura a vetrina: zoccolo pieno, vetri colorati, corrimano e pilastri (i pet si vedono da fuori)
	local walls = Build.Model("Walls", model)
	local BASE_H, GLASS_H = 3.5, 7
	local glassColor = theme.wall:Lerp(Color3.new(1, 1, 1), 0.55)
	local function wallRun(name: string, center: Vector3, length: number, alongX: boolean, skipEnds: boolean?)
		local size = function(thick: number, h: number): Vector3
			return if alongX then Vector3.new(length, h, thick) else Vector3.new(thick, h, length)
		end
		Build.Part({ name = name .. "Base", size = size(2, BASE_H), cframe = at(center + Vector3.new(0, BASE_H / 2, 0)), color = theme.wall, parent = walls })
		local glass = Build.Part({ name = name .. "Glass", size = size(0.6, GLASS_H), cframe = at(center + Vector3.new(0, BASE_H + GLASS_H / 2, 0)), color = glassColor, material = Enum.Material.Glass, transparency = 0.55, castShadow = false, parent = walls })
		glass.Reflectance = 0.08
		Build.Part({ name = name .. "Rail", size = size(2.4, 1.2), cframe = at(center + Vector3.new(0, BASE_H + GLASS_H + 0.6, 0)), color = theme.trim, parent = walls })
		-- pilastri ogni ~10 stud lungo il tratto
		local count = math.max(1, math.floor(length / 10))
		for k = if skipEnds then 1 else 0, if skipEnds then count - 1 else count do
			local t = -length / 2 + length * k / count
			local offset = if alongX then Vector3.new(t, 0, 0) else Vector3.new(0, 0, t)
			Build.Part({ name = "Post", size = Vector3.new(1.8, H, 1.8), cframe = at(center + offset + Vector3.new(0, H / 2, 0)), color = theme.trim, parent = walls })
			Build.Part({ name = "PostCap", size = Vector3.new(2.4, 0.8, 2.4), cframe = at(center + offset + Vector3.new(0, H + 0.4, 0)), color = Color3.fromRGB(255, 255, 255), parent = walls })
		end
	end
	wallRun("Back", Vector3.new(0, 0, D / 2 - 1), W - 2, true)
	for _, sx in { -1, 1 } do
		-- i pilastri d'angolo li mettono il retro e il fronte (niente doppioni sovrapposti)
		wallRun("Side", Vector3.new(sx * (W / 2 - 1), 0, 0), D - 2, false, true)
		local inner = L.GateWidth / 2 + 4
		local seg = (W / 2 - 1) - inner
		wallRun("Front", Vector3.new(sx * (inner + seg / 2), 0, -D / 2 + 1), seg, true)
		-- torri ai lati del cancello con bandierine
		Build.Part({ name = "GatePost", size = Vector3.new(4, H + 4, 4), cframe = at(Vector3.new(sx * (L.GateWidth / 2 + 2), (H + 4) / 2, -D / 2 + 1)), color = theme.trim, parent = walls })
		Build.Part({ name = "GateCap", size = Vector3.new(5, 1.6, 5), cframe = at(Vector3.new(sx * (L.GateWidth / 2 + 2), H + 4.8, -D / 2 + 1)), color = Color3.fromRGB(255, 255, 255), parent = walls })
		Build.Part({ name = "FlagPole", size = Vector3.new(6, 0.35, 0.35), cframe = at(Vector3.new(sx * (L.GateWidth / 2 + 2), H + 8.6, -D / 2 + 1)) * CFrame.Angles(0, 0, math.rad(90)), color = Color3.fromRGB(255, 255, 255), shape = Enum.PartType.Cylinder, parent = walls })
		Build.Part({ name = "Flag", size = Vector3.new(3.2, 2, 0.2), cframe = at(Vector3.new(sx * (L.GateWidth / 2 + 2) + sx * 1.6, H + 10.4, -D / 2 + 1)), color = theme.wall, collide = false, parent = walls })
	end
	-- trave sopra il cancello con insegna del proprietario
	Build.Part({ name = "GateBeam", size = Vector3.new(L.GateWidth + 8, 3, 3), cframe = at(Vector3.new(0, H + 2, -D / 2 + 1)), color = theme.trim, parent = walls })
	local sign = Build.Part({ name = "OwnerSign", size = Vector3.new(L.GateWidth + 4, 5, 0.6), cframe = at(Vector3.new(0, H + 6.3, -D / 2 + 0.6)), color = Color3.fromRGB(255, 255, 255), parent = walls })
	local gui = Instance.new("SurfaceGui")
	gui.Name = "SignGui"
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 36
	gui.LightInfluence = 0.15
	gui.Parent = sign
	local face = Instance.new("ImageLabel")
	face.Name = "Avatar"
	face.BackgroundTransparency = 1
	face.Size = UDim2.fromScale(0.24, 0.92)
	face.Position = UDim2.fromScale(0.02, 0.04)
	face.ScaleType = Enum.ScaleType.Fit
	face.Image = ""
	face.Parent = gui
	local label = Instance.new("TextLabel")
	label.Name = "Owner"
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(0.72, 0.9)
	label.Position = UDim2.fromScale(0.27, 0.05)
	label.Font = Enum.Font.LuckiestGuy
	label.TextScaled = true
	label.TextColor3 = theme.trim
	label.Text = "FREE"
	label.Parent = gui

	-- barriera laser nel cancello (attiva solo quando il proprietario blocca il lotto)
	local barrier = Build.Part({
		name = "Barrier",
		size = Vector3.new(L.GateWidth, H, 1),
		cframe = at(Vector3.new(0, H / 2, -D / 2 + 1)),
		color = Color3.fromRGB(255, 60, 90),
		material = Enum.Material.ForceField,
		transparency = 1,
		collide = false,
		castShadow = false,
		parent = model,
	})
	barrier.CollisionGroup = `Barrier{index}`

	-- incubatrici
	local incubators = {}
	for i, pos in L.Incubators do
		local cf = at(pos)
		local baseP = Build.Part({ name = `Incubator{i}`, size = Vector3.new(1.4, 5.2, 5.2), cframe = cf * CFrame.new(0, 0.7, 0) * CFrame.Angles(0, 0, math.rad(90)), color = STONE, shape = Enum.PartType.Cylinder, parent = model })
		local ring = Build.Part({ name = "Ring", size = Vector3.new(0.4, 5.6, 5.6), cframe = cf * CFrame.new(0, 1.25, 0) * CFrame.Angles(0, 0, math.rad(90)), color = Color3.fromRGB(255, 160, 60), material = Enum.Material.Neon, shape = Enum.PartType.Cylinder, collide = false, castShadow = false, parent = baseP })
		-- l'attachment va prima messo nella parte: WorldCFrame dipende dalla parte che lo contiene
		local att = Instance.new("Attachment")
		att.Name = "EggPoint"
		att.Parent = baseP
		att.WorldCFrame = cf * CFrame.new(0, 1.45, 0)
		local hatch = prompt(baseP, "HatchPrompt", "HATCH", 0.4, "Owner")
		local steal = prompt(baseP, "StealPrompt", "STEAL", 2, "Others")
		baseP:SetAttribute("Slot", tostring(i))
		CollectionService:AddTag(baseP, "Incubator")
		incubators[i] = { base = baseP, ring = ring, slot = tostring(i), prompt = hatch, stealPrompt = steal }
	end

	-- piedistalli con pedana di raccolta
	local pedestals = {}
	for i, pos in L.Pedestals do
		local cf = at(pos)
		local baseP = Build.Part({ name = `Pedestal{i}`, size = Vector3.new(2, 6.4, 6.4), cframe = cf * CFrame.new(0, 1, 0) * CFrame.Angles(0, 0, math.rad(90)), color = STONE, shape = Enum.PartType.Cylinder, parent = model })
		Build.Part({ name = "Top", size = Vector3.new(0.3, 6.8, 6.8), cframe = cf * CFrame.new(0, 2.05, 0) * CFrame.Angles(0, 0, math.rad(90)), color = theme.wall, shape = Enum.PartType.Cylinder, collide = false, parent = baseP })
		local stand = Instance.new("Attachment")
		stand.Name = "PetPoint"
		stand.Parent = baseP
		stand.WorldCFrame = cf * CFrame.new(0, 2.2, 0) -- i pet guardano il cancello
		local pad = Build.Part({ name = "CollectPad", size = Vector3.new(4.6, 0.5, 3.2), cframe = cf * CFrame.new(L.CollectPadOffset) * CFrame.new(0, 0.25, 0), color = Color3.fromRGB(120, 230, 110), material = Enum.Material.SmoothPlastic, parent = baseP })
		pad:SetAttribute("Slot", i)
		CollectionService:AddTag(pad, "CollectPad")
		local sell = prompt(baseP, "SellPrompt", "SELL", 1, "Owner")
		local steal = prompt(baseP, "StealPrompt", "STEAL", 2, "Others")
		baseP:SetAttribute("Slot", i)
		CollectionService:AddTag(baseP, "Pedestal")
		pedestals[i] = { base = baseP, pad = pad, slot = i, prompt = sell, stealPrompt = steal }
	end

	-- console della barriera
	local consoleCf = at(L.BarrierConsole)
	local console = Build.Part({ name = "BarrierConsole", size = Vector3.new(3.4, 3.2, 3.4), cframe = consoleCf * CFrame.new(0, 1.6, 0), color = theme.trim, parent = model })
	Build.Part({ name = "Button", size = Vector3.new(0.8, 2.6, 2.6), cframe = consoleCf * CFrame.new(0, 3.5, 0) * CFrame.Angles(0, 0, math.rad(90)), color = Color3.fromRGB(255, 60, 70), material = Enum.Material.Neon, shape = Enum.PartType.Cylinder, collide = false, parent = console })
	local consolePrompt = prompt(console, "BarrierPrompt", "LOCK BASE", 0.3, "Owner")

	-- posti per le trappole
	local traps = {}
	for i, pos in L.Traps do
		local spot = Build.Part({ name = `TrapSpot{i}`, size = Vector3.new(0.1, 4, 4), cframe = at(pos) * CFrame.new(0, 0.06, 0) * CFrame.Angles(0, 0, math.rad(90)), color = theme.wall:Lerp(Color3.new(0, 0, 0), 0.15), shape = Enum.PartType.Cylinder, collide = false, transparency = 0.5, parent = model })
		spot:SetAttribute("Slot", tostring(i))
		traps[i] = spot
	end

	CollectionService:AddTag(model, "Plot")
	return {
		index = index,
		cframe = base,
		model = model,
		owner = nil,
		theme = theme,
		incubators = incubators,
		pedestals = pedestals,
		gateBarrier = barrier,
		console = console,
		consolePrompt = consolePrompt,
		traps = traps,
		sign = sign,
		occupants = {},
	}
end

local function setupCollisionGroups()
	for i = 1, MapLayout.PlotCount do
		pcall(function()
			PhysicsService:RegisterCollisionGroup(`Barrier{i}`)
			PhysicsService:RegisterCollisionGroup(`Owner{i}`)
		end)
	end
	for i = 1, MapLayout.PlotCount do
		-- la barriera blocca tutti tranne il proprietario del lotto
		PhysicsService:CollisionGroupSetCollidable(`Barrier{i}`, `Owner{i}`, false)
		for j = 1, MapLayout.PlotCount do
			if i ~= j then
				PhysicsService:CollisionGroupSetCollidable(`Barrier{i}`, `Owner{j}`, true)
			end
		end
	end
end

function PlotService.Init(services)
	S = services
	setupCollisionGroups()
	local folder = Instance.new("Folder")
	folder.Name = "Plots"
	folder.Parent = workspace
	for i = 1, MapLayout.PlotCount do
		PlotService.Plots[i] = buildPlot(i, folder)
	end
end

local function refreshSign(plot: Plot)
	local gui = plot.sign:FindFirstChild("SignGui")
	if not gui then
		return
	end
	local label = gui:FindFirstChild("Owner") :: TextLabel
	local face = gui:FindFirstChild("Avatar") :: ImageLabel
	if plot.owner then
		label.Text = plot.owner.DisplayName
		face.Image = `rbxthumb://type=AvatarHeadShot&id={plot.owner.UserId}&w=150&h=150`
	else
		label.Text = ""
		face.Image = ""
	end
	plot.model:SetAttribute("OwnerUserId", if plot.owner then plot.owner.UserId else 0)
	plot.model:SetAttribute("OwnerName", if plot.owner then plot.owner.DisplayName else "")
end

-- Mostra come bloccate le incubatrici e i piedistalli non ancora sbloccati
function PlotService.RefreshLocks(player: Player)
	local plot = PlotService.Get(player)
	local data = S.DataService.Get(player)
	if not plot or not data then
		return
	end
	local incCount = PlotService.IncubatorCount(player)
	local pedCount = Upgrades.PedestalCount(data.Upgrades.Pedestals)
	for i, inc in plot.incubators do
		local locked = i > incCount
		inc.base.Transparency = if locked then 0.7 else 0
		inc.ring.Transparency = if locked then 1 else 0
		inc.base:SetAttribute("Locked", locked)
	end
	for i, ped in plot.pedestals do
		local locked = i > pedCount
		ped.base.Transparency = if locked then 0.7 else 0
		ped.pad.Transparency = if locked then 1 else 0
		ped.base:SetAttribute("Locked", locked)
		for _, d in ped.base:GetChildren() do
			if d:IsA("BasePart") and d ~= ped.pad then
				d.Transparency = if locked then 0.75 else 0
			end
		end
	end
end

function PlotService.IncubatorCount(player: Player): number
	local data = S.DataService.Get(player)
	if not data then
		return 0
	end
	return math.min(Upgrades.IncubatorCount(data.Upgrades.Incubators, S.MonetizationService.HasPass(player, "ExtraIncubator")), Upgrades.MaxIncubators)
end

function PlotService.PedestalCount(player: Player): number
	local data = S.DataService.Get(player)
	if not data then
		return 0
	end
	return Upgrades.PedestalCount(data.Upgrades.Pedestals)
end

local function setCharacterGroup(character: Model, group: string)
	for _, d in character:GetDescendants() do
		if d:IsA("BasePart") then
			d.CollisionGroup = group
		end
	end
	character.DescendantAdded:Connect(function(d)
		if d:IsA("BasePart") then
			d.CollisionGroup = group
		end
	end)
end

local function assign(player: Player)
	if PlotService.Get(player) then
		return
	end
	for _, plot in PlotService.Plots do
		if plot.owner == nil then
			plot.owner = player
			player:SetAttribute("PlotIndex", plot.index)
			refreshSign(plot)
			PlotService.RefreshLocks(player)
			if player.Character then
				setCharacterGroup(player.Character, `Owner{plot.index}`)
			end
			PlotService.Assigned:Fire(player, plot)
			return
		end
	end
	warn(`[PlotService] nessun lotto libero per {player.Name}`)
end

local function release(player: Player)
	local plot = PlotService.Get(player)
	if not plot then
		return
	end
	PlotService.Released:Fire(player, plot)
	plot.owner = nil
	table.clear(plot.occupants)
	refreshSign(plot)
	player:SetAttribute("PlotIndex", nil)
	for _, inc in plot.incubators do
		inc.prompt.Enabled = false
		inc.stealPrompt.Enabled = false
	end
	for _, ped in plot.pedestals do
		ped.prompt.Enabled = false
		ped.stealPrompt.Enabled = false
	end
end

function PlotService.Start()
	S.DataService.Loaded:Connect(function(player)
		assign(player)
	end)
	Players.PlayerRemoving:Connect(release)
	Players.PlayerAdded:Connect(function(player)
		player.CharacterAdded:Connect(function(character)
			local plot = PlotService.Get(player)
			setCharacterGroup(character, if plot then `Owner{plot.index}` else "Default")
		end)
	end)
	-- rilevamento ingressi nei lotti (allarme, consegna della refurtiva)
	task.spawn(function()
		while true do
			task.wait(0.25)
			for _, plot in PlotService.Plots do
				for _, player in Players:GetPlayers() do
					local char = player.Character
					local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
					local inside = hrp ~= nil and PlotService.Contains(plot, hrp.Position)
					if inside and not plot.occupants[player] then
						plot.occupants[player] = true
						PlotService.Entered:Fire(player, plot)
					elseif not inside and plot.occupants[player] then
						plot.occupants[player] = nil
					end
				end
			end
		end
	end)
end

function PlotService.Get(player: Player): Plot?
	for _, plot in PlotService.Plots do
		if plot.owner == player then
			return plot
		end
	end
	return nil
end

function PlotService.ByIndex(index: number): Plot?
	return PlotService.Plots[index]
end

-- Vero se la posizione e' dentro il recinto del lotto
function PlotService.Contains(plot: Plot, pos: Vector3): boolean
	local lp = plot.cframe:PointToObjectSpace(pos)
	return math.abs(lp.X) <= MapLayout.PlotSize.X / 2 - 1 and math.abs(lp.Z) <= MapLayout.PlotSize.Z / 2 - 1 and lp.Y > -3 and lp.Y < 20
end

function PlotService.PlotAt(pos: Vector3): Plot?
	for _, plot in PlotService.Plots do
		if PlotService.Contains(plot, pos) then
			return plot
		end
	end
	return nil
end

function PlotService.SpawnCFrame(player: Player): CFrame
	local plot = PlotService.Get(player)
	if plot then
		local cf = plot.cframe * CFrame.new(L.SpawnOffset)
		return CFrame.lookAt(cf.Position, cf.Position + plot.cframe.LookVector)
	end
	return CFrame.new(MapLayout.SummitCenter + Vector3.new(0, 4, 60))
end

return PlotService
