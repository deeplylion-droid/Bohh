-- Pannello dei potenziamenti (monete) e delle trappole del lotto.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Combat = require(ReplicatedStorage.Shared.Config.Combat)
local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)
local Upgrades = require(ReplicatedStorage.Shared.Config.Upgrades)
local Kit = require(script.Parent.Parent.Kit)

local Theme = Kit.Theme
local New = Kit.New

local Panel = {}

local function effectText(T, id: string, level: number, C): string
	local passes = function(key)
		return game:GetService("Players").LocalPlayer:GetAttribute("Pass_" .. key) == true
	end
	if id == "Speed" then
		return T("UpgradeDesc_Speed", { value = tostring(Upgrades.WalkSpeed(level)) })
	elseif id == "Strength" then
		return T("UpgradeDesc_Strength", { value = Format.Percent(Upgrades.WeightReduction(level)) })
	elseif id == "Backpack" then
		return T("UpgradeDesc_Backpack", { value = tostring(Upgrades.CarryCapacity(level, passes("BigBackpack"))) })
	elseif id == "Incubators" then
		return T(
			"UpgradeDesc_Incubators",
			{ value = tostring(Upgrades.IncubatorCount(level, passes("ExtraIncubator"))) }
		)
	elseif id == "HatchSpeed" then
		return T("UpgradeDesc_HatchSpeed", { value = Format.Percent(1 - Upgrades.HatchFactor(level, false)) })
	elseif id == "Pedestals" then
		return T("UpgradeDesc_Pedestals", { value = tostring(Upgrades.PedestalCount(level)) })
	elseif id == "Barrier" then
		return T(
			"UpgradeDesc_Barrier",
			{ value = Format.Duration(Upgrades.BarrierDuration(level, passes("SuperBarrier"))) }
		)
	end
	local _ = C
	return ""
end

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("MenuUpgrades"), UDim2.fromOffset(760, 560), "Blue", parent)
	local scroll = New("ScrollingFrame", {
		BackgroundTransparency = 1,
		Size = UDim2.fromScale(1, 1),
		CanvasSize = UDim2.new(),
		AutomaticCanvasSize = Enum.AutomaticSize.Y,
		ScrollBarThickness = 8,
		ScrollBarImageColor3 = Theme.Muted,
		BorderSizePixel = 0,
		Parent = p.Body,
	}, {
		New("UIListLayout", { Padding = UDim.new(0, 10), SortOrder = Enum.SortOrder.LayoutOrder }),
		New("UIPadding", {
			PaddingTop = UDim.new(0, 18),
			PaddingLeft = UDim.new(0, 6),
			PaddingRight = UDim.new(0, 14),
			PaddingBottom = UDim.new(0, 10),
		}),
	})

	local rows = {}
	for i, id in Upgrades.Order do
		local def = Upgrades.List[id]
		local card = Kit.Card({ Size = UDim2.new(1, 0, 0, 84), LayoutOrder = i, Parent = scroll })
		Kit.Icon(def.icon, { Size = UDim2.fromOffset(56, 56), Position = UDim2.fromOffset(12, 14), Parent = card })
		local name = Kit.Text({
			Size = UDim2.new(0.5, 0, 0, 30),
			Position = UDim2.fromOffset(80, 10),
			TextXAlignment = Enum.TextXAlignment.Left,
			Parent = card,
		})
		local desc = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(0.55, 0, 0, 22),
			Position = UDim2.fromOffset(82, 46),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextColor3 = Theme.Muted,
			Stroke = false,
			Parent = card,
		})
		-- barra del livello
		local bar = New("Frame", {
			BackgroundColor3 = Color3.fromRGB(29, 22, 48),
			Size = UDim2.new(0.18, 0, 0, 16),
			Position = UDim2.new(0.62, -40, 0, 34),
			Parent = card,
		}, { Kit.Corner(UDim.new(1, 0)) })
		local fill = New(
			"Frame",
			{ BackgroundColor3 = Theme.Green, Size = UDim2.fromScale(0, 1), Parent = bar },
			{ Kit.Corner(UDim.new(1, 0)) }
		)
		local lvl = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(0.18, 0, 0, 20),
			Position = UDim2.new(0.62, -40, 0, 10),
			Stroke = 2,
			Parent = card,
		})
		local buy = Kit.Button({
			Color = "Green",
			Text = "",
			Size = UDim2.fromOffset(170, 62),
			Position = UDim2.new(1, -182, 0, 11),
			TextSize = 30,
			Parent = card,
			OnClick = function()
				Net.Event("BuyUpgrade"):FireServer(id)
			end,
		})
		rows[id] = { name = name, desc = desc, fill = fill, lvl = lvl, buy = buy }
	end

	-- trappole del lotto
	local trapHeader = Kit.Text({ Size = UDim2.new(1, 0, 0, 40), LayoutOrder = 100, Parent = scroll })
	local trapRows = {}
	for i, id in Combat.TrapOrder do
		local def = Combat.Traps[id]
		local card = Kit.Card({ Size = UDim2.new(1, 0, 0, 74), LayoutOrder = 100 + i, Parent = scroll })
		Kit.Icon("Trap", { Size = UDim2.fromOffset(48, 48), Position = UDim2.fromOffset(14, 13), Parent = card })
		local name = Kit.Text({
			Size = UDim2.new(0.45, 0, 0, 28),
			Position = UDim2.fromOffset(76, 8),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextColor3 = def.color,
			Parent = card,
		})
		local desc = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(0.5, 0, 0, 20),
			Position = UDim2.fromOffset(78, 42),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextColor3 = Theme.Muted,
			Stroke = false,
			Parent = card,
		})
		local slots = {}
		for s = 1, Combat.TrapSlots do
			local slot = tostring(s)
			local b = Kit.Button({
				Color = "Orange",
				Text = "",
				Size = UDim2.fromOffset(92, 50),
				Position = UDim2.new(1, -(104 * (Combat.TrapSlots - s + 1)), 0, 12),
				TextSize = 22,
				Parent = card,
				OnClick = function()
					Net.Event("BuyTrap"):FireServer(slot, id)
				end,
			})
			slots[slot] = b
		end
		trapRows[id] = { name = name, desc = desc, slots = slots, price = def.price }
	end

	local function refresh()
		local data = C.State.Data
		if not data then
			return
		end
		p.Title.Text = T("MenuUpgrades")
		for id, row in rows do
			local level = data.Upgrades[id] or 0
			local def = Upgrades.List[id]
			row.name.Text = T("Upgrade_" .. id)
			row.desc.Text = effectText(T, id, level, C)
			row.fill.Size = UDim2.fromScale(level / def.max, 1)
			row.lvl.Text = `{level}/{def.max}`
			local cost = Upgrades.Cost(id, level)
			if cost then
				row.buy.SetText(Format.Money(cost))
				row.buy.SetColor(if data.Coins >= cost then "Green" else "Grey")
			else
				row.buy.SetText(T("Max"))
				row.buy.SetColor("Purple")
			end
		end
		trapHeader.Text = T("MenuDefense") .. " · " .. T("Prompt_Traps")
		for id, row in trapRows do
			row.name.Text = T("Trap_" .. id)
			row.desc.Text = T("TrapDesc_" .. id)
			for slot, b in row.slots do
				local armed = data.Traps and data.Traps[slot]
				if armed == id then
					b.SetText("✔")
					b.SetColor("Green")
				elseif armed then
					b.SetText("—")
					b.SetColor("Grey")
				else
					b.SetText(Format.Money(row.price))
					b.SetColor(if data.Coins >= row.price then "Orange" else "Grey")
				end
			end
		end
	end
	for _, key in { "Coins", "Upgrades", "Traps" } do
		C.State.Watch(key, function()
			if p.Frame.Visible then
				refresh()
			end
		end)
	end
	C.Lang.Changed:Connect(refresh)
	return { Frame = p.Frame, Close = p.Close, OnOpen = refresh }
end

return Panel
