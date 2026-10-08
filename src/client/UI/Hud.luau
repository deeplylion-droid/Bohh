-- HUD sempre visibile: monete, menu, eventi e potenziamenti attivi, barriera, trasporto, schiaffo.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Events = require(ReplicatedStorage.Shared.Config.Events)
local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Kit = require(script.Parent.Kit)

local Theme = Kit.Theme
local New = Kit.New
local player = Players.LocalPlayer

local Hud = {}

function Hud.Build(gui: ScreenGui, C)
	local T = C.Lang.T
	local texts: { { label: TextLabel, key: string, args: any } } = {}
	local function bindText(label: TextLabel, key: string, args: any?)
		table.insert(texts, { label = label, key = key, args = args })
		label.Text = T(key, args)
	end
	C.Lang.Changed:Connect(function()
		for _, t in texts do
			t.label.Text = T(t.key, t.args)
		end
	end)

	local hud = {}

	---------------------------------------------------------------------------------------
	-- Monete (in alto al centro)
	---------------------------------------------------------------------------------------
	local coins = New("Frame", {
		Name = "Coins",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(280, 74),
		Position = UDim2.new(0.5, 0, 0, 8),
		AnchorPoint = Vector2.new(0.5, 0),
		Parent = gui,
	}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(5), Kit.Gradient(Theme.PanelTop, Theme.PanelBottom), New("UIScale") })
	New("Frame", {
		Name = "CoinIcon",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(58, 58),
		Position = UDim2.new(0, 8, 0.5, 0),
		AnchorPoint = Vector2.new(0, 0.5),
		Parent = coins,
	}, {
		Kit.Corner(UDim.new(1, 0)),
		Kit.Stroke(4),
		Kit.Gradient(Color3.fromRGB(255, 240, 150), Color3.fromRGB(245, 155, 0)),
		Kit.Text({ Text = "$", Size = UDim2.fromScale(0.7, 0.7), Position = UDim2.fromScale(0.15, 0.12), TextColor3 = Color3.fromRGB(184, 107, 0), Stroke = false }),
	})
	local coinText = Kit.Text({ Text = "$0", Size = UDim2.new(1, -86, 0, 40), Position = UDim2.new(0, 74, 0, 6), TextColor3 = Theme.Gold, TextXAlignment = Enum.TextXAlignment.Left, Parent = coins })
	local rateText = Kit.Text({ Text = "+$0/s", Font = Theme.BodyFont, Size = UDim2.new(1, -86, 0, 22), Position = UDim2.new(0, 76, 0, 46), TextColor3 = Theme.Green, TextXAlignment = Enum.TextXAlignment.Left, Stroke = 2, Parent = coins })
	local shown = 0
	local target = 0
	RunService.RenderStepped:Connect(function(dt)
		if shown ~= target then
			local diff = target - shown
			if math.abs(diff) < 1 then
				shown = target
			else
				shown += diff * math.min(1, dt * 10)
			end
			coinText.Text = Format.Money(shown)
		end
	end)
	C.State.Watch("Coins", function(v)
		local before = target
		target = v or 0
		if shown == 0 then
			shown = target
			coinText.Text = Format.Money(shown)
		elseif target > before then
			Kit.Bounce(coins, 0.06)
		end
	end)
	local function refreshRate()
		rateText.Text = Format.Rate(player:GetAttribute("Income") or 0)
	end
	player:GetAttributeChangedSignal("Income"):Connect(refreshRate)
	refreshRate()
	hud.Coins = coins

	---------------------------------------------------------------------------------------
	-- Menu a sinistra
	---------------------------------------------------------------------------------------
	local menu = New("Frame", {
		Name = "Menu",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(220, 330),
		Position = UDim2.new(0, 16, 0.5, -10),
		AnchorPoint = Vector2.new(0, 0.5),
		Parent = gui,
	})
	local items = {
		{ name = "Shop", key = "MenuShop", color = "Green", icon = "Shop", x = 0, y = 0, rot = -4 },
		{ name = "Upgrades", key = "MenuUpgrades", color = "Blue", icon = "Upgrades", x = 112, y = 0, rot = 4 },
		{ name = "Index", key = "MenuIndex", color = "Purple", icon = "Index", x = 0, y = 128, rot = 4 },
		{ name = "Gifts", key = "MenuGifts", color = "Pink", icon = "Gifts", x = 112, y = 128, rot = -4 },
	}
	hud.Badges = {}
	for _, it in items do
		local b = Kit.Button({
			Name = it.name,
			Icon = it.icon,
			Color = it.color,
			Size = UDim2.fromOffset(100, 92),
			Position = UDim2.fromOffset(it.x, it.y),
			Rotation = it.rot,
			Parent = menu,
			OnClick = function()
				C.UI.Toggle(it.name)
			end,
		})
		local label = Kit.Text({ Size = UDim2.fromOffset(120, 26), Position = UDim2.fromOffset(it.x - 10, it.y + 98), Parent = menu })
		bindText(label, it.key)
		hud.Badges[it.name] = Kit.Badge(b.Frame)
	end
	local small = {
		{ name = "Codes", color = "Orange", icon = "Codes", x = 0 },
		{ name = "Settings", color = "Grey", icon = "Settings", x = 74 },
	}
	for _, it in small do
		Kit.Button({
			Name = it.name,
			Icon = it.icon,
			Color = it.color,
			Size = UDim2.fromOffset(62, 58),
			Position = UDim2.fromOffset(it.x, 262),
			Parent = menu,
			OnClick = function()
				C.UI.Toggle(it.name)
			end,
		})
	end
	if player:GetAttribute("IsAdmin") or RunService:IsStudio() then
		Kit.Button({ Name = "Admin", Icon = "Admin", Color = "Red", Size = UDim2.fromOffset(62, 58), Position = UDim2.fromOffset(148, 262), Parent = menu, OnClick = function()
			C.UI.Toggle("Admin")
		end })
	else
		player:GetAttributeChangedSignal("IsAdmin"):Connect(function()
			if player:GetAttribute("IsAdmin") and not menu:FindFirstChild("Admin") then
				Kit.Button({ Name = "Admin", Icon = "Admin", Color = "Red", Size = UDim2.fromOffset(62, 58), Position = UDim2.fromOffset(148, 262), Parent = menu, OnClick = function()
					C.UI.Toggle("Admin")
				end })
			end
		end)
	end

	---------------------------------------------------------------------------------------
	-- Colonna destra: evento attivo, potenziamenti attivi, barriera
	---------------------------------------------------------------------------------------
	local right = New("Frame", {
		Name = "Right",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(330, 400),
		Position = UDim2.new(1, -16, 0, 70),
		AnchorPoint = Vector2.new(1, 0),
		Parent = gui,
	}, { New("UIListLayout", { Padding = UDim.new(0, 10), HorizontalAlignment = Enum.HorizontalAlignment.Right, SortOrder = Enum.SortOrder.LayoutOrder }) })

	local eventCard = New("Frame", {
		Name = "Event",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(320, 84),
		Visible = false,
		LayoutOrder = 1,
		Parent = right,
	}, { Kit.Corner(UDim.new(0, 22)), Kit.Stroke(5), Kit.Gradient(Color3.fromRGB(255, 227, 107), Color3.fromRGB(255, 171, 23)), New("UIScale") })
	local eventIcon = Kit.Icon("GoldenHour", { Size = UDim2.fromOffset(56, 56), Position = UDim2.fromOffset(10, 14), Parent = eventCard })
	local eventTitle = Kit.Text({ Size = UDim2.new(1, -84, 0, 34), Position = UDim2.fromOffset(74, 8), TextXAlignment = Enum.TextXAlignment.Left, Parent = eventCard })
	local eventSub = Kit.Text({ Font = Theme.BodyFont, Size = UDim2.new(1, -84, 0, 24), Position = UDim2.fromOffset(74, 48), TextXAlignment = Enum.TextXAlignment.Left, TextColor3 = Color3.fromRGB(90, 50, 0), Stroke = false, Parent = eventCard })

	local function chip(order: number, iconName: string)
		local f = New("Frame", {
			BackgroundColor3 = Color3.fromRGB(29, 22, 48),
			BackgroundTransparency = 0.15,
			Size = UDim2.fromOffset(240, 44),
			Visible = false,
			LayoutOrder = order,
			Parent = right,
		}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(4) })
		Kit.Icon(iconName, { Size = UDim2.fromOffset(32, 32), Position = UDim2.fromOffset(8, 6), Parent = f })
		local text = Kit.Text({ Font = Theme.BodyFont, Size = UDim2.new(1, -54, 0, 28), Position = UDim2.fromOffset(46, 8), TextXAlignment = Enum.TextXAlignment.Left, Stroke = 2, RichText = true, Parent = f })
		return f, text
	end
	local luckChip, luckText = chip(2, "Luck")
	local friendChip, friendText = chip(3, "Friends")

	-- pulsante della barriera (il proprio lotto si puo' bloccare da ovunque)
	local barrier = Kit.Button({
		Name = "Barrier",
		Icon = "Barrier",
		Color = "Red",
		Size = UDim2.fromOffset(96, 90),
		Position = UDim2.new(1, -16, 0.62, 0),
		AnchorPoint = Vector2.new(1, 0.5),
		Parent = gui,
		OnClick = function()
			Net.Event("ToggleBarrier"):FireServer()
		end,
	})
	local barrierLabel = Kit.Text({ Size = UDim2.fromOffset(140, 26), Position = UDim2.new(0.5, 0, 1, 6), AnchorPoint = Vector2.new(0.5, 0), Parent = barrier.Frame })

	local function refreshRight()
		local now = workspace:GetServerTimeNow()
		-- evento
		local eventId = workspace:GetAttribute("EventId")
		local endsAt = workspace:GetAttribute("EventEndsAt") or 0
		if eventId and Events.List[eventId] and endsAt > now then
			eventCard.Visible = true
			eventTitle.Text = T("Event_" .. eventId)
			eventSub.Text = Format.Clock(endsAt - now) .. " · " .. T("EventDesc_" .. eventId)
			local icon = Events.List[eventId].icon
			if eventIcon:IsA("TextLabel") then
				eventIcon.Text = Theme.Emoji[icon] or "⭐"
			end
		else
			eventCard.Visible = false
		end
		-- fortuna
		local luckUntil = player:GetAttribute("LuckUntil") or 0
		local nowUnix = now
		if luckUntil > nowUnix then
			luckChip.Visible = true
			luckText.Text = `{T("Luck")} <font color="#9dff6b">{Format.Clock(luckUntil - nowUnix)}</font>`
		else
			luckChip.Visible = false
		end
		local fb = player:GetAttribute("FriendBonus") or 0
		friendChip.Visible = fb > 0
		friendText.Text = `{T("FriendBonus")} <font color="#9dff6b">+{math.floor(fb * 100)}%</font>`
		-- barriera
		local plotIndex = player:GetAttribute("PlotIndex")
		barrier.Frame.Visible = plotIndex ~= nil
		local readyAt = player:GetAttribute("BarrierReadyAt") or 0
		local plot = plotIndex and workspace:FindFirstChild("Plots") and workspace.Plots:FindFirstChild("Plot" .. plotIndex)
		if plot and plot:GetAttribute("BarrierOn") then
			local untilT = plot:GetAttribute("BarrierUntil") or now
			barrierLabel.Text = Format.Clock(untilT - now)
			barrier.SetColor("Cyan")
		elseif readyAt > now then
			barrierLabel.Text = Format.Clock(readyAt - now)
			barrier.SetColor("Grey")
		else
			barrierLabel.Text = T("MenuDefense")
			barrier.SetColor("Red")
		end
	end
	task.spawn(function()
		while gui.Parent do
			refreshRight()
			task.wait(0.25)
		end
	end)

	---------------------------------------------------------------------------------------
	-- Cosa sto trasportando (in basso al centro)
	---------------------------------------------------------------------------------------
	local carry = New("Frame", {
		Name = "Carry",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(440, 96),
		Position = UDim2.new(0.5, 0, 1, -14),
		AnchorPoint = Vector2.new(0.5, 1),
		Visible = false,
		Parent = gui,
	}, { Kit.Corner(UDim.new(0, 26)), Kit.Stroke(5), Kit.Gradient(Theme.PanelTop, Theme.PanelBottom), New("UIScale") })
	local carryEgg = New("Frame", {
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(62, 76),
		Position = UDim2.fromOffset(12, 10),
		Parent = carry,
	}, { Kit.Corner(UDim.new(0.5, 0)), Kit.Stroke(4) })
	local carryTitle = Kit.Text({ Size = UDim2.new(1, -96, 0, 34), Position = UDim2.fromOffset(86, 8), TextXAlignment = Enum.TextXAlignment.Left, Parent = carry })
	local carrySub = Kit.Text({ Font = Theme.BodyFont, Size = UDim2.new(1, -96, 0, 22), Position = UDim2.fromOffset(88, 44), TextXAlignment = Enum.TextXAlignment.Left, Stroke = 2, RichText = true, Parent = carry })
	local carryHint = Kit.Text({ Font = Theme.BodyFont, Size = UDim2.new(1, -96, 0, 18), Position = UDim2.fromOffset(88, 68), TextXAlignment = Enum.TextXAlignment.Left, TextColor3 = Theme.Muted, Stroke = false, Parent = carry })

	local function refreshCarry()
		local n = player:GetAttribute("Carrying") or 0
		local wasVisible = carry.Visible
		carry.Visible = n > 0
		if n == 0 then
			return
		end
		local rarity = player:GetAttribute("CarryRarity") or "Common"
		local r = Rarities.List[rarity] or Rarities.List.Common
		local kind = player:GetAttribute("CarryKind")
		local petId = player:GetAttribute("CarryPet")
		local stolen = player:GetAttribute("Thief")
		carryEgg.BackgroundColor3 = r.color
		local name = if kind == "Pet" and petId then T("Pet_" .. petId) else T("Egg_" .. rarity)
		carryTitle.Text = if n > 1 then `{name} ×{n}` else name
		carryTitle.TextColor3 = r.color
		local speed = player:GetAttribute("WalkSpeed") or 16
		local data = C.State.Data
		local base = 16 + 1.5 * ((data and data.Upgrades and data.Upgrades.Speed) or 0)
		local pct = math.floor((speed / base - 1) * 100 + 0.5)
		carrySub.Text = T("CarrySpeed", { pct = `<font color="#ff8a7a">{pct}%</font>` }) .. (if pct <= -20 then " · " .. T("Heavy") else "")
		carryHint.Text = if stolen then T("CarryStolenHint") else T("CarryHint")
		if not wasVisible then
			Kit.Pop(carry)
		end
	end
	for _, a in { "Carrying", "CarryRarity", "WalkSpeed", "Thief" } do
		player:GetAttributeChangedSignal(a):Connect(refreshCarry)
	end
	C.Lang.Changed:Connect(refreshCarry)
	refreshCarry()

	---------------------------------------------------------------------------------------
	-- Schiaffo (schermi touch)
	---------------------------------------------------------------------------------------
	local slap = Kit.Button({
		Name = "Slap",
		Icon = "Slap",
		Color = "Red",
		Size = UDim2.fromOffset(118, 118),
		Position = UDim2.new(1, -150, 1, -200),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Corner = UDim.new(1, 0),
		Parent = gui,
		OnClick = function()
			C.Combat.SlapButton()
		end,
	})
	local slapLabel = Kit.Text({ Size = UDim2.fromOffset(130, 26), Position = UDim2.new(0.5, 0, 1, -2), AnchorPoint = Vector2.new(0.5, 0), Parent = slap.Frame })
	bindText(slapLabel, "BatSlap")
	slap.Frame.Visible = UserInputService.TouchEnabled
	hud.Slap = slap

	---------------------------------------------------------------------------------------
	-- Striscione centrale (valanga, avvisi importanti) e nome della zona
	---------------------------------------------------------------------------------------
	local banner = New("Frame", {
		Name = "Banner",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(500, 96),
		Position = UDim2.new(0.5, 0, 0, 96),
		AnchorPoint = Vector2.new(0.5, 0),
		Rotation = -1.5,
		Visible = false,
		Parent = gui,
	}, { Kit.Corner(UDim.new(0, 22)), Kit.Stroke(5), Kit.Gradient(Color3.fromRGB(255, 90, 78), Color3.fromRGB(216, 27, 43)), New("UIScale") })
	local bannerTitle = Kit.Text({ Size = UDim2.new(0.92, 0, 0, 52), Position = UDim2.new(0.04, 0, 0, 8), RichText = true, Parent = banner })
	local bannerSub = Kit.Text({ Font = Theme.BodyFont, Size = UDim2.new(0.92, 0, 0, 26), Position = UDim2.new(0.04, 0, 0, 60), Stroke = 2, Parent = banner })
	hud.Banner = banner
	-- priority: chi ha la priorita' piu' alta tiene lo striscione (furto 3 > valanga 2 > altro 1);
	-- quando lo libera, gli altri lo riprendono al loro aggiornamento successivo
	local bannerOwner = 0
	function hud.ShowBanner(title: string?, sub: string?, colors: { Color3 }?, priority: number?)
		local prio = priority or 1
		if not title then
			if prio >= bannerOwner then
				banner.Visible = false
				bannerOwner = 0
			end
			return
		end
		if banner.Visible and prio < bannerOwner then
			return
		end
		bannerOwner = prio
		if not banner.Visible then
			banner.Visible = true
			Kit.Pop(banner)
		end
		bannerTitle.Text = title
		bannerSub.Text = sub or ""
		if colors then
			banner:FindFirstChildOfClass("UIGradient").Color = ColorSequence.new(colors[1], colors[2])
		end
	end

	local zoneLabel = Kit.Text({ Size = UDim2.fromOffset(520, 64), Position = UDim2.new(0.5, 0, 0.2, 0), AnchorPoint = Vector2.new(0.5, 0.5), TextTransparency = 1, Stroke = 5, Parent = gui })
	local zoneStroke = zoneLabel:FindFirstChildOfClass("UIStroke") :: UIStroke
	zoneStroke.Transparency = 1
	function hud.ShowZone(name: string, color: Color3)
		zoneLabel.Text = string.upper(name)
		zoneLabel.TextColor3 = color
		zoneLabel.TextTransparency = 0
		zoneStroke.Transparency = 0
		Kit.Bounce(zoneLabel, 0.25)
		task.delay(2.2, function()
			Kit.Tween(zoneLabel, 0.6, { TextTransparency = 1 })
			Kit.Tween(zoneStroke, 0.6, { Transparency = 1 })
		end)
	end

	return hud
end

return Hud
