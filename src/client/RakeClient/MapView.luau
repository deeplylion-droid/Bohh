-- Mappa del tablet: biomi, lago, sentieri, punti di interesse (toccali per sceglierli come
-- destinazione), percorso giallo da seguire, la tua freccia, compagni, telecamere con il loro
-- cono visivo, area di caccia e ultimo avvistamento.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local Nav = require(script.Parent:WaitForChild("Nav"))

local MapView = {}
MapView.__index = MapView

local HALF = Config.MAP.SIZE / 2
local YELLOW = Color3.fromRGB(255, 215, 70)

local function make(className: string, props: { [string]: any }, parent: Instance?): any
	local inst = Instance.new(className)
	for k, v in props do
		(inst :: any)[k] = v
	end
	inst.Parent = parent
	return inst
end

local function round(parent: Instance)
	make("UICorner", { CornerRadius = UDim.new(1, 0) }, parent)
end

function MapView.new(parent: Instance, size: number, zIndex: number)
	local self = setmetatable({}, MapView)
	self.size = size
	self.z = zIndex
	local frame = make("Frame", {
		Size = UDim2.fromOffset(size, size),
		BackgroundColor3 = Color3.fromRGB(16, 24, 18),
		BorderSizePixel = 0,
		ClipsDescendants = true,
		ZIndex = zIndex,
	}, parent)
	make("UIStroke", { Color = Color3.fromRGB(150, 255, 180), Transparency = 0.5 }, frame)
	self.frame = frame
	local function z(n: number): number
		return zIndex + n
	end
	-- biomi
	local biomes = {
		{ 0.5, 0, Color3.fromRGB(26, 46, 28), "PINETA" },
		{ 0, 0, Color3.fromRGB(34, 44, 26), "CAMPEGGIO" },
		{ 0, 0.5, Color3.fromRGB(30, 34, 24), "PALUDE" },
		{ 0.5, 0.5, Color3.fromRGB(38, 38, 34), "MINIERA" },
	}
	for _, b in biomes do
		local f = make("Frame", { Position = UDim2.fromScale(b[1], b[2]), Size = UDim2.fromScale(0.5, 0.5), BackgroundColor3 = b[3], BorderSizePixel = 0, ZIndex = z(0) }, frame)
		make("TextLabel", {
			Position = UDim2.fromScale(b[1] == 0 and 0.04 or 0.55, b[2] == 0 and 0.03 or 0.92),
			Size = UDim2.fromOffset(100, 12),
			BackgroundTransparency = 1,
			Text = b[4],
			Font = Enum.Font.GothamBold,
			TextSize = math.max(8, size / 40),
			TextColor3 = Color3.fromRGB(120, 140, 120),
			TextTransparency = 0.3,
			TextXAlignment = Enum.TextXAlignment.Left,
			ZIndex = z(1),
		}, frame)
		f.Name = b[4]
	end
	-- griglia ogni 100 stud
	for i = 1, 7 do
		make("Frame", { Position = UDim2.fromScale(i / 8, 0), Size = UDim2.new(0, 1, 1, 0), BackgroundColor3 = Color3.new(1, 1, 1), BackgroundTransparency = 0.94, BorderSizePixel = 0, ZIndex = z(1) }, frame)
		make("Frame", { Position = UDim2.fromScale(0, i / 8), Size = UDim2.new(1, 0, 0, 1), BackgroundColor3 = Color3.new(1, 1, 1), BackgroundTransparency = 0.94, BorderSizePixel = 0, ZIndex = z(1) }, frame)
	end
	local lake = Config.MAP.LAKE
	local lx, ly = self:toPx(lake.center)
	local lr = lake.radius / (HALF * 2) * size * 2
	local lakeFrame = make("Frame", { AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromOffset(lx, ly), Size = UDim2.fromOffset(lr, lr), BackgroundColor3 = Color3.fromRGB(30, 62, 92), BorderSizePixel = 0, ZIndex = z(2) }, frame)
	round(lakeFrame)
	-- sentieri
	for _, pair in Nav.PATHS do
		self:line(Nav.POIS[pair[1]].pos, Nav.POIS[pair[2]].pos, Color3.fromRGB(150, 118, 78), math.max(2, size / 110), z(3), frame)
	end
	self.routeLayer = make("Folder", { Name = "Percorso" }, frame)
	self.dynamic = make("Folder", { Name = "Dinamici" }, frame)
	-- punti di interesse (pulsanti)
	for i, poi in Nav.POIS do
		local x, y = self:toPx(poi.pos)
		local button = make("TextButton", {
			AnchorPoint = Vector2.new(0.5, 0.5),
			Position = UDim2.fromOffset(x, y),
			Size = UDim2.fromOffset(math.max(18, size / 16), math.max(18, size / 16)),
			BackgroundColor3 = Color3.fromRGB(235, 225, 190),
			Text = Nav.ICONS[i],
			TextSize = math.max(11, size / 26),
			AutoButtonColor = true,
			ZIndex = z(6),
		}, frame)
		round(button)
		make("UIStroke", { Color = Color3.fromRGB(40, 30, 20), Thickness = 1.5 }, button)
		make("TextLabel", {
			AnchorPoint = Vector2.new(0.5, 0),
			Position = UDim2.new(0.5, 0, 1, 1),
			Size = UDim2.fromOffset(120, 12),
			BackgroundTransparency = 1,
			Text = poi.name,
			Font = Enum.Font.GothamBold,
			TextSize = math.max(8, size / 42),
			TextColor3 = Color3.fromRGB(240, 235, 215),
			TextStrokeTransparency = 0.3,
			ZIndex = z(6),
		}, button)
		button.Activated:Connect(function()
			if Nav.manual and Nav.manual.poi == i then
				Nav.clear()
			else
				Nav.setPoi(i)
			end
			self.nextRoute = 0
		end)
	end
	self.info = make("TextLabel", {
		AnchorPoint = Vector2.new(0, 1),
		Position = UDim2.new(0, 6, 1, -4),
		Size = UDim2.new(1, -12, 0, 14),
		BackgroundTransparency = 1,
		Font = Enum.Font.Code,
		TextSize = math.max(10, size / 34),
		TextColor3 = YELLOW,
		TextStrokeTransparency = 0.4,
		TextXAlignment = Enum.TextXAlignment.Left,
		ZIndex = z(9),
	}, frame)
	make("TextLabel", {
		AnchorPoint = Vector2.new(1, 0),
		Position = UDim2.new(1, -6, 0, 4),
		Size = UDim2.fromOffset(16, 16),
		BackgroundTransparency = 1,
		Text = "N▲",
		Font = Enum.Font.GothamBold,
		TextSize = 11,
		TextColor3 = Color3.fromRGB(255, 120, 100),
		ZIndex = z(9),
	}, frame)
	self.nextRoute = 0
	return self
end

function MapView:toPx(p: Vector3): (number, number)
	return (p.X + HALF) / (HALF * 2) * self.size, (p.Z + HALF) / (HALF * 2) * self.size
end

function MapView:line(a: Vector3, b: Vector3, color: Color3, thickness: number, z: number, parent: Instance)
	local ax, ay = self:toPx(a)
	local bx, by = self:toPx(b)
	local dx, dy = bx - ax, by - ay
	local len = math.sqrt(dx * dx + dy * dy)
	return make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromOffset((ax + bx) / 2, (ay + by) / 2),
		Size = UDim2.fromOffset(len, thickness),
		Rotation = math.deg(math.atan2(dy, dx)),
		BackgroundColor3 = color,
		BorderSizePixel = 0,
		ZIndex = z,
	}, parent)
end

function MapView:dot(p: Vector3, size: number, color: Color3, z: number, roundIt: boolean?): Frame
	local x, y = self:toPx(p)
	local f = make("Frame", { AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromOffset(x, y), Size = UDim2.fromOffset(size, size), BackgroundColor3 = color, BorderSizePixel = 0, ZIndex = z }, self.dynamic)
	if roundIt then
		round(f)
	end
	return f
end

function MapView:update(player: Player, state: Folder, selectedCam: Model?)
	local z = self.z
	local s = self.size
	self.dynamic:ClearAllChildren()
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	local origin = hrp and hrp.Position or workspace.CurrentCamera.CFrame.Position

	-- percorso verso la destinazione
	local dest = Nav.destination(state)
	local now = os.clock()
	if now >= self.nextRoute then
		self.nextRoute = now + 0.5
		self.routeLayer:ClearAllChildren()
		if dest then
			local points, total = Nav.route(origin, dest.pos)
			for i = 2, #points do
				self:line(points[i - 1], points[i], YELLOW, math.max(3, s / 80), z + 4, self.routeLayer)
			end
			self.info.Text = ("▶ %s · %d m"):format(dest.name, Nav.meters(total))
		else
			self.info.Text = "Tocca un luogo per tracciare il percorso"
		end
	end
	if dest then
		local f = self:dot(dest.pos, math.max(10, s / 30), YELLOW, z + 5)
		f.Rotation = 45
	end

	local hintR = state:GetAttribute("HintR") or 0
	if hintR > 0 then
		local area = self:dot(Vector3.new(state:GetAttribute("HintX") or 0, 0, state:GetAttribute("HintZ") or 0), hintR / HALF * s, Color3.fromRGB(255, 40, 40), z + 3, true)
		area.BackgroundTransparency = 0.7
	end
	local seenAt = state:GetAttribute("LastSeenTime") or 0
	local age = workspace:GetServerTimeNow() - seenAt
	if seenAt > 0 and age < 60 then
		local x = self:dot(Vector3.new(state:GetAttribute("LastSeenX") or 0, 0, state:GetAttribute("LastSeenZ") or 0), math.max(8, s / 30), Color3.fromRGB(255, 60, 60), z + 7)
		x.Rotation = 45
		x.BackgroundTransparency = math.clamp(age / 60, 0, 0.8)
	end
	-- telecamere con cono visivo
	local world = workspace:FindFirstChild("RakeHunt")
	local cams = world and world:FindFirstChild("Telecamere")
	if cams then
		for _, m in cams:GetChildren() do
			local body = m:FindFirstChild("Body") :: BasePart?
			if body then
				local color = Color3.fromRGB(90, 170, 255)
				if not m:GetAttribute("Online") then
					color = Color3.fromRGB(90, 90, 90)
				elseif m:GetAttribute("Sees") then
					color = Color3.fromRGB(255, 70, 50)
				end
				if m == selectedCam then
					color = Color3.fromRGB(255, 255, 255)
				end
				local look = body.CFrame.LookVector * Vector3.new(1, 0, 1)
				if look.Magnitude > 0.1 and m:GetAttribute("Type") ~= "Trappola" then
					for _, ang in { -0.6, 0.6 } do
						local edge = CFrame.Angles(0, ang, 0) * look.Unit
						local ray = self:line(body.Position, body.Position + edge * 70, color, 1, z + 5, self.dynamic)
						ray.BackgroundTransparency = 0.5
					end
				end
				self:dot(body.Position, math.max(6, s / 45), color, z + 6, true)
			end
		end
	end
	for _, p in Players:GetPlayers() do
		local phrp = p.Character and p.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
		local status = p:GetAttribute("Status")
		if phrp and status ~= "Fuori" and p ~= player then
			self:dot(phrp.Position, math.max(7, s / 40), status == "Braccato" and Color3.fromRGB(255, 80, 80) or Color3.fromRGB(110, 230, 110), z + 7, true)
		end
	end
	-- la tua freccia
	local x, y = self:toPx(origin)
	local look = workspace.CurrentCamera.CFrame.LookVector
	if hrp then
		look = hrp.CFrame.LookVector
	end
	make("TextLabel", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromOffset(x, y),
		Size = UDim2.fromOffset(18, 18),
		BackgroundTransparency = 1,
		Text = "▲",
		TextSize = math.max(14, s / 22),
		TextColor3 = Color3.fromRGB(255, 255, 255),
		TextStrokeTransparency = 0,
		Rotation = math.deg(math.atan2(look.X, -look.Z)),
		ZIndex = z + 8,
	}, self.dynamic)
end

return MapView
