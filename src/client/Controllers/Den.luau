-- Tana dei Mostri lato client: la barriera del cancello diventa attraversabile (e verde) solo per
-- chi ha sbloccato la Tana, e per lui sparisce il pulsante per sbloccarla. Il server riporta fuori
-- chi passa senza averla sbloccata (DenService).

local CollectionService = game:GetService("CollectionService")

local Den = {}

local C
local unlocked = false

function Den.Init(controllers)
	C = controllers
end

local function apply(gate: Instance)
	if not gate:IsA("BasePart") then
		return
	end
	gate.CanCollide = not unlocked
	gate.Transparency = if unlocked then 0.7 else 0.25
	gate.Color = if unlocked then Color3.fromRGB(110, 255, 150) else Color3.fromRGB(255, 50, 70)
	local prompt = gate:FindFirstChildWhichIsA("ProximityPrompt")
	if prompt then
		prompt.Enabled = not unlocked
	end
end

function Den.Start()
	CollectionService:GetInstanceAddedSignal("DenGate"):Connect(apply)
	C.State.Watch("Unlocks", function(unlocks)
		unlocked = type(unlocks) == "table" and unlocks.Den == true
		for _, gate in CollectionService:GetTagged("DenGate") do
			apply(gate)
		end
	end)
	for _, gate in CollectionService:GetTagged("DenGate") do
		apply(gate)
	end
end

return Den
