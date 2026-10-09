-- Schiaffo: suono quando qualcuno colpisce e pulsante per gli schermi touch. L'animazione del colpo
-- la fa partire il server (StringValue "toolanim" nella mazza, vedi CombatService.Swing).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)

local Combat = {}

local C
local player = Players.LocalPlayer

function Combat.Init(controllers)
	C = controllers
end

-- Pulsante touch: impugna la mazza (se non ce l'ha in mano) e colpisce
function Combat.SlapButton()
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if not hum then
		return
	end
	if (player:GetAttribute("Carrying") or 0) > 0 then
		return
	end
	local tool = char:FindFirstChild("Bat")
	if not tool then
		local backpack = player:FindFirstChildOfClass("Backpack")
		tool = backpack and backpack:FindFirstChild("Bat")
		if tool then
			hum:EquipTool(tool :: Tool)
		end
	end
	if tool then
		(tool :: Tool):Activate()
	end
	Net.Event("Swing"):FireServer()
end

function Combat.Start()
	-- lo swing di qualsiasi giocatore (inviato dal server come effetto)
	C.Effects.On("Swing", function(params)
		local p = Players:GetPlayerByUserId(params.userId)
		if p and p.Character then
			C.Audio.Play("Whoosh", (p.Character:GetPivot()).Position, 0.6)
		end
	end)
end

return Combat
