-- HUD sempre visibile: monete, menu, eventi e potenziamenti attivi, barriera, trasporto, schiaffo.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Assets = require(ReplicatedStorage.Shared.Assets)
local Events = require(ReplicatedStorage.Shared.Config.Events)
local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Visuals = require(ReplicatedStorage.Shared.Visuals)
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
		Kit.Text({
			Text = "$",
			Size = UDim2.fromScale(0.7, 0.7),
			Position = UDim2.fromScale(0.15, 0.12),
			TextColor3 = Color3.fromRGB(184, 107, 0),
			Stroke = false,
		}),
	})
	local coinText = Kit.Text({
		Text = "$0",
		Size = UDim2.new(1, -86, 0, 40),
		Position = UDim2.new(0, 74, 0, 6),
		TextColor3 = Theme.Gold,
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = coins,
	})
	local rateText = Kit.Text({
		Text = "+$0/s",
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -86, 0, 22),
		Position = UDim2.new(0, 76, 0, 46),
		TextColor3 = Theme.Green,
		TextXAlignment = Enum.TextXAlignment.Left,
		Stroke = 2,
		Parent = coins,
	})
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
		Size = UDim2.fromOffset(220, 338),
		Position = UDim2.new(0, 16, 0.5, -10),
		AnchorPoint = Vector2.new(0, 0.5),
		Parent = gui,
	})
	local items = {
		{ name = "Shop", key = "MenuShop", color = "Green", icon = "Shop", x = 0, y = 0, rot = -4 },
		{ name = "Upgrades", key = "MenuUpgrades", color = "Blue", icon = "Upgrades", x = 112, y = 0, rot = 4 },
		{ name = "Index", key = "MenuIndex", color = "Purple", icon = "Index", x = 0, y = 136, rot = 4 },
		{ name = "Gifts", key = "MenuGifts", color = "Pink", icon = "Gifts", x = 112, y = 136, rot = -4 },
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
		local label = Kit.Text({
			Size = UDim2.fromOffset(108, 24),
			Position = UDim2.fromOffset(it.x - 4, it.y + 98),
			MaxTextSize = 22,
			Parent = menu,
		})
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
			Position = UDim2.fromOffset(it.x, 270),
			Parent = menu,
			OnClick = function()
				C.UI.Toggle(it.name)
			end,
		})
	end
	if player:GetAttribute("IsAdmin") or RunService:IsStudio() then
		Kit.Button({
			Name = "Admin",
			Icon = "Admin",
			Color = "Red",
			Size = UDim2.fromOffset(62, 58),
			Position = UDim2.fromOffset(148, 270),
			Parent = menu,
			OnClick = function()
				C.UI.Toggle("Admin")
			end,
		})
	else
		player:GetAttributeChangedSignal("IsAdmin"):Connect(function()
			if player:GetAttribute("IsAdmin") and not menu:FindFirstChild("Admin") then
				Kit.Button({
					Name = "Admin",
					Icon = "Admin",
					Color = "Red",
					Size = UDim2.fromOffset(62, 58),
					Position = UDim2.fromOffset(148, 270),
					Parent = menu,
					OnClick = function()
						C.UI.Toggle("Admin")
					end,
				})
			end
		end)
	end

	---------------------------------------------------------------------------------------
	-- Riga di stato sotto le monete: evento attivo, fortuna e bonus amici (lontano dall'elenco
	-- dei giocatori di Roblox, che su PC occupa l'angolo in alto a destra)
	---------------------------------------------------------------------------------------
	local status = New("Frame", {
		Name = "Status",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(720, 100),
		Position = UDim2.new(0.5, 0, 0, 92),
		AnchorPoint = Vector2.new(0.5, 0),
		Parent = gui,
	}, {
		New("UIListLayout", {
			FillDirection = Enum.FillDirection.Horizontal,
			Padding = UDim.new(0, 12),
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			SortOrder = Enum.SortOrder.LayoutOrder,
		}),
	})

	local eventCard = New("Frame", {
		Name = "Event",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(360, 100),
		Visible = false,
		LayoutOrder = 1,
		Parent = status,
	}, {
		Kit.Corner(UDim.new(0, 22)),
		Kit.Stroke(5),
		Kit.Gradient(Color3.fromRGB(255, 227, 107), Color3.fromRGB(255, 171, 23)),
		New("UIScale"),
	})
	local eventIcon = Kit.Icon(
		"GoldenHour",
		{ Size = UDim2.fromOffset(60, 60), Position = UDim2.fromOffset(10, 20), Parent = eventCard }
	)
	local eventTitle = Kit.Text({
		Size = UDim2.new(1, -168, 0, 36),
		Position = UDim2.fromOffset(80, 8),
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = eventCard,
	})
	local eventClock = Kit.Text({
		Size = UDim2.fromOffset(76, 36),
		Position = UDim2.new(1, -86, 0, 8),
		TextXAlignment = Enum.TextXAlignment.Right,
		Parent = eventCard,
	})
	local eventSub = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -94, 0, 44),
		Position = UDim2.fromOffset(82, 48),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Top,
		TextWrapped = true,
		TextColor3 = Color3.fromRGB(90, 50, 0),
		Stroke = false,
		MaxTextSize = 22,
		Parent = eventCard,
	})

	local chips = New("Frame", {
		Name = "Chips",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(240, 98),
		Visible = false,
		LayoutOrder = 2,
		Parent = status,
	}, { New("UIListLayout", { Padding = UDim.new(0, 10), SortOrder = Enum.SortOrder.LayoutOrder }) })
	local function chip(order: number, iconName: string)
		local f = New("Frame", {
			BackgroundColor3 = Color3.fromRGB(29, 22, 48),
			BackgroundTransparency = 0.15,
			Size = UDim2.fromOffset(240, 44),
			Visible = false,
			LayoutOrder = order,
			Parent = chips,
		}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(4) })
		Kit.Icon(iconName, { Size = UDim2.fromOffset(32, 32), Position = UDim2.fromOffset(8, 6), Parent = f })
		local text = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(1, -56, 0, 28),
			Position = UDim2.fromOffset(46, 8),
			TextXAlignment = Enum.TextXAlignment.Left,
			Stroke = 2,
			RichText = true,
			Parent = f,
		})
		return f, text
	end
	local luckChip, luckText = chip(1, "Luck")
	local friendChip, friendText = chip(2, "Friends")

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
	local barrierLabel = Kit.Text({
		Size = UDim2.fromOffset(140, 26),
		Position = UDim2.new(0.5, 0, 1, 6),
		AnchorPoint = Vector2.new(0.5, 0),
		Parent = barrier.Frame,
	})

	local function refreshRight()
		local now = workspace:GetServerTimeNow()
		-- evento
		local eventId = workspace:GetAttribute("EventId")
		local endsAt = workspace:GetAttribute("EventEndsAt") or 0
		if eventId and Events.List[eventId] and endsAt > now then
			eventCard.Visible = true
			eventTitle.Text = T("Event_" .. eventId)
			eventClock.Text = Format.Clock(endsAt - now)
			eventSub.Text = T("EventDesc_" .. eventId)
			local icon = Events.List[eventId].icon
			if eventIcon:IsA("ImageLabel") then
				eventIcon.Image = Assets.Images["Icon" .. icon] or eventIcon.Image
			elseif eventIcon:IsA("TextLabel") then
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
		chips.Visible = luckChip.Visible or friendChip.Visible
		-- barriera
		local plotIndex = player:GetAttribute("PlotIndex")
		barrier.Frame.Visible = plotIndex ~= nil
		local readyAt = player:GetAttribute("BarrierReadyAt") or 0
		local plot = plotIndex
			and workspace:FindFirstChild("Plots")
			and workspace.Plots:FindFirstChild("Plot" .. plotIndex)
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
	-- uovo del colore della rarita' (o il pet rubato in 3D)
	local carryEgg = Kit.Icon("Egg", {
		Size = UDim2.fromOffset(78, 78),
		Position = UDim2.fromOffset(6, 9),
		Parent = carry,
	})
	local carryView: ViewportFrame? = nil
	local carryViewPet: string? = nil
	local function showCarryPet(petId: string?)
		if petId == carryViewPet then
			return
		end
		carryViewPet = petId
		if carryView then
			carryView:Destroy()
			carryView = nil
		end
		carryEgg.Visible = petId == nil
		if not petId then
			return
		end
		local vp = New("ViewportFrame", {
			BackgroundTransparency = 1,
			Size = UDim2.fromOffset(84, 84),
			Position = UDim2.fromOffset(4, 6),
			Ambient = Color3.fromRGB(200, 200, 210),
			LightColor = Color3.fromRGB(255, 250, 240),
			LightDirection = Vector3.new(-0.5, -1, -0.6),
			Parent = carry,
		})
		local ok, model = pcall(Visuals.MakePet, petId, "None", "Normal")
		if ok and model then
			model:PivotTo(CFrame.new())
			model.Parent = vp
			local _, size = model:GetBoundingBox()
			local cam = New("Camera", { FieldOfView = 30, Parent = vp })
			local dist = math.max(size.X, size.Y, size.Z) * 2.2
			local center = Vector3.new(0, size.Y / 2, 0)
			cam.CFrame = CFrame.lookAt(center + Vector3.new(dist * 0.45, dist * 0.18, -dist), center)
			vp.CurrentCamera = cam
		end
		carryView = vp
	end
	local carryTitle = Kit.Text({
		Size = UDim2.new(1, -96, 0, 34),
		Position = UDim2.fromOffset(86, 8),
		TextXAlignment = Enum.TextXAlignment.Left,
		Parent = carry,
	})
	local carrySub = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -96, 0, 22),
		Position = UDim2.fromOffset(88, 44),
		TextXAlignment = Enum.TextXAlignment.Left,
		Stroke = 2,
		RichText = true,
		Parent = carry,
	})
	local carryHint = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -96, 0, 18),
		Position = UDim2.fromOffset(88, 68),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = Theme.Muted,
		Stroke = false,
		Parent = carry,
	})

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
		showCarryPet(if kind == "Pet" then petId else nil)
		if carryEgg:IsA("ImageLabel") then
			carryEgg.ImageColor3 = r.color:Lerp(Color3.new(1, 1, 1), 0.2)
		end
		local name = if kind == "Pet" and petId then T("Pet_" .. petId) else T("Egg_" .. rarity)
		carryTitle.Text = if n > 1 then `{name} ×{n}` else name
		carryTitle.TextColor3 = r.color
		local speed = player:GetAttribute("WalkSpeed") or 16
		local data = C.State.Data
		local base = 16 + 1.5 * ((data and data.Upgrades and data.Upgrades.Speed) or 0)
		local pct = math.floor((speed / base - 1) * 100 + 0.5)
		carrySub.Text = T("CarrySpeed", { pct = `<font color="#ff8a7a">{pct}%</font>` })
			.. (if pct <= -20 then " · " .. T("Heavy") else "")
		carryHint.Text = if stolen then T("CarryStolenHint") else T("CarryHint")
		if not wasVisible then
			Kit.Pop(carry)
		end
	end
	for _, a in { "Carrying", "CarryRarity", "CarryKind", "CarryPet", "WalkSpeed", "Thief" } do
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
	local slapLabel = Kit.Text({
		Size = UDim2.fromOffset(130, 26),
		Position = UDim2.new(0.5, 0, 1, -2),
		AnchorPoint = Vector2.new(0.5, 0),
		Parent = slap.Frame,
	})
	bindText(slapLabel, "BatSlap")
	slap.Frame.Visible = UserInputService.TouchEnabled
	hud.Slap = slap

	---------------------------------------------------------------------------------------
	-- Posizioni che dipendono dallo schermo: la scala dell'interfaccia e i comandi di Roblox
	-- (chat in alto a sinistra su PC, barra degli strumenti in basso al centro, salto su touch)
	---------------------------------------------------------------------------------------
	local scaleObj = gui:FindFirstChild("Scale") :: UIScale?
	local function place()
		local s = if scaleObj then scaleObj.Scale else 1
		local vp = workspace.CurrentCamera.ViewportSize
		local touch = UserInputService.TouchEnabled
		carry.Position = UDim2.new(0.5, 0, 1, -math.floor(80 / s))
		menu.Position = UDim2.new(0, 16, if touch then 0.5 else 0.66, -10)
		if touch then
			-- pulsante del salto (TouchJump di Roblox): centro e raggio in pixel dello schermo
			local small = math.min(vp.X, vp.Y) <= 500
			local jr = if small then 35 else 60
			local jx = if small then 60 else 110
			local jy = if small then 55 else 150
			-- schiaffo a sinistra del salto, alla stessa altezza; barriera sopra il salto
			slap.Frame.Position = UDim2.new(1, -(jx + jr + 16) / s - 59, 1, -jy / s)
			barrier.Frame.AnchorPoint = Vector2.new(0.5, 1)
			barrier.Frame.Position = UDim2.new(1, -jx / s, 1, -(jy + jr + 16) / s - 34)
		else
			barrier.Frame.AnchorPoint = Vector2.new(1, 0.5)
			barrier.Frame.Position = UDim2.new(1, -16, 0.62, 0)
		end
	end
	place()
	workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(place)
	if scaleObj then
		scaleObj:GetPropertyChangedSignal("Scale"):Connect(place)
	end

	---------------------------------------------------------------------------------------
	-- Striscione centrale (valanga, avvisi importanti) e nome della zona
	---------------------------------------------------------------------------------------
	local banner = New("Frame", {
		Name = "Banner",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(500, 96),
		Position = UDim2.new(0.5, 0, 0, 204),
		AnchorPoint = Vector2.new(0.5, 0),
		Rotation = -1.5,
		Visible = false,
		Parent = gui,
	}, {
		Kit.Corner(UDim.new(0, 22)),
		Kit.Stroke(5),
		Kit.Gradient(Color3.fromRGB(255, 90, 78), Color3.fromRGB(216, 27, 43)),
		New("UIScale"),
	})
	local bannerTitle = Kit.Text({
		Size = UDim2.new(0.92, 0, 0, 52),
		Position = UDim2.new(0.04, 0, 0, 8),
		RichText = true,
		Parent = banner,
	})
	local bannerSub = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(0.92, 0, 0, 26),
		Position = UDim2.new(0.04, 0, 0, 60),
		Stroke = 2,
		Parent = banner,
	})
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

	local zoneLabel = Kit.Text({
		Size = UDim2.fromOffset(520, 64),
		Position = UDim2.new(0.5, 0, 0, 252),
		AnchorPoint = Vector2.new(0.5, 0.5),
		TextTransparency = 1,
		Stroke = 5,
		Parent = gui,
	})
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
