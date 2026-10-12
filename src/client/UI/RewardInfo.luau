-- Come mostrare i premi della piazza (ruota e missioni): icona, testo e colore. Gli importi in
-- monete sono quelli che riceverebbe il giocatore ora (minuti del suo guadagno, con il minimo),
-- le uova dipendono dalla zona piu' profonda da cui ha consegnato.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Format = require(ReplicatedStorage.Shared.Util.Format)
local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Rewards = require(ReplicatedStorage.Shared.Config.Rewards)

local player = Players.LocalPlayer

local RewardInfo = {}

function RewardInfo.BestZone(data): string
	local zone = data and data.Stats and data.Stats.BestZone
	return if zone and Plaza.EggTiers[zone] then zone else "Meadow"
end

function RewardInfo.EggRarity(reward, data): string
	if reward.kind == "Primal" then
		return "Primal"
	end
	if reward.rarity then
		return reward.rarity
	end
	local tiers = Plaza.EggTiers[RewardInfo.BestZone(data)]
	return tiers[math.clamp(reward.tier or 1, 1, #tiers)]
end

function RewardInfo.Coins(reward): number
	local income = player:GetAttribute("Income") or 0
	local minutes = reward.minutes or Rewards.CoinScaleMinutes
	return math.max(reward.min or reward.amount or 0, math.floor(income * 60 * minutes))
end

function RewardInfo.Icon(reward): string
	if reward.kind == "Coins" then
		local m = reward.minutes or 0
		return if m >= 45 then "CoinsLarge" elseif m >= 15 then "CoinsMedium" else "CoinsSmall"
	elseif reward.kind == "Luck" then
		return "Luck"
	elseif reward.kind == "Spin" then
		return "Wheel"
	end
	return "Egg"
end

function RewardInfo.Text(T, reward, data): string
	if reward.kind == "Coins" then
		return Format.Money(RewardInfo.Coins(reward))
	elseif reward.kind == "Luck" then
		return `x2 {reward.amount}m`
	elseif reward.kind == "Spin" then
		return RewardInfo.Spins(T, reward.amount or 1)
	end
	return T("Rarity_" .. RewardInfo.EggRarity(reward, data))
end

function RewardInfo.Spins(T, n: number): string
	return if n == 1 then T("SpinsCount1") else T("SpinsCount", { n = n })
end

function RewardInfo.Color(reward, data): Color3
	if reward.kind == "Egg" or reward.kind == "Primal" then
		local r = Rarities.List[RewardInfo.EggRarity(reward, data)]
		if r then
			return r.color
		end
	elseif reward.kind == "Coins" then
		return Color3.fromRGB(255, 225, 77)
	elseif reward.kind == "Luck" then
		return Color3.fromRGB(157, 255, 107)
	end
	return Color3.new(1, 1, 1)
end

return RewardInfo
