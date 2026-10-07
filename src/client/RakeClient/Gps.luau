-- GPS da escursionismo (in basso a destra): mappa topografica generata dal terreno (rilievo
-- ombreggiato, curve di livello, acqua, sentieri, rocce) che scorre intorno al giocatore, con
-- punti di interesse, telecamere, compagni, area di caccia e ultimo avvistamento. M cambia lo zoom.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local ContextActionService = game:GetService("ContextActionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))

local Gps = {}
Gps.__index = Gps

local HALF = Config.MAP.SIZE / 2
local CELLS = 80
local CELL_STUDS = Config.MAP.SIZE / CELLS
local CELL_PX = 5
local MAP_PX = CELLS * CELL_PX
local SCREEN = 210
local ZOOMS = { 1, 1.7, 2.6 }

local M = Enum.Material
local PALETTE = {
	[M.Grass] = Color3.fromRGB(62, 88, 54),
	[M.LeafyGrass] = Color3.fromRGB(70, 92, 52),
	[M.Mud] = Color3.fromRGB(86, 74, 54),
	[M.Ground] = Color3.fromRGB(168, 146, 104),
	[M.WoodPlanks] = Color3.fromRGB(160, 124, 82),
	[M.Rock] = Color3.fromRGB(122, 122, 120),
	[M.Slate] = Color3.fromRGB(104, 104, 104),
	[M.Sand] = Color3.fromRGB(176, 162, 120),
	[M.Water] = Color3.fromRGB(44, 82, 112),
}

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
	local t = make("TextLabel", { BackgroundTransparency = 1, Font = Enum.Font.Code, TextSize = 11, TextColor3 = Color3.fromRGB(20, 26, 22), ZIndex = 6 }, parent)
	for k, v in props do
		(t :: any)[k] = v
	end
	return t
end

function Gps.new(player: Player, state: Folder, parent: Instance)
	local self = setmetatable({}, Gps)
	self.player = player
	self.state = state
	self.zoomIndex = 2
	self.built = false
	self.nextTry = 0
	self.nextOverlay = 0

	local device = make("Frame", {
		Name = "GPS",
		AnchorPoint = Vector2.new(1, 1),
		Position = UDim2.new(1, -22, 1, -18),
		Size = UDim2.fromOffset(SCREEN + 30, SCREEN + 92),
		BackgroundColor3 = Color3.fromRGB(196, 92, 30),
	}, parent)
	corner(device, 26)
	make("UIGradient", { Rotation = 90, Color = ColorSequence.new(Color3.fromRGB(214, 110, 44), Color3.fromRGB(120, 52, 18)) }, device)
	make("UIStroke", { Color = Color3.fromRGB(30, 22, 16), Thickness = 2 }, device)
	local antenna = make("Frame", { AnchorPoint = Vector2.new(0, 1), Position = UDim2.new(0, 22, 0, 6), Size = UDim2.fromOffset(18, 40), BackgroundColor3 = Color3.fromRGB(28, 28, 30) }, device)
	corner(antenna, 8)
	local bezel = make("Frame", {
		Position = UDim2.fromOffset(9, 12),
		Size = UDim2.fromOffset(SCREEN + 12, SCREEN + 12),
		BackgroundColor3 = Color3.fromRGB(22, 22, 24),
	}, device)
	corner(bezel, 12)
	local screen = make("Frame", {
		Position = UDim2.fromOffset(6, 6),
		Size = UDim2.fromOffset(SCREEN, SCREEN),
		BackgroundColor3 = Color3.fromRGB(150, 170, 150),
		ClipsDescendants = true,
	}, bezel)
	corner(screen, 6)
	self.screen = screen

	self.canvas = make("CanvasGroup", {
		Size = UDim2.fromOffset(MAP_PX, MAP_PX),
		BackgroundColor3 = Color3.fromRGB(62, 88, 54),
		BorderSizePixel = 0,
		ZIndex = 1,
	}, screen)
	self.scale = make("UIScale", { Scale = ZOOMS[self.zoomIndex] }, self.canvas)
	self.overlay = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundTransparency = 1, ZIndex = 3 }, screen)
	self.loading = label(screen, { Size = UDim2.fromScale(1, 1), Text = "ACQUISIZIONE SATELLITI…", TextColor3 = Color3.fromRGB(30, 40, 30), ZIndex = 8 })

	-- barra superiore e inferiore dello schermo
	local top = make("Frame", { Size = UDim2.new(1, 0, 0, 16), BackgroundColor3 = Color3.fromRGB(230, 236, 222), BackgroundTransparency = 0.15, BorderSizePixel = 0, ZIndex = 6 }, screen)
	self.heading = label(top, { Position = UDim2.fromOffset(5, 0), Size = UDim2.new(0.5, 0, 1, 0), TextXAlignment = Enum.TextXAlignment.Left, Font = Enum.Font.Code })
	self.coords = label(top, { AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -5, 0, 0), Size = UDim2.new(0.6, 0, 1, 0), TextXAlignment = Enum.TextXAlignment.Right })
	local bottom = make("Frame", { AnchorPoint = Vector2.new(0, 1), Position = UDim2.fromScale(0, 1), Size = UDim2.new(1, 0, 0, 16), BackgroundColor3 = Color3.fromRGB(230, 236, 222), BackgroundTransparency = 0.15, BorderSizePixel = 0, ZIndex = 6 }, screen)
	self.scaleBar = make("Frame", { Position = UDim2.fromOffset(6, 9), Size = UDim2.fromOffset(40, 2), BackgroundColor3 = Color3.fromRGB(20, 20, 20), BorderSizePixel = 0, ZIndex = 7 }, bottom)
	self.scaleText = label(bottom, { Position = UDim2.fromOffset(6, -1), Size = UDim2.fromOffset(80, 10), TextSize = 9, TextXAlignment = Enum.TextXAlignment.Left })
	self.elevation = label(bottom, { AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -5, 0, 0), Size = UDim2.new(0.6, 0, 1, 0), TextXAlignment = Enum.TextXAlignment.Right })
	local north = label(screen, { AnchorPoint = Vector2.new(1, 0), Position = UDim2.new(1, -6, 0, 20), Size = UDim2.fromOffset(16, 16), Text = "N", Font = Enum.Font.GothamBlack, TextSize = 12, BackgroundTransparency = 0, BackgroundColor3 = Color3.fromRGB(240, 240, 230) })
	corner(north, 8)

	self.arrow = label(screen, {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromOffset(18, 18),
		Text = "▲",
		TextSize = 18,
		TextColor3 = Color3.fromRGB(220, 30, 30),
		TextStrokeTransparency = 0,
		TextStrokeColor3 = Color3.new(1, 1, 1),
		ZIndex = 9,
	})

	-- tasti e marchio
	label(device, { AnchorPoint = Vector2.new(0.5, 1), Position = UDim2.new(0.5, 0, 1, -50), Size = UDim2.fromOffset(160, 14), Text = "TRAIL·GPS 64", Font = Enum.Font.GothamBlack, TextSize = 11, TextColor3 = Color3.fromRGB(40, 20, 10) })
	for i, txt in { "−", "M", "+" } do
		local b = make("TextButton", {
			AnchorPoint = Vector2.new(0.5, 1),
			Position = UDim2.new(0.5, (i - 2) * 56, 1, -12),
			Size = UDim2.fromOffset(46, 30),
			Text = txt,
			Font = Enum.Font.GothamBold,
			TextSize = 14,
			TextColor3 = Color3.fromRGB(220, 220, 220),
			BackgroundColor3 = Color3.fromRGB(34, 34, 36),
			AutoButtonColor = true,
		}, device)
		corner(b, 10)
		b.Activated:Connect(function()
			if txt == "+" then
				self.zoomIndex = math.min(#ZOOMS, self.zoomIndex + 1)
			elseif txt == "−" then
				self.zoomIndex = math.max(1, self.zoomIndex - 1)
			else
				self:cycleZoom()
			end
			self.scale.Scale = ZOOMS[self.zoomIndex]
		end)
	end

	if not RunService:IsClient() then
		return self -- (nei test sul server non ci sono input né frame)
	end
	ContextActionService:BindAction("ZoomGPS", function(_, inputState)
		if inputState == Enum.UserInputState.Begin then
			self:cycleZoom()
		end
		return Enum.ContextActionResult.Sink
	end, false, Enum.KeyCode.M)

	RunService.RenderStepped:Connect(function()
		local ok, err = pcall(self.update, self)
		if not ok and not self.warned then
			self.warned = true
			warn("[GPS] " .. tostring(err))
		end
	end)
	return self
end

function Gps:cycleZoom()
	self.zoomIndex = self.zoomIndex % #ZOOMS + 1
	self.scale.Scale = ZOOMS[self.zoomIndex]
end

-- Disegna la mappa campionando il terreno con raggi verticali (serve il terreno già replicato)
function Gps:build(): boolean
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { workspace.Terrain }
	params.IgnoreWater = false
	local heights, mats = {}, {}
	local hits = 0
	for i = 1, CELLS do
		heights[i], mats[i] = {}, {}
		for k = 1, CELLS do
			local x = -HALF + (i - 0.5) * CELL_STUDS
			local z = -HALF + (k - 0.5) * CELL_STUDS
			local r = workspace:Raycast(Vector3.new(x, 300, z), Vector3.new(0, -600, 0), params)
			if r then
				hits += 1
				heights[i][k] = r.Position.Y
				mats[i][k] = r.Material
			else
				heights[i][k] = 0
				mats[i][k] = M.Grass
			end
		end
	end
	if hits < CELLS * CELLS * 0.9 then
		return false
	end
	self.heights = heights
	local light = Vector3.new(-0.6, 0.7, -0.4).Unit
	for i = 1, CELLS do
		for k = 1, CELLS do
			local h = heights[i][k]
			local hx = heights[math.min(i + 1, CELLS)][k] - heights[math.max(i - 1, 1)][k]
			local hz = heights[i][math.min(k + 1, CELLS)] - heights[i][math.max(k - 1, 1)]
			local normal = Vector3.new(-hx, CELL_STUDS * 2, -hz).Unit
			local mat = mats[i][k]
			local base = PALETTE[mat] or PALETTE[M.Grass]
			local shade = 0.72 + normal:Dot(light) * 0.4
			if mat == M.Water then
				shade = 1
			end
			local color = Color3.new(math.clamp(base.R * shade, 0, 1), math.clamp(base.G * shade, 0, 1), math.clamp(base.B * shade, 0, 1))
			-- curve di livello ogni 6 stud
			local band = math.floor(h / 6)
			if mat ~= M.Water and ((i > 1 and math.floor(heights[i - 1][k] / 6) ~= band) or (k > 1 and math.floor(heights[i][k - 1] / 6) ~= band)) then
				color = color:Lerp(Color3.fromRGB(70, 50, 30), 0.35)
			end
			make("Frame", {
				Position = UDim2.fromOffset((i - 1) * CELL_PX, (k - 1) * CELL_PX),
				Size = UDim2.fromOffset(CELL_PX, CELL_PX),
				BackgroundColor3 = color,
				BorderSizePixel = 0,
			}, self.canvas)
		end
	end
	-- punti di interesse disegnati sulla mappa
	for i, poi in Config.MAP.POIS do
		local px, pz = (poi.pos.X + HALF) / CELL_STUDS * CELL_PX, (poi.pos.Z + HALF) / CELL_STUDS * CELL_PX
		local icon = make("Frame", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromOffset(px, pz),
			Size = UDim2.fromOffset(i == 1 and 7 or 5, i == 1 and 7 or 5),
			BackgroundColor3 = i == 1 and Color3.fromRGB(240, 200, 60) or Color3.fromRGB(40, 30, 20),
			BorderSizePixel = 0,
			Rotation = 45,
		}, self.canvas)
		make("UIStroke", { Color = Color3.fromRGB(250, 245, 230), Thickness = 1 }, icon)
		make("TextLabel", {
			AnchorPoint = Vector2.new(0.5, 0),
			Position = UDim2.fromOffset(px, pz + 4),
			Size = UDim2.fromOffset(90, 9),
			BackgroundTransparency = 1,
			Text = poi.name,
			Font = Enum.Font.GothamBold,
			TextSize = 7,
			TextColor3 = Color3.fromRGB(30, 22, 14),
			TextStrokeColor3 = Color3.fromRGB(240, 236, 220),
			TextStrokeTransparency = 0.2,
		}, self.canvas)
	end
	self.built = true
	self.loading.Visible = false
	return true
end

function Gps:toScreen(x: number, z: number, center: Vector3, zoom: number): (number, number)
	local k = CELL_PX / CELL_STUDS * zoom
	return SCREEN / 2 + (x - center.X) * k, SCREEN / 2 + (z - center.Z) * k
end

function Gps:marker(name: string, props: { [string]: any }): any
	self.markers = self.markers or {}
	local m = self.markers[name]
	if not m then
		m = make(props.ClassName or "Frame", { AnchorPoint = Vector2.new(0.5, 0.5), BorderSizePixel = 0, ZIndex = 4 }, self.overlay)
		self.markers[name] = m
	end
	for k, v in props do
		if k ~= "ClassName" then
			(m :: any)[k] = v
		end
	end
	self.used[name] = true
	return m
end

function Gps:update()
	local now = os.clock()
	if not self.built then
		if now >= self.nextTry and workspace:FindFirstChild("RakeHunt") and workspace.RakeHunt:FindFirstChild("Vegetazione") then
			self.nextTry = now + 5
			self:build()
		end
		return
	end
	local char = self.player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	local camera = workspace.CurrentCamera
	local center = hrp and hrp.Position or camera.CFrame.Position
	local zoom = ZOOMS[self.zoomIndex]
	local k = CELL_PX / CELL_STUDS * zoom
	self.canvas.Position = UDim2.fromOffset(SCREEN / 2 - (center.X + HALF) * k, SCREEN / 2 - (center.Z + HALF) * k)

	local look = camera.CFrame.LookVector
	local heading = (math.deg(math.atan2(look.X, -look.Z)) + 360) % 360
	self.arrow.Rotation = heading
	local names = { "N", "NE", "E", "SE", "S", "SO", "O", "NO" }
	self.heading.Text = ("%s %03d°"):format(names[math.floor((heading + 22.5) / 45) % 8 + 1], math.floor(heading))
	self.coords.Text = ("X%+04d Z%+04d"):format(math.floor(center.X), math.floor(center.Z))
	self.elevation.Text = ("QUOTA %d m"):format(math.floor(center.Y * 0.28))
	local barStuds = zoom >= 2.5 and 50 or (zoom >= 1.5 and 100 or 150)
	self.scaleBar.Size = UDim2.fromOffset(barStuds * k, 2)
	self.scaleText.Text = ("%d m"):format(math.floor(barStuds * 0.28))

	if now < self.nextOverlay then
		return
	end
	self.nextOverlay = now + 0.15
	self.used = {}
	local state = self.state

	local hintR = state:GetAttribute("HintR") or 0
	if hintR > 0 then
		local x, y = self:toScreen(state:GetAttribute("HintX") or 0, state:GetAttribute("HintZ") or 0, center, zoom)
		local area = self:marker("area", {
			Position = UDim2.fromOffset(x, y),
			Size = UDim2.fromOffset(hintR * 2 * k, hintR * 2 * k),
			BackgroundColor3 = Color3.fromRGB(230, 40, 30),
			BackgroundTransparency = 0.72,
		})
		if not area:FindFirstChildOfClass("UICorner") then
			corner(area, 999)
			make("UIStroke", { Color = Color3.fromRGB(200, 20, 20), Thickness = 1.5 }, area)
		end
	end
	local seenAt = state:GetAttribute("LastSeenTime") or 0
	local age = workspace:GetServerTimeNow() - seenAt
	if seenAt > 0 and age < 60 then
		local x, y = self:toScreen(state:GetAttribute("LastSeenX") or 0, state:GetAttribute("LastSeenZ") or 0, center, zoom)
		self:marker("seen", {
			ClassName = "TextLabel",
			Position = UDim2.fromOffset(x, y),
			Size = UDim2.fromOffset(14, 14),
			BackgroundTransparency = 1,
			Text = "✕",
			Font = Enum.Font.GothamBlack,
			TextSize = 14,
			TextColor3 = Color3.fromRGB(220, 20, 20),
			TextTransparency = (now % 0.8 < 0.4) and 0 or 0.5,
		})
	end
	local world = workspace:FindFirstChild("RakeHunt")
	local cams = world and world:FindFirstChild("Telecamere")
	if cams then
		for _, m in cams:GetChildren() do
			local body = m:FindFirstChild("Body") :: BasePart?
			if body then
				local x, y = self:toScreen(body.Position.X, body.Position.Z, center, zoom)
				local lookC = body.CFrame.LookVector
				local camHeading = math.deg(math.atan2(lookC.X, -lookC.Z))
				self:marker("cam" .. tostring(m:GetAttribute("Id")), {
					ClassName = "TextLabel",
					Position = UDim2.fromOffset(x, y),
					Size = UDim2.fromOffset(12, 12),
					BackgroundTransparency = 1,
					Text = "▲",
					TextSize = 11,
					Rotation = camHeading,
					TextColor3 = m:GetAttribute("Online") and (m:GetAttribute("Sees") and Color3.fromRGB(255, 60, 40) or Color3.fromRGB(30, 90, 220)) or Color3.fromRGB(90, 90, 90),
					TextStrokeColor3 = Color3.new(1, 1, 1),
					TextStrokeTransparency = 0.3,
				})
			end
		end
	end
	local tape = world and world:FindFirstChild("NastroAudio")
	local tapePart = tape and tape:FindFirstChild("Nastro") :: BasePart?
	if tapePart then
		local x, y = self:toScreen(tapePart.Position.X, tapePart.Position.Z, center, zoom)
		self:marker("tape", { Position = UDim2.fromOffset(x, y), Size = UDim2.fromOffset(7, 7), BackgroundColor3 = Color3.fromRGB(250, 220, 40), Rotation = 45 })
	end
	for _, p in Players:GetPlayers() do
		if p ~= self.player then
			local phrp = p.Character and p.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
			local status = p:GetAttribute("Status")
			if phrp and status ~= "Fuori" then
				local x, y = self:toScreen(phrp.Position.X, phrp.Position.Z, center, zoom)
				local dot = self:marker("p" .. p.UserId, {
					Position = UDim2.fromOffset(x, y),
					Size = UDim2.fromOffset(7, 7),
					BackgroundColor3 = status == "Braccato" and Color3.fromRGB(230, 40, 40) or Color3.fromRGB(40, 170, 60),
				})
				if not dot:FindFirstChildOfClass("UICorner") then
					corner(dot, 99)
					make("UIStroke", { Color = Color3.new(1, 1, 1), Thickness = 1 }, dot)
				end
			end
		end
	end
	for name, m in self.markers or {} do
		m.Visible = self.used[name] == true
	end
end

return Gps
