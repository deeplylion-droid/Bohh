-- HUD minimale: fase e obiettivo, barre del giocatore, stato della caccia, squadra, notifiche e debriefing.
local Lighting = game:GetService("Lighting")
local TweenService = game:GetService("TweenService")

local Watch = require(script.Parent:WaitForChild("Watch"))

local Hud = {}
Hud.__index = Hud

local TEXT = Color3.fromRGB(222, 226, 214)
local MUTED = Color3.fromRGB(150, 156, 145)
local PANEL = Color3.fromRGB(12, 15, 13)

local function make(className: string, props: { [string]: any }, parent: Instance?): any
	local inst = Instance.new(className)
	for k, v in props do
		(inst :: any)[k] = v
	end
	inst.Parent = parent
	return inst
end

local function corner(parent: Instance, radius: number?)
	make("UICorner", { CornerRadius = UDim.new(0, radius or 8) }, parent)
end

local function padding(parent: Instance, px: number)
	make("UIPadding", {
		PaddingLeft = UDim.new(0, px),
		PaddingRight = UDim.new(0, px),
		PaddingTop = UDim.new(0, px),
		PaddingBottom = UDim.new(0, px),
	}, parent)
end

local function panel(parent: Instance, props: { [string]: any }): Frame
	local f = make("Frame", props, parent)
	f.BackgroundColor3 = PANEL
	f.BackgroundTransparency = 0.3
	f.BorderSizePixel = 0
	corner(f)
	return f
end

local function text(parent: Instance, props: { [string]: any }): TextLabel
	local t = make("TextLabel", {
		BackgroundTransparency = 1,
		Font = Enum.Font.Gotham,
		TextColor3 = TEXT,
		TextSize = 14,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextWrapped = true,
		Size = UDim2.new(1, 0, 0, 18),
	}, parent)
	for k, v in props do
		(t :: any)[k] = v
	end
	return t
end

local function edgeFrame(parent: Instance, size: UDim2, pos: UDim2, rotation: number): Frame
	local f = make("Frame", {
		Size = size,
		Position = pos,
		BackgroundColor3 = Color3.fromRGB(0, 0, 0),
		BorderSizePixel = 0,
		BackgroundTransparency = 0,
	}, parent)
	make("UIGradient", {
		Rotation = rotation,
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(1, 1) }),
	}, f)
	return f
end

function Hud.new(player: Player, state: Folder)
	local self = setmetatable({}, Hud)
	self.player = player
	self.state = state

	local gui = make("ScreenGui", {
		Name = "RakeHUD",
		ResetOnSpawn = false,
		IgnoreGuiInset = true,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	}, player:WaitForChild("PlayerGui"))
	self.gui = gui

	-- Vignetta della paura
	local vignette = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundTransparency = 1, ZIndex = 0 }, gui)
	edgeFrame(vignette, UDim2.fromScale(0.35, 1), UDim2.fromScale(0, 0), 0)
	edgeFrame(vignette, UDim2.fromScale(0.35, 1), UDim2.fromScale(0.65, 0), 180)
	edgeFrame(vignette, UDim2.fromScale(1, 0.35), UDim2.fromScale(0, 0), 90)
	edgeFrame(vignette, UDim2.fromScale(1, 0.35), UDim2.fromScale(0, 0.65), 270)
	self.vignette = make("CanvasGroup", { Size = UDim2.fromScale(1, 1), BackgroundTransparency = 1, GroupTransparency = 1, ZIndex = 0 }, gui)
	vignette.Parent = self.vignette

	self.flash = make("Frame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = Color3.fromRGB(0, 0, 0),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
		ZIndex = 20,
	}, gui)

	-- In alto: fase, orario, obiettivo
	local top = panel(gui, {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 104),
		Size = UDim2.new(0, 480, 0, 74),
	})
	padding(top, 10)
	self.phase = text(top, { Font = Enum.Font.GothamBold, TextSize = 17, Size = UDim2.new(1, 0, 0, 20), TextXAlignment = Enum.TextXAlignment.Center })
	self.objective = text(top, { Position = UDim2.new(0, 0, 0, 22), Size = UDim2.new(1, 0, 0, 18), TextXAlignment = Enum.TextXAlignment.Center })
	self.progress = text(top, {
		Position = UDim2.new(0, 0, 0, 40),
		Size = UDim2.new(1, 0, 0, 16),
		TextSize = 13,
		TextColor3 = MUTED,
		TextXAlignment = Enum.TextXAlignment.Center,
	})

	-- Notifiche
	self.feed = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 186),
		Size = UDim2.new(0, 520, 0, 150),
		BackgroundTransparency = 1,
	}, gui)
	make("UIListLayout", { Padding = UDim.new(0, 4), HorizontalAlignment = Enum.HorizontalAlignment.Center }, self.feed)

	-- Smartwatch al polso: compare (con l'avambraccio) quando lo consulti col tasto G
	local wrist = make("Frame", {
		Name = "Polso",
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, 40, 1, 520),
		Size = UDim2.fromOffset(250, 470),
		BackgroundTransparency = 1,
	}, gui)
	self.wrist = wrist
	local sleeve = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 250),
		Size = UDim2.fromOffset(170, 320),
		BackgroundColor3 = Color3.fromRGB(46, 54, 40),
		BorderSizePixel = 0,
	}, wrist)
	corner(sleeve, 40)
	make("UIGradient", { Rotation = 0, Color = ColorSequence.new({ ColorSequenceKeypoint.new(0, Color3.fromRGB(28, 32, 24)), ColorSequenceKeypoint.new(0.5, Color3.fromRGB(58, 68, 50)), ColorSequenceKeypoint.new(1, Color3.fromRGB(24, 28, 22)) }) }, sleeve)
	make("Frame", { Position = UDim2.fromOffset(0, 0), Size = UDim2.new(1, 0, 0, 18), BackgroundColor3 = Color3.fromRGB(30, 34, 26), BorderSizePixel = 0 }, sleeve)
	local skinFore = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 40),
		Size = UDim2.fromOffset(120, 230),
		BackgroundColor3 = Color3.fromRGB(200, 160, 130),
		BorderSizePixel = 0,
	}, wrist)
	corner(skinFore, 50)
	local hand = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 4, 0, 0),
		Size = UDim2.fromOffset(132, 92),
		BackgroundColor3 = Color3.fromRGB(205, 165, 134),
		BorderSizePixel = 0,
	}, wrist)
	corner(hand, 40)
	for _, f in { skinFore, hand } do
		make("UIGradient", { Rotation = 0, Color = ColorSequence.new({ ColorSequenceKeypoint.new(0, Color3.fromRGB(150, 150, 150)), ColorSequenceKeypoint.new(0.5, Color3.new(1, 1, 1)), ColorSequenceKeypoint.new(1, Color3.fromRGB(140, 140, 140)) }) }, f)
	end
	self.skin = { skinFore, hand }
	self.watch = Watch.new(wrist)
	self.watch.root.AnchorPoint = Vector2.new(0.5, 0)
	self.watch.root.Position = UDim2.new(0.5, 0, 0, 30)
	self.watchShown = false
	-- indicatore di avviso quando l'orologio è abbassato
	self.watchAlert = make("TextLabel", {
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, 20, 1, -20),
		Size = UDim2.fromOffset(120, 26),
		BackgroundColor3 = Color3.fromRGB(10, 12, 12),
		BackgroundTransparency = 0.35,
		Font = Enum.Font.GothamBold,
		TextSize = 13,
		TextColor3 = Color3.fromRGB(255, 90, 70),
		Visible = false,
	}, gui)
	corner(self.watchAlert, 8)
	-- bordo di sangue quando la salute è bassa
	self.blood = make("CanvasGroup", { Size = UDim2.fromScale(1, 1), BackgroundTransparency = 1, GroupTransparency = 1, ZIndex = 0 }, gui)
	for _, info in { { 0, UDim2.fromScale(0.3, 1), UDim2.fromScale(0, 0) }, { 180, UDim2.fromScale(0.3, 1), UDim2.fromScale(0.7, 0) }, { 90, UDim2.fromScale(1, 0.3), UDim2.fromScale(0, 0) }, { 270, UDim2.fromScale(1, 0.3), UDim2.fromScale(0, 0.7) } } do
		local f = make("Frame", { Size = info[2], Position = info[3], BackgroundColor3 = Color3.fromRGB(120, 0, 0), BorderSizePixel = 0 }, self.blood)
		make("UIGradient", { Rotation = info[1], Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(1, 1) }) }, f)
	end

	-- Centro: messaggi grandi (briefing, braccato)
	self.center = text(gui, {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.62),
		Size = UDim2.new(0, 620, 0, 120),
		TextSize = 20,
		Font = Enum.Font.GothamBold,
		TextXAlignment = Enum.TextXAlignment.Center,
		TextStrokeTransparency = 0.4,
		RichText = true,
	})

	-- Debriefing
	local debrief = panel(gui, {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.new(0, 400, 0, 0),
		AutomaticSize = Enum.AutomaticSize.Y,
		Visible = false,
		BackgroundTransparency = 0.1,
		ZIndex = 10,
	})
	padding(debrief, 16)
	self.debrief = debrief
	self.debriefText = text(debrief, {
		Size = UDim2.new(1, 0, 0, 0),
		AutomaticSize = Enum.AutomaticSize.Y,
		RichText = true,
		TextSize = 15,
		ZIndex = 11,
	})

	self.lastUpdate = 0
	state:GetAttributeChangedSignal("Phase"):Connect(function()
		if state:GetAttribute("Phase") ~= "Debriefing" then
			debrief.Visible = false
		end
	end)
	return self
end

function Hud:notify(message: string)
	local label = text(self.feed, {
		Text = message,
		Size = UDim2.new(1, 0, 0, 0),
		AutomaticSize = Enum.AutomaticSize.Y,
		TextXAlignment = Enum.TextXAlignment.Center,
		TextSize = 15,
		TextStrokeTransparency = 0.5,
	})
	local children = {}
	for _, c in self.feed:GetChildren() do
		if c:IsA("TextLabel") then
			table.insert(children, c)
		end
	end
	if #children > 5 then
		children[1]:Destroy()
	end
	task.delay(6, function()
		if label.Parent then
			local tween = TweenService:Create(label, TweenInfo.new(0.8), { TextTransparency = 1, TextStrokeTransparency = 1 })
			tween:Play()
			tween.Completed:Wait()
			label:Destroy()
		end
	end)
end

function Hud:setWatchVisible(shown: boolean)
	if self.watchShown == shown then
		return
	end
	self.watchShown = shown
	local char = self.player.Character
	local hand = char and (char:FindFirstChild("LeftHand") or char:FindFirstChild("Left Arm"))
	if hand and hand:IsA("BasePart") then
		for _, f in self.skin do
			f.BackgroundColor3 = hand.Color
		end
	end
	TweenService:Create(self.wrist, TweenInfo.new(shown and 0.35 or 0.25, Enum.EasingStyle.Back, shown and Enum.EasingDirection.Out or Enum.EasingDirection.In), {
		Position = shown and UDim2.new(0, 40, 1, 60) or UDim2.new(0, 40, 1, 520),
		Rotation = shown and -8 or 0,
	}):Play()
end

function Hud:pulse()
	self.flash.BackgroundTransparency = 0.2
	TweenService:Create(self.flash, TweenInfo.new(0.6), { BackgroundTransparency = 1 }):Play()
end

local function clock(): string
	local t = Lighting.ClockTime
	return ("%02d:%02d"):format(math.floor(t), math.floor((t % 1) * 60))
end


-- vitals: { stamina, fear, nv, nvOn, exhausted, panic }
function Hud:update(vitals)
	local player, state = self.player, self.state
	self.watch:update(vitals, player)
	local health = player:GetAttribute("Health") or 100
	self.blood.GroupTransparency = 1 - math.clamp((60 - health) / 50, 0, 1) * 0.85
	self.vignette.GroupTransparency = 1 - math.clamp((vitals.fear - 30) / 70, 0, 1) * 0.85

	local now = os.clock()
	if now - self.lastUpdate < 0.15 then
		return
	end
	self.lastUpdate = now


	local phase = state:GetAttribute("Phase") or "Attesa"
	local timeLeft = state:GetAttribute("TimeLeft") or 0
	local status = player:GetAttribute("Status") or "Lobby"
	if phase == "Attesa" then
		self.phase.Text = "In attesa di giocatori…"
	elseif phase == "Briefing" then
		self.phase.Text = ("Briefing — si parte tra %d s"):format(timeLeft)
	elseif phase == "Notte" then
		self.phase.Text = ("Notte · %s · alba tra %d:%02d"):format(clock(), timeLeft // 60, timeLeft % 60)
	else
		self.phase.Text = ("Debriefing · %d s"):format(timeLeft)
	end
	local objective = state:GetAttribute("Objective")
	self.objective.Text = objective and phase ~= "Attesa" and (objective .. ": " .. (state:GetAttribute("ObjectiveText") or "")) or ""
	self.progress.Text = phase == "Notte" and (state:GetAttribute("ObjectiveProgress") or "") or ""

	-- avviso dell'orologio quando non lo stai guardando
	local alert = self.watch.lastAlert or ""
	self.watchAlert.Visible = not self.watchShown and alert ~= "" and alert ~= "OK" and os.clock() % 1 < 0.6
	self.watchAlert.Text = "⌚ " .. alert .. "  [G]"

	-- Messaggio centrale
	if status == "Braccato" then
		local left = math.max(0, math.ceil((player:GetAttribute("DownedUntil") or 0) - workspace:GetServerTimeNow()))
		self.center.Text = ("<font color=\"#ff6a5a\">SEI STATO COLPITO</font>\nUn compagno deve rianimarti entro %d s"):format(left)
	elseif status == "Fuori" and phase == "Notte" then
		self.center.Text = "Sei fuori gioco. Osservi i compagni: puoi aprire il tablet [T] per aiutarli."
	elseif phase == "Briefing" then
		self.center.Text = "<font size=\"16\">1 Torcia · 2 Telecamera · 3 Fucile a dardi · 4 Tablet\n"
			.. "Shift scatto · T tablet · G orologio · N visore · R tipo camera · tasto destro mirino</font>"
	else
		self.center.Text = ""
	end
end

function Hud:showDebrief(data)
	local lines = {
		data.won and "<font size=\"22\" color=\"#8fd18f\"><b>MISSIONE COMPIUTA</b></font>"
			or "<font size=\"22\" color=\"#ff7060\"><b>MISSIONE FALLITA</b></font>",
		data.reason,
		"",
		"<b>Obiettivo:</b> " .. tostring(data.objective),
		"",
	}
	for _, row in data.breakdown do
		table.insert(lines, ("%s: +%d XP"):format(row[1], row[2]))
	end
	table.insert(lines, "")
	table.insert(lines, ("<b>Totale: +%d XP</b>%s"):format(data.xp, data.halved and " (dimezzati per la sconfitta)" or ""))
	table.insert(lines, ("Rango: <b>%s</b> · Livello %d · %d XP"):format(data.rank, data.level, data.totalXP))
	if data.nextXP then
		table.insert(lines, ("Prossimo rango a %d XP"):format(data.nextXP))
	end
	self.debriefText.Text = table.concat(lines, "\n")
	self.debrief.Visible = true
end

return Hud
