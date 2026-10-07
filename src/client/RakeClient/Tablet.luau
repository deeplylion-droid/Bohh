-- Tablet di sorveglianza: mostra i feed delle telecamere (la visuale si sposta sulla camera),
-- con interferenze quando la creatura è vicina, visione IR e una mini-mappa del bosco.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local Lighting = game:GetService("Lighting")
local ContextActionService = game:GetService("ContextActionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))

local Tablet = {}
Tablet.__index = Tablet

local MAP_PX = 210
local HALF = Config.MAP.SIZE / 2
local STATIC_LINES = 36

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
		TextColor3 = Color3.fromRGB(220, 235, 220),
		TextSize = 16,
		TextStrokeTransparency = 0.5,
	}, parent)
	for k, v in props do
		(t :: any)[k] = v
	end
	return t
end

local function button(parent: Instance, text: string, pos: UDim2, callback: () -> ())
	local b = make("TextButton", {
		Text = text,
		Font = Enum.Font.GothamBold,
		TextSize = 18,
		TextColor3 = Color3.fromRGB(230, 235, 225),
		BackgroundColor3 = Color3.fromRGB(25, 30, 28),
		BackgroundTransparency = 0.2,
		Size = UDim2.new(0, 64, 0, 44),
		Position = pos,
		AnchorPoint = Vector2.new(0.5, 1),
		AutoButtonColor = true,
	}, parent)
	make("UICorner", { CornerRadius = UDim.new(0, 8) }, b)
	b.Activated:Connect(callback)
	return b
end

local function toMap(x: number, z: number): UDim2
	return UDim2.fromOffset((x + HALF) / (HALF * 2) * MAP_PX, (z + HALF) / (HALF * 2) * MAP_PX)
end

function Tablet.new(player: Player, state: Folder, remotes: Folder, hud)
	local self = setmetatable({}, Tablet)
	self.player = player
	self.state = state
	self.remotes = remotes
	self.hud = hud
	self.isOpen = false
	self.index = 1
	self.nextMap = 0

	local gui = make("ScreenGui", {
		Name = "RakeTablet",
		ResetOnSpawn = false,
		IgnoreGuiInset = true,
		Enabled = false,
		DisplayOrder = 5,
	}, player:WaitForChild("PlayerGui"))
	self.gui = gui

	self.black = make("Frame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = Color3.fromRGB(0, 0, 0),
		BorderSizePixel = 0,
		Visible = false,
	}, gui)
	self.snow = make("Frame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = Color3.fromRGB(160, 160, 160),
		BackgroundTransparency = 1,
		BorderSizePixel = 0,
	}, gui)
	self.lines = {}
	for i = 1, STATIC_LINES do
		self.lines[i] = make("Frame", {
			Size = UDim2.new(1, 0, 0, 2),
			BackgroundColor3 = Color3.fromRGB(230, 230, 230),
			BorderSizePixel = 0,
			Visible = false,
		}, gui)
	end
	-- Cornice del tablet
	make("UIStroke", { Thickness = 14, Color = Color3.fromRGB(18, 18, 18) }, make("Frame", {
		Size = UDim2.new(1, -14, 1, -14),
		Position = UDim2.fromOffset(7, 7),
		BackgroundTransparency = 1,
	}, gui))

	self.header = label(gui, {
		Position = UDim2.fromOffset(28, 22),
		Size = UDim2.new(1, -300, 0, 24),
		TextXAlignment = Enum.TextXAlignment.Left,
	})
	self.rec = label(gui, {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -28, 0, 22),
		Size = UDim2.new(0, 200, 0, 24),
		TextXAlignment = Enum.TextXAlignment.Right,
		TextColor3 = Color3.fromRGB(255, 70, 70),
	})
	self.alert = label(gui, {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 56),
		Size = UDim2.new(0, 500, 0, 30),
		TextSize = 22,
		TextColor3 = Color3.fromRGB(255, 80, 70),
		Font = Enum.Font.GothamBold,
	})
	self.message = label(gui, {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.45),
		Size = UDim2.new(0, 600, 0, 80),
		TextSize = 22,
		TextWrapped = true,
	})
	self.hint = label(gui, {
		AnchorPoint = Vector2.new(0.5, 1),
		Position = UDim2.new(0.5, 0, 1, -82),
		Size = UDim2.new(0, 600, 0, 20),
		TextSize = 13,
		TextColor3 = Color3.fromRGB(170, 180, 170),
		Text = "Q/E cambia camera · Z/C ruota (motorizzata) · T chiudi",
	})

	button(gui, "◀", UDim2.new(0.5, -150, 1, -26), function() self:switch(-1) end)
	self.rotL = button(gui, "⟲", UDim2.new(0.5, -75, 1, -26), function() self:rotate(-1) end)
	self.rotR = button(gui, "⟳", UDim2.new(0.5, 75, 1, -26), function() self:rotate(1) end)
	button(gui, "▶", UDim2.new(0.5, 150, 1, -26), function() self:switch(1) end)
	button(gui, "✕", UDim2.new(0.5, 0, 1, -26), function() self:close() end)

	-- Mini-mappa
	local map = make("Frame", {
		AnchorPoint = Vector2.new(1, 1),
		Position = UDim2.new(1, -24, 1, -24),
		Size = UDim2.fromOffset(MAP_PX, MAP_PX),
		BackgroundColor3 = Color3.fromRGB(14, 24, 16),
		BackgroundTransparency = 0.15,
		BorderSizePixel = 0,
		ClipsDescendants = true,
	}, gui)
	make("UIStroke", { Color = Color3.fromRGB(90, 120, 90) }, map)
	self.map = map
	self.dots = make("Folder", { Name = "Punti" }, map)
	for _, poi in Config.MAP.POIS do
		local dot = make("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = toMap(poi.pos.X, poi.pos.Z),
			Size = UDim2.fromOffset(6, 6),
			BackgroundColor3 = Color3.fromRGB(230, 220, 170),
			BorderSizePixel = 0,
			ZIndex = 2,
		}, map)
		label(dot, {
			Text = poi.name,
			TextSize = 10,
			Font = Enum.Font.Gotham,
			Size = UDim2.fromOffset(120, 12),
			Position = UDim2.fromOffset(-57, 7),
			TextColor3 = Color3.fromRGB(200, 200, 170),
		})
	end
	local lake = Config.MAP.LAKE
	local lakeDot = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = toMap(lake.center.X, lake.center.Z),
		Size = UDim2.fromOffset(lake.radius / HALF * MAP_PX, lake.radius / HALF * MAP_PX),
		BackgroundColor3 = Color3.fromRGB(40, 70, 110),
		BorderSizePixel = 0,
	}, map)
	make("UICorner", { CornerRadius = UDim.new(1, 0) }, lakeDot)

	self.cc = make("ColorCorrectionEffect", { Name = "TabletFeed", Enabled = false }, Lighting)
	return self
end

function Tablet:cameras(): { Model }
	local folder = workspace:FindFirstChild("RakeHunt") and workspace.RakeHunt:FindFirstChild("Telecamere")
	local list = {}
	if folder then
		for _, m in folder:GetChildren() do
			if m:IsA("Model") and m.PrimaryPart then
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
	self.gui.Enabled = true
	local camera = workspace.CurrentCamera
	self.savedFov = camera.FieldOfView
	camera.CameraType = Enum.CameraType.Scriptable

	ContextActionService:BindActionAtPriority("TabletPrev", function(_, inputState)
		if inputState == Enum.UserInputState.Begin then
			self:switch(-1)
		end
		return Enum.ContextActionResult.Sink
	end, false, 3000, Enum.KeyCode.Q, Enum.KeyCode.Left, Enum.KeyCode.DPadLeft)
	ContextActionService:BindActionAtPriority("TabletNext", function(_, inputState)
		if inputState == Enum.UserInputState.Begin then
			self:switch(1)
		end
		return Enum.ContextActionResult.Sink
	end, false, 3000, Enum.KeyCode.E, Enum.KeyCode.Right, Enum.KeyCode.DPadRight)
	ContextActionService:BindActionAtPriority("TabletRotate", function(_, inputState, input)
		if inputState == Enum.UserInputState.Begin then
			self:rotate(input.KeyCode == Enum.KeyCode.Z and -1 or 1)
		end
		return Enum.ContextActionResult.Sink
	end, false, 3000, Enum.KeyCode.Z, Enum.KeyCode.C)

	RunService:BindToRenderStep("RakeTablet", Enum.RenderPriority.Camera.Value + 1, function()
		self:render()
	end)
end

function Tablet:close()
	if not self.isOpen then
		return
	end
	self.isOpen = false
	self.gui.Enabled = false
	self.cc.Enabled = false
	RunService:UnbindFromRenderStep("RakeTablet")
	for _, name in { "TabletPrev", "TabletNext", "TabletRotate" } do
		ContextActionService:UnbindAction(name)
	end
	local camera = workspace.CurrentCamera
	camera.CameraType = Enum.CameraType.Custom
	camera.FieldOfView = self.savedFov or 70
	local hum = self.player.Character and self.player.Character:FindFirstChildOfClass("Humanoid")
	if hum then
		camera.CameraSubject = hum
	end
end

local function rakeRoot(): BasePart?
	local folder = workspace:FindFirstChild("RakeHunt")
	local rake = folder and folder:FindFirstChild("TheRake")
	return rake and rake:FindFirstChild("HumanoidRootPart") :: BasePart?
end

function Tablet:setStatic(noise: number)
	self.snow.BackgroundTransparency = 1 - noise * 0.45
	for _, line in self.lines do
		if math.random() < noise then
			line.Visible = true
			line.Position = UDim2.fromScale(0, math.random())
			line.BackgroundTransparency = 0.2 + math.random() * 0.6
			line.Size = UDim2.new(1, 0, 0, math.random(1, 4))
		else
			line.Visible = false
		end
	end
end

function Tablet:render()
	if self.player:GetAttribute("Status") == "Braccato" then
		self:close()
		return
	end
	local camera = workspace.CurrentCamera
	local m = self:current()
	local blink = os.clock() % 1 < 0.5
	self.alert.Text = ""
	self.rotL.Visible = false
	self.rotR.Visible = false

	if not m then
		self.black.Visible = true
		self.cc.Enabled = false
		self:setStatic(0.15)
		self.header.Text = "NESSUNA TELECAMERA"
		self.rec.Text = ""
		self.message.Text = "Nessuna telecamera piazzata.\nEquipaggia la Telecamera [2] e fai clic per piazzarla."
	else
		local id = m:GetAttribute("Id") or 0
		local camType = m:GetAttribute("Type") or "Fissa"
		local online = m:GetAttribute("Online")
		local battery = (m:GetAttribute("Battery") or 0) / Config.CAMERAS.BATTERY
		self.header.Text = ("CAM %02d · %s · %s · batt. %d%%"):format(id, string.upper(camType), m:GetAttribute("Label") or "", math.floor(battery * 100))

		if not online then
			self.black.Visible = true
			self.cc.Enabled = false
			self:setStatic(0.6)
			self.rec.Text = ""
			self.message.Text = "NESSUN SEGNALE\nBatteria esaurita: recupera la camera per ricaricarla."
		elseif camType == "Trappola" then
			self.black.Visible = true
			self.cc.Enabled = false
			self:setStatic(0.05)
			self.rec.Text = blink and "● ARMATA" or ""
			self.message.Text = "Camera trappola: nessun feed live.\nScatta una foto quando rileva movimento davanti a sé."
		else
			self.black.Visible = false
			self.message.Text = ""
			self.rec.Text = blink and "● REC" or ""
			local body = m.PrimaryPart :: BasePart
			local noise = 0
			local root = rakeRoot()
			if root then
				noise = math.clamp(1 - (root.Position - body.Position).Magnitude / Config.CAMERAS.DISTORT_RANGE, 0, 1)
			end
			for _, w in Config.WEATHER do
				if w.name == self.state:GetAttribute("Weather") then
					noise = math.max(noise, w.cameraNoise * 0.4)
				end
			end
			local jitter = noise * 0.03
			camera.CFrame = body.CFrame
				* CFrame.new(0, 0, -1)
				* CFrame.Angles((math.random() - 0.5) * jitter, (math.random() - 0.5) * jitter, 0)
			camera.FieldOfView = Config.CAMERAS.FOV
			self:setStatic(noise)

			local night = Lighting.ClockTime >= 19.5 or Lighting.ClockTime < 6
			local cc = self.cc
			cc.Enabled = true
			if camType == "IR" then
				cc.TintColor = Color3.fromRGB(150, 255, 160)
				cc.Brightness = 0.35
				cc.Contrast = 0.35
				cc.Saturation = -1
			else
				cc.TintColor = Color3.fromRGB(255, 255, 255)
				cc.Brightness = night and -0.05 or 0
				cc.Contrast = 0.15 + noise * 0.5
				cc.Saturation = -0.6
			end
			if m:GetAttribute("Sees") then
				self.alert.Text = "⚠ MOVIMENTO RILEVATO"
			elseif noise > 0.45 then
				self.alert.Text = blink and "INTERFERENZA" or ""
			end
			local motorized = camType == "Motorizzata"
			self.rotL.Visible = motorized
			self.rotR.Visible = motorized
		end
	end

	if os.clock() >= self.nextMap then
		self.nextMap = os.clock() + 0.25
		self:drawMap(m)
	end
end

local function dot(parent: Instance, x: number, z: number, size: number, color: Color3, round: boolean?)
	local f = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = toMap(x, z),
		Size = UDim2.fromOffset(size, size),
		BackgroundColor3 = color,
		BorderSizePixel = 0,
		ZIndex = 3,
	}, parent)
	if round then
		make("UICorner", { CornerRadius = UDim.new(1, 0) }, f)
	end
	return f
end

function Tablet:drawMap(selected: Model?)
	local layer = self.dots
	layer:ClearAllChildren()
	local state = self.state

	local hintR = state:GetAttribute("HintR") or 0
	if hintR > 0 then
		local size = hintR / HALF * MAP_PX
		local area = dot(layer, state:GetAttribute("HintX") or 0, state:GetAttribute("HintZ") or 0, size, Color3.fromRGB(255, 40, 40), true)
		area.BackgroundTransparency = 0.65
		area.ZIndex = 1
	end
	local seenAt = state:GetAttribute("LastSeenTime") or 0
	local age = workspace:GetServerTimeNow() - seenAt
	if seenAt > 0 and age < 60 then
		local x = dot(layer, state:GetAttribute("LastSeenX") or 0, state:GetAttribute("LastSeenZ") or 0, 9, Color3.fromRGB(255, 60, 60))
		x.Rotation = 45
		x.BackgroundTransparency = math.clamp(age / 60, 0, 0.8)
	end

	for _, m in self:cameras() do
		local body = m.PrimaryPart
		local color = Color3.fromRGB(90, 160, 255)
		if not m:GetAttribute("Online") then
			color = Color3.fromRGB(90, 90, 90)
		elseif m:GetAttribute("Type") == "Trappola" then
			color = Color3.fromRGB(255, 160, 60)
		end
		if m == selected then
			color = Color3.fromRGB(255, 240, 80)
		end
		local d = dot(layer, body.Position.X, body.Position.Z, m == selected and 8 or 6, color, true)
		local look = body.CFrame.LookVector
		local tick = make("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.new(0.5, look.X * 7, 0.5, look.Z * 7),
			Size = UDim2.fromOffset(3, 3),
			BackgroundColor3 = color,
			BorderSizePixel = 0,
		}, d)
		tick.ZIndex = 3
	end

	for _, p in Players:GetPlayers() do
		local hrp = p.Character and p.Character:FindFirstChild("HumanoidRootPart")
		local status = p:GetAttribute("Status")
		if hrp and status ~= "Fuori" then
			local color = status == "Braccato" and Color3.fromRGB(255, 80, 80) or Color3.fromRGB(110, 230, 110)
			if p == self.player then
				color = Color3.fromRGB(255, 255, 255)
			end
			dot(layer, hrp.Position.X, hrp.Position.Z, 6, color, true)
		end
	end
end

return Tablet
