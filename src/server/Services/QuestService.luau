-- Missioni giornaliere e settimanali. Per ogni giocatore se ne estraggono alcune all'inizio del
-- giorno (mezzanotte UTC) e della settimana (lunedi'); avanzano con i contatori che gli altri
-- servizi segnalano con QuestService.Add(player, stat, n). Si riscattano dal pannello Missioni;
-- riscattarle tutte da' un premio in piu' (un giro della ruota / un uovo Primordiale).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)
local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)

local QuestService = {}

local S

local DAY = 86400
local WEEK = 7 * DAY
local MONDAY = 4 * DAY -- il 5 gennaio 1970 era lunedi'

local byId: { [string]: Plaza.Quest } = {}
for _, q in Plaza.Quests.Daily do
	byId[q.id] = q
end
for _, q in Plaza.Quests.Weekly do
	byId[q.id] = q
end

local refresh: (Player, any) -> boolean

function QuestService.Init(services)
	S = services
	-- le missioni del giorno sono gia' pronte nell'istantanea che riceve il client
	table.insert(S.DataService.PreLoad, function(player, data)
		refresh(player, data)
	end)
end

-- per i test: estrae le missioni di un giocatore (anche finto) nei suoi dati
function QuestService.Refresh(player: any, data): boolean
	return refresh(player, data)
end

function QuestService.DayIndex(t: number): number
	return t // DAY
end

function QuestService.WeekIndex(t: number): number
	return (t - MONDAY) // WEEK
end

-- count missioni diverse dall'elenco, sempre le stesse per lo stesso giocatore e periodo
local function pick(pool: { Plaza.Quest }, count: number, seed: number)
	local rng = Random.new(seed)
	local ids = {}
	for _, q in pool do
		table.insert(ids, q.id)
	end
	for i = #ids, 2, -1 do
		local j = rng:NextInteger(1, i)
		ids[i], ids[j] = ids[j], ids[i]
	end
	local out = {}
	for i = 1, math.min(count, #ids) do
		table.insert(out, { Id = ids[i], P = 0, C = false })
	end
	return out
end

-- Estrae le nuove missioni quando cambia il giorno o la settimana (true se e' cambiato qualcosa)
refresh = function(player: Player, data): boolean
	local q = data.Quests
	local now = os.time()
	local day, week = QuestService.DayIndex(now), QuestService.WeekIndex(now)
	local changed = false
	if q.Day ~= day then
		q.Day = day
		q.Daily = pick(Plaza.Quests.Daily, Plaza.Quests.DailyCount, player.UserId * 7 + day * 131)
		q.DailyBonus = false
		changed = true
	end
	if q.Week ~= week then
		q.Week = week
		q.Weekly = pick(Plaza.Quests.Weekly, Plaza.Quests.WeeklyCount, player.UserId * 11 + week * 977)
		q.WeeklyBonus = false
		changed = true
	end
	if changed then
		S.StateService.Push(player, { "Quests" })
	end
	return changed
end

-- Fa avanzare le missioni che contano questo contatore
function QuestService.Add(player: Player, stat: string, n: number?)
	local data = S.DataService.Get(player)
	if not data or not data.Quests then
		return
	end
	refresh(player, data)
	local changed = false
	for _, list in { data.Quests.Daily, data.Quests.Weekly } do
		for _, e in list do
			local def = byId[e.Id]
			if def and def.stat == stat and e.P < def.target then
				e.P = math.min(def.target, e.P + (n or 1))
				changed = true
				if e.P >= def.target then
					S.StateService.Notify(
						player,
						"QuestDone",
						{ reward = "Quest_" .. def.stat, rewardArgs = { n = def.target } },
						"Gold"
					)
				end
			end
		end
	end
	if changed then
		S.StateService.Push(player, { "Quests" })
	end
end

local function give(player: Player, reward)
	local key, args = S.RewardService.Give(player, reward)
	S.StateService.Notify(player, "RewardGot", { reward = key, rewardArgs = args }, "Gold")
end

local function claim(player: Player, kind: any, index: any)
	local data = S.DataService.Get(player)
	if not data or not data.Quests then
		return
	end
	refresh(player, data)
	local q = data.Quests
	if kind == "Daily" or kind == "Weekly" then
		local e = type(index) == "number" and q[kind][index]
		local def = e and byId[e.Id]
		if not e or not def or e.C or e.P < def.target then
			return
		end
		e.C = true
		S.StateService.Push(player, { "Quests" })
		give(player, def.reward)
		S.AnalyticsService.Custom(player, "QuestClaim", 1, { quest = def.id })
	elseif kind == "DailyBonus" or kind == "WeeklyBonus" then
		local list = if kind == "DailyBonus" then q.Daily else q.Weekly
		if q[kind] or #list == 0 then
			return
		end
		for _, e in list do
			if not e.C then
				return
			end
		end
		q[kind] = true
		S.StateService.Push(player, { "Quests" })
		give(player, if kind == "DailyBonus" then Plaza.Quests.DailyBonus else Plaza.Quests.WeeklyBonus)
		S.AnalyticsService.Custom(player, "QuestBonus", 1, { kind = kind })
	end
end

function QuestService.Start()
	Net.Event("ClaimQuest").OnServerEvent:Connect(claim)
	-- a mezzanotte chi e' in gioco riceve le nuove missioni senza dover rientrare
	task.spawn(function()
		while true do
			task.wait(20)
			for _, player in Players:GetPlayers() do
				local data = S.DataService.Get(player)
				if data and data.Quests then
					refresh(player, data)
				end
			end
		end
	end)
end

return QuestService
