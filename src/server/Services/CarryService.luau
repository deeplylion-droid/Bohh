-- Trasporto di uova e refurtiva sopra la testa, rallentamento, cadute e consegna al lotto.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local CollectionService = game:GetService("CollectionService")

local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Upgrades = require(ReplicatedStorage.Shared.Config.Upgrades)

local CarryService = {}

export type EggInfo = {
	id: string,
	rarity: string,
	nestId: string?,
	zone: string?,
	cosmicMin: number?,
	remaining: number?, -- secondi di incubazione rimasti (uova rubate)
	duration: number?,
}

export type Carried = {
	kind: "Egg" | "Pet",
	model: Model,
	egg: EggInfo?,
	stolen: any?, -- dati del furto (vedi StealService)
	rarity: string,
	weight: number,
}

local S
local noRoomAt: { [Player]: number } = {}
local carried: { [Player]: { Carried } } = {}
local dropped: { [string]: { ball: BasePart, egg: EggInfo } } = {}
local droppedFolder: Folder

function CarryService.Init(services)
	S = services
	droppedFolder = Instance.new("Folder")
	droppedFolder.Name = "DroppedEggs"
	droppedFolder.Parent = workspace
end

function CarryService.Items(player: Player): { Carried }
	return carried[player] or {}
end

function CarryService.Count(player: Player): number
	return #(carried[player] or {})
end

function CarryService.Capacity(player: Player): number
	local data = S.DataService.Get(player)
	if not data then
		return 1
	end
	return Upgrades.CarryCapacity(data.Upgrades.Backpack, S.MonetizationService.HasPass(player, "BigBackpack"))
end

function CarryService.CanCarry(player: Player): boolean
	return CarryService.Count(player) < CarryService.Capacity(player) and not S.RagdollService.IsRagdolled(player)
end

function CarryService.IsCarryingStolen(player: Player): boolean
	for _, c in carried[player] or {} do
		if c.stolen then
			return true
		end
	end
	return false
end

-- Moltiplicatore di velocita' dovuto al peso: conta l'oggetto piu' pesante, piu' un 6% per ogni oggetto extra
function CarryService.SpeedMultiplier(player: Player): number
	local list = carried[player]
	if not list or #list == 0 then
		return 1
	end
	local data = S.DataService.Get(player)
	local reduction = if data then Upgrades.WeightReduction(data.Upgrades.Strength) else 0
	local heaviest = 1
	local stolen = false
	for _, c in list do
		heaviest = math.min(heaviest, c.weight)
		stolen = stolen or c.stolen ~= nil
	end
	local w = 1 - (1 - heaviest) * (1 - reduction)
	w *= 1 - 0.06 * (#list - 1)
	if stolen then
		w *= GameConfig.StealSpeedMult
	end
	return math.max(w, 0.3)
end

local function publish(player: Player)
	local list = carried[player] or {}
	player:SetAttribute("Carrying", #list)
	local top = list[#list]
	player:SetAttribute("CarryRarity", if top then top.rarity else nil)
	player:SetAttribute("CarryKind", if top then top.kind else nil)
	player:SetAttribute("CarryPet", if top and top.kind == "Pet" and top.stolen then top.stolen.petId else nil)
	player:SetAttribute("Thief", CarryService.IsCarryingStolen(player))
	S.CharacterService.UpdateSpeed(player)
	-- con le mani occupate la mazza viene riposta
	if #list > 0 then
		local char = player.Character
		local hum = char and char:FindFirstChildOfClass("Humanoid")
		if hum then
			hum:UnequipTools()
		end
	end
end

local function prepareVisual(model: Model)
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = false
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
			d.Massless = true
		elseif d:IsA("ProximityPrompt") then
			d:Destroy()
		end
	end
end

-- Posiziona e salda gli oggetti trasportati uno sopra l'altro sopra la testa
local function restack(player: Player)
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	local head = char and char:FindFirstChild("Head") :: BasePart?
	if not hrp or not head then
		return
	end
	local list = carried[player] or {}
	local y = (head.Position.Y - hrp.Position.Y) + head.Size.Y / 2 + 0.4
	for _, c in list do
		local m = c.model
		for _, w in m:GetDescendants() do
			if w:IsA("WeldConstraint") and w.Name == "CarryWeld" then
				w:Destroy()
			end
		end
		local _, size = m:GetBoundingBox()
		m:PivotTo(hrp.CFrame * CFrame.new(0, y, 0))
		y += size.Y + 0.15
		local root = m.PrimaryPart or m:FindFirstChildWhichIsA("BasePart")
		if root then
			for _, d in m:GetDescendants() do
				if d:IsA("BasePart") and d ~= root then
					local w = Instance.new("WeldConstraint")
					w.Name = "CarryWeld"
					w.Part0 = root
					w.Part1 = d
					w.Parent = d
				end
			end
			local w = Instance.new("WeldConstraint")
			w.Name = "CarryWeld"
			w.Part0 = hrp
			w.Part1 = root
			w.Parent = root
		end
		m.Parent = char
	end
end

local function push(player: Player, item: Carried)
	carried[player] = carried[player] or {}
	prepareVisual(item.model)
	table.insert(carried[player], item)
	restack(player)
	publish(player)
end

-- Raccoglie un uovo (da un nido o da terra). Il modello passa al giocatore.
function CarryService.AddEgg(player: Player, egg: EggInfo, model: Model): boolean
	if not CarryService.CanCarry(player) then
		S.StateService.Notify(player, "BackpackFull", nil, "Bad")
		return false
	end
	push(player, { kind = "Egg", model = model, egg = egg, rarity = egg.rarity, weight = Rarities.Get(egg.rarity).weight })
	S.StateService.Effect(player, "Pickup", { rarity = egg.rarity })
	S.TutorialService.Advance(player, "PickedUp")
	return true
end

-- Refurtiva (uovo o pet rubato): stolen contiene i dati per riconsegnarla o restituirla
function CarryService.AddStolen(player: Player, model: Model, stolen: any, rarity: string, kind: "Egg" | "Pet")
	push(player, { kind = kind, model = model, stolen = stolen, rarity = rarity, weight = Rarities.Get(rarity).weight })
end

local function removeAt(player: Player, index: number): Carried?
	local list = carried[player]
	if not list or not list[index] then
		return nil
	end
	local item = table.remove(list, index)
	restack(player)
	publish(player)
	return item
end

---------------------------------------------------------------------------------------------
-- Uova cadute a terra: palle fisiche che rotolano giu' per il pendio
---------------------------------------------------------------------------------------------
local function returnEgg(egg: EggInfo)
	if egg.nestId then
		S.NestService.ReturnEgg(egg)
	end
end

local function spawnDropped(egg: EggInfo, model: Model, cframe: CFrame, velocity: Vector3)
	local ball = Instance.new("Part")
	ball.Name = "DroppedEgg"
	ball.Shape = Enum.PartType.Ball
	ball.Size = Vector3.one * 2.7
	ball.Transparency = 1
	ball.CFrame = cframe
	ball.CanCollide = true
	ball.CanQuery = true
	ball.CanTouch = false
	ball.CustomPhysicalProperties = PhysicalProperties.new(1.2, 0.35, 0.25, 1, 1)
	ball.Parent = droppedFolder
	for _, w in model:GetDescendants() do
		if w:IsA("WeldConstraint") then
			w:Destroy()
		end
	end
	model:PivotTo(cframe * CFrame.new(0, -1.5, 0))
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = false
			d.CanCollide = false
			d.Massless = true
			local w = Instance.new("WeldConstraint")
			w.Part0 = ball
			w.Part1 = d
			w.Parent = d
		end
	end
	model.Parent = ball
	ball:SetNetworkOwner(nil)
	ball.AssemblyLinearVelocity = velocity
	ball.AssemblyAngularVelocity = Vector3.new(math.random(-6, 6), 0, math.random(-6, 6))
	ball:SetAttribute("Rarity", egg.rarity)
	CollectionService:AddTag(ball, "Egg")

	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "PickupPrompt"
	prompt.ActionText = "PICK UP"
	prompt.ObjectText = egg.rarity
	prompt.HoldDuration = GameConfig.PickupHold
	prompt.MaxActivationDistance = 10
	prompt.RequiresLineOfSight = false
	prompt.Style = Enum.ProximityPromptStyle.Custom
	prompt:SetAttribute("Kind", "Egg")
	prompt:SetAttribute("Rarity", egg.rarity)
	prompt.Parent = ball
	dropped[egg.id] = { ball = ball, egg = egg }

	prompt.Triggered:Connect(function(player)
		local entry = dropped[egg.id]
		if not entry or not CarryService.CanCarry(player) then
			if entry then
				S.StateService.Notify(player, "BackpackFull", nil, "Bad")
			end
			return
		end
		dropped[egg.id] = nil
		local m = ball:FindFirstChildOfClass("Model")
		if m then
			m.Parent = nil
			for _, w in m:GetDescendants() do
				if w:IsA("WeldConstraint") then
					w:Destroy()
				end
			end
		end
		ball:Destroy()
		if m then
			CarryService.AddEgg(player, egg, m)
		end
	end)

	task.delay(GameConfig.DroppedEggLifetime, function()
		local entry = dropped[egg.id]
		if entry and entry.ball == ball then
			dropped[egg.id] = nil
			S.StateService.Effect(nil, "Poof", { position = ball.Position })
			ball:Destroy()
			returnEgg(egg)
		end
	end)
	-- se rotola nel vuoto torna subito al nido
	task.spawn(function()
		while ball.Parent do
			task.wait(0.5)
			if ball.Parent and ball.Position.Y < 60 and dropped[egg.id] then
				dropped[egg.id] = nil
				ball:Destroy()
				returnEgg(egg)
			end
		end
	end)
end

-- Fa cadere tutto cio' che il giocatore trasporta. reason: Slapped, Trap, Obstacle, Guardian (rotolano)
-- oppure Void, Died, Buried, Left (le uova tornano subito al nido, la refurtiva al proprietario)
function CarryService.DropAll(player: Player, reason: string)
	local list = carried[player]
	if not list or #list == 0 then
		return
	end
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	local rolls = (reason == "Slapped" or reason == "Trap" or reason == "Obstacle" or reason == "Guardian") and hrp ~= nil
	carried[player] = {}
	for i, item in list do
		if item.stolen then
			S.StealService.Cancel(player, item, reason)
			item.model:Destroy()
		elseif item.egg then
			if rolls and hrp then
				local back = -hrp.CFrame.LookVector
				local vel = back * 14 + Vector3.new(math.random(-6, 6), 18 + i * 3, math.random(-6, 6))
				spawnDropped(item.egg, item.model, hrp.CFrame * CFrame.new(0, 4 + i * 2.5, 1.5), vel)
			else
				item.model:Destroy()
				returnEgg(item.egg)
			end
		else
			item.model:Destroy()
		end
	end
	publish(player)
	if rolls then
		S.StateService.Notify(player, "EggDropped", nil, "Bad")
	end
end

-- Toglie un oggetto trasportato (usato da StealService per la consegna/annullamento)
function CarryService.Remove(player: Player, item: Carried)
	local list = carried[player]
	if not list then
		return
	end
	local i = table.find(list, item)
	if i then
		removeAt(player, i)
	end
end

---------------------------------------------------------------------------------------------
-- Consegna nel proprio lotto
---------------------------------------------------------------------------------------------
local function tryDeliver(player: Player)
	local list = carried[player]
	if not list or #list == 0 then
		return
	end
	local plot = S.PlotService.Get(player)
	local hrp = S.CharacterService.Root(player)
	if not plot or not hrp or not S.PlotService.Contains(plot, hrp.Position) then
		return
	end
	local i = 1
	while i <= #list do
		local item = list[i]
		local ok = false
		if item.stolen then
			ok = S.StealService.Complete(player, item)
		elseif item.egg then
			ok = S.HatchService.Insert(player, item.egg)
			if ok then
				if item.egg.nestId then
					S.NestService.Delivered(item.egg)
				end
				local data = S.DataService.Get(player)
				data.Stats.Delivered += 1
				S.TutorialService.Advance(player, "Delivered")
			elseif os.clock() - (noRoomAt[player] or 0) > 6 then
				-- un solo avviso ogni tanto (il controllo gira ogni secondo per ogni uovo)
				noRoomAt[player] = os.clock()
				S.StateService.Notify(player, "NoIncubator", nil, "Bad")
			end
		end
		if ok then
			table.remove(list, i)
			item.model:Destroy()
		else
			i += 1
		end
	end
	restack(player)
	publish(player)
end

function CarryService.Start()
	S.PlotService.Entered:Connect(function(player, plot)
		if plot.owner == player then
			tryDeliver(player)
		end
	end)
	-- controllo periodico (es. incubatrice liberata mentre si e' gia' nel lotto)
	task.spawn(function()
		while true do
			task.wait(1)
			for player, list in carried do
				if #list > 0 then
					tryDeliver(player)
				end
			end
		end
	end)
	Players.PlayerRemoving:Connect(function(player)
		CarryService.DropAll(player, "Left")
		carried[player] = nil
		noRoomAt[player] = nil
	end)
end

return CarryService
