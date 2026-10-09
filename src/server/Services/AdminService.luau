-- Pannello admin (solo proprietario e admin indicati in Config.Game): eventi dal vivo,
-- uova speciali, valanghe, annunci filtrati.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TextService = game:GetService("TextService")

local Events = require(ReplicatedStorage.Shared.Config.Events)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Net = require(ReplicatedStorage.Shared.Net)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Zones = require(ReplicatedStorage.Shared.Config.Zones)

local AdminService = {}

local S

function AdminService.Init(services)
	S = services
end

function AdminService.IsAdmin(player: Player): boolean
	if player.UserId == GameConfig.CreatorUserId or table.find(GameConfig.ExtraAdmins, player.UserId) then
		return true
	end
	-- in Studio (test locale) chiunque puo' provare il pannello
	return RunService:IsStudio()
end

local ACTIONS = {
	Event = function(_player, args)
		if type(args.id) == "string" and Events.List[args.id] then
			S.EventService.StartEvent(args.id)
		end
	end,
	StopEvent = function()
		S.EventService.StopEvent()
	end,
	SpawnEgg = function(_player, args)
		if
			type(args.rarity) == "string"
			and Rarities.List[args.rarity]
			and type(args.zone) == "string"
			and Zones.List[args.zone]
		then
			S.NestService.SpawnSpecial(args.zone, args.rarity)
		end
	end,
	Avalanche = function()
		S.AvalancheService.TriggerSoon(5)
	end,
	Coins = function(player, args)
		local n = tonumber(args.amount)
		if n and n > 0 and n <= 1e15 then
			S.DataService.AddCoins(player, n, "Admin")
		end
	end,
	Luck = function(player, args)
		local m = tonumber(args.minutes)
		if m and m > 0 and m <= 600 then
			S.MonetizationService.AddLuck(player, m)
		end
	end,
	Announce = function(player, args)
		if type(args.text) ~= "string" or #args.text == 0 or #args.text > 120 then
			return
		end
		local ok, result = pcall(function()
			local filtered = TextService:FilterStringAsync(args.text, player.UserId, Enum.TextFilterContext.PublicChat)
			return filtered:GetNonChatStringForBroadcastAsync()
		end)
		if ok and result then
			S.StateService.Announce("AnnounceAdmin", { text = result }, "Legendary")
		end
	end,
}

function AdminService.Start()
	Net.Event("AdminAction").OnServerEvent:Connect(function(player, action, args)
		if not AdminService.IsAdmin(player) or type(action) ~= "string" then
			return
		end
		local fn = ACTIONS[action]
		if fn then
			fn(player, if type(args) == "table" then args else {})
		end
	end)
end

return AdminService
