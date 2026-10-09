-- Album dei pet: 8 righe (rarita') x 4 pet, anteprime 3D, sagome per quelli da scoprire,
-- premio e bonus permanente quando una riga e' completa.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Format = require(ReplicatedStorage.Shared.Util.Format)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Net = require(ReplicatedStorage.Shared.Net)
local Pets = require(ReplicatedStorage.Shared.Config.Pets)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Rewards = require(ReplicatedStorage.Shared.Config.Rewards)
local Visuals = require(ReplicatedStorage.Shared.Visuals)
local Kit = require(script.Parent.Parent.Kit)

local Theme = Kit.Theme
local New = Kit.New

local Panel = {}

-- Anteprima 3D di un pet in un ViewportFrame
local function preview(parent: GuiObject, petId: string, discovered: boolean)
	local vp = New("ViewportFrame", {
		BackgroundTransparency = 1,
		Size = UDim2.fromScale(1, 0.72),
		Ambient = Color3.fromRGB(200, 200, 210),
		LightColor = Color3.fromRGB(255, 250, 240),
		LightDirection = Vector3.new(-0.5, -1, -0.6),
		Parent = parent,
	})
	local model = Visuals.MakePet(petId, "None", "Normal")
	for _, d in model:GetDescendants() do
		if d:IsA("ParticleEmitter") or d:IsA("PointLight") then
			d:Destroy()
		elseif d:IsA("BasePart") and not discovered then
			d.Color = Color3.fromRGB(20, 14, 36)
			d.Material = Enum.Material.SmoothPlastic
			d.Reflectance = 0
		end
	end
	model:PivotTo(CFrame.new())
	model.Parent = vp
	local _, size = model:GetBoundingBox()
	local cam = New("Camera", { FieldOfView = 30, Parent = vp })
	local dist = math.max(size.X, size.Y, size.Z) * 2.3
	local center = Vector3.new(0, size.Y / 2, 0)
	cam.CFrame = CFrame.lookAt(center + Vector3.new(dist * 0.45, dist * 0.18, -dist), center)
	vp.CurrentCamera = cam
	return vp
end

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("IndexTitle"), UDim2.fromOffset(880, 600), "Purple", parent)
	local progress = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, 0, 0, 26),
		Position = UDim2.fromOffset(0, 18),
		Stroke = 2,
		Parent = p.Body,
	})
	local scroll = New("ScrollingFrame", {
		BackgroundTransparency = 1,
		Size = UDim2.new(1, 0, 1, -54),
		Position = UDim2.fromOffset(0, 54),
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		ScrollBarThickness = 8,
		ScrollBarImageColor3 = Theme.Muted,
		BorderSizePixel = 0,
		Parent = p.Body,
	}, {
		New("UIListLayout", { Padding = UDim.new(0, 12), SortOrder = Enum.SortOrder.LayoutOrder }),
		New(
			"UIPadding",
			{ PaddingRight = UDim.new(0, 14), PaddingBottom = UDim.new(0, 10), PaddingLeft = UDim.new(0, 4) }
		),
	})
	local built = false
	local rows = {}

	local function build()
		built = true
		for i, rarity in Rarities.Order do
			local r = Rarities.List[rarity]
			local row = New("Frame", {
				BackgroundColor3 = Color3.new(1, 1, 1),
				Size = UDim2.new(1, 0, 0, 196),
				LayoutOrder = i,
				Parent = scroll,
			}, {
				Kit.Corner(UDim.new(0, 20)),
				Kit.Stroke(4),
				Kit.Gradient(r.color:Lerp(Theme.Card, 0.6), Theme.Card),
			})
			local title = Kit.Text({
				Size = UDim2.new(0.4, 0, 0, 32),
				Position = UDim2.fromOffset(14, 8),
				TextXAlignment = Enum.TextXAlignment.Left,
				TextColor3 = r.color,
				Parent = row,
			})
			if Rarities.Gradients[rarity] then
				New("UIGradient", { Color = Rarities.Gradients[rarity], Parent = title })
				title.TextColor3 = Color3.new(1, 1, 1)
			end
			local reward = Kit.Text({
				Font = Theme.BodyFont,
				Size = UDim2.new(0.42, 0, 0, 22),
				Position = UDim2.new(0.4, 0, 0, 12),
				TextXAlignment = Enum.TextXAlignment.Right,
				TextColor3 = Theme.Muted,
				Stroke = false,
				Parent = row,
			})
			local claim = Kit.Button({
				Text = "",
				Color = "Yellow",
				Size = UDim2.fromOffset(130, 40),
				Position = UDim2.new(1, -142, 0, 6),
				TextSize = 22,
				Parent = row,
				OnClick = function()
					Net.Event("ClaimIndexRow"):FireServer(rarity)
				end,
			})
			local slots = {}
			for k, pet in Pets.ByRarity[rarity] do
				local slot = New("Frame", {
					BackgroundColor3 = Color3.fromRGB(29, 22, 48),
					BackgroundTransparency = 0.35,
					Size = UDim2.new(0.235, 0, 0, 138),
					Position = UDim2.new((k - 1) * 0.25 + 0.0075, 0, 0, 50),
					Parent = row,
				}, { Kit.Corner(UDim.new(0, 16)) })
				local name = Kit.Text({
					Font = Theme.BodyFont,
					Size = UDim2.new(0.92, 0, 0, 22),
					Position = UDim2.new(0.04, 0, 1, -30),
					Stroke = 2,
					Parent = slot,
				})
				local dots = Kit.Text({
					Font = Theme.BodyFont,
					Size = UDim2.new(0.9, 0, 0, 16),
					Position = UDim2.new(0.05, 0, 0, 4),
					TextXAlignment = Enum.TextXAlignment.Right,
					Stroke = false,
					Parent = slot,
				})
				slots[pet.id] = { frame = slot, name = name, dots = dots, vp = nil, discovered = nil }
			end
			rows[rarity] = { title = title, reward = reward, claim = claim, slots = slots }
		end
	end

	local MUT_DOTS = { Gold = "🟡", Diamond = "🔷", Rainbow = "🌈", Cosmic = "🟣" }

	local function refresh()
		if not built then
			build()
		end
		local data = C.State.Data
		local index = (data and data.Index) or {}
		local claimed = (data and data.IndexClaimed) or {}
		p.Title.Text = T("IndexTitle")
		local found = 0
		for rarity, row in rows do
			row.title.Text = T("Rarity_" .. rarity)
			local complete = true
			for petId, slot in row.slots do
				local entry = index[petId]
				local discovered = entry ~= nil
				if discovered then
					found += 1
				else
					complete = false
				end
				if slot.discovered ~= discovered then
					slot.discovered = discovered
					if slot.vp then
						slot.vp:Destroy()
					end
					slot.vp = preview(slot.frame, petId, discovered)
				end
				slot.name.Text = if discovered then T("Pet_" .. petId) else T("Undiscovered")
				local dots = ""
				if entry then
					for _, m in { "Gold", "Diamond", "Rainbow", "Cosmic" } do
						if entry[m] then
							dots ..= MUT_DOTS[m]
						end
					end
				end
				slot.dots.Text = dots
			end
			local bonus = math.floor(GameConfig.IndexRowBonus * 100) .. "%"
			row.reward.Text = T("IndexRowReward", { bonus = bonus, coins = Format.Money(Rewards.IndexRow[rarity]) })
			if claimed[rarity] then
				row.claim.SetText(T("Claimed"))
				row.claim.SetColor("Purple")
			elseif complete then
				row.claim.SetText(T("Claim"))
				row.claim.SetColor("Yellow")
			else
				row.claim.SetText(T("Locked"))
				row.claim.SetColor("Grey")
			end
		end
		progress.Text = T("IndexProgress", { n = found, total = #Pets.List })
	end
	for _, key in { "Index", "IndexClaimed" } do
		C.State.Watch(key, function()
			if p.Frame.Visible then
				refresh()
			end
		end)
	end
	C.Lang.Changed:Connect(function()
		if built then
			refresh()
		end
	end)
	return { Frame = p.Frame, Close = p.Close, OnOpen = refresh }
end

return Panel
