--!strict
-- Tempi della valanga condivisi da server e client.
-- workspace:GetAttribute("AvalancheAt") = istante (tempo del server) in cui parte la prossima valanga.
-- Il fronte scende di quota in modo lineare per Duration secondi: chi non e' al riparo viene travolto.

local GameConfig = require(script.Parent.Config.Game)

local Avalanche = {}

Avalanche.TopY = 324
Avalanche.BottomY = 112
Avalanche.Duration = GameConfig.AvalancheDuration
Avalanche.Warning = GameConfig.AvalancheWarning
Avalanche.Band = 14 -- spessore (in quota) della massa di neve

-- Quota del fronte al tempo now (nil se la valanga non e' in corso)
function Avalanche.FrontY(startAt: number?, now: number): number?
	if not startAt or now < startAt then
		return nil
	end
	local f = (now - startAt) / Avalanche.Duration
	if f > 1 then
		return nil
	end
	-- parte lenta e accelera un po' (piu' drammatica)
	local e = f * f * 0.35 + f * 0.65
	return Avalanche.TopY - (Avalanche.TopY - Avalanche.BottomY) * e
end

return Avalanche
