-- Schiaffi con le mazze: fanno cadere a terra il bersaglio e gli fanno perdere cio' che trasporta.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Combat = require(ReplicatedStorage.Shared.Config.Combat)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Net = require(ReplicatedStorage.Shared.Net)

local CombatService = {}

local S
local lastSwing: { [Player]: number } = {}

function CombatService.Init(services)
	S = services
end

function CombatService.OwnsBat(player: Player, batId: string): boolean
	local data = S.DataService.Get(player)
	local def = Combat.Bats[batId]
	if not data or not def then
		return false
	end
	if def.vipOnly then
		return S.MonetizationService.HasPass(player, "VIP")
	end
	return def.price == 0 or data.Bats[batId] == true
end

local function makeTool(batId: string): Tool
	local def = Combat.Bats[batId]
	local tool = Instance.new("Tool")
	tool.Name = "Bat"
	tool.CanBeDropped = false
	tool.RequiresHandle = true
	tool.ToolTip = batId
	tool:SetAttribute("BatId", batId)
	local model = S.AssetService.Clone("Bats", "Bat" .. batId)
	local handle: BasePart
	if model and model.PrimaryPart then
		-- il modello della mazza: tutte le parti saldate a una maniglia invisibile
		handle = Instance.new("Part")
		handle.Name = "Handle"
		handle.Size = Vector3.new(0.6, 1.4, 0.6)
		handle.Transparency = 1
		handle.CanCollide = false
		handle.Massless = true
		handle.CFrame = CFrame.new(0, 0.7, 0)
		model:PivotTo(CFrame.new())
		for _, d in model:GetDescendants() do
			if d:IsA("BasePart") then
				d.Anchored = false
				d.CanCollide = false
				d.Massless = true
				local w = Instance.new("WeldConstraint")
				w.Part0 = handle
				w.Part1 = d
				w.Parent = d
			end
		end
		model.Parent = handle
	else
		-- mazza semplice: manico e testa colorata
		handle = Instance.new("Part")
		handle.Name = "Handle"
		handle.Size = Vector3.new(0.5, 3.2, 0.5)
		handle.Color = Color3.fromRGB(150, 100, 60)
		handle.Material = Enum.Material.Wood
		handle.CanCollide = false
		handle.Massless = true
		local head = Instance.new("Part")
		head.Name = "Head"
		head.Shape = Enum.PartType.Cylinder
		head.Size = Vector3.new(2.4, 1.6, 1.6)
		head.Color = def.color
		head.Material = Enum.Material.SmoothPlastic
		head.CanCollide = false
		head.Massless = true
		head.CFrame = handle.CFrame * CFrame.new(0, 1.8, 0)
		head.Parent = handle
		local w = Instance.new("WeldConstraint")
		w.Part0 = handle
		w.Part1 = head
		w.Parent = head
	end
	handle.Parent = tool
	tool.Grip = CFrame.new(0, -0.9, 0) * CFrame.Angles(math.rad(-10), 0, 0)
	tool.Activated:Connect(function()
		local char = tool.Parent
		local player = char and Players:GetPlayerFromCharacter(char)
		if player then
			CombatService.Swing(player)
		end
	end)
	return tool
end

function CombatService.GiveBat(player: Player)
	local data = S.DataService.Get(player)
	if not data or not player.Character then
		return
	end
	local batId = data.EquippedBat
	if not CombatService.OwnsBat(player, batId) then
		batId = "RubberMallet"
	end
	local backpack = player:FindFirstChildOfClass("Backpack")
	for _, container in { backpack, player.Character } do
		if container then
			for _, t in container:GetChildren() do
				if t:IsA("Tool") and t.Name == "Bat" then
					t:Destroy()
				end
			end
		end
	end
	if backpack then
		makeTool(batId).Parent = backpack
	end
end

function CombatService.Swing(player: Player)
	local data = S.DataService.Get(player)
	local def = Combat.Bats[data and data.EquippedBat or "RubberMallet"] or Combat.Bats.RubberMallet
	local now = os.clock()
	if now - (lastSwing[player] or 0) < def.cooldown * 0.9 then
		return
	end
	if S.CarryService.Count(player) > 0 or S.RagdollService.IsRagdolled(player) then
		return
	end
	lastSwing[player] = now
	local hrp = S.CharacterService.Root(player)
	if not hrp then
		return
	end
	S.StateService.Effect(nil, "Swing", { userId = player.UserId })
	local look = hrp.CFrame.LookVector
	local best, bestDist = nil, def.range + 2.5
	for _, other in Players:GetPlayers() do
		if other ~= player then
			local ohrp = S.CharacterService.Root(other)
			if ohrp then
				local delta = ohrp.Position - hrp.Position
				local flat = Vector3.new(delta.X, 0, delta.Z)
				local dist = flat.Magnitude
				if dist < bestDist and math.abs(delta.Y) < 6 and (dist < 2.5 or flat.Unit:Dot(look) > 0.15) then
					best, bestDist = other, dist
				end
			end
		end
	end
	if not best then
		return
	end
	-- protezioni: appena rinato, gia' a terra, o a casa propria
	if S.CharacterService.IsProtected(best) or S.RagdollService.IsRagdolled(best) then
		return
	end
	local home = S.PlotService.Get(best)
	local bhrp = S.CharacterService.Root(best)
	if home and bhrp and S.PlotService.Contains(home, bhrp.Position) then
		return
	end
	local dir = (Vector3.new(bhrp.Position.X - hrp.Position.X, 0, bhrp.Position.Z - hrp.Position.Z)).Unit
	if dir ~= dir then
		dir = look
	end
	S.CarryService.DropAll(best, "Slapped")
	S.RagdollService.Ragdoll(best, GameConfig.SlapRagdoll, dir * def.knockback + Vector3.new(0, def.knockback * 0.45, 0))
	S.StateService.Notify(best, "SlappedBy", { name = player.DisplayName }, "Bad")
	S.StateService.Effect(nil, "Slap", { position = bhrp.Position, bat = data and data.EquippedBat })
end

local function buyBat(player: Player, batId: any)
	local def = type(batId) == "string" and Combat.Bats[batId]
	local data = S.DataService.Get(player)
	if not def or not data or def.vipOnly or data.Bats[batId] then
		return
	end
	if not S.DataService.SpendCoins(player, def.price, "Bat") then
		S.StateService.Notify(player, "NotEnoughCoins", nil, "Bad")
		return
	end
	S.StateService.Set(player, { "Bats", batId }, true)
	S.StateService.Set(player, { "EquippedBat" }, batId)
	CombatService.GiveBat(player)
	S.StateService.Effect(player, "Purchase", {})
end

local function equipBat(player: Player, batId: any)
	if type(batId) ~= "string" or not CombatService.OwnsBat(player, batId) then
		return
	end
	S.StateService.Set(player, { "EquippedBat" }, batId)
	CombatService.GiveBat(player)
end

function CombatService.Start()
	Net.Event("BuyBat").OnServerEvent:Connect(buyBat)
	Net.Event("EquipBat").OnServerEvent:Connect(equipBat)
	Net.Event("Swing").OnServerEvent:Connect(function(player)
		CombatService.Swing(player)
	end)
	local function setup(player: Player)
		player.CharacterAdded:Connect(function()
			S.DataService.Wait(player, 30)
			task.wait(0.2)
			CombatService.GiveBat(player)
		end)
	end
	for _, p in Players:GetPlayers() do
		setup(p)
	end
	Players.PlayerAdded:Connect(setup)
	Players.PlayerRemoving:Connect(function(p)
		lastSwing[p] = nil
	end)
end

return CombatService
