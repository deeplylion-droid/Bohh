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

-- colori dei testi RichText sui riquadri bianchi
local GREEN = "#08b04a"
local SOFT = "#686492"
local RED = "#ec1a46"

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
	-- Monete (in alto al centro): pillola bianca con la moneta che sporge a sinistra
	---------------------------------------------------------------------------------------
	local coins, coinsFace = Kit.Surface({
		Name = "Coins",
		Size = UDim2.fromOffset(284, 72),
		Position = UDim2.new(0.5, 0, 0, 8),
		AnchorPoint = Vector2.new(0.5, 0),
		Corner = Theme.Pill,
		Stroke = 2.5,
		StrokeColor = Theme.Buttons.Yellow[2],
		Parent = gui,
	})
	Kit.Icon("Coin", {
		Name = "CoinIcon",
		Size = UDim2.fromOffset(74, 74),
		Position = UDim2.new(0, -10, 0.5, 0),
		AnchorPoint = Vector2.new(0, 0.5),
		ZIndex = 4,
		Parent = coinsFace,
	})
	local coinText = Kit.Text({
		Text = "$0",
		Size = UDim2.new(1, -92, 0, 40),
		Position = UDim2.new(0, 72, 0, 5),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = Theme.Ink,
		Stroke = false,
		ZIndex = 4,
		Parent = coinsFace,
	})
	local rateText = Kit.Text({
		Text = "+$0/s",
		Font = Theme.HeadFont,
		Size = UDim2.new(1, -92, 0, 20),
		Position = UDim2.new(0, 73, 0, 45),
		TextColor3 = Theme.GreenInk,
		TextXAlignment = Enum.TextXAlignment.Left,
		Stroke = false,
		ZIndex = 4,
		Parent = coinsFace,
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
	-- Menu a sinistra: riquadri colorati con l'icona che sporge e il nome sul bordo in basso
	---------------------------------------------------------------------------------------
	local menu = New("Frame", {
		Name = "Menu",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(332, 334),
		Position = UDim2.new(0, 16, 0.5, -10),
		AnchorPoint = Vector2.new(0, 0.5),
		Parent = gui,
	})
	local items = {
		{ name = "Shop", key = "MenuShop", color = "Red", icon = "Shop", x = 0, y = 0 },
		{ name = "Upgrades", key = "MenuUpgrades", color = "Blue", icon = "Upgrades", x = 112, y = 0 },
		{ name = "Index", key = "MenuIndex", color = "Purple", icon = "Index", x = 224, y = 0 },
		{ name = "Gifts", key = "MenuGifts", color = "Pink", icon = "Gifts", x = 0, y = 132 },
		{ name = "Quests", key = "MenuQuests", color = "Cyan", icon = "Quests", x = 112, y = 132 },
		{ name = "Wheel", key = "MenuWheel", color = "Yellow", icon = "Wheel", x = 224, y = 132 },
	}
	hud.Badges = {}
	for _, it in items do
		local b = Kit.Button({
			Name = it.name,
			Icon = it.icon,
			Color = it.color,
			Size = UDim2.fromOffset(100, 100),
			Position = UDim2.fromOffset(it.x, it.y),
			Corner = UDim.new(0, 30),
			Parent = menu,
			OnClick = function()
				C.UI.Toggle(it.name)
			end,
		})
		-- icona grande, un po' in alto: in basso c'e' il nome
		if b.Icon then
			b.Icon.Size = UDim2.fromScale(0.84, 0.84)
			b.Icon.Position = UDim2.fromScale(0.08, -0.02)
		end
		-- nome sul bordo in basso, contornato del colore del pulsante piu' scuro
		local label = Kit.Text({
			Name = "Label",
			Size = UDim2.fromOffset(124, 26),
			Position = UDim2.new(0.5, 0, 1, -17),
			AnchorPoint = Vector2.new(0.5, 0),
			Stroke = 3,
			StrokeColor = Kit.Tint(Theme.Buttons[it.color][2], -0.25),
			MaxTextSize = 21,
			ZIndex = 5,
			Parent = b.Face,
		})
		bindText(label, it.key)
		hud.Badges[it.name] = Kit.Badge(b.Frame)
	end
	local small = {
		{ name = "Codes", color = "Orange", icon = "Codes", x = 0 },
		{ name = "Settings", color = "Grey", icon = "Settings", x = 72 },
	}
	local function smallButton(name: string, color: string, icon: string, x: number)
		Kit.Button({
			Name = name,
			Icon = icon,
			Color = color,
			Size = UDim2.fromOffset(60, 60),
			Position = UDim2.fromOffset(x, 270),
			Corner = UDim.new(0, 20),
			Parent = menu,
			OnClick = function()
				C.UI.Toggle(name)
			end,
		})
	end
	for _, it in small do
		smallButton(it.name, it.color, it.icon, it.x)
	end
	if player:GetAttribute("IsAdmin") or RunService:IsStudio() then
		smallButton("Admin", "Red", "Admin", 144)
	else
		player:GetAttributeChangedSignal("IsAdmin"):Connect(function()
			if player:GetAttribute("IsAdmin") and not menu:FindFirstChild("Admin") then
				smallButton("Admin", "Red", "Admin", 144)
			end
		end)
	end

	---------------------------------------------------------------------------------------
	-- Riga di stato sotto le monete: evento attivo, fortuna e bonus amici (lontano dall'elenco
	-- dei giocatori di Roblox, che su PC occupa l'angolo in alto a destra)
	---------------------------------------------------------------------------------------
	-- colonna in alto, sotto le monete e lontano dal centro dello schermo: nome della zona,
	-- avvisi importanti (valanga, furti), annunci a tutto il server, evento attivo e potenziamenti
	local top = New("Frame", {
		Name = "TopStack",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(720, 340),
		Position = UDim2.new(0.5, 0, 0, 94),
		AnchorPoint = Vector2.new(0.5, 0),
		Parent = gui,
	}, {
		New("UIListLayout", {
			Padding = UDim.new(0, 10),
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			SortOrder = Enum.SortOrder.LayoutOrder,
		}),
	})
	hud.TopStack = top
	-- posto per gli annunci (li crea Notify)
	hud.AnnounceSlot = New("Frame", {
		Name = "AnnounceSlot",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(600, 48),
		Visible = false,
		LayoutOrder = 2,
		Parent = top,
	})
	local status = New("Frame", {
		Name = "Status",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(720, 104),
		Visible = false,
		LayoutOrder = 3,
		Parent = top,
	}, {
		New("UIListLayout", {
			FillDirection = Enum.FillDirection.Horizontal,
			Padding = UDim.new(0, 12),
			HorizontalAlignment = Enum.HorizontalAlignment.Center,
			SortOrder = Enum.SortOrder.LayoutOrder,
		}),
	})

	-- evento: scheda bianca con il tondo colorato dell'evento e il tempo che resta
	local eventCard, eventFace = Kit.Surface({
		Name = "Event",
		Size = UDim2.fromOffset(372, 96),
		Visible = false,
		LayoutOrder = 1,
		Corner = UDim.new(0, 22),
		Stroke = 2,
		StrokeTransparency = 0.8,
		Parent = status,
	})
	local eventBadge, eventIcon = Kit.IconBadge("GoldenHour", "Yellow", {
		Size = UDim2.fromOffset(72, 72),
		Position = UDim2.fromOffset(12, 12),
		ZIndex = 4,
		Ring = false,
		IconScale = 0.86,
		Parent = eventFace,
	})
	local eventTitle = Kit.Text({
		Size = UDim2.new(1, -192, 0, 32),
		Position = UDim2.fromOffset(96, 10),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = Theme.Ink,
		Stroke = false,
		ZIndex = 4,
		Parent = eventFace,
	})
	local clockPill = New("Frame", {
		Name = "Clock",
		BackgroundColor3 = Theme.Ink,
		Size = UDim2.fromOffset(80, 30),
		Position = UDim2.new(1, -90, 0, 11),
		ZIndex = 4,
		Parent = eventFace,
	}, { Kit.Corner(Theme.Pill) })
	local eventClock = Kit.Text({
		Size = UDim2.new(1, -14, 0.76, 0),
		Position = UDim2.new(0, 7, 0.12, 0),
		Stroke = false,
		ZIndex = 5,
		Parent = clockPill,
	})
	local eventSub = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -110, 0, 40),
		Position = UDim2.fromOffset(97, 46),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Top,
		TextWrapped = true,
		TextColor3 = Theme.InkSoft,
		Stroke = false,
		MaxTextSize = 19,
		ZIndex = 4,
		Parent = eventFace,
	})

	local chips = New("Frame", {
		Name = "Chips",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(250, 156),
		Visible = false,
		LayoutOrder = 2,
		Parent = status,
	}, { New("UIListLayout", { Padding = UDim.new(0, 10), SortOrder = Enum.SortOrder.LayoutOrder }) })
	local function chip(order: number, iconName: string)
		local f, face = Kit.Surface({
			Size = UDim2.fromOffset(250, 44),
			Visible = false,
			LayoutOrder = order,
			Corner = Theme.Pill,
			Stroke = 2,
			StrokeTransparency = 0.8,
			Shadow = 4,
			Parent = chips,
		})
		Kit.Icon(
			iconName,
			{ Size = UDim2.fromOffset(34, 34), Position = UDim2.fromOffset(8, 5), ZIndex = 4, Parent = face }
		)
		local text = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(1, -62, 0, 26),
			Position = UDim2.fromOffset(48, 9),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextColor3 = Theme.Ink,
			Stroke = false,
			RichText = true,
			ZIndex = 4,
			Parent = face,
		})
		return f, text
	end
	local luckChip, luckText = chip(1, "Luck")
	local friendChip, friendText = chip(2, "Friends")
	local kingChip, kingText = chip(0, "King")

	-- pulsante della barriera (il proprio lotto si puo' bloccare da ovunque)
	local barrier = Kit.Button({
		Name = "Barrier",
		Icon = "Barrier",
		Color = "Red",
		Size = UDim2.fromOffset(94, 94),
		Corner = UDim.new(0, 30),
		Position = UDim2.new(1, -16, 0.62, 0),
		AnchorPoint = Vector2.new(1, 0.5),
		Parent = gui,
		OnClick = function()
			Net.Event("ToggleBarrier"):FireServer()
		end,
	})
	local _, barrierLabel = Kit.Tag({
		Size = UDim2.fromOffset(110, 30),
		Position = UDim2.new(0.5, 0, 1, 12),
		AnchorPoint = Vector2.new(0.5, 0),
		ZIndex = 3,
		Parent = barrier.Frame,
	})

	local shownEvent: string? = nil -- evento di cui il tondo ha gia' colore e icona
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
			if eventId ~= shownEvent then
				shownEvent = eventId
				local def = Events.List[eventId]
				Kit.Paint(eventBadge, Kit.Tint(def.color, 0.3), def.color)
				if eventIcon and eventIcon:IsA("ImageLabel") then
					eventIcon.Image = Assets.Images["Icon" .. def.icon] or eventIcon.Image
				elseif eventIcon and eventIcon:IsA("TextLabel") then
					eventIcon.Text = Theme.Emoji[def.icon] or "⭐"
				end
			end
		else
			eventCard.Visible = false
		end
		-- fortuna
		local luckUntil = player:GetAttribute("LuckUntil") or 0
		local nowUnix = now
		if luckUntil > nowUnix then
			luckChip.Visible = true
			luckText.Text = `{T("Luck")} <font color="{GREEN}">{Format.Clock(luckUntil - nowUnix)}</font>`
		else
			luckChip.Visible = false
		end
		local fb = player:GetAttribute("FriendBonus") or 0
		friendChip.Visible = fb > 0
		friendText.Text = `{T("FriendBonus")} <font color="{GREEN}">+{math.floor(fb * 100)}%</font>`
		-- re della collina (solo a chi e' in cima al monumento)
		kingChip.Visible = player:GetAttribute("OnHill") == true
		if kingChip.Visible then
			if player:GetAttribute("King") and player:GetAttribute("KingIdle") then
				kingText.Text = `<font color="{SOFT}">{T("KingIdle")}</font>`
			elseif player:GetAttribute("King") then
				local rate = Format.Rate(player:GetAttribute("KingRate") or 0)
				kingText.Text = `{T("KingYou")} <font color="{GREEN}">{rate}</font>`
			else
				kingText.Text = `<font color="{RED}">{T("KingContested")}</font>`
			end
		end
		chips.Visible = luckChip.Visible or friendChip.Visible or kingChip.Visible
		status.Visible = eventCard.Visible or chips.Visible
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
	-- Cosa sto trasportando (in basso al centro): scheda del colore della rarita'
	---------------------------------------------------------------------------------------
	local carry, carryFace = Kit.Surface({
		Name = "Carry",
		Size = UDim2.fromOffset(450, 100),
		Position = UDim2.new(0.5, 0, 1, -14),
		AnchorPoint = Vector2.new(0.5, 1),
		Visible = false,
		Corner = UDim.new(0, 24),
		Color = Theme.Buttons.Blue[3],
		Color2 = Theme.Buttons.Blue[1],
		Stroke = 2.5,
		StrokeColor = Theme.Buttons.Blue[2],
		Parent = gui,
	})
	local carryStroke = carryFace:FindFirstChildOfClass("UIStroke") :: UIStroke
	-- tondo bianco con l'uovo del colore della rarita' (o il pet rubato in 3D)
	local eggDisc = New("Frame", {
		Name = "Disc",
		BackgroundColor3 = Theme.Card,
		Size = UDim2.fromOffset(80, 80),
		Position = UDim2.fromOffset(10, 10),
		ZIndex = 3,
		Parent = carryFace,
	}, { Kit.Corner(Theme.Pill), Kit.Gradient(Theme.Card, Theme.CardShade) })
	local carryEgg = Kit.Icon("Egg", {
		Size = UDim2.fromOffset(64, 64),
		Position = UDim2.fromOffset(8, 8),
		ZIndex = 4,
		Parent = eggDisc,
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
			Position = UDim2.fromOffset(-2, -4),
			Ambient = Color3.fromRGB(200, 200, 210),
			LightColor = Color3.fromRGB(255, 250, 240),
			LightDirection = Vector3.new(-0.5, -1, -0.6),
			ZIndex = 4,
			Parent = eggDisc,
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
		Size = UDim2.new(1, -116, 0, 36),
		Position = UDim2.fromOffset(102, 9),
		TextXAlignment = Enum.TextXAlignment.Left,
		Stroke = 2.5,
		ZIndex = 4,
		Parent = carryFace,
	})
	local carrySub = Kit.Text({
		Font = Theme.HeadFont,
		Size = UDim2.new(1, -116, 0, 22),
		Position = UDim2.fromOffset(103, 47),
		TextXAlignment = Enum.TextXAlignment.Left,
		RichText = true,
		ZIndex = 4,
		Parent = carryFace,
	})
	local carryHint = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -116, 0, 19),
		Position = UDim2.fromOffset(103, 71),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = Theme.Muted,
		Stroke = 1.5,
		ZIndex = 4,
		Parent = carryFace,
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
		-- la scheda prende il colore della rarita'
		local deep = r.color:Lerp(r.colorDark, 0.55)
		local edge = Kit.Tint(r.colorDark, -0.25)
		Kit.Paint(carryFace, Kit.Tint(r.color, 0.12), deep)
		carryStroke.Color = edge
		local name = if kind == "Pet" and petId then T("Pet_" .. petId) else T("Egg_" .. rarity)
		carryTitle.Text = if n > 1 then `{name} ×{n}` else name
		for _, label in { carryTitle, carrySub, carryHint } do
			local st = label:FindFirstChildOfClass("UIStroke")
			if st then
				st.Color = edge
			end
		end
		local speed = player:GetAttribute("WalkSpeed") or 16
		local data = C.State.Data
		local base = 16 + 1.5 * ((data and data.Upgrades and data.Upgrades.Speed) or 0)
		local pct = math.floor((speed / base - 1) * 100 + 0.5)
		carrySub.Text = T("CarrySpeed", { pct = `<font color="#ffe14a">{pct}%</font>` })
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
		Size = UDim2.fromOffset(116, 116),
		Position = UDim2.new(1, -150, 1, -200),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Corner = Theme.Pill,
		Parent = gui,
		OnClick = function()
			C.Combat.SlapButton()
		end,
	})
	local slapLabel = Kit.Text({
		Size = UDim2.fromOffset(130, 26),
		Position = UDim2.new(0.5, 0, 1, 0),
		AnchorPoint = Vector2.new(0.5, 0),
		Stroke = 3,
		StrokeColor = Kit.Tint(Theme.Buttons.Red[2], -0.25),
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
			local tiny = math.min(vp.X, vp.Y) <= 500
			local jr = if tiny then 35 else 60
			local jx = if tiny then 60 else 110
			local jy = if tiny then 55 else 150
			-- schiaffo a sinistra del salto, alla stessa altezza; barriera sopra il salto
			slap.Frame.Position = UDim2.new(1, -(jx + jr + 16) / s - 59, 1, -jy / s)
			barrier.Frame.AnchorPoint = Vector2.new(0.5, 1)
			barrier.Frame.Position = UDim2.new(1, -jx / s, 1, -(jy + jr + 16) / s - 36)
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
	-- Avvisi importanti (valanga, furti) e nome della zona: nella colonna in alto sotto le
	-- monete, non al centro dello schermo
	---------------------------------------------------------------------------------------
	local red = Theme.Buttons.Red
	local banner, bannerFace = Kit.Surface({
		Name = "Banner",
		Size = UDim2.fromOffset(520, 72),
		Visible = false,
		LayoutOrder = 1,
		Corner = UDim.new(0, 22),
		Color = red[3],
		Color2 = red[1],
		Stroke = 2.5,
		StrokeColor = red[2],
		Parent = top,
	})
	local bannerStroke = bannerFace:FindFirstChildOfClass("UIStroke") :: UIStroke
	local bannerTitle = Kit.Text({
		Size = UDim2.new(0.92, 0, 0, 36),
		Position = UDim2.new(0.04, 0, 0, 6),
		RichText = true,
		Stroke = 2.5,
		StrokeColor = red[2],
		ZIndex = 4,
		Parent = bannerFace,
	})
	local bannerSub = Kit.Text({
		Font = Theme.HeadFont,
		Size = UDim2.new(0.92, 0, 0, 21),
		Position = UDim2.new(0.04, 0, 0, 43),
		Stroke = 1.5,
		StrokeColor = red[2],
		ZIndex = 4,
		Parent = bannerFace,
	})
	hud.Banner = banner
	local function bannerColors(top: Color3, bottom: Color3)
		local edge = Kit.Tint(bottom, -0.3)
		Kit.Paint(bannerFace, top, bottom)
		bannerStroke.Color = edge
		for _, label in { bannerTitle, bannerSub } do
			local st = label:FindFirstChildOfClass("UIStroke")
			if st then
				st.Color = edge
			end
		end
	end
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
			bannerColors(colors[1], colors[2] or colors[1])
		else
			bannerColors(red[3], red[1])
		end
	end

	local zoneLabel = Kit.Text({
		Name = "Zone",
		Size = UDim2.fromOffset(540, 48),
		TextTransparency = 1,
		Stroke = 3.5,
		Visible = false,
		LayoutOrder = 0,
		Parent = top,
	})
	local zoneStroke = zoneLabel:FindFirstChildOfClass("UIStroke") :: UIStroke
	zoneStroke.Transparency = 1
	local zoneShown = 0
	function hud.ShowZone(name: string, color: Color3)
		zoneShown += 1
		local mine = zoneShown
		zoneLabel.Text = string.upper(name)
		zoneLabel.TextColor3 = color
		zoneStroke.Color = Kit.Tint(color, -0.65)
		zoneLabel.TextTransparency = 0
		zoneStroke.Transparency = 0
		zoneLabel.Visible = true
		Kit.Bounce(zoneLabel, 0.25)
		task.delay(2.2, function()
			if mine ~= zoneShown then
				return
			end
			Kit.Tween(zoneLabel, 0.6, { TextTransparency = 1 })
			Kit.Tween(zoneStroke, 0.6, { Transparency = 1 })
			task.wait(0.62)
			if mine == zoneShown then
				zoneLabel.Visible = false
			end
		end)
	end

	return hud
end

return Hud
