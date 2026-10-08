-- Statistiche per Creator Hub (Analytics): economia, imbuto del tutorial, eventi personalizzati.
-- Tutte le chiamate sono protette: un errore di analytics non deve mai bloccare il gioco.

local AnalyticsService = game:GetService("AnalyticsService")

local Analytics = {}

function Analytics.Init(_S) end

function Analytics.Economy(player: Player, flow: "Source" | "Sink", amount: number, balance: number, reason: string)
	pcall(function()
		local flowType = if flow == "Source" then Enum.AnalyticsEconomyFlowType.Source else Enum.AnalyticsEconomyFlowType.Sink
		local txType = if reason == "Purchase" then Enum.AnalyticsEconomyTransactionType.IAP.Name else Enum.AnalyticsEconomyTransactionType.Gameplay.Name
		AnalyticsService:LogEconomyEvent(player, flowType, "Coins", math.floor(amount), math.floor(balance), txType, reason)
	end)
end

function Analytics.Funnel(player: Player, step: number, name: string)
	pcall(function()
		AnalyticsService:LogOnboardingFunnelStepEvent(player, step, name)
	end)
end

function Analytics.Custom(player: Player, name: string, value: number?, fields: { [string]: string }?)
	pcall(function()
		local custom = nil
		if fields then
			custom = {}
			local i = 1
			for k, v in fields do
				if i > 3 then
					break
				end
				custom[Enum.AnalyticsCustomFieldKeys[`CustomField0{i}`].Name] = `{k}:{v}`
				i += 1
			end
		end
		AnalyticsService:LogCustomEvent(player, name, value or 1, custom)
	end)
end

return Analytics
