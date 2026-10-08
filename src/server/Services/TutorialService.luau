-- Tutorial guidato per i nuovi giocatori. Passi (salvati in data.Tutorial):
-- 1 schiudi il primo uovo, 2 raccogli i soldi, 3 compra un potenziamento,
-- 4 scendi e raccogli un uovo, 5 riportalo al lotto, 6 completato.

local TutorialService = {}

local S

-- evento che fa avanzare ciascun passo
local STEP_EVENT = { [1] = "Hatched", [2] = "Collected", [3] = "Upgraded", [4] = "PickedUp", [5] = "Delivered" }
local STEP_NAME = { "Hatch", "Collect", "Upgrade", "Pickup", "Deliver", "Done" }
TutorialService.Done = 6

function TutorialService.Init(services)
	S = services
end

function TutorialService.Advance(player: Player, event: string)
	local data = S.DataService.Get(player)
	if not data or data.Tutorial >= TutorialService.Done then
		return
	end
	if STEP_EVENT[data.Tutorial] ~= event then
		return
	end
	local step = data.Tutorial + 1
	S.StateService.Set(player, { "Tutorial" }, step)
	S.AnalyticsService.Funnel(player, step, STEP_NAME[step])
	if step == TutorialService.Done then
		S.DataService.AddCoins(player, 250, "Tutorial")
		S.StateService.Notify(player, "TutDone", nil, "Gold")
	end
end

function TutorialService.Start()
	S.PlotService.Assigned:Connect(function(player)
		local data = S.DataService.Get(player)
		if data and data.Tutorial == 0 then
			S.StateService.Set(player, { "Tutorial" }, 1)
			S.AnalyticsService.Funnel(player, 1, "Hatch")
		end
	end)
end

return TutorialService
