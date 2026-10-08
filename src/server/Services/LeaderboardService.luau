-- Classifiche globali (OrderedDataStore): piu' ricchi, ladri migliori, guadagno migliore.
-- Mostrate su tre tabelloni nella piazza della vetta e nell'interfaccia.

local DataStoreService = game:GetService("DataStoreService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Net = require(ReplicatedStorage.Shared.Net)
local Build = require(script.Parent.Parent.World.Build)

local LeaderboardService = {}

local S
local BOARDS = {
	{ key = "Money", store = "LB_TotalEarned_v1", title = "LbMoney", value = function(data) return data.TotalEarned end },
	{ key = "Steals", store = "LB_Steals_v1", title = "LbSteals", value = function(data) return data.Stats.Steals end },
	{ key = "Income", store = "LB_BestIncome_v1", title = "LbIncome", value = function(data) return data.Stats.BestIncome or 0 end },
}
local stores = {}
local cache = { Money = {}, Steals = {}, Income = {} }
local boardParts = {}

function LeaderboardService.Init(services)
	S = services
end

-- I valori molto grandi vengono salvati in forma compressa (logaritmica) per stare negli interi
local function encode(v: number): number
	if v < 1 then
		return 0
	end
	return math.floor(math.log10(v) * 1e6)
end

local function decode(v: number): number
	return 10 ^ (v / 1e6)
end

local function buildBoards()
	local folder = Build.Model("Leaderboards", workspace:FindFirstChild("Map"))
	local c = MapLayout.SummitCenter
	for i, b in BOARDS do
		local angle = math.rad(-55 + (i - 1) * 55)
		local pos = c + Vector3.new(math.sin(angle) * 58, 9, -math.cos(angle) * 58)
		local cf = CFrame.lookAt(pos, Vector3.new(c.X, pos.Y, c.Z))
		local board = Build.Part({ name = "Board" .. b.key, size = Vector3.new(16, 18, 1), cframe = cf, color = Color3.fromRGB(40, 30, 72), parent = folder })
		for _, sx in { -1, 1 } do
			Build.Part({ name = "Leg", size = Vector3.new(1.2, 10, 1.2), cframe = cf * CFrame.new(sx * 6, -13, 0.6), color = Color3.fromRGB(120, 80, 50), material = Enum.Material.Wood, parent = folder })
		end
		local gui = Instance.new("SurfaceGui")
		gui.Name = "BoardGui"
		gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
		gui.PixelsPerStud = 30
		gui.LightInfluence = 0
		gui.Parent = board
		board:SetAttribute("BoardKey", b.key)
		board:SetAttribute("TitleKey", b.title)
		game:GetService("CollectionService"):AddTag(board, "LeaderboardBoard")
		boardParts[b.key] = board
	end
end

local function publishAll()
	for _, player in Players:GetPlayers() do
		local data = S.DataService.Get(player)
		if data then
			for _, b in BOARDS do
				local v = b.value(data)
				pcall(function()
					stores[b.key]:SetAsync(tostring(player.UserId), encode(v))
				end)
			end
		end
	end
end

local nameCache = {}
local function nameOf(userId: number): string
	if nameCache[userId] then
		return nameCache[userId]
	end
	local ok, name = pcall(Players.GetNameFromUserIdAsync, Players, userId)
	nameCache[userId] = if ok then name else "?"
	return nameCache[userId]
end

local function fetchAll()
	for _, b in BOARDS do
		local ok, pages = pcall(function()
			return stores[b.key]:GetSortedAsync(false, 10)
		end)
		if ok and pages then
			local list = {}
			for rank, entry in pages:GetCurrentPage() do
				local uid = tonumber(entry.key) or 0
				table.insert(list, { rank = rank, userId = uid, name = nameOf(uid), value = decode(entry.value) })
			end
			cache[b.key] = list
		end
		-- i tabelloni leggono i dati dall'attributo (il client li disegna)
		local part = boardParts[b.key]
		if part then
			part:SetAttribute("Data", game:GetService("HttpService"):JSONEncode(cache[b.key]))
		end
	end
end

function LeaderboardService.Start()
	for _, b in BOARDS do
		stores[b.key] = DataStoreService:GetOrderedDataStore(b.store)
	end
	S.MapService.WaitReady()
	buildBoards()
	Net.Function("GetLeaderboards").OnServerInvoke = function()
		return cache
	end
	if S.Options.test then
		return
	end
	task.spawn(function()
		task.wait(10)
		while true do
			pcall(publishAll)
			pcall(fetchAll)
			task.wait(120)
		end
	end)
	S.DataService.Releasing:Connect(function(player, data)
		for _, b in BOARDS do
			local v = b.value(data)
			task.spawn(pcall, function()
				stores[b.key]:SetAsync(tostring(player.UserId), encode(v))
			end)
		end
	end)
end

return LeaderboardService
