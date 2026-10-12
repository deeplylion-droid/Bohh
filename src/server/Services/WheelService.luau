-- Ruota della fortuna nella piazza: un giro gratis ogni qualche ora, giri extra dalle missioni e dai
-- Robux. Il server estrae lo spicchio e lo comunica: la ruota della piazza gira per tutti (attributi
-- del modello, animata dai client) e il premio arriva quando si ferma.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)
local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)
local Weighted = require(ReplicatedStorage.Shared.Util.Weighted)

local WheelService = {}

local S
local rng = Random.new()
local pending: { [Player]: number } = {} -- spicchio vinto, consegnato a fine giro
local busyUntil: { [Player]: number } = {}

function WheelService.Init(services)
	S = services
end

function WheelService.AddSpins(player: Player, n: number)
	local data = S.DataService.Get(player)
	if not data or n <= 0 then
		return
	end
	S.StateService.Set(player, { "Wheel", "Spins" }, (data.Wheel.Spins or 0) + n)
end

-- Consegna il premio del giro in corso (a fine animazione, o subito se il giocatore esce)
local function finish(player: Player)
	local index = pending[player]
	pending[player] = nil
	local seg = index and Plaza.Wheel.Segments[index]
	if not seg then
		return
	end
	local key, args = S.RewardService.Give(player, seg)
	S.StateService.Notify(player, "WheelWon", { reward = key, rewardArgs = args }, "Gold")
	if seg.kind == "Primal" then
		S.StateService.Announce("AnnounceWheelJackpot", { name = player.DisplayName }, "Primal")
	end
end

local function spin(player: Player): (boolean, any)
	local data = S.DataService.Get(player)
	if not data or not data.Wheel then
		return false, "WheelBusy"
	end
	if (busyUntil[player] or 0) > os.clock() or pending[player] then
		return false, "WheelBusy"
	end
	local now = os.time()
	if now >= (data.Wheel.NextFree or 0) then
		S.StateService.Set(player, { "Wheel", "NextFree" }, now + Plaza.Wheel.FreeEvery)
	elseif (data.Wheel.Spins or 0) > 0 then
		S.StateService.Set(player, { "Wheel", "Spins" }, data.Wheel.Spins - 1)
	else
		return false, "WheelNoSpins"
	end
	local entries = {}
	for i, seg in Plaza.Wheel.Segments do
		table.insert(entries, { value = i, weight = seg.weight })
	end
	local index = Weighted.Pick(entries, rng)
	pending[player] = index
	busyUntil[player] = os.clock() + Plaza.Wheel.SpinTime
	-- la ruota della piazza gira per tutti verso lo spicchio estratto
	for _, wheel in CollectionService:GetTagged("FortuneWheel") do
		wheel:SetAttribute("SpinIndex", index)
		wheel:SetAttribute("SpinStart", workspace:GetServerTimeNow())
	end
	task.delay(Plaza.Wheel.SpinTime, finish, player)
	S.QuestService.Add(player, "Wheel", 1)
	S.AnalyticsService.Custom(player, "WheelSpin", 1, { segment = index })
	return true, index
end

function WheelService.Start()
	Net.Function("SpinWheel").OnServerInvoke = spin
	-- chi esce durante il giro riceve comunque il premio (prima del salvataggio finale)
	S.DataService.Releasing:Connect(function(player)
		finish(player)
	end)
	Players.PlayerRemoving:Connect(function(player)
		busyUntil[player] = nil
	end)
end

return WheelService
