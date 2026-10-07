-- Bussola in alto, trasparente: tacche e punti cardinali, icone dei punti di interesse con la
-- distanza in metri, la destinazione (che indica la direzione del sentiero da seguire e la
-- distanza lungo il percorso), compagni, area di caccia e ultimo avvistamento.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local Nav = require(script.Parent:WaitForChild("Nav"))

local Compass = {}
Compass.__index = Compass

local WIDTH = 640
local HALF_FOV = 95 -- gradi visibili per lato

local function make(className: string, props: { [string]: any }, parent: Instance?): any
	local inst = Instance.new(className)
	for k, v in props do
		(inst :: any)[k] = v
	end
	inst.Parent = parent
	return inst
end

local function heading(v: Vector3): number
	return (math.deg(math.atan2(v.X, -v.Z)) + 360) % 360
end

local function relative(target: number, current: number): number
	return ((target - current + 540) % 360) - 180
end

function Compass.new(player: Player, state: Folder, parent: Instance)
	local self = setmetatable({}, Compass)
	self.player = player
	self.state = state
	local bar = make("Frame", {
		Name = "Bussola",
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 8),
		Size = UDim2.fromOffset(WIDTH, 58),
		BackgroundColor3 = Color3.new(0, 0, 0),
		BackgroundTransparency = 0.55,
		BorderSizePixel = 0,
		ClipsDescendants = true,
	}, parent)
	make("UIGradient", {
		Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 1),
			NumberSequenceKeypoint.new(0.18, 0.2),
			NumberSequenceKeypoint.new(0.82, 0.2),
			NumberSequenceKeypoint.new(1, 1),
		}),
	}, bar)
	self.bar = bar
	self.ticks = {}
	for deg = 0, 345, 15 do
		local cardinal = ({ [0] = "N", [45] = "NE", [90] = "E", [135] = "SE", [180] = "S", [225] = "SO", [270] = "O", [315] = "NO" })[deg]
		local tick = make("Frame", {
			AnchorPoint = Vector2.new(0.5, 0),
			Size = UDim2.fromOffset(cardinal and 2 or 1, cardinal and 10 or 6),
			BackgroundColor3 = Color3.fromRGB(230, 230, 220),
			BackgroundTransparency = cardinal and 0.1 or 0.45,
			BorderSizePixel = 0,
		}, bar)
		local text
		if cardinal then
			text = make("TextLabel", {
				AnchorPoint = Vector2.new(0.5, 0),
				Size = UDim2.fromOffset(30, 14),
				BackgroundTransparency = 1,
				Text = cardinal,
				Font = Enum.Font.GothamBold,
				TextSize = cardinal == "N" and 14 or 12,
				TextColor3 = cardinal == "N" and Color3.fromRGB(255, 120, 100) or Color3.fromRGB(235, 235, 225),
				TextStrokeTransparency = 0.6,
			}, bar)
		end
		table.insert(self.ticks, { deg = deg, tick = tick, text = text })
	end
	make("TextLabel", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, -3),
		Size = UDim2.fromOffset(14, 10),
		BackgroundTransparency = 1,
		Text = "▼",
		TextSize = 10,
		TextColor3 = Color3.fromRGB(255, 220, 90),
		ZIndex = 5,
	}, bar)
	self.degrees = make("TextLabel", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 1, 2),
		Size = UDim2.fromOffset(120, 14),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamMedium,
		TextSize = 11,
		TextColor3 = Color3.fromRGB(230, 230, 220),
		TextStrokeTransparency = 0.6,
	}, parent)
	self.destination = make("TextLabel", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 0, 82),
		Size = UDim2.fromOffset(400, 16),
		BackgroundTransparency = 1,
		Font = Enum.Font.GothamBold,
		TextSize = 13,
		TextColor3 = Color3.fromRGB(255, 220, 90),
		TextStrokeTransparency = 0.5,
	}, parent)
	self.markers = {}
	self.nextRoute = 0
	if RunService:IsClient() then
		RunService.RenderStepped:Connect(function()
			local ok, err = pcall(self.update, self)
			if not ok and not self.warned then
				self.warned = true
				warn("[Bussola] " .. tostring(err))
			end
		end)
	end
	return self
end

function Compass:marker(key: string, text: string, color: Color3, size: number): TextLabel
	local m = self.markers[key]
	if not m then
		m = make("TextLabel", {
			AnchorPoint = Vector2.new(0.5, 0),
			Size = UDim2.fromOffset(70, 34),
			BackgroundTransparency = 1,
			Font = Enum.Font.GothamBold,
			TextStrokeTransparency = 0.45,
			RichText = true,
			ZIndex = 4,
		}, self.bar)
		self.markers[key] = m
	end
	m.Text = text
	m.TextColor3 = color
	m.TextSize = size
	self.used[key] = true
	return m
end

function Compass:place(m: TextLabel, rel: number, clampEdge: boolean)
	if math.abs(rel) > HALF_FOV then
		if not clampEdge then
			m.Visible = false
			return
		end
		rel = math.sign(rel) * HALF_FOV
	end
	m.Visible = true
	m.Position = UDim2.new(0.5, rel / HALF_FOV * WIDTH / 2, 0, 14)
	m.TextTransparency = math.clamp((math.abs(rel) - HALF_FOV * 0.7) / (HALF_FOV * 0.3), 0, 0.7)
end

function Compass:update()
	local camera = workspace.CurrentCamera
	local look = camera.CFrame.LookVector
	local current = heading(look)
	self.degrees.Text = ("%03d°"):format(math.floor(current))
	for _, t in self.ticks do
		local rel = relative(t.deg, current)
		local visible = math.abs(rel) <= HALF_FOV
		t.tick.Visible = visible
		local x = rel / HALF_FOV * WIDTH / 2
		t.tick.Position = UDim2.new(0.5, x, 0, 0)
		if t.text then
			t.text.Visible = visible
			t.text.Position = UDim2.new(0.5, x, 0, 10)
		end
	end

	local char = self.player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	local origin = hrp and hrp.Position or camera.CFrame.Position
	self.used = {}
	local function dir(p: Vector3): (number, number)
		local d = Vector3.new(p.X - origin.X, 0, p.Z - origin.Z)
		return relative(heading(d), current), d.Magnitude
	end

	local dest = Nav.destination(self.state)
	for i, poi in Nav.POIS do
		local rel, dist = dir(poi.pos)
		local isDest = dest and dest.poi == i
		if not isDest then
			local m = self:marker("poi" .. i, ("%s\n<font size=\"10\">%d m</font>"):format(Nav.ICONS[i], Nav.meters(dist)), Color3.fromRGB(235, 235, 225), 15)
			self:place(m, rel, false)
		end
	end
	if dest then
		local now = os.clock()
		if now >= self.nextRoute then
			self.nextRoute = now + 0.5
			self.routePoints, self.routeLength = Nav.route(origin, dest.pos)
		end
		local target = Nav.nextWaypoint(self.routePoints, origin)
		local rel = dir(target)
		local icon = dest.poi and Nav.ICONS[dest.poi] or "◆"
		local m = self:marker("dest", ("%s\n<font size=\"11\">%d m</font>"):format(icon, Nav.meters(self.routeLength or 0)), Color3.fromRGB(255, 220, 90), 18)
		self:place(m, rel, true)
		self.destination.Text = ("▶ %s · %d m lungo il sentiero"):format(dest.name, Nav.meters(self.routeLength or 0))
	else
		self.destination.Text = ""
	end
	local state = self.state
	if (state:GetAttribute("HintR") or 0) > 0 and not (dest and dest.name == "Area di caccia") then
		local rel, dist = dir(Vector3.new(state:GetAttribute("HintX") or 0, 0, state:GetAttribute("HintZ") or 0))
		self:place(self:marker("hunt", ("⚠\n<font size=\"10\">%d m</font>"):format(Nav.meters(dist)), Color3.fromRGB(255, 80, 60), 15), rel, false)
	end
	local seenAt = state:GetAttribute("LastSeenTime") or 0
	if seenAt > 0 and workspace:GetServerTimeNow() - seenAt < 45 then
		local rel, dist = dir(Vector3.new(state:GetAttribute("LastSeenX") or 0, 0, state:GetAttribute("LastSeenZ") or 0))
		self:place(self:marker("seen", ("✕\n<font size=\"10\">%d m</font>"):format(Nav.meters(dist)), Color3.fromRGB(255, 60, 50), 16), rel, false)
	end
	for _, p in Players:GetPlayers() do
		if p ~= self.player then
			local phrp = p.Character and p.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
			local status = p:GetAttribute("Status")
			if phrp and (status == "OK" or status == "Braccato") then
				local rel, dist = dir(phrp.Position)
				local color = status == "Braccato" and Color3.fromRGB(255, 70, 60) or Color3.fromRGB(110, 230, 120)
				self:place(self:marker("p" .. p.UserId, ("●\n<font size=\"10\">%s %d m</font>"):format(p.DisplayName:sub(1, 8), Nav.meters(dist)), color, 12), rel, status == "Braccato")
			end
		end
	end
	for key, m in self.markers do
		if not self.used[key] then
			m.Visible = false
		end
	end
end

return Compass
