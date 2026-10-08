-- Chi trasporta qualcosa alza le braccia sopra la testa; i ladri hanno la scritta "LADRO!"
-- e un contorno rosso visibile a tutti.

local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local Carry = {}

local C
local highlights: { [Player]: Highlight } = {}
local tags: { [Player]: BillboardGui } = {}

function Carry.Init(controllers)
	C = controllers
end

-- Posa a braccia alzate (R15 e R6): sovrascrive la trasformazione delle spalle dopo l'animazione
local function armsUp(char: Model)
	local r15 = char:FindFirstChild("RightUpperArm")
	if r15 then
		local rs = (char:FindFirstChild("RightUpperArm") :: BasePart):FindFirstChild("RightShoulder") :: Motor6D?
		local ls = char:FindFirstChild("LeftUpperArm") and (char:FindFirstChild("LeftUpperArm") :: BasePart):FindFirstChild("LeftShoulder") :: Motor6D?
		if rs then
			rs.Transform = CFrame.Angles(math.rad(170), 0, math.rad(-12))
		end
		if ls then
			ls.Transform = CFrame.Angles(math.rad(170), 0, math.rad(12))
		end
		return
	end
	local torso = char:FindFirstChild("Torso")
	if torso then
		local rs = torso:FindFirstChild("Right Shoulder") :: Motor6D?
		local ls = torso:FindFirstChild("Left Shoulder") :: Motor6D?
		if rs then
			rs.Transform = CFrame.Angles(0, 0, math.rad(170))
		end
		if ls then
			ls.Transform = CFrame.Angles(0, 0, math.rad(-170))
		end
	end
end

local function thiefVisuals(p: Player)
	local isThief = p:GetAttribute("Thief") == true
	local char = p.Character
	if isThief and char then
		if not highlights[p] then
			local h = Instance.new("Highlight")
			h.FillColor = Color3.fromRGB(255, 60, 60)
			h.FillTransparency = 0.75
			h.OutlineColor = Color3.fromRGB(255, 40, 40)
			h.OutlineTransparency = 0
			h.DepthMode = Enum.HighlightDepthMode.AlwaysOnTop
			h.Adornee = char
			h.Parent = char
			highlights[p] = h
		end
		if not tags[p] then
			local Kit = C.UI.Kit
			local gui = Kit.New("BillboardGui", {
				Name = "ThiefTag",
				Size = UDim2.fromOffset(180, 54),
				StudsOffset = Vector3.new(0, 7.5, 0),
				AlwaysOnTop = true,
				MaxDistance = 300,
				LightInfluence = 0,
				Adornee = char:FindFirstChild("Head"),
				Parent = char,
			})
			local label = Kit.Text({ Text = C.Lang.T("Thief"), TextColor3 = Color3.fromRGB(255, 70, 70), Size = UDim2.fromScale(1, 1), Parent = gui })
			Kit.Pop(label)
			tags[p] = gui
		end
	else
		if highlights[p] then
			highlights[p]:Destroy()
			highlights[p] = nil
		end
		if tags[p] then
			tags[p]:Destroy()
			tags[p] = nil
		end
	end
end

local function setup(p: Player)
	p:GetAttributeChangedSignal("Thief"):Connect(function()
		thiefVisuals(p)
	end)
	p.CharacterAdded:Connect(function()
		highlights[p] = nil
		tags[p] = nil
		task.wait(0.5)
		thiefVisuals(p)
	end)
end

function Carry.Start()
	for _, p in Players:GetPlayers() do
		setup(p)
	end
	Players.PlayerAdded:Connect(setup)
	Players.PlayerRemoving:Connect(function(p)
		highlights[p] = nil
		tags[p] = nil
	end)
	-- dopo l'animatore: braccia alzate per chi trasporta
	RunService.Stepped:Connect(function()
		for _, p in Players:GetPlayers() do
			if (p:GetAttribute("Carrying") or 0) > 0 and not p:GetAttribute("Ragdolled") then
				local char = p.Character
				if char then
					armsUp(char)
				end
			end
		end
	end)
end

return Carry
