-- Progressione persistente (DataStore): XP, livello e rango "Criptidologo".
-- In Studio serve "Enable Studio Access to API Services", altrimenti i dati restano solo in memoria.
local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))

local Progression = {}

local DEFAULT = { XP = 0, Runs = 0, Wins = 0, Captures = 0, Evidence = 0, Revives = 0 }

local store: DataStore? = nil
do
	local ok, result = pcall(function()
		return DataStoreService:GetDataStore("RakeHunt_Profili_v1")
	end)
	if ok then
		store = result
	end
end

local profiles: { [Player]: { [string]: number } } = {}

local function key(player: Player): string
	return "p_" .. player.UserId
end

function Progression.rankFor(xp: number): (string, number?)
	local name, nextXp = Config.RANKS[1].name, nil
	for i, rank in Config.RANKS do
		if xp >= rank.xp then
			name = rank.name
			nextXp = Config.RANKS[i + 1] and Config.RANKS[i + 1].xp or nil
		end
	end
	return name, nextXp
end

function Progression.levelFor(xp: number): number
	return math.floor(math.sqrt(xp / 40)) + 1
end

local function refresh(player: Player)
	local data = profiles[player]
	local stats = player:FindFirstChild("leaderstats")
	if not data or not stats then
		return
	end
	local rank = Progression.rankFor(data.XP)
	;(stats:FindFirstChild("Rango") :: StringValue).Value = rank
	;(stats:FindFirstChild("Livello") :: IntValue).Value = Progression.levelFor(data.XP)
	player:SetAttribute("XP", data.XP)
end

function Progression.load(player: Player)
	local data = table.clone(DEFAULT)
	if store then
		local ok, saved = pcall(function()
			return (store :: DataStore):GetAsync(key(player))
		end)
		if ok and type(saved) == "table" then
			for k, v in saved do
				data[k] = v
			end
		elseif not ok then
			warn("[Progressione] Caricamento fallito per " .. player.Name .. ": " .. tostring(saved))
		end
	end
	profiles[player] = data

	local stats = Instance.new("Folder")
	stats.Name = "leaderstats"
	local rank = Instance.new("StringValue")
	rank.Name = "Rango"
	rank.Parent = stats
	local level = Instance.new("IntValue")
	level.Name = "Livello"
	level.Parent = stats
	stats.Parent = player
	refresh(player)
end

function Progression.get(player: Player)
	return profiles[player]
end

function Progression.save(player: Player)
	local data = profiles[player]
	if not store or not data then
		return
	end
	local ok, err = pcall(function()
		(store :: DataStore):SetAsync(key(player), data)
	end)
	if not ok then
		warn("[Progressione] Salvataggio fallito per " .. player.Name .. ": " .. tostring(err))
	end
end

function Progression.award(player: Player, xp: number, counters: { [string]: number })
	local data = profiles[player]
	if not data then
		return
	end
	data.XP += xp
	for k, v in counters do
		data[k] = (data[k] or 0) + v
	end
	refresh(player)
	task.spawn(Progression.save, player)
end

function Progression.release(player: Player)
	Progression.save(player)
	profiles[player] = nil
end

game:BindToClose(function()
	for _, player in Players:GetPlayers() do
		Progression.save(player)
	end
end)

return Progression
