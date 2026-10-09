-- Valanga ciclica: avviso, poi un fronte di neve scende lungo la montagna. Chi non e' in un rifugio
-- (o in vetta/nel cratere) viene travolto: perde le uova (tornano ai nidi) e torna al lotto.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Avalanche = require(ReplicatedStorage.Shared.Avalanche)
local Events = require(ReplicatedStorage.Shared.Config.Events)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Net = require(ReplicatedStorage.Shared.Net)

local AvalancheService = {}

local S
local nextAt = 0

function AvalancheService.Init(services)
	S = services
end

local function interval(): number
	if S.EventService.IsActive("SuperAvalanche") then
		return Events.SuperAvalancheInterval
	end
	return GameConfig.AvalancheInterval
end

-- Anticipa la prossima valanga (admin, eventi)
function AvalancheService.TriggerSoon(seconds: number)
	local now = workspace:GetServerTimeNow()
	local at = now + math.max(seconds, Avalanche.Warning)
	if at < nextAt or nextAt < now then
		nextAt = at
		workspace:SetAttribute("AvalancheAt", nextAt)
	end
end

local function bury(player: Player)
	S.CarryService.DropAll(player, "Buried")
	Net.Event("Buried"):FireClient(player)
	S.CharacterService.ReturnToBase(player, "Buried")
end

local function runWave(startAt: number)
	local hit: { [Player]: boolean } = {}
	while true do
		local now = workspace:GetServerTimeNow()
		local front = Avalanche.FrontY(startAt, now)
		if not front then
			break
		end
		for _, player in Players:GetPlayers() do
			if not hit[player] then
				local hrp = S.CharacterService.Root(player)
				if hrp then
					local pos = hrp.Position
					local zone = MapLayout.ZoneAt(pos)
					if
						zone ~= "Summit"
						and pos.Z < 545
						and pos.Y <= front + 3
						and pos.Y >= front - Avalanche.Band
						and not MapLayout.IsSheltered(pos)
					then
						hit[player] = true
						bury(player)
					end
				end
			end
		end
		task.wait(0.1)
	end
end

function AvalancheService.Start()
	if S.Options.test then
		return
	end
	nextAt = workspace:GetServerTimeNow() + interval()
	workspace:SetAttribute("AvalancheAt", nextAt)
	task.spawn(function()
		while true do
			local now = workspace:GetServerTimeNow()
			if now >= nextAt then
				local startAt = nextAt
				runWave(startAt)
				nextAt = workspace:GetServerTimeNow() + interval()
				workspace:SetAttribute("AvalancheAt", nextAt)
			end
			task.wait(0.2)
		end
	end)
end

return AvalancheService
