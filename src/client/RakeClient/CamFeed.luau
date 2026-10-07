-- Anteprime delle telecamere sui monitor della Ranger Station (solo client).
-- Ogni monitor ha un ViewportFrame con una ricostruzione della scena davanti alla telecamera:
-- terreno campionato, alberi/rocce/costruzioni clonati una volta, creatura (con la sua posa) e
-- compagni aggiornati 10 volte al secondo. I feed si attivano solo vicino alla stazione.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local CollectionService = game:GetService("CollectionService")
local Lighting = game:GetService("Lighting")

local CamFeed = {}

local RANGE = 85
local MAX_PARTS = 260
local GRID = 6

local function make(className: string, props: { [string]: any }, parent: Instance?): any
	local inst = Instance.new(className)
	for k, v in props do
		(inst :: any)[k] = v
	end
	inst.Parent = parent
	return inst
end

local function cameras(): { Model }
	local folder = workspace:FindFirstChild("RakeHunt")
	folder = folder and folder:FindFirstChild("Telecamere")
	local list = {}
	if folder then
		for _, m in folder:GetChildren() do
			if m:IsA("Model") and m:FindFirstChild("Body") and m:GetAttribute("Type") ~= "Trappola" then
				table.insert(list, m)
			end
		end
	end
	table.sort(list, function(a, b)
		return (a:GetAttribute("Id") or 0) < (b:GetAttribute("Id") or 0)
	end)
	return list
end

-- Ricostruisce in un Folder la scena statica davanti alla telecamera
local function buildScene(body: BasePart): Folder
	local scene = Instance.new("Folder")
	scene.Name = "Scena"
	local origin = body.Position
	local look = body.CFrame.LookVector
	-- terreno: griglia di blocchi alla quota del suolo
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { workspace.Terrain }
	local terrain = workspace.Terrain
	local center = origin + Vector3.new(look.X, 0, look.Z).Unit * 35
	for gx = -7, 7 do
		for gz = -7, 7 do
			local p = center + Vector3.new(gx * GRID, 0, gz * GRID)
			local hit = workspace:Raycast(Vector3.new(p.X, origin.Y + 60, p.Z), Vector3.new(0, -160, 0), params)
			if hit then
				local color = hit.Material == Enum.Material.Water and Color3.fromRGB(14, 20, 18) or terrain:GetMaterialColor(hit.Material)
				make("Part", {
					Anchored = true,
					CanCollide = false,
					CanQuery = false,
					CanTouch = false,
					Size = Vector3.new(GRID + 0.4, 2, GRID + 0.4),
					CFrame = CFrame.new(hit.Position - Vector3.new(0, 1, 0)) * CFrame.Angles(math.asin(math.clamp(-hit.Normal.Z, -1, 1)) * 0.8, 0, math.asin(math.clamp(hit.Normal.X, -1, 1)) * 0.8),
					Color = color,
					Material = Enum.Material.SmoothPlastic,
				}, scene)
			end
		end
	end
	-- oggetti vicini nel campo visivo
	local candidates = {}
	local world = workspace:FindFirstChild("RakeHunt")
	for _, name in { "Vegetazione", "Mappa", "Prove" } do
		local folder = world and world:FindFirstChild(name)
		if folder then
			for _, d in folder:GetDescendants() do
				if d:IsA("BasePart") and d.Transparency < 0.95 then
					local to = d.Position - origin
					local dist = to.Magnitude
					if dist < RANGE and (dist < 6 or to.Unit:Dot(look) > 0.35) then
						table.insert(candidates, { d, dist })
					end
				end
			end
		end
	end
	table.sort(candidates, function(a, b)
		return a[2] < b[2]
	end)
	for i = 1, math.min(#candidates, MAX_PARTS) do
		local ok, copy = pcall(function()
			return candidates[i][1]:Clone()
		end)
		if ok and copy then
			for _, child in copy:GetChildren() do
				if not child:IsA("SpecialMesh") and not child:IsA("SurfaceAppearance") then
					child:Destroy()
				end
			end
			copy.Anchored = true
			copy.CanCollide = false
			copy.CanQuery = false
			copy.CanTouch = false
			copy.Parent = scene
		end
	end
	return scene
end

type Monitor = {
	part: BasePart,
	gui: SurfaceGui,
	viewport: ViewportFrame,
	vcam: Camera,
	title: TextLabel,
	alert: TextLabel,
	message: TextLabel,
	snow: Frame,
	camModel: Model?,
	scene: Folder?,
	rake: BasePart?,
	rakeBones: { [string]: Bone }?,
	eyes: { BasePart },
	people: { [Player]: BasePart },
}

local function newMonitor(part: BasePart, playerGui: Instance): Monitor
	local old = part:FindFirstChildOfClass("SurfaceGui")
	if old then
		old.Enabled = false
	end
	-- la SurfaceGui sta nel PlayerGui (Adornee sul monitor): i pezzi del ViewportFrame non devono
	-- mai trovarsi sotto Workspace, altrimenti diventano oggetti fisici veri
	local gui = make("SurfaceGui", {
		Name = "Feed",
		Adornee = part,
		ResetOnSpawn = false,
		Face = Enum.NormalId.Back,
		SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud,
		PixelsPerStud = 140,
		LightInfluence = 0,
		Brightness = 1.6,
		ClipsDescendants = true,
	}, playerGui)
	local viewport = make("ViewportFrame", {
		Size = UDim2.fromScale(1, 1),
		BackgroundColor3 = Color3.fromRGB(2, 4, 3),
		Ambient = Color3.fromRGB(60, 66, 76),
		LightColor = Color3.fromRGB(150, 160, 180),
		LightDirection = Vector3.new(-0.3, -1, -0.2),
	}, gui)
	local vcam = make("Camera", { FieldOfView = 70 }, viewport)
	viewport.CurrentCamera = vcam
	for i = 0, 29 do
		make("Frame", { Position = UDim2.fromScale(0, i / 30), Size = UDim2.new(1, 0, 0, 1), BackgroundColor3 = Color3.new(0, 0, 0), BackgroundTransparency = 0.75, BorderSizePixel = 0 }, gui)
	end
	local snow = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.fromRGB(180, 180, 180), BackgroundTransparency = 1, BorderSizePixel = 0 }, gui)
	local function text(props)
		local t = make("TextLabel", { BackgroundTransparency = 1, Font = Enum.Font.Code, TextColor3 = Color3.fromRGB(170, 255, 190), TextStrokeTransparency = 0.5, TextScaled = true }, gui)
		for k, v in props do
			(t :: any)[k] = v
		end
		return t
	end
	return {
		part = part,
		gui = gui,
		viewport = viewport,
		vcam = vcam,
		snow = snow,
		title = text({ Position = UDim2.fromScale(0.03, 0.03), Size = UDim2.fromScale(0.94, 0.12), TextXAlignment = Enum.TextXAlignment.Left }),
		alert = text({ Position = UDim2.fromScale(0.05, 0.8), Size = UDim2.fromScale(0.9, 0.13), TextColor3 = Color3.fromRGB(255, 80, 70) }),
		message = text({ AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromScale(0.85, 0.3) }),
		camModel = nil,
		scene = nil,
		rake = nil,
		rakeBones = nil,
		eyes = {},
		people = {},
	}
end

local function clearDynamic(mon: Monitor)
	if mon.rake then
		mon.rake:Destroy()
		mon.rake = nil
		mon.rakeBones = nil
	end
	for _, e in mon.eyes do
		e:Destroy()
	end
	table.clear(mon.eyes)
	for _, p in mon.people do
		p:Destroy()
	end
	table.clear(mon.people)
end

local function setCamera(mon: Monitor, camModel: Model?)
	if mon.camModel == camModel then
		return
	end
	clearDynamic(mon)
	if mon.scene then
		mon.scene:Destroy()
		mon.scene = nil
	end
	mon.camModel = camModel
	if camModel then
		local body = camModel:FindFirstChild("Body") :: BasePart
		local ok, scene = pcall(buildScene, body)
		if ok then
			scene.Parent = mon.viewport
			mon.scene = scene
		else
			warn("[Monitor] " .. tostring(scene))
		end
	end
end

local function updateDynamic(mon: Monitor, body: BasePart)
	local folder = workspace:FindFirstChild("RakeHunt")
	local rake = folder and folder:FindFirstChild("TheRake")
	local realBody = rake and rake:FindFirstChild("Body") :: BasePart?
	if realBody and (realBody.Position - body.Position).Magnitude < RANGE + 20 then
		if not mon.rake then
			local copy = realBody:Clone()
			for _, d in copy:GetDescendants() do
				if not d:IsA("Bone") then
					d:Destroy()
				end
			end
			copy.Anchored = true
			copy.CanCollide = false
			copy.CanQuery = false
			copy.CanTouch = false
			copy.Parent = mon.viewport
			mon.rake = copy
			mon.rakeBones = {}
			for _, d in copy:GetDescendants() do
				if d:IsA("Bone") then
					(mon.rakeBones :: any)[d.Name] = d
				end
			end
		end
		local copy = mon.rake :: BasePart
		copy.CFrame = realBody.CFrame
		for _, d in realBody:GetDescendants() do
			if d:IsA("Bone") then
				local twin = (mon.rakeBones :: any)[d.Name]
				if twin then
					twin.Transform = d.Transform
				end
			end
		end
		local realEyes = {}
		for _, e in workspace:GetChildren() do
			if e.Name == "OcchioLocale" and e:IsA("BasePart") then
				table.insert(realEyes, e)
			end
		end
		for i, e in realEyes do
			local twin = mon.eyes[i]
			if not twin then
				twin = make("Part", { Shape = Enum.PartType.Ball, Size = Vector3.new(0.3, 0.3, 0.3), Material = Enum.Material.Neon, Anchored = true, CanCollide = false, CanQuery = false }, mon.viewport)
				mon.eyes[i] = twin
			end
			twin.CFrame = e.CFrame
			twin.Color = e.Color
		end
	elseif mon.rake then
		clearDynamic(mon)
	end
	-- compagni come sagome scure
	for _, p in Players:GetPlayers() do
		local hrp = p.Character and p.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
		local near = hrp and (hrp.Position - body.Position).Magnitude < RANGE
		local twin = mon.people[p]
		if near and hrp then
			if not twin then
				twin = make("Part", { Shape = Enum.PartType.Cylinder, Size = Vector3.new(5, 1.8, 1.8), Color = Color3.fromRGB(40, 44, 40), Material = Enum.Material.SmoothPlastic, Anchored = true, CanCollide = false, CanQuery = false }, mon.viewport)
				mon.people[p] = twin
			end
			twin.CFrame = CFrame.new(hrp.Position) * CFrame.Angles(0, 0, math.pi / 2)
		elseif twin then
			twin:Destroy()
			mon.people[p] = nil
		end
	end
end

CamFeed._buildScene = buildScene

function CamFeed.start(player: Player)
	local monitors: { Monitor } = {}
	local page, nextPage, nextUpdate = 0, 0, 0

	local function refreshList()
		table.clear(monitors)
		local parts = CollectionService:GetTagged("MonitorScreen")
		table.sort(parts, function(a, b)
			return (a:GetAttribute("Index") or 0) < (b:GetAttribute("Index") or 0)
		end)
		for _, p in parts do
			if p:IsA("BasePart") then
				table.insert(monitors, newMonitor(p, player:WaitForChild("PlayerGui")))
			end
		end
	end

	RunService.Heartbeat:Connect(function()
		local now = os.clock()
		if now < nextUpdate then
			return
		end
		nextUpdate = now + 0.1
		if #monitors == 0 then
			if #CollectionService:GetTagged("MonitorScreen") == 0 then
				return
			end
			refreshList()
		end
		local hrp = player.Character and player.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
		local nearStation = hrp ~= nil and (hrp.Position - monitors[1].part.Position).Magnitude < 60
		local list = cameras()
		if now >= nextPage then
			nextPage = now + 8
			page += 1
		end
		local pages = math.max(1, math.ceil(#list / #monitors))
		local offset = ((page % pages) * #monitors)
		local blink = now % 1 < 0.55
		local night = Lighting.ClockTime >= 19.5 or Lighting.ClockTime < 6
		for i, mon in monitors do
			local camModel = nearStation and list[offset + i] or nil
			setCamera(mon, camModel)
			if not camModel then
				mon.viewport.Visible = false
				mon.title.Text = ("CAM -- %s"):format(blink and "●" or "")
				mon.message.Text = #list == 0 and "NESSUNA TELECAMERA" or "IN ATTESA"
				mon.alert.Text = ""
				mon.snow.BackgroundTransparency = 0.85
				continue
			end
			local body = camModel:FindFirstChild("Body") :: BasePart?
			if not body then
				continue
			end
			local camType = camModel:GetAttribute("Type")
			local online = camModel:GetAttribute("Online")
			mon.title.Text = ("CAM %02d %s %s %s"):format(camModel:GetAttribute("Id") or 0, string.upper(camType or ""), string.upper(camModel:GetAttribute("Label") or ""), blink and "● REC" or "")
			if not online then
				mon.viewport.Visible = false
				mon.message.Text = "NESSUN SEGNALE"
				mon.alert.Text = ""
				mon.snow.BackgroundTransparency = 0.5 + math.random() * 0.2
				continue
			end
			mon.viewport.Visible = true
			mon.message.Text = ""
			mon.vcam.CFrame = body.CFrame * CFrame.new(0, 0, -1.25)
			-- tutte le telecamere hanno la visione notturna a infrarossi
			if night then
				mon.viewport.ImageColor3 = Color3.fromRGB(150, 255, 165)
				mon.viewport.Ambient = camType == "IR" and Color3.fromRGB(175, 185, 175) or Color3.fromRGB(140, 150, 140)
				mon.viewport.LightColor = Color3.fromRGB(200, 220, 200)
			else
				mon.viewport.ImageColor3 = Color3.fromRGB(205, 215, 225)
				mon.viewport.Ambient = Color3.fromRGB(150, 150, 150)
				mon.viewport.LightColor = Color3.fromRGB(150, 160, 180)
			end
			updateDynamic(mon, body)
			local noise = 0
			if mon.rake then
				noise = math.clamp(1 - ((mon.rake :: BasePart).Position - body.Position).Magnitude / 45, 0, 1)
			end
			mon.snow.BackgroundTransparency = 1 - noise * 0.45 * (0.5 + math.random() * 0.5)
			mon.alert.Text = camModel:GetAttribute("Sees") and (blink and "⚠ MOVIMENTO" or "") or ""
		end
	end)
end

return CamFeed
