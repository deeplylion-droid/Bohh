-- Tana dei Mostri: il cancello nel cratere si apre per sempre pagando con le monete (il client rende
-- la barriera attraversabile solo a chi l'ha sbloccata). Chi si trova oltre il cancello senza averla
-- sbloccata viene riportato davanti all'ingresso.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)

local DenService = {}

local S

function DenService.Init(services)
	S = services
end

function DenService.IsUnlocked(player: Player): boolean
	local data = S.DataService.Get(player)
	return data ~= nil and data.Unlocks ~= nil and data.Unlocks.Den == true
end

function DenService.Unlock(player: Player)
	if DenService.IsUnlocked(player) or not S.DataService.Get(player) then
		return
	end
	if not S.DataService.SpendCoins(player, MapLayout.Den.UnlockPrice, "DenUnlock") then
		S.StateService.Notify(player, "NotEnoughCoins", nil, "Bad")
		return
	end
	S.StateService.Set(player, { "Unlocks", "Den" }, true)
	S.StateService.Notify(player, "DenUnlocked", nil, "Gold")
	S.StateService.Effect(player, "Purchase", {})
	S.AnalyticsService.Custom(player, "DenUnlock", 1)
end

-- Davanti al cancello, dalla parte del cratere, rivolti verso l'ingresso
function DenService.OutsideCFrame(): CFrame
	local gate = MapLayout.DenGateFrame()
	local spot = gate * CFrame.new(0, 3, -10)
	return CFrame.lookAt(spot.Position, gate.Position + Vector3.new(0, 3, 0))
end

local function enforce()
	for _, player in Players:GetPlayers() do
		local hrp = S.CharacterService.Root(player)
		if hrp and MapLayout.InDen(hrp.Position) and not DenService.IsUnlocked(player) then
			local char = player.Character
			if char then
				char:PivotTo(DenService.OutsideCFrame())
			end
			S.StateService.Notify(player, "DenLocked", { price = MapLayout.Den.UnlockPrice }, "Bad")
		end
	end
end

function DenService.Start()
	S.MapService.WaitReady()
	for _, gate in CollectionService:GetTagged("DenGate") do
		local prompt = gate:FindFirstChildWhichIsA("ProximityPrompt")
		if prompt then
			prompt.Triggered:Connect(DenService.Unlock)
		end
	end
	task.spawn(function()
		while true do
			task.wait(0.5)
			enforce()
		end
	end)
end

return DenService
