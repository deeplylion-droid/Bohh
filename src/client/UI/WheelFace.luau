-- Spicchi della ruota della fortuna: icona e testo del premio sopra l'immagine della ruota (nel
-- pannello e sulla ruota della piazza) e il calcolo dell'angolo d'arrivo dei giri.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Kit = require(script.Parent.Kit)
local RewardInfo = require(script.Parent.RewardInfo)

local New = Kit.New

local WheelFace = {}

WheelFace.Count = #Plaza.Wheel.Segments
WheelFace.Step = 360 / WheelFace.Count

-- Aggiunge a face (immagine quadrata della ruota) un braccio per spicchio con icona e testo.
-- Ritorna refresh() per aggiornare i testi (lingua, guadagno, zona migliore) e la lista dei bracci.
function WheelFace.Build(face: GuiObject, C, z: number?): (() -> (), { Frame })
	local T = C.Lang.T
	local zi = z or face.ZIndex
	local arms, labels, icons = {}, {}, {}
	for i, seg in Plaza.Wheel.Segments do
		local arm = New("Frame", {
			Name = "Arm" .. i,
			BackgroundTransparency = 1,
			Size = UDim2.fromScale(1, 1),
			Rotation = (i - 1) * WheelFace.Step,
			ZIndex = zi + 1,
			Parent = face,
		})
		icons[i] = Kit.Icon(RewardInfo.Icon(seg), {
			Size = UDim2.fromScale(0.135, 0.135),
			Position = UDim2.fromScale(0.5, 0.165),
			AnchorPoint = Vector2.new(0.5, 0.5),
			ZIndex = zi + 2,
			Parent = arm,
		})
		labels[i] = Kit.Text({
			Size = UDim2.fromScale(0.2, 0.062),
			Position = UDim2.fromScale(0.5, 0.272),
			AnchorPoint = Vector2.new(0.5, 0.5),
			ZIndex = zi + 2,
			Parent = arm,
		})
		arms[i] = arm
	end
	local function refresh()
		local data = C.State.Data
		for i, seg in Plaza.Wheel.Segments do
			labels[i].Text = if seg.kind == "Primal" then T("Jackpot") else RewardInfo.Text(T, seg, data)
			labels[i].TextColor3 = if seg.kind == "Coins" or seg.kind == "Luck"
				then Color3.new(1, 1, 1)
				else RewardInfo.Color(seg, data):Lerp(Color3.new(1, 1, 1), 0.55)
			local icon = icons[i]
			if icon:IsA("ImageLabel") and (seg.kind == "Egg" or seg.kind == "Primal") then
				local r = Rarities.List[RewardInfo.EggRarity(seg, data)]
				icon.ImageColor3 = if r then r.color:Lerp(Color3.new(1, 1, 1), 0.25) else Color3.new(1, 1, 1)
			end
		end
	end
	refresh()
	return refresh, arms
end

-- Angolo finale (gradi, senso orario) per fermarsi sullo spicchio index partendo da current,
-- dopo turns giri completi; jitter (-0.5..0.5) sposta l'arrivo dentro lo spicchio.
function WheelFace.Target(current: number, index: number, turns: number, jitter: number): number
	local want = (-(index - 1) * WheelFace.Step + jitter * WheelFace.Step * 0.7) % 360
	local delta = (want - current % 360) % 360
	return current + delta + 360 * turns
end

-- Andamento del giro: parte veloce e rallenta fino a fermarsi (0..1 -> 0..1)
function WheelFace.Ease(u: number): number
	u = math.clamp(u, 0, 1)
	return 1 - (1 - u) ^ 4
end

return WheelFace
