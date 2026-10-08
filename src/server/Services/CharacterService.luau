-- Comparsa dei personaggi nel proprio lotto, velocita', effetti di stato e caduta nel vuoto.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Upgrades = require(ReplicatedStorage.Shared.Config.Upgrades)

local CharacterService = {}

local S
-- effetti temporanei: [player] = { Slow = fino a, Root = fino a, ... }
local effects: { [Player]: { [string]: number } } = {}

function CharacterService.Init(services)
	S = services
end

local function humanoidOf(player: Player): Humanoid?
	local char = player.Character
	return char and char:FindFirstChildOfClass("Humanoid")
end

function CharacterService.Root(player: Player): BasePart?
	local char = player.Character
	return char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
end

-- Ricalcola la velocita' di camminata: livello Velocita' x peso trasportato x effetti
function CharacterService.UpdateSpeed(player: Player)
	local hum = humanoidOf(player)
	local data = S.DataService.Get(player)
	if not hum or not data then
		return
	end
	local speed = Upgrades.WalkSpeed(data.Upgrades.Speed)
	speed *= S.CarryService.SpeedMultiplier(player)
	local now = os.clock()
	local fx = effects[player]
	if fx then
		if (fx.Root or 0) > now then
			speed = 0
		elseif (fx.Slow or 0) > now then
			speed *= 0.45
		end
	end
	hum.WalkSpeed = speed
	player:SetAttribute("WalkSpeed", speed)
end

-- Applica un effetto per 'duration' secondi (Slow, Root)
function CharacterService.ApplyEffect(player: Player, name: string, duration: number)
	effects[player] = effects[player] or {}
	effects[player][name] = os.clock() + duration
	player:SetAttribute("Effect_" .. name, workspace:GetServerTimeNow() + duration)
	CharacterService.UpdateSpeed(player)
	task.delay(duration + 0.05, function()
		if player.Parent then
			CharacterService.UpdateSpeed(player)
		end
	end)
end

function CharacterService.IsProtected(player: Player): boolean
	return (player:GetAttribute("ProtectedUntil") or 0) > workspace:GetServerTimeNow()
end

-- Riporta il giocatore nel suo lotto senza farlo morire (caduta, valanga, lava)
function CharacterService.ReturnToBase(player: Player, reasonKey: string?)
	local char = player.Character
	if not char then
		return
	end
	S.CarryService.DropAll(player, "Void")
	S.RagdollService.Recover(player)
	char:PivotTo(S.PlotService.SpawnCFrame(player))
	local hrp = CharacterService.Root(player)
	if hrp then
		hrp.AssemblyLinearVelocity = Vector3.zero
	end
	player:SetAttribute("ProtectedUntil", workspace:GetServerTimeNow() + 2)
	if reasonKey then
		S.StateService.Notify(player, reasonKey, nil, "Bad")
	end
end

local function onCharacter(player: Player, character: Model)
	local hum = character:WaitForChild("Humanoid", 10) :: Humanoid?
	if not hum then
		return
	end
	hum.BreakJointsOnDeath = false
	hum.RequiresNeck = false
	character:PivotTo(S.PlotService.SpawnCFrame(player))
	player:SetAttribute("ProtectedUntil", workspace:GetServerTimeNow() + GameConfig.SpawnProtection)
	CharacterService.UpdateSpeed(player)
	hum.Died:Connect(function()
		S.CarryService.DropAll(player, "Died")
		task.delay(2, function()
			if player.Parent == Players then
				player:LoadCharacter()
			end
		end)
	end)
end

local function spawn(player: Player)
	S.MapService.WaitReady()
	if player.Parent ~= Players then
		return
	end
	player:LoadCharacter()
end

function CharacterService.Start()
	if S.Options.test then
		return
	end
	local function setup(player: Player)
		player.CharacterAdded:Connect(function(character)
			onCharacter(player, character)
		end)
	end
	for _, p in Players:GetPlayers() do
		setup(p)
	end
	Players.PlayerAdded:Connect(setup)
	S.PlotService.Assigned:Connect(function(player)
		task.spawn(spawn, player)
	end)
	Players.PlayerRemoving:Connect(function(player)
		effects[player] = nil
	end)
	-- caduta nel mare di nuvole
	local acc = 0
	RunService.Heartbeat:Connect(function(dt)
		acc += dt
		if acc < 0.2 then
			return
		end
		acc = 0
		for _, player in Players:GetPlayers() do
			local hrp = CharacterService.Root(player)
			if hrp and hrp.Position.Y < MapLayout.VoidY then
				CharacterService.ReturnToBase(player, "FellOff")
			end
		end
	end)
end

return CharacterService
