-- Acquisto dei potenziamenti con le monete.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)
local Upgrades = require(ReplicatedStorage.Shared.Config.Upgrades)

local UpgradeService = {}

local S

function UpgradeService.Init(services)
	S = services
end

function UpgradeService.Buy(player: Player, id: any)
	if type(id) ~= "string" or not Upgrades.List[id] then
		return
	end
	local data = S.DataService.Get(player)
	if not data then
		return
	end
	local level = data.Upgrades[id] or 0
	local cost = Upgrades.Cost(id, level)
	if not cost then
		return -- livello massimo
	end
	if not S.DataService.SpendCoins(player, cost, "Upgrade_" .. id) then
		S.StateService.Notify(player, "NotEnoughCoins", nil, "Bad")
		return
	end
	S.StateService.Set(player, { "Upgrades", id }, level + 1)
	if id == "Speed" or id == "Strength" then
		S.CharacterService.UpdateSpeed(player)
	elseif id == "Incubators" then
		S.PlotService.RefreshLocks(player)
		S.HatchService.FillPending(player)
	elseif id == "Pedestals" then
		S.PlotService.RefreshLocks(player)
		S.PetService.Reflow(player)
	end
	S.StateService.Notify(player, "UpgradeBought", { upgrade = "Upgrade_" .. id }, "Good")
	S.StateService.Effect(player, "Upgrade", { id = id })
	S.TutorialService.Advance(player, "Upgraded")
	S.AnalyticsService.Custom(player, "Upgrade", level + 1, { id = id })
end

function UpgradeService.Start()
	Net.Event("BuyUpgrade").OnServerEvent:Connect(UpgradeService.Buy)
end

return UpgradeService
