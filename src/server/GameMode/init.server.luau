-- Coin Rush: ciclo dei round (attesa -> intervallo -> round -> risultati).
-- Durante il round i giocatori vengono portati nell'arena sospesa e devono raccogliere
-- più monete possibile. Chi cade o muore è eliminato. Vince chi ha più monete.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage.Shared.Config)
local Arena = require(script.Arena)
local Coins = require(script.Coins)

-- Stato condiviso letto dall'HUD dei client
local gameState = Instance.new("Folder")
gameState.Name = "GameState"
local status = Instance.new("StringValue")
status.Name = "Status"
status.Parent = gameState
local timeLeft = Instance.new("IntValue")
timeLeft.Name = "TimeLeft"
timeLeft.Parent = gameState
gameState.Parent = ReplicatedStorage

local function setupLeaderstats(player: Player)
	local leaderstats = Instance.new("Folder")
	leaderstats.Name = "leaderstats"
	local coins = Instance.new("IntValue")
	coins.Name = "Monete"
	coins.Parent = leaderstats
	local wins = Instance.new("IntValue")
	wins.Name = "Vittorie"
	wins.Parent = leaderstats
	leaderstats.Parent = player
end

Players.PlayerAdded:Connect(setupLeaderstats)
for _, player in Players:GetPlayers() do
	setupLeaderstats(player)
end

local arena = Arena.build()
local participants: { [Player]: boolean } = {}

Players.PlayerRemoving:Connect(function(player)
	participants[player] = nil
end)

local function participantCount(): number
	local count = 0
	for _ in participants do
		count += 1
	end
	return count
end

local function stat(player: Player, name: string): IntValue
	return (player:WaitForChild("leaderstats") :: Folder):WaitForChild(name) :: IntValue
end

-- Conto alla rovescia; onTick viene chiamato ogni secondo e può interromperlo restituendo true.
local function countdown(seconds: number, text: string, onTick: (() -> boolean)?)
	status.Value = text
	for t = seconds, 1, -1 do
		timeLeft.Value = t
		if onTick and onTick() then
			break
		end
		task.wait(1)
	end
	timeLeft.Value = 0
end

-- Elimina chi è caduto dall'arena senza aspettare FallenPartsDestroyHeight.
local function eliminateFallen()
	local limit = Arena.floorHeight(arena) - Config.FALL_LIMIT
	for player in participants do
		local character = player.Character
		local root = character and character:FindFirstChild("HumanoidRootPart") :: BasePart?
		local humanoid = character and character:FindFirstChildOfClass("Humanoid")
		if root and humanoid and root.Position.Y < limit then
			humanoid.Health = 0
		end
	end
end

local function waitForPlayers()
	while #Players:GetPlayers() < Config.MIN_PLAYERS do
		status.Value = string.format("In attesa di giocatori (%d/%d)", #Players:GetPlayers(), Config.MIN_PLAYERS)
		timeLeft.Value = 0
		task.wait(1)
	end
end

local function runRound()
	participants = {}
	local connections = {}

	for _, player in Players:GetPlayers() do
		local character = player.Character
		local humanoid = character and character:FindFirstChildOfClass("Humanoid")
		if character and humanoid and humanoid.Health > 0 then
			participants[player] = true
			stat(player, "Monete").Value = 0
			character:PivotTo(CFrame.new(Arena.randomSurfacePoint(arena, 4)))
			table.insert(
				connections,
				humanoid.Died:Connect(function()
					participants[player] = nil
				end)
			)
		end
	end

	if participantCount() == 0 then
		return
	end

	local coins = Coins.new(arena, function(player)
		if not participants[player] then
			return false
		end
		stat(player, "Monete").Value += Config.COIN_VALUE
		return true
	end)

	local running = true
	task.spawn(function()
		while running do
			coins:spawn()
			task.wait(Config.COIN_SPAWN_INTERVAL)
		end
	end)

	countdown(Config.ROUND_DURATION, "Raccogli le monete!", function()
		eliminateFallen()
		return participantCount() == 0
	end)

	running = false
	coins:destroy()
	for _, connection in connections do
		connection:Disconnect()
	end

	-- Vince chi è sopravvissuto con più monete (pareggio = vittoria per tutti)
	local best, winners = 0, {}
	for player in participants do
		local score = stat(player, "Monete").Value
		if score > best then
			best, winners = score, { player }
		elseif score == best and score > 0 then
			table.insert(winners, player)
		end
	end

	if #winners == 0 then
		status.Value = "Nessun vincitore questa volta!"
	else
		local names = {}
		for _, player in winners do
			stat(player, "Vittorie").Value += 1
			table.insert(names, player.DisplayName)
		end
		status.Value = string.format("Vince %s con %d monete!", table.concat(names, ", "), best)
	end
	timeLeft.Value = 0
	task.wait(Config.RESULTS_DURATION)

	-- Riporta i sopravvissuti nella lobby
	for player in participants do
		if player.Parent then
			player:LoadCharacter()
		end
	end
	participants = {}
end

while true do
	waitForPlayers()
	countdown(Config.INTERMISSION, "Il round inizia tra poco", function()
		return #Players:GetPlayers() < Config.MIN_PLAYERS
	end)
	if #Players:GetPlayers() >= Config.MIN_PLAYERS then
		runRound()
	end
end
