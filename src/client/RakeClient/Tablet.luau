-- Tablet di sorveglianza: la visuale passa alla telecamera scelta, dentro la cornice di un tablet
-- rinforzato, con scanline, rumore quando la creatura è vicina, visione IR, zoom e mini-mappa.
-- Ogni frame è protetto da pcall: in caso di errore il tablet lo mostra e resta chiudibile.
local RunService = game:GetService("RunService")
local Lighting = game:GetService("Lighting")
local ContextActionService = game:GetService("ContextActionService")
local UserInputService = game:GetService("UserInputService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local Sfx = require(Shared:WaitForChild("Sfx"))
local MapView = require(script.Parent:WaitForChild("MapView"))

local Tablet = {}
Tablet.__index = Tablet

local STATIC_LINES = 40
local SCANLINES = 70
local BEZEL = Color3.fromRGB(20, 21, 22)
local GREEN = Color3.fromRGB(150, 255, 180)

local function make(className: string, props: { [string]: any }, parent: Instance?): any
	local inst = Instance.new(className)
	for k, v in props do
		(inst :: any)[k] = v
	end
	inst.Parent = parent
	return inst
end

local function label(parent: Instance, props: { [string]: any }): TextLabel
	local t = make("TextLabel", {
		BackgroundTransparency = 1,
		Font = Enum.Font.Code,
		TextColor3 = GREEN,
		TextSize = 16,
		TextStrokeTransparency = 0.6,
		ZIndex = 6,
	}, parent)
	for k, v in props do
		(t :: any)[k] = v
	end
	return t
end

local function corner(parent: Instance, r: number)
	make("UICorner", { CornerRadius = UDim.new(0, r) }, parent)
end

local function rakeRoot(): BasePart?
	local folder = workspace:FindFirstChild("RakeHunt")
	local rake = folder and folder:FindFirstChild("TheRake")
	return rake and rake:FindFirstChild("HumanoidRootPart") :: BasePart?
end

function Tablet.new(player: Player, state: Folder, remotes: Folder)
	local self = setmetatable({}, Tablet)
	self.player = player
	self.state = state
	self.remotes = remotes
	self.isOpen = false
	self.index = 1
	self.zoom = 1
	self.nextMap = 0
	self.lastError = nil

	local gui = make("ScreenGui", {
		Name = "RakeTablet",
		ResetOnSpawn = false,
		IgnoreGuiInset = true,
		Enabled = false,
		DisplayOrder = 5,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	}, player:WaitForChild("PlayerGui"))
	self.gui = gui

	-- Schermo: tutto ciò che sta fuori è coperto dalla cornice (un tratto molto spesso)
	local screen = make("Frame", {
		Name = "Schermo",
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.47),
		Size = UDim2.fromScale(0.84, 0.76),
		BackgroundTransparency = 1,
		ClipsDescendants = true,
		ZIndex = 1,
	}, gui)
	corner(screen, 22)
	local stroke = make("UIStroke", { Thickness = 1600, Color = BEZEL, ApplyStrokeMode = Enum.ApplyStrokeMode.Border }, screen)
	make("UIGradient", {
		Rotation = 90,
		Color = ColorSequence.new(Color3.fromRGB(34, 36, 38), Color3.fromRGB(10, 10, 11)),
	}, stroke)
	self.screen = screen

	self.black = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.fromRGB(2, 4, 3), BorderSizePixel = 0, Visible = false, ZIndex = 2 }, screen)
	self.snow = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.fromRGB(170, 175, 170), BackgroundTransparency = 1, BorderSizePixel = 0, ZIndex = 3 }, screen)
	self.lines = {}
	for i = 1, STATIC_LINES do
		self.lines[i] = make("Frame", { Size = UDim2.new(1, 0, 0, 2), BackgroundColor3 = Color3.fromRGB(235, 235, 235), BorderSizePixel = 0, Visible = false, ZIndex = 3 }, screen)
	end
	for i = 0, SCANLINES - 1 do
		make("Frame", {
			Position = UDim2.fromScale(0, i / SCANLINES),
			Size = UDim2.new(1, 0, 0, 1),
			BackgroundColor3 = Color3.new(0, 0, 0),
			BackgroundTransparency = 0.8,
			BorderSizePixel = 0,
			ZIndex = 4,
		}, screen)
	end
	-- vignetta interna dello schermo
	for _, info in { { 0, UDim2.fromScale(0.25, 1), UDim2.fromScale(0, 0) }, { 180, UDim2.fromScale(0.25, 1), UDim2.fromScale(0.75, 0) }, { 90, UDim2.fromScale(1, 0.25), UDim2.fromScale(0, 0) }, { 270, UDim2.fromScale(1, 0.25), UDim2.fromScale(0, 0.75) } } do
		local f = make("Frame", { Size = info[2], Position = info[3], BackgroundColor3 = Color3.new(0, 0, 0), BorderSizePixel = 0, ZIndex = 4 }, screen)
		make("UIGradient", { Rotation = info[1], Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.35), NumberSequenceKeypoint.new(1, 1) }) }, f)
	end
	-- angoli del mirino e croce centrale
	for _, c in { { 0, 0 }, { 1, 0 }, { 0, 1 }, { 1, 1 } } do
		local x, y = c[1], c[2]
		local px = UDim2.new(x, x == 0 and 40 or -40, y, y == 0 and 50 or -50)
		make("Frame", { AnchorPoint = Vector2.new(x, y), Position = px, Size = UDim2.fromOffset(34, 2), BackgroundColor3 = GREEN, BackgroundTransparency = 0.35, BorderSizePixel = 0, ZIndex = 5 }, screen)
		make("Frame", { AnchorPoint = Vector2.new(x, y), Position = px, Size = UDim2.fromOffset(2, 34), BackgroundColor3 = GREEN, BackgroundTransparency = 0.35, BorderSizePixel = 0, ZIndex = 5 }, screen)
	end
	label(screen, { Text = "+", TextSize = 22, AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(30, 30), TextTransparency = 0.4 })

	-- barra di stato
	self.rec = label(screen, { Position = UDim2.fromOffset(22, 14), Size = UDim2.fromOffset(90, 22), TextXAlignment = Enum.TextXAlignment.Left, TextColor3 = Color3.fromRGB(255, 70, 70), Font = Enum.Font.Code })
	self.header = label(screen, { Position = UDim2.fromOffset(110, 14), Size = UDim2.new(1, -420, 0, 22), TextXAlignment = Enum.TextXAlignment.Left })
	self.clock = label(screen, { AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -150, 0, 14), Size = UDim2.fromOffset(140, 22), TextXAlignment = Enum.TextXAlignment.Right })
	local battery = make("Frame", { AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -60, 0, 18), Size = UDim2.fromOffset(38, 15), BackgroundTransparency = 1, ZIndex = 6 }, screen)
	make("UIStroke", { Color = GREEN, Thickness = 1.5 }, battery)
	self.batteryFill = make("Frame", { Position = UDim2.fromOffset(2, 2), Size = UDim2.new(1, -4, 1, -4), BackgroundColor3 = GREEN, BorderSizePixel = 0, ZIndex = 6 }, battery)
	self.signal = {}
	for i = 1, 4 do
		self.signal[i] = make("Frame", {
			AnchorPoint = Vector2.new(0, 1),
			Position = UDim2.new(1, -118 + i * 7, 0, 33),
			Size = UDim2.fromOffset(5, 4 + i * 3),
			BackgroundColor3 = GREEN,
			BorderSizePixel = 0,
			ZIndex = 6,
		}, screen)
	end
	self.alert = label(screen, {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 48),
		Size = UDim2.fromOffset(420, 32),
		TextSize = 20,
		Font = Enum.Font.GothamBold,
		TextColor3 = Color3.fromRGB(255, 255, 255),
		BackgroundColor3 = Color3.fromRGB(170, 20, 20),
		BackgroundTransparency = 1,
	})
	self.message = label(screen, {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.45),
		Size = UDim2.new(0.8, 0, 0, 100),
		TextSize = 22,
		TextWrapped = true,
		ZIndex = 7,
	})
	self.info = label(screen, {
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, 22, 1, -14),
		Size = UDim2.fromOffset(420, 40),
		TextSize = 14,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Bottom,
	})

	-- pannello obiettivi e stato della caccia
	local panel = make("Frame", {
		Position = UDim2.fromOffset(22, 48),
		Size = UDim2.fromOffset(280, 0),
		AutomaticSize = Enum.AutomaticSize.Y,
		BackgroundColor3 = Color3.fromRGB(4, 14, 8),
		BackgroundTransparency = 0.25,
		ZIndex = 6,
	}, screen)
	corner(panel, 8)
	make("UIStroke", { Color = GREEN, Transparency = 0.6 }, panel)
	make("UIPadding", { PaddingLeft = UDim.new(0, 10), PaddingRight = UDim.new(0, 10), PaddingTop = UDim.new(0, 8), PaddingBottom = UDim.new(0, 8) }, panel)
	self.panelText = label(panel, {
		Size = UDim2.new(1, 0, 0, 0),
		AutomaticSize = Enum.AutomaticSize.Y,
		TextSize = 13,
		TextWrapped = true,
		RichText = true,
		TextXAlignment = Enum.TextXAlignment.Left,
		TextYAlignment = Enum.TextYAlignment.Top,
		ZIndex = 7,
	})
	self.panel = panel

	-- mappa: piccola nell'angolo, a tutto schermo con M o con il tasto MAPPA
	self.miniMap = MapView.new(screen, 230, 6)
	self.miniMap.frame.AnchorPoint = Vector2.new(1, 1)
	self.miniMap.frame.Position = UDim2.new(1, -18, 1, -18)
	self.bigMapHolder = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = Color3.fromRGB(4, 8, 6),
		Visible = false,
		ZIndex = 20,
	}, screen)
	self.bigMap = nil
	self.mapMode = false

	-- cornice: marchio, sensore e tasti fisici
	label(gui, { Text = "BLACKWOOD RANGER · TRK-7", Font = Enum.Font.GothamBold, TextSize = 13, TextColor3 = Color3.fromRGB(110, 112, 110), AnchorPoint = Vector2.new(0, 1), Position = UDim2.new(0.08, 0, 0.09, -2), Size = UDim2.fromOffset(260, 18), TextXAlignment = Enum.TextXAlignment.Left, ZIndex = 8 })
	local lensDot = make("Frame", { AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.045), Size = UDim2.fromOffset(10, 10), BackgroundColor3 = Color3.fromRGB(8, 10, 14), ZIndex = 8 }, gui)
	corner(lensDot, 99)
	make("UIStroke", { Color = Color3.fromRGB(50, 52, 56), Thickness = 2 }, lensDot)
	self.powerLed = make("Frame", { AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.new(0.92, 0, 0.045, 0), Size = UDim2.fromOffset(7, 7), BackgroundColor3 = Color3.fromRGB(80, 255, 120), ZIndex = 8 }, gui)
	corner(self.powerLed, 99)

	local function key(text: string, x: number, callback: () -> ()): TextButton
		local b = make("TextButton", {
			Text = text,
			Font = Enum.Font.GothamBold,
			TextSize = 18,
			TextColor3 = Color3.fromRGB(190, 195, 190),
			BackgroundColor3 = Color3.fromRGB(38, 40, 42),
			AutoButtonColor = true,
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(0.5, x, 0.93, 0),
			Size = UDim2.fromOffset(62, 36),
			ZIndex = 8,
		}, gui)
		corner(b, 8)
		make("UIStroke", { Color = Color3.fromRGB(70, 72, 74), Thickness = 1.5, ApplyStrokeMode = Enum.ApplyStrokeMode.Border }, b)
		b.Activated:Connect(callback)
		return b
	end
	key("◀", -170, function()
		self:switch(-1)
	end)
	self.rotL = key("⟲", -85, function()
		self:rotate(-1)
	end)
	key("✕", 0, function()
		self:close()
	end)
	self.rotR = key("⟳", 85, function()
		self:rotate(1)
	end)
	key("▶", 170, function()
		self:switch(1)
	end)
	local mapKey = key("MAPPA", 270, function()
		self:toggleMap()
	end)
	mapKey.Size = UDim2.fromOffset(90, 36)
	label(gui, {
		Text = "Q/E camera · Z/C ruota · rotella zoom · M mappa · T chiudi",
		Font = Enum.Font.Gotham,
		TextSize = 12,
		TextColor3 = Color3.fromRGB(100, 104, 100),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.975),
		Size = UDim2.fromOffset(400, 16),
		ZIndex = 8,
	})

	self.cc = make("ColorCorrectionEffect", { Name = "TabletFeed", Enabled = false }, Lighting)
	self.staticSound = Sfx.new("Static", SoundService, { Volume = 0 })
	return self
end

function Tablet:cameras(): { Model }
	local folder = workspace:FindFirstChild("RakeHunt")
	folder = folder and folder:FindFirstChild("Telecamere")
	local list = {}
	if folder then
		for _, m in folder:GetChildren() do
			if m:IsA("Model") and m:FindFirstChild("Body") then
				table.insert(list, m)
			end
		end
	end
	table.sort(list, function(a, b)
		return (a:GetAttribute("Id") or 0) < (b:GetAttribute("Id") or 0)
	end)
	return list
end

function Tablet:current(): Model?
	local list = self:cameras()
	if #list == 0 then
		return nil
	end
	self.index = (self.index - 1) % #list + 1
	return list[self.index]
end

function Tablet:switch(dir: number)
	self.index += dir
	self.zoom = 1
end

function Tablet:rotate(dir: number)
	local m = self:current()
	if m and m:GetAttribute("Type") == "Motorizzata" then
		self.remotes.RotateCamera:FireServer(m:GetAttribute("Id"), dir)
	end
end

function Tablet:toggle()
	if self.isOpen then
		self:close()
	else
		self:open()
	end
end

function Tablet:open()
	if self.isOpen or self.player:GetAttribute("Status") == "Braccato" then
		return
	end
	self.isOpen = true
	self.lastError = nil
	self.gui.Enabled = true
	local camera = workspace.CurrentCamera
	camera.CameraType = Enum.CameraType.Scriptable
	self.staticSound:Play()

	local function bind(name: string, keys: { Enum.KeyCode }, fn: (Enum.KeyCode) -> ())
		ContextActionService:BindActionAtPriority(name, function(_, inputState, input)
			if inputState == Enum.UserInputState.Begin then
				fn(input.KeyCode)
			end
			return Enum.ContextActionResult.Sink
		end, false, 3000, table.unpack(keys))
	end
	bind("TabletPrev", { Enum.KeyCode.Q, Enum.KeyCode.Left, Enum.KeyCode.DPadLeft }, function()
		self:switch(-1)
	end)
	bind("TabletNext", { Enum.KeyCode.E, Enum.KeyCode.Right, Enum.KeyCode.DPadRight }, function()
		self:switch(1)
	end)
	bind("TabletRotate", { Enum.KeyCode.Z, Enum.KeyCode.C }, function(code)
		self:rotate(code == Enum.KeyCode.Z and -1 or 1)
	end)
	bind("TabletMap", { Enum.KeyCode.M }, function()
		self:toggleMap()
	end)
	self.wheel = UserInputService.InputChanged:Connect(function(input)
		if input.UserInputType == Enum.UserInputType.MouseWheel then
			self.zoom = math.clamp(self.zoom + input.Position.Z * 0.25, 1, 3)
		end
	end)

	RunService:BindToRenderStep("RakeTablet", Enum.RenderPriority.Camera.Value + 1, function()
		local ok, err = pcall(self.render, self)
		if not ok and err ~= self.lastError then
			self.lastError = err
			warn("[Tablet] " .. tostring(err))
			self.black.Visible = true
			self.message.Text = "ERRORE DEL TABLET\n" .. tostring(err)
		end
	end)
end

-- Accende in locale l'illuminatore IR della camera che stai guardando (e alza l'esposizione)
function Tablet:setIlluminator(light: SpotLight?)
	if self.illuminator == light then
		return
	end
	if self.illuminator then
		self.illuminator.Enabled = false
	end
	self.illuminator = light
	if light then
		light.Enabled = true
		if not self.savedExposure then
			self.savedExposure = Lighting.ExposureCompensation
		end
		Lighting.ExposureCompensation = (self.savedExposure or 0) + 1.3
	elseif self.savedExposure then
		Lighting.ExposureCompensation = self.savedExposure
		self.savedExposure = nil
	end
end

function Tablet:close()
	if not self.isOpen then
		return
	end
	self:setIlluminator(nil)
	self.isOpen = false
	self.gui.Enabled = false
	self.cc.Enabled = false
	self.staticSound:Stop()
	RunService:UnbindFromRenderStep("RakeTablet")
	for _, name in { "TabletPrev", "TabletNext", "TabletRotate", "TabletMap" } do
		ContextActionService:UnbindAction(name)
	end
	if self.wheel then
		self.wheel:Disconnect()
		self.wheel = nil
	end
	local camera = workspace.CurrentCamera
	camera.CameraType = Enum.CameraType.Custom
	camera.FieldOfView = 70
	local hum = self.player.Character and self.player.Character:FindFirstChildOfClass("Humanoid")
	if hum then
		camera.CameraSubject = hum
	end
end

function Tablet:setStatic(noise: number)
	self.snow.BackgroundTransparency = 1 - noise * 0.5
	for _, line in self.lines do
		if math.random() < noise then
			line.Visible = true
			line.Position = UDim2.fromScale(0, math.random())
			line.BackgroundTransparency = 0.2 + math.random() * 0.6
			line.Size = UDim2.new(1, 0, 0, math.random(1, 5))
		else
			line.Visible = false
		end
	end
	self.staticSound.Volume = 0.05 + noise * 0.6
	for i, bar in self.signal do
		bar.BackgroundTransparency = (i / 4 > 1 - noise * 0.9 + 0.05) and 0.8 or 0
	end
end

function Tablet:render()
	if self.player:GetAttribute("Status") == "Braccato" then
		self:close()
		return
	end
	local camera = workspace.CurrentCamera
	local m = self:current()
	local blink = os.clock() % 1 < 0.55
	local t = Lighting.ClockTime
	self.clock.Text = ("%02d:%02d:%02d"):format(math.floor(t), math.floor(t % 1 * 60), math.floor(os.clock() * 7 % 60))
	self.alert.Text = ""
	self.alert.BackgroundTransparency = 1
	self.rotL.Visible = false
	self.rotR.Visible = false
	self.powerLed.BackgroundTransparency = blink and 0 or 0.6

	if not m then
		self:setIlluminator(nil)
		self.black.Visible = true
		self.cc.Enabled = false
		self:setStatic(0.2)
		self.header.Text = "NESSUNA TELECAMERA"
		self.rec.Text = ""
		self.info.Text = ""
		self.batteryFill.Size = UDim2.new(0, 0, 1, -4)
		self.message.Text = "Nessuna telecamera piazzata.\nEquipaggia la Telecamera [2] e fai clic per piazzarla."
	else
		local id = m:GetAttribute("Id") or 0
		local camType = m:GetAttribute("Type") or "Fissa"
		local online = m:GetAttribute("Online")
		local battery = math.clamp((m:GetAttribute("Battery") or 0) / Config.CAMERAS.BATTERY, 0, 1)
		self.header.Text = ("CAM %02d · %s · %s"):format(id, string.upper(camType), string.upper(m:GetAttribute("Label") or ""))
		self.batteryFill.Size = UDim2.new(battery, -4, 1, -4)
		self.batteryFill.BackgroundColor3 = battery < 0.2 and Color3.fromRGB(255, 80, 60) or GREEN
		local nightNow = Lighting.ClockTime >= 19.5 or Lighting.ClockTime < 6
		self.info.Text = ("ZOOM %.1fx · %s\nproprietario: %s"):format(self.zoom, nightNow and "VISIONE NOTTURNA IR" or "DIURNA", m:GetAttribute("OwnerName") or "?")

		if not online or camType == "Trappola" then
			self:setIlluminator(nil)
		end
		if not online then
			self.black.Visible = true
			self.cc.Enabled = false
			self:setStatic(0.7)
			self.rec.Text = ""
			self.message.Text = "NESSUN SEGNALE\nBatteria esaurita: recupera la camera per ricaricarla."
		elseif camType == "Trappola" then
			self.black.Visible = true
			self.cc.Enabled = false
			self:setStatic(0.05)
			self.rec.Text = blink and "● ARMATA" or ""
			self.message.Text = "CAMERA TRAPPOLA\nNessun video in diretta: scatta una foto quando rileva un movimento."
		else
			self.black.Visible = false
			self.message.Text = ""
			self.rec.Text = blink and "● REC" or ""
			local body = m:FindFirstChild("Body") :: BasePart
			local noise = 0
			local root = rakeRoot()
			if root then
				noise = math.clamp(1 - (root.Position - body.Position).Magnitude / Config.CAMERAS.DISTORT_RANGE, 0, 1)
			end
			for _, w in Config.WEATHER do
				if w.name == self.state:GetAttribute("Weather") then
					noise = math.max(noise, w.cameraNoise * 0.35)
				end
			end
			local jitter = noise * 0.035
			camera.CFrame = body.CFrame
				* CFrame.new(0, 0, -1.25)
				* CFrame.Angles((math.random() - 0.5) * jitter, (math.random() - 0.5) * jitter, 0)
			camera.FieldOfView = Config.CAMERAS.FOV / self.zoom
			self:setStatic(noise)

			local night = Lighting.ClockTime >= 19.5 or Lighting.ClockTime < 6
			local cc = self.cc
			cc.Enabled = true
			-- visione notturna a infrarossi di serie su tutte le telecamere
			self:setIlluminator(night and body:FindFirstChild("Illuminatore") :: SpotLight? or nil)
			if night then
				cc.TintColor = Color3.fromRGB(170, 255, 175)
				cc.Brightness = camType == "IR" and 0.3 or 0.24
				cc.Contrast = 0.4 + noise * 0.4
				cc.Saturation = -1
			else
				cc.TintColor = Color3.fromRGB(230, 240, 255)
				cc.Brightness = night and 0.04 or 0
				cc.Contrast = 0.2 + noise * 0.6
				cc.Saturation = -0.7
			end
			if m:GetAttribute("Sees") then
				self.alert.Text = "⚠ MOVIMENTO RILEVATO"
				self.alert.BackgroundTransparency = blink and 0.2 or 0.6
			elseif noise > 0.45 then
				self.alert.Text = blink and "INTERFERENZA" or ""
			end
			local motorized = camType == "Motorizzata"
			self.rotL.Visible = motorized
			self.rotR.Visible = motorized
		end
	end

	if os.clock() >= self.nextMap then
		self.nextMap = os.clock() + 0.2
		self:updatePanel()
		if self.mapMode and self.bigMap then
			self.bigMap:update(self.player, self.state, m)
		else
			self.miniMap:update(self.player, self.state, m)
		end
	end
end

local STATUS_TEXT = {
	OK = "<font color=\"#8fe6a0\">●</font>",
	Braccato = "<font color=\"#ff7060\">⚠</font>",
	Fuori = "<font color=\"#888888\">✖</font>",
	Lobby = "<font color=\"#aaaaaa\">○</font>",
}

function Tablet:updatePanel()
	local state = self.state
	local tracking = math.floor(state:GetAttribute("Tracking") or 0)
	local bar = string.rep("█", math.floor(tracking / 10)) .. string.rep("░", 10 - math.floor(tracking / 10))
	local zone = state:GetAttribute("ZoneHint") or ""
	local lines = {
		("<b>OBIETTIVO · %s</b>"):format(string.upper(state:GetAttribute("Objective") or "—")),
		state:GetAttribute("ObjectiveText") or "",
		("<font color=\"#ffd75a\">%s</font>"):format(state:GetAttribute("ObjectiveProgress") or ""),
		"",
		("TRACCIAMENTO %s %d%%"):format(bar, tracking),
		"ZONA DI CACCIA: " .. (zone ~= "" and string.upper(zone) or "SCONOSCIUTA"),
		("COPERTURA %d%% · CAMERE %d · PROVE %d"):format(state:GetAttribute("Coverage") or 0, state:GetAttribute("CamerasActive") or 0, state:GetAttribute("Evidence") or 0),
		("MINACCIA: %s · METEO: %s"):format(string.upper(state:GetAttribute("RakeState") or "—"), string.upper(state:GetAttribute("Weather") or "—")),
		"",
		"<b>SQUADRA</b>",
	}
	for _, p in game:GetService("Players"):GetPlayers() do
		table.insert(lines, ("%s %s  %d%%"):format(STATUS_TEXT[p:GetAttribute("Status") or "Lobby"] or "", p.DisplayName, math.floor(p:GetAttribute("Health") or 100)))
	end
	self.panelText.Text = table.concat(lines, "\n")
	self.panel.Visible = not self.mapMode
end

function Tablet:toggleMap()
	self.mapMode = not self.mapMode
	if self.mapMode and not self.bigMap then
		local size = math.floor(math.min(self.screen.AbsoluteSize.X, self.screen.AbsoluteSize.Y) * 0.92)
		self.bigMap = MapView.new(self.bigMapHolder, math.max(size, 300), 21)
		self.bigMap.frame.AnchorPoint = Vector2.new(0.5, 0.5)
		self.bigMap.frame.Position = UDim2.fromScale(0.5, 0.5)
	end
	self.bigMapHolder.Visible = self.mapMode
	self.miniMap.frame.Visible = not self.mapMode
	self.nextMap = 0
end

return Tablet
