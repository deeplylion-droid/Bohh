-- Valanga lato client: conto alla rovescia sullo striscione, sirena, cartelli sui rifugi, muro di
-- neve che scende lungo il sentiero alla quota del fronte, tremolio della telecamera e lampo
-- bianco per chi viene travolto.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Assets = require(ReplicatedStorage.Shared.Assets)
local AvalancheTiming = require(ReplicatedStorage.Shared.Avalanche)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Net = require(ReplicatedStorage.Shared.Net)

local Avalanche = {}

local C
local player = Players.LocalPlayer
local samples: { { s: number, y: number } } = {}
local markers: { BillboardGui } = {}
local wall: { model: Model, balls: { { part: BasePart, x: number, size: number, seed: number } }, cloud: Part, front: Part, rumble: Sound? }
local phase = "none" -- none | warn | wave
local lowGfx = false
local lastWarn = 0

local SMOKE = "rbxasset://textures/particles/smoke_main.dds"
local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"

local WARN_COLORS = { Color3.fromRGB(255, 120, 70), Color3.fromRGB(216, 27, 43) }
local SAFE_COLORS = { Color3.fromRGB(120, 230, 120), Color3.fromRGB(30, 160, 70) }

function Avalanche.Init(controllers)
	C = controllers
end

---------------------------------------------------------------------------------------------
-- Quota -> posizione sul sentiero (la quota scende in modo monotono lungo il sentiero)
---------------------------------------------------------------------------------------------
local function buildSamples()
	local s = 0
	while s <= MapLayout.PathLength do
		local p = MapLayout.PathPoint(s)
		table.insert(samples, { s = s, y = p.Y })
		s += 3
	end
end

local function sAtY(y: number): number
	if y >= samples[1].y then
		return 0
	end
	if y <= samples[#samples].y then
		return samples[#samples].s
	end
	local lo, hi = 1, #samples
	while hi - lo > 1 do
		local mid = (lo + hi) // 2
		if samples[mid].y > y then
			lo = mid
		else
			hi = mid
		end
	end
	local a, b = samples[lo], samples[hi]
	local f = (a.y - y) / math.max(a.y - b.y, 1e-6)
	return a.s + (b.s - a.s) * f
end

-- Sistema di riferimento sul sentiero: X attraverso, LookVector verso valle
local function pathFrame(s: number): CFrame
	local p, dir = MapLayout.PathPoint(s)
	local flat = Vector3.new(dir.X, 0, dir.Z).Unit
	local right = flat:Cross(Vector3.yAxis)
	return CFrame.fromMatrix(p, right, Vector3.yAxis)
end

---------------------------------------------------------------------------------------------
-- Costruzione: muro di neve e cartelli dei rifugi
---------------------------------------------------------------------------------------------
local function newPart(props: { [string]: any }): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	for k, v in props do
		(p :: any)[k] = v
	end
	return p
end

local function buildWall()
	local model = Instance.new("Model")
	model.Name = "AvalancheWall"
	local balls = {}
	local width = MapLayout.PathWidth
	local count = 9
	for i = 1, count do
		local x = -width / 2 + (i - 0.5) * width / count + (math.random() - 0.5) * 2
		local size = 9 + math.random() * 7
		local ball = newPart({
			Name = "Snow",
			Shape = Enum.PartType.Ball,
			Size = Vector3.one * size,
			Color = Color3.fromRGB(246, 251, 255),
			Material = Enum.Material.Snow,
			Parent = model,
		})
		table.insert(balls, { part = ball, x = x, size = size, seed = math.random() * 10 })
	end
	-- nuvola di neve sollevata dietro al fronte
	local cloud = newPart({ Name = "Cloud", Size = Vector3.new(width, 10, 36), Transparency = 1, Parent = model })
	local e = Instance.new("ParticleEmitter")
	e.Texture = SMOKE
	e.Color = ColorSequence.new(Color3.fromRGB(255, 255, 255), Color3.fromRGB(220, 234, 255))
	e.LightInfluence = 0.4
	e.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 8), NumberSequenceKeypoint.new(1, 18) })
	e.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.25), NumberSequenceKeypoint.new(0.7, 0.55), NumberSequenceKeypoint.new(1, 1) })
	e.Lifetime = NumberRange.new(1.6, 2.6)
	e.Speed = NumberRange.new(4, 10)
	e.SpreadAngle = Vector2.new(50, 50)
	e.EmissionDirection = Enum.NormalId.Top
	e.Shape = Enum.ParticleEmitterShape.Box
	e.ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume
	e.Rotation = NumberRange.new(0, 360)
	e.RotSpeed = NumberRange.new(-30, 30)
	e.Rate = 0
	e.Parent = cloud
	-- schegge di ghiaccio luccicanti davanti
	local front = newPart({ Name = "Front", Size = Vector3.new(width, 6, 4), Transparency = 1, Parent = model })
	local chips = Instance.new("ParticleEmitter")
	chips.Texture = SPARKLE
	chips.Color = ColorSequence.new(Color3.fromRGB(220, 244, 255))
	chips.LightEmission = 0.6
	chips.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.7), NumberSequenceKeypoint.new(1, 0.2) })
	chips.Lifetime = NumberRange.new(0.6, 1.2)
	chips.Speed = NumberRange.new(10, 22)
	chips.SpreadAngle = Vector2.new(35, 35)
	chips.Acceleration = Vector3.new(0, -30, 0)
	chips.EmissionDirection = Enum.NormalId.Front
	chips.Shape = Enum.ParticleEmitterShape.Box
	chips.Rate = 0
	chips.Parent = front
	local rumble = nil
	if Assets.Sounds.Rumble then
		rumble = Instance.new("Sound")
		rumble.SoundId = Assets.Sounds.Rumble
		rumble.Looped = true
		rumble.Volume = 1.2
		rumble.RollOffMinDistance = 30
		rumble.RollOffMaxDistance = 400
		rumble.Parent = front
	end
	wall = { model = model, balls = balls, cloud = cloud, front = front, rumble = rumble }
end

local function buildMarkers()
	local Kit = C.UI.Kit
	for i = 1, #MapLayout.Shelters do
		local cf = MapLayout.ShelterFrame(i)
		local att = Instance.new("Attachment")
		att.WorldPosition = cf.Position + Vector3.new(0, MapLayout.ShelterSize.Y + 5, 0)
		att.Parent = workspace.Terrain
		local gui = Kit.New("BillboardGui", {
			Name = "ShelterMarker",
			Size = UDim2.fromOffset(200, 90),
			AlwaysOnTop = true,
			MaxDistance = 320,
			LightInfluence = 0,
			Enabled = false,
			Adornee = att,
			Parent = att,
		})
		local label = Kit.Text({ Text = "🏠 " .. C.Lang.T("Shelter"), TextColor3 = Color3.fromRGB(150, 255, 120), Size = UDim2.new(1, 0, 0.55, 0), Parent = gui })
		Kit.Text({ Text = "▼", TextColor3 = Color3.fromRGB(150, 255, 120), Size = UDim2.new(0.4, 0, 0.42, 0), Position = UDim2.new(0.3, 0, 0.56, 0), Parent = gui })
		C.Lang.Changed:Connect(function()
			label.Text = "🏠 " .. C.Lang.T("Shelter")
		end)
		table.insert(markers, gui)
	end
end

---------------------------------------------------------------------------------------------
-- Aggiornamento
---------------------------------------------------------------------------------------------
local function rootPart(): BasePart?
	local char = player.Character
	return char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
end

local function setMarkers(on: boolean)
	for _, m in markers do
		m.Enabled = on
	end
end

local function setWall(on: boolean)
	if on then
		if not wall.model.Parent then
			wall.model.Parent = workspace
			local cloudEmitter = wall.cloud:FindFirstChildOfClass("ParticleEmitter")
			local chips = wall.front:FindFirstChildOfClass("ParticleEmitter")
			if cloudEmitter then
				cloudEmitter.Rate = if lowGfx then 14 else 40
			end
			if chips then
				chips.Rate = if lowGfx then 10 else 30
			end
			if wall.rumble and C.State.Get("Settings", "Sfx") ~= false then
				wall.rumble:Play()
			end
		end
	elseif wall.model.Parent then
		local cloudEmitter = wall.cloud:FindFirstChildOfClass("ParticleEmitter")
		local chips = wall.front:FindFirstChildOfClass("ParticleEmitter")
		if cloudEmitter then
			cloudEmitter.Rate = 0
		end
		if chips then
			chips.Rate = 0
		end
		if wall.rumble then
			wall.rumble:Stop()
		end
		-- lascia svanire le particelle prima di togliere il modello
		task.delay(3, function()
			if phase ~= "wave" then
				wall.model.Parent = nil
			end
		end)
	end
end

local function moveWall(front: number, t: number)
	local sLead = sAtY(front - AvalancheTiming.Band)
	local sTail = sAtY(front + 3)
	local lead = pathFrame(sLead)
	local parts, cfs = {}, {}
	for _, b in wall.balls do
		local roll = t * 9 / b.size + b.seed
		local bob = math.abs(math.sin(t * 5 + b.seed)) * 1.2
		table.insert(parts, b.part)
		table.insert(cfs, lead * CFrame.new(b.x, b.size * 0.42 + bob, -math.sin(b.seed * 3) * 2) * CFrame.Angles(-roll, 0, 0))
	end
	table.insert(parts, wall.front)
	table.insert(cfs, lead * CFrame.new(0, 3, -5))
	table.insert(parts, wall.cloud)
	table.insert(cfs, pathFrame((sLead + sTail) / 2) * CFrame.new(0, 5, 0))
	workspace:BulkMoveTo(parts, cfs, Enum.BulkMoveMode.FireCFrameChanged)
	return lead.Position
end

local function flash()
	local Kit = C.UI.Kit
	local f = Kit.New("Frame", {
		Name = "SnowFlash",
		BackgroundColor3 = Color3.fromRGB(250, 252, 255),
		BackgroundTransparency = 0,
		Size = UDim2.fromScale(1, 1),
		ZIndex = 50,
		Parent = C.UI.Gui("Overlay"),
	})
	Kit.Tween(f, 1.6, { BackgroundTransparency = 1 }, Enum.EasingStyle.Quad, Enum.EasingDirection.In)
	task.delay(1.7, function()
		f:Destroy()
	end)
end

local lastShown = ""
local function tick(t: number)
	local at = workspace:GetAttribute("AvalancheAt")
	local hrp = rootPart()
	local pos = hrp and hrp.Position
	local sheltered = pos ~= nil and MapLayout.IsSheltered(pos)
	local onSummit = pos ~= nil and MapLayout.ZoneAt(pos) == "Summit"
	local front = AvalancheTiming.FrontY(at, t)
	local newPhase = "none"
	if front then
		newPhase = "wave"
	elseif at and t < at and at - t <= AvalancheTiming.Warning then
		newPhase = "warn"
	end

	if newPhase ~= phase then
		local old = phase
		phase = newPhase
		if newPhase == "warn" then
			C.Audio.Play("Alarm")
		end
		if newPhase ~= "none" and not onSummit then
			C.Zones.SetOverride("Avalanche", "Danger", 2)
		elseif newPhase == "none" then
			C.Zones.ClearOverride("Avalanche")
		end
		setMarkers(newPhase ~= "none")
		setWall(newPhase == "wave")
		if newPhase == "none" and old ~= "none" then
			C.UI.Hud.ShowBanner(nil, nil, nil, 2)
			lastShown = ""
		end
	end

	if phase == "none" then
		return
	end
	local T = C.Lang.T
	local title = if phase == "warn" then T("AvalancheWarn", { t = `{math.ceil(at - t)}s` }) else T("AvalancheNow")
	local sub = if sheltered then T("SafeInShelter") else T("AvalancheWarnSub")
	local key = title .. sub
	if key ~= lastShown then
		lastShown = key
		C.UI.Hud.ShowBanner("❄️ " .. title, sub, if sheltered then SAFE_COLORS else WARN_COLORS, 2)
	end
	if phase == "wave" and front then
		local leadPos = moveWall(front, t)
		-- la terra trema quando il fronte e' vicino
		if pos then
			local d = (leadPos - pos).Magnitude
			if d < 140 then
				C.Effects.CameraShake(0.5 * (1 - d / 140) + 0.05, 0.25)
			end
		end
	end
end

function Avalanche.Start()
	buildSamples()
	buildWall()
	buildMarkers()
	C.State.Watch("Settings", function(settings)
		lowGfx = settings ~= nil and settings.LowGfx == true
	end)
	Net.Event("Buried").OnClientEvent:Connect(function()
		flash()
		C.Effects.CameraShake(1.2, 0.8)
		C.Audio.Play("Bonk")
	end)
	local accum = 0
	RunService.RenderStepped:Connect(function(dt)
		local t = workspace:GetServerTimeNow()
		-- il muro si muove a ogni fotogramma, il resto 10 volte al secondo
		accum += dt
		if phase == "wave" or accum >= 0.1 then
			accum = 0
			local ok, err = pcall(tick, t)
			if not ok and os.clock() - lastWarn > 5 then
				lastWarn = os.clock()
				warn("[Avalanche] " .. tostring(err))
			end
		end
	end)
end

return Avalanche
