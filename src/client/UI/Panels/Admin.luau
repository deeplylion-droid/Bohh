-- Pannello admin (visibile solo agli admin; il server ricontrolla sempre i permessi).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Events = require(ReplicatedStorage.Shared.Config.Events)
local Net = require(ReplicatedStorage.Shared.Net)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Zones = require(ReplicatedStorage.Shared.Config.Zones)
local Kit = require(script.Parent.Parent.Kit)

local Theme = Kit.Theme
local New = Kit.New

local Panel = {}

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel("ADMIN", UDim2.fromOffset(820, 560), "Red", parent)
	local function send(action: string, args: { [string]: any }?)
		Net.Event("AdminAction"):FireServer(action, args or {})
	end
	local grid = New("Frame", {
		BackgroundTransparency = 1,
		Size = UDim2.new(1, 0, 0, 200),
		Position = UDim2.fromOffset(0, 20),
		Parent = p.Body,
	}, {
		New("UIGridLayout", {
			CellSize = UDim2.fromOffset(240, 56),
			CellPadding = UDim2.fromOffset(12, 12),
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
		}),
	})
	for _, id in Events.Order do
		Kit.Button({
			Text = T("Event_" .. id),
			Color = "Purple",
			Size = UDim2.fromOffset(240, 56),
			TextSize = 20,
			Parent = grid,
			OnClick = function()
				send("Event", { id = id })
			end,
		})
	end
	Kit.Button({
		Text = "STOP EVENT",
		Color = "Grey",
		Size = UDim2.fromOffset(240, 56),
		TextSize = 20,
		Parent = grid,
		OnClick = function()
			send("StopEvent")
		end,
	})
	Kit.Button({
		Text = T("AvalancheNow"),
		Color = "Blue",
		Size = UDim2.fromOffset(240, 56),
		TextSize = 20,
		Parent = grid,
		OnClick = function()
			send("Avalanche")
		end,
	})
	Kit.Button({
		Text = "+$1M",
		Color = "Yellow",
		Size = UDim2.fromOffset(240, 56),
		TextSize = 22,
		Parent = grid,
		OnClick = function()
			send("Coins", { amount = 1e6 })
		end,
	})
	Kit.Button({
		Text = T("Luck") .. " 30m",
		Color = "Green",
		Size = UDim2.fromOffset(240, 56),
		TextSize = 20,
		Parent = grid,
		OnClick = function()
			send("Luck", { minutes = 30 })
		end,
	})
	Kit.Button({
		Text = "HATCH NOW ⏩",
		Color = "Pink",
		Size = UDim2.fromOffset(240, 56),
		TextSize = 20,
		Parent = grid,
		OnClick = function()
			send("HatchNow")
		end,
	})

	-- uovo speciale: rarita' + zona
	local rarityIndex, zoneIndex = 5, 5
	local eggRow = Kit.Card({ Size = UDim2.new(1, -10, 0, 76), Position = UDim2.new(0, 5, 0, 240), Parent = p.Body })
	local rarityBtn = Kit.Button({
		Text = "",
		Color = "Orange",
		Size = UDim2.fromOffset(180, 54),
		Position = UDim2.fromOffset(12, 11),
		TextSize = 20,
		Parent = eggRow,
	})
	local zoneBtn = Kit.Button({
		Text = "",
		Color = "Blue",
		Size = UDim2.fromOffset(180, 54),
		Position = UDim2.fromOffset(200, 11),
		TextSize = 20,
		Parent = eggRow,
	})
	-- l'uovo nella zona scelta (da andare a prendere) o direttamente in un'incubatrice del lotto
	Kit.Button({
		Text = "SPAWN 🥚",
		Color = "Green",
		Size = UDim2.fromOffset(180, 54),
		Position = UDim2.fromOffset(388, 11),
		TextSize = 22,
		Parent = eggRow,
		OnClick = function()
			send("SpawnEgg", { rarity = Rarities.Order[rarityIndex], zone = Zones.Order[zoneIndex] })
		end,
	})
	Kit.Button({
		Text = "TO BASE 🏠",
		Color = "Purple",
		Size = UDim2.fromOffset(180, 54),
		Position = UDim2.fromOffset(576, 11),
		TextSize = 22,
		Parent = eggRow,
		OnClick = function()
			send("EggToBase", { rarity = Rarities.Order[rarityIndex] })
		end,
	})
	local function refreshEgg()
		rarityBtn.SetText(T("Rarity_" .. Rarities.Order[rarityIndex]))
		zoneBtn.SetText(T("Zone_" .. Zones.Order[zoneIndex]))
	end
	rarityBtn.Face.Activated:Connect(function()
		rarityIndex = rarityIndex % #Rarities.Order + 1
		refreshEgg()
	end)
	zoneBtn.Face.Activated:Connect(function()
		zoneIndex = zoneIndex % #Zones.Order + 1
		refreshEgg()
	end)
	refreshEgg()

	-- annuncio a tutto il server (filtrato da Roblox)
	local box = New("TextBox", {
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.new(1, -230, 0, 58),
		Position = UDim2.new(0, 5, 0, 336),
		Font = Theme.BodyFont,
		TextScaled = true,
		TextColor3 = Theme.Outline,
		PlaceholderText = "Announcement...",
		ClearTextOnFocus = false,
		Text = "",
		Parent = p.Body,
	}, { Kit.Corner(UDim.new(0, 16)), Kit.Stroke(4), Kit.Padding(10) })
	Kit.Button({
		Text = "📣",
		Color = "Pink",
		Size = UDim2.fromOffset(200, 58),
		Position = UDim2.new(1, -210, 0, 336),
		TextSize = 28,
		Parent = p.Body,
		OnClick = function()
			if box.Text ~= "" then
				send("Announce", { text = box.Text })
				box.Text = ""
			end
		end,
	})
	return { Frame = p.Frame, Close = p.Close }
end

return Panel
