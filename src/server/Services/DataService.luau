-- Salvataggio dei dati dei giocatori con ProfileStore (sessione bloccata: niente duplicazioni).

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local ProfileStore = require(script.Parent.Parent.Vendor.ProfileStore)
local Signal = require(ReplicatedStorage.Shared.Util.Signal)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)

local DataService = {}

DataService.Version = 1
DataService.Loaded = Signal.new() -- (player, data)
-- funzioni (player, data) eseguite (anche con attese) dopo il caricamento ma prima di Loaded
DataService.PreLoad = {} :: { (Player, any) -> () }
DataService.Releasing = Signal.new() -- (player, data) prima della chiusura della sessione

local TEMPLATE = {
	Version = 1,
	Coins = GameConfig.StartingCoins,
	TotalEarned = 0,
	Upgrades = { Speed = 0, Strength = 0, Backpack = 0, Incubators = 0, HatchSpeed = 0, Pedestals = 0, Barrier = 0 },
	Pets = {}, -- [uid] = { Id, Mutation, Size, Slot, Bank, Got }
	NextUid = 1,
	Incubators = {}, -- ["1".."9"] = { Rarity, Start, Duration, Mutation?, Source? }
	PendingEggs = {}, -- lista di { Rarity, Source } in attesa di incubatrice
	Index = {}, -- [petId] = { [variante] = true }
	IndexClaimed = {}, -- [rarita'] = true
	Bats = { RubberMallet = true },
	EquippedBat = "RubberMallet",
	Traps = {}, -- ["1".."3"] = trapId
	Stats = { Steals = 0, Stolen = 0, Hatched = 0, Delivered = 0, PlayTime = 0, BestIncome = 0 },
	Codes = {},
	Daily = { Last = 0, Streak = 0 },
	LuckUntil = 0,
	Settings = { Music = true, Sfx = true, LowGfx = false, Lang = "" },
	Tutorial = 0,
	LastOnline = 0,
	GroupClaimed = false,
	Purchases = {}, -- [PurchaseId] = os.time()
	PurchaseOrder = {},
}

local STORE_NAME = "PlayerData_v1"

local store
local profiles: { [Player]: any } = {}
local waiting: { [Player]: { thread } } = {}
local S

local function useMock(): boolean
	-- In sessione di test o in Studio senza accesso alle API si usa l'archivio simulato
	return (S and S.Options.test) or false
end

function DataService.Init(services)
	S = services
	store = ProfileStore.New(STORE_NAME, TEMPLATE)
	if useMock() then
		store = store.Mock
	end
end

local function resume(player: Player)
	local list = waiting[player]
	waiting[player] = nil
	if list then
		for _, th in list do
			task.spawn(th)
		end
	end
end

local function migrate(data)
	-- aggiornamenti futuri dello schema: if data.Version < 2 then ... end
	data.Version = DataService.Version
end

local function onPlayerAdded(player: Player)
	local profile = store:StartSessionAsync(`Player_{player.UserId}`, {
		Cancel = function()
			return player.Parent ~= Players
		end,
	})
	if profile == nil then
		resume(player)
		player:Kick("Impossibile caricare i tuoi dati, riprova tra poco. / Could not load your data, please rejoin.")
		return
	end
	profile:AddUserId(player.UserId)
	profile:Reconcile()
	migrate(profile.Data)
	profile.OnSessionEnd:Connect(function()
		profiles[player] = nil
		if player.Parent == Players then
			player:Kick("Sessione chiusa: rientra nel gioco. / Session ended, please rejoin.")
		end
	end)
	if player.Parent ~= Players then
		profile:EndSession()
		resume(player)
		return
	end
	profiles[player] = profile
	-- preparazioni che devono essere pronte prima degli altri servizi (game pass posseduti...)
	for _, fn in DataService.PreLoad do
		local ok, err = pcall(fn, player, profile.Data)
		if not ok then
			warn(`[DataService] preparazione di {player.Name}: {err}`)
		end
	end
	if player.Parent ~= Players then
		return
	end
	resume(player)
	DataService.Loaded:Fire(player, profile.Data)
end

local function onPlayerRemoving(player: Player)
	local profile = profiles[player]
	if profile then
		profile.Data.LastOnline = os.time()
		DataService.Releasing:Fire(player, profile.Data)
		-- i servizi possono scrivere gli ultimi dati in modo sincrono durante Releasing
		task.defer(function()
			if profile:IsActive() then
				profile:EndSession()
			end
		end)
	end
	resume(player)
end

function DataService.Start()
	for _, p in Players:GetPlayers() do
		task.spawn(onPlayerAdded, p)
	end
	Players.PlayerAdded:Connect(onPlayerAdded)
	Players.PlayerRemoving:Connect(onPlayerRemoving)
	if not RunService:IsStudio() then
		game:BindToClose(function()
			for player, profile in profiles do
				profile.Data.LastOnline = os.time()
				DataService.Releasing:Fire(player, profile.Data)
			end
		end)
	end
end

-- Dati del giocatore (nil se non ancora caricati).
function DataService.Get(player: Player)
	local p = profiles[player]
	return p and p.Data
end

function DataService.Profile(player: Player)
	return profiles[player]
end

-- Attende il caricamento (massimo timeout secondi).
function DataService.Wait(player: Player, timeout: number?)
	if profiles[player] then
		return profiles[player].Data
	end
	if player.Parent ~= Players then
		return nil
	end
	local thread = coroutine.running()
	waiting[player] = waiting[player] or {}
	table.insert(waiting[player], thread)
	local done = false
	task.delay(timeout or 30, function()
		if not done then
			local list = waiting[player]
			if list then
				local i = table.find(list, thread)
				if i then
					table.remove(list, i)
					task.spawn(thread)
				end
			end
		end
	end)
	coroutine.yield()
	done = true
	local p = profiles[player]
	return p and p.Data
end

function DataService.IsLoaded(player: Player): boolean
	return profiles[player] ~= nil
end

-- Monete -----------------------------------------------------------------------------------

function DataService.AddCoins(player: Player, amount: number, reason: string?)
	local data = DataService.Get(player)
	if not data or amount <= 0 or amount ~= amount then
		return
	end
	data.Coins += amount
	data.TotalEarned += amount
	S.StateService.Set(player, { "Coins" }, data.Coins)
	S.StateService.Set(player, { "TotalEarned" }, data.TotalEarned)
	if reason then
		S.AnalyticsService.Economy(player, "Source", amount, data.Coins, reason)
	end
end

function DataService.SpendCoins(player: Player, amount: number, reason: string?): boolean
	local data = DataService.Get(player)
	if not data or amount < 0 or amount ~= amount or data.Coins < amount then
		return false
	end
	data.Coins -= amount
	S.StateService.Set(player, { "Coins" }, data.Coins)
	if reason then
		S.AnalyticsService.Economy(player, "Sink", amount, data.Coins, reason)
	end
	return true
end

function DataService.NewUid(player: Player): string
	local data = DataService.Get(player)
	local uid = tostring(data.NextUid)
	data.NextUid += 1
	return uid
end

return DataService
