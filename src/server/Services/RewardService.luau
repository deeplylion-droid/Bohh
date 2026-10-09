-- Premi: giornaliero (serie di 7 giorni), regali a tempo di gioco, gruppo, codici,
-- guadagni offline al rientro e bonus per gli amici nello stesso server.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Net = require(ReplicatedStorage.Shared.Net)
local Rewards = require(ReplicatedStorage.Shared.Config.Rewards)

local RewardService = {}

local S
local sessionStart: { [Player]: number } = {}
local claimedPlaytime: { [Player]: { [number]: boolean } } = {}

-- Codici attivi: CODICE = premio
local CODES = {
	LAUNCH = { kind = "Coins", amount = 1000 },
	EGGS = { kind = "Luck", amount = 15 },
	MOUNTAIN = { kind = "Egg", amount = 1, rarity = "Rare" },
}

function RewardService.Init(services)
	S = services
end

local DAY = 86400

local function scaledCoins(player: Player, amount: number): number
	-- i premi in monete crescono con i guadagni del giocatore (alcuni minuti di guadagno)
	local income = S.PetService.TotalIncome(player)
	return math.max(amount, math.floor(income * 60 * Rewards.CoinScaleMinutes))
end

-- Consegna un premio e ritorna la sua descrizione (chiave + argomenti) per il client
function RewardService.Give(player: Player, reward): (string, { [string]: any })
	if reward.kind == "Coins" then
		local amount = scaledCoins(player, reward.amount)
		S.DataService.AddCoins(player, amount, "Reward")
		S.StateService.Effect(player, "Coins", { amount = amount })
		return "RewardCoins", { amount = amount }
	elseif reward.kind == "Luck" then
		S.MonetizationService.AddLuck(player, reward.amount)
		return "RewardLuck", { t = reward.amount .. "m" }
	else
		for _ = 1, reward.amount do
			S.HatchService.AddPending(player, reward.rarity)
		end
		return "RewardEgg", { egg = "Egg_" .. reward.rarity }
	end
end

local function claimDaily(player: Player)
	local data = S.DataService.Get(player)
	if not data then
		return
	end
	local now = os.time()
	if now - data.Daily.Last < DAY then
		return
	end
	-- serie: si azzera se si salta piu' di un giorno
	local streak = if now - data.Daily.Last < DAY * 2 then data.Daily.Streak + 1 else 1
	if streak > #Rewards.Daily then
		streak = 1
	end
	local key, args = RewardService.Give(player, Rewards.Daily[streak])
	S.StateService.Set(player, { "Daily" }, { Last = now, Streak = streak })
	S.StateService.Notify(player, "RewardGot", { reward = key, rewardArgs = args }, "Gold")
end

local function claimPlaytime(player: Player, index: any)
	local entry = type(index) == "number" and Rewards.Playtime[index]
	if not entry or not sessionStart[player] then
		return
	end
	claimedPlaytime[player] = claimedPlaytime[player] or {}
	if claimedPlaytime[player][index] then
		return
	end
	if os.clock() - sessionStart[player] < entry.minutes * 60 - 2 then
		return
	end
	claimedPlaytime[player][index] = true
	player:SetAttribute("PlaytimeClaimed_" .. index, true)
	local key, args = RewardService.Give(player, entry.reward)
	S.StateService.Notify(player, "RewardGot", { reward = key, rewardArgs = args }, "Gold")
end

local function claimGroup(player: Player)
	local data = S.DataService.Get(player)
	if not data or data.GroupClaimed or GameConfig.GroupId == 0 then
		return
	end
	local ok, inGroup = pcall(player.IsInGroup, player, GameConfig.GroupId)
	if not ok or not inGroup then
		S.StateService.Notify(player, "GroupNotMember", nil, "Bad")
		return
	end
	S.StateService.Set(player, { "GroupClaimed" }, true)
	local key, args = RewardService.Give(player, { kind = "Coins", amount = GameConfig.GroupReward })
	S.StateService.Notify(player, "RewardGot", { reward = key, rewardArgs = args }, "Gold")
end

local function redeem(player: Player, code: any): (boolean, string)
	if type(code) ~= "string" or #code > 30 then
		return false, "CodeInvalid"
	end
	local data = S.DataService.Get(player)
	if not data then
		return false, "CodeInvalid"
	end
	code = string.upper((string.gsub(code, "%s", "")))
	local reward = CODES[code]
	if not reward then
		return false, "CodeInvalid"
	end
	if data.Codes[code] then
		return false, "CodeUsed"
	end
	data.Codes[code] = os.time()
	local key, args = RewardService.Give(player, reward)
	S.StateService.Notify(player, "RewardGot", { reward = key, rewardArgs = args }, "Gold")
	return true, "CodeOk"
end

-- Guadagni maturati mentre il giocatore era offline (quota ridotta, con un massimo)
local function offlineEarnings(player: Player, data)
	if data.LastOnline == 0 then
		return
	end
	local away = math.min(os.time() - data.LastOnline, GameConfig.OfflineMaxSeconds)
	if away < 60 then
		return
	end
	local rate = if S.MonetizationService.HasPass(player, "VIP")
		then GameConfig.OfflineRateVIP
		else GameConfig.OfflineRate
	local amount = math.floor(S.PetService.TotalIncome(player) * away * rate)
	if amount >= 1 then
		S.DataService.AddCoins(player, amount, "Offline")
		player:SetAttribute("OfflineEarned", amount)
		player:SetAttribute("OfflineSeconds", away)
	end
end

-- Bonus +10% per ogni amico nel server (massimo +40%)
local function refreshFriendBonus()
	local list = Players:GetPlayers()
	for _, p in list do
		local friends = 0
		for _, q in list do
			if q ~= p then
				local ok, isFriend = pcall(p.IsFriendsWith, p, q.UserId)
				if ok and isFriend then
					friends += 1
				end
			end
		end
		local bonus = math.min(GameConfig.FriendBonusMax, friends * GameConfig.FriendBonusEach)
		p:SetAttribute("FriendBonus", bonus)
		S.PetService.PublishIncome(p)
	end
end

function RewardService.Start()
	Net.Event("ClaimDaily").OnServerEvent:Connect(claimDaily)
	Net.Event("ClaimPlaytime").OnServerEvent:Connect(claimPlaytime)
	Net.Event("ClaimGroup").OnServerEvent:Connect(claimGroup)
	Net.Function("RedeemCode").OnServerInvoke = redeem
	S.DataService.Loaded:Connect(function(player, data)
		sessionStart[player] = os.clock()
		player:SetAttribute("SessionStart", workspace:GetServerTimeNow())
		-- il guadagno si calcola dai pet salvati (non serve attendere il lotto)
		task.defer(offlineEarnings, player, data)
		task.spawn(refreshFriendBonus)
	end)
	Players.PlayerRemoving:Connect(function(player)
		local data = S.DataService.Get(player)
		if data and sessionStart[player] then
			data.Stats.PlayTime += math.floor(os.clock() - sessionStart[player])
		end
		sessionStart[player] = nil
		claimedPlaytime[player] = nil
		task.defer(refreshFriendBonus)
	end)
end

return RewardService
