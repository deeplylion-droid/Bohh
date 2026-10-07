-- Smartwatch al polso (HUD in basso a sinistra): anelli di stamina e paura, ora e bussola,
-- battito cardiaco che pulsa, batterie di torcia e visore, attrezzatura e avvisi con bip.
local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")

local Sfx = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Sfx"))

local Watch = {}
Watch.__index = Watch

local DOTS = 40
local FACE = 176
local TEAL = Color3.fromRGB(70, 230, 190)
local PURPLE = Color3.fromRGB(190, 90, 255)
local RED = Color3.fromRGB(255, 70, 60)
local DIM = Color3.fromRGB(38, 42, 44)
local TEXT = Color3.fromRGB(225, 235, 230)
local MUTED = Color3.fromRGB(120, 130, 128)

local function make(className: string, props: { [string]: any }, parent: Instance?): any
	local inst = Instance.new(className)
	for k, v in props do
		(inst :: any)[k] = v
	end
	inst.Parent = parent
	return inst
end

local function corner(parent: Instance, r: number)
	make("UICorner", { CornerRadius = UDim.new(0, r) }, parent)
end

local function label(parent: Instance, props: { [string]: any }): TextLabel
	local t = make("TextLabel", { BackgroundTransparency = 1, Font = Enum.Font.GothamMedium, TextColor3 = TEXT, TextSize = 12 }, parent)
	for k, v in props do
		(t :: any)[k] = v
	end
	return t
end

local function ring(parent: Instance, radius: number, size: number)
	local dots = {}
	for i = 1, DOTS do
		local a = (i - 1) / DOTS * math.pi * 2 - math.pi / 2
		local d = make("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(0.5, math.cos(a) * radius, 0.5, math.sin(a) * radius),
			Size = UDim2.fromOffset(size, size),
			BackgroundColor3 = DIM,
			BorderSizePixel = 0,
			ZIndex = 4,
		}, parent)
		corner(d, 99)
		dots[i] = d
	end
	return dots
end

local function fill(dots, value: number, color: Color3)
	local lit = math.floor(math.clamp(value, 0, 1) * #dots + 0.5)
	for i, d in dots do
		d.BackgroundColor3 = i <= lit and color or DIM
	end
end

local function battery(parent: Instance, pos: UDim2, name: string)
	local holder = make("Frame", { Position = pos, Size = UDim2.fromOffset(58, 12), BackgroundTransparency = 1, ZIndex = 4 }, parent)
	label(holder, { Text = name, Size = UDim2.fromOffset(14, 12), TextSize = 10, TextColor3 = MUTED, ZIndex = 4 })
	local shell = make("Frame", { Position = UDim2.fromOffset(16, 1), Size = UDim2.fromOffset(28, 10), BackgroundTransparency = 1, ZIndex = 4 }, holder)
	make("UIStroke", { Color = MUTED, Thickness = 1 }, shell)
	corner(shell, 2)
	local bar = make("Frame", { Position = UDim2.fromOffset(1, 1), Size = UDim2.new(1, -2, 1, -2), BackgroundColor3 = TEAL, BorderSizePixel = 0, ZIndex = 4 }, shell)
	local pct = label(holder, { Position = UDim2.fromOffset(46, 0), Size = UDim2.fromOffset(20, 12), TextSize = 9, TextXAlignment = Enum.TextXAlignment.Left, TextColor3 = MUTED, ZIndex = 4 })
	return { bar = bar, pct = pct }
end

local function setBattery(b, value: number, active: boolean)
	value = math.clamp(value, 0, 1)
	b.bar.Size = UDim2.new(value, -2, 1, -2)
	b.bar.BackgroundColor3 = value < 0.2 and RED or (active and Color3.fromRGB(255, 220, 120) or TEAL)
	b.pct.Text = ("%d"):format(math.floor(value * 100))
end

function Watch.new(parent: Instance)
	local self = setmetatable({}, Watch)
	local root = make("Frame", {
		Name = "Smartwatch",
		AnchorPoint = Vector2.new(0, 0),
		Position = UDim2.new(0, 0, 0, 0),
		Size = UDim2.fromOffset(210, 290),
		BackgroundTransparency = 1,
	}, parent)
	self.root = root
	-- cinturino
	for _, info in { { 0, -0.02 }, { 1, 1.02 } } do
		local strap = make("Frame", {
			AnchorPoint = Vector2.new(0.5, info[1]),
			Position = UDim2.fromScale(0.5, info[2] == -0.02 and 0 or 1),
			Size = UDim2.fromOffset(120, 64),
			BackgroundColor3 = Color3.fromRGB(26, 27, 29),
			BorderSizePixel = 0,
			ZIndex = 1,
		}, root)
		corner(strap, 16)
		make("UIGradient", { Rotation = 0, Color = ColorSequence.new({ ColorSequenceKeypoint.new(0, Color3.fromRGB(18, 18, 20)), ColorSequenceKeypoint.new(0.5, Color3.fromRGB(44, 45, 48)), ColorSequenceKeypoint.new(1, Color3.fromRGB(18, 18, 20)) }) }, strap)
		for k = 1, 3 do
			local hole = make("Frame", { AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.new(0.5, 0, info[1] == 0 and 0.2 or 0.8, (k - 2) * 0), Size = UDim2.fromOffset(8, 8), BackgroundColor3 = Color3.fromRGB(8, 8, 9), ZIndex = 1 }, strap)
			corner(hole, 99)
			hole.Position = UDim2.new(0.5, (k - 2) * 26, info[1] == 0 and 0.3 or 0.7, 0)
		end
	end
	-- cassa
	local case = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(204, 204),
		BackgroundColor3 = Color3.fromRGB(70, 74, 78),
		ZIndex = 2,
	}, root)
	corner(case, 52)
	make("UIGradient", { Rotation = 45, Color = ColorSequence.new({ ColorSequenceKeypoint.new(0, Color3.fromRGB(150, 155, 160)), ColorSequenceKeypoint.new(0.35, Color3.fromRGB(60, 63, 67)), ColorSequenceKeypoint.new(1, Color3.fromRGB(30, 32, 34)) }) }, case)
	make("UIStroke", { Color = Color3.fromRGB(20, 21, 22), Thickness = 2 }, case)
	local crown = make("Frame", { AnchorPoint = Vector2.new(0, 0.5), Position = UDim2.new(1, -2, 0.42, 0), Size = UDim2.fromOffset(9, 30), BackgroundColor3 = Color3.fromRGB(90, 94, 98), ZIndex = 1 }, case)
	corner(crown, 4)
	local button = make("Frame", { AnchorPoint = Vector2.new(0, 0.5), Position = UDim2.new(1, -2, 0.68, 0), Size = UDim2.fromOffset(6, 20), BackgroundColor3 = Color3.fromRGB(170, 40, 30), ZIndex = 1 }, case)
	corner(button, 3)
	-- schermo
	local screen = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(FACE, FACE),
		BackgroundColor3 = Color3.fromRGB(4, 6, 7),
		ClipsDescendants = true,
		ZIndex = 3,
	}, case)
	corner(screen, 42)
	make("UIStroke", { Color = Color3.fromRGB(8, 9, 10), Thickness = 3 }, screen)
	self.screen = screen
	self.stamina = ring(screen, 80, 5)
	self.fear = ring(screen, 70, 4)
	self.time = label(screen, { AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 30), Size = UDim2.fromOffset(120, 30), Font = Enum.Font.GothamBold, TextSize = 30, ZIndex = 4 })
	self.compass = label(screen, { AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 60), Size = UDim2.fromOffset(120, 12), TextSize = 10, TextColor3 = MUTED, ZIndex = 4 })
	self.heart = label(screen, { AnchorPoint = Vector2.new(1, 0.5), Position = UDim2.new(0.5, -4, 0, 88), Size = UDim2.fromOffset(24, 24), Text = "♥", TextSize = 18, TextColor3 = RED, ZIndex = 4 })
	self.bpm = label(screen, { AnchorPoint = Vector2.new(0, 0.5), Position = UDim2.new(0.5, 0, 0, 88), Size = UDim2.fromOffset(60, 20), Font = Enum.Font.GothamBold, TextSize = 18, TextXAlignment = Enum.TextXAlignment.Left, ZIndex = 4 })
	label(screen, { AnchorPoint = Vector2.new(0, 0.5), Position = UDim2.new(0.5, 36, 0, 90), Size = UDim2.fromOffset(30, 12), Text = "BPM", TextSize = 8, TextColor3 = MUTED, TextXAlignment = Enum.TextXAlignment.Left, ZIndex = 4 })
	self.torch = battery(screen, UDim2.fromOffset(32, 104), "T")
	self.nv = battery(screen, UDim2.fromOffset(92, 104), "V")
	self.gear = label(screen, { AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 122), Size = UDim2.fromOffset(140, 12), TextSize = 10, TextColor3 = TEXT, RichText = true, ZIndex = 4 })
	self.status = label(screen, { AnchorPoint = Vector2.new(0.5, 0), Position = UDim2.new(0.5, 0, 0, 136), Size = UDim2.fromOffset(120, 12), Font = Enum.Font.GothamBold, TextSize = 10, TextColor3 = TEAL, ZIndex = 4 })
	self.alarm = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = RED, BackgroundTransparency = 1, BorderSizePixel = 0, ZIndex = 5 }, screen)
	self.sos = label(self.alarm, { Size = UDim2.fromScale(1, 1), Text = "SOS", Font = Enum.Font.GothamBlack, TextSize = 44, TextTransparency = 1, ZIndex = 6 })
	-- riflesso del vetro
	local glass = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.new(1, 1, 1), BackgroundTransparency = 0.9, BorderSizePixel = 0, ZIndex = 7 }, screen)
	make("UIGradient", { Rotation = 60, Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(0.35, 1), NumberSequenceKeypoint.new(1, 1) }) }, glass)
	self.rank = label(root, { AnchorPoint = Vector2.new(0.5, 1), Position = UDim2.new(0.5, 0, 1, -4), Size = UDim2.fromOffset(200, 12), TextSize = 10, TextColor3 = MUTED, ZIndex = 2 })

	self.beatPhase = 0
	self.lastAlert = ""
	self.beep = Sfx.new("WatchBeep", SoundService, { Volume = 0.5 })
	return self
end

-- info: { stamina, fear, nv, nvOn, exhausted, panic, closeness, sprinting, dt }
function Watch:update(info, player: Player)
	local status = player:GetAttribute("Status") or "Lobby"
	fill(self.stamina, info.stamina / 100, info.exhausted and Color3.fromRGB(255, 170, 60) or TEAL)
	fill(self.fear, info.fear / 100, info.panic and RED or PURPLE)

	-- battito: sale con paura, corsa e creatura vicina
	local bpm = 66 + info.fear * 0.7 + (info.sprinting and 28 or 0) + info.closeness * 35
	self.beatPhase += info.dt * bpm / 60
	local beat = self.beatPhase % 1
	local pulse = beat < 0.12 and 1 or (beat < 0.3 and 0.5 or 0)
	self.heart.TextSize = 16 + pulse * 6
	self.bpm.Text = tostring(math.floor(bpm))
	self.bpm.TextColor3 = bpm > 130 and RED or TEXT

	local t = Lighting.ClockTime
	self.time.Text = ("%02d:%02d"):format(math.floor(t), math.floor(t % 1 * 60))
	local look = workspace.CurrentCamera.CFrame.LookVector
	local heading = (math.deg(math.atan2(look.X, -look.Z)) + 360) % 360
	local names = { "N", "NE", "E", "SE", "S", "SO", "O", "NO" }
	self.compass.Text = ("%s  %03d°"):format(names[math.floor((heading + 22.5) / 45) % 8 + 1], math.floor(heading))

	setBattery(self.torch, (player:GetAttribute("TorchBattery") or 0) / info.config.EQUIPMENT.TORCH_BATTERY, player:GetAttribute("TorchOn") == true)
	setBattery(self.nv, info.nv, info.nvOn)
	local health = math.floor(player:GetAttribute("Health") or 100)
	self.gear.Text = ("<font color=\"%s\">VITA %d%%</font> · DARDI %d · %s %d"):format(
		health < 40 and "#ff5a46" or "#78e6be",
		health,
		player:GetAttribute("Darts") or 0,
		string.upper(string.sub(player:GetAttribute("CamType") or "Fissa", 1, 4)),
		player:GetAttribute("Kits_" .. (player:GetAttribute("CamType") or "Fissa")) or 0
	)

	local alert = ""
	if status == "Braccato" then
		alert = "SOS"
	elseif info.panic then
		alert = "PANICO"
	elseif (player:GetAttribute("Health") or 100) < 35 then
		alert = "FERITO"
	elseif info.closeness > 0.3 then
		alert = "MOVIMENTO VICINO"
	elseif info.exhausted then
		alert = "FIATONE"
	elseif (player:GetAttribute("TorchBattery") or 1) < 20 then
		alert = "BATTERIA TORCIA"
	end
	self.status.Text = alert ~= "" and alert or "OK"
	self.status.TextColor3 = alert ~= "" and RED or TEAL
	if alert ~= self.lastAlert then
		self.lastAlert = alert
		if alert ~= "" then
			self.beep:Play()
		end
	end
	local sos = status == "Braccato"
	local flash = sos and (os.clock() % 0.8 < 0.4)
	self.alarm.BackgroundTransparency = flash and 0.25 or 1
	self.sos.TextTransparency = sos and 0 or 1

	local stats = player:FindFirstChild("leaderstats")
	local rank = stats and stats:FindFirstChild("Rango")
	local level = stats and stats:FindFirstChild("Livello")
	self.rank.Text = rank and level and ("%s · LIV %d"):format(string.upper(rank.Value), level.Value) or ""
end

return Watch
