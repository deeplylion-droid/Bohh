-- Ostacoli lato client: disegna palle di neve, tronchi e massi che rotolano, tronchi oscillanti,
-- capre che caricano, geyser, colate di lava e raffiche di vento in base al tempo del server
-- (le stesse funzioni di Shared.Obstacles usate dal server) e segnala al server i propri contatti.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Net = require(ReplicatedStorage.Shared.Net)
local Obstacles = require(ReplicatedStorage.Shared.Obstacles)

local ObstaclesController = {}

type Piece = { part: BasePart, offset: CFrame, hip: Vector3?, phase: number? }
type Visual = { model: Model, pieces: { Piece } }

local C
local player = Players.LocalPlayer
local folder: Folder
local hitEvent: RemoteEvent
local lastReport = 0
local lastWarn = 0
local lowGfx = false

local DRAW_RANGE = 430 -- oltre questa distanza dalla telecamera gli ostacoli non si aggiornano
local SOUND_RANGE = 140

local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"
local SMOKE = "rbxasset://textures/particles/smoke_main.dds"
local FIRE = "rbxasset://textures/particles/fire_main.dds"

local WOOD = Color3.fromRGB(150, 98, 56)
local WOOD_CUT = Color3.fromRGB(232, 190, 124)
local ROCK = { Canyon = Color3.fromRGB(198, 118, 78), Crater = Color3.fromRGB(78, 62, 70) }

function ObstaclesController.Init(controllers)
	C = controllers
end

---------------------------------------------------------------------------------------------
-- Costruzione
---------------------------------------------------------------------------------------------
local function newPart(props: { [string]: any }): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.TopSurface = Enum.SurfaceType.Smooth
	p.BottomSurface = Enum.SurfaceType.Smooth
	p.Material = Enum.Material.SmoothPlastic
	for k, v in props do
		(p :: any)[k] = v
	end
	return p
end

local function ellipsoid(size: Vector3, color: Color3, material: Enum.Material?): Part
	local p = newPart({ Size = size, Color = color, Material = material or Enum.Material.SmoothPlastic })
	local m = Instance.new("SpecialMesh")
	m.MeshType = Enum.MeshType.Sphere
	m.Parent = p
	return p
end

local function emitter(parent: Instance, props: { [string]: any }): ParticleEmitter
	local e = Instance.new("ParticleEmitter")
	e.LightInfluence = 0
	e.Rotation = NumberRange.new(0, 360)
	e.RotSpeed = NumberRange.new(-60, 60)
	for k, v in props do
		(e :: any)[k] = v
	end
	e.Parent = parent
	return e
end

-- Modello pronto da Assets.Props (nil se manca o e' un segnaposto)
local function prop(name: string): Model?
	local root = ReplicatedStorage:FindFirstChild("Assets")
	local f = root and root:FindFirstChild("Props")
	local m = f and f:FindFirstChild(name)
	if m and not m:GetAttribute("Placeholder") then
		return (m :: Model):Clone()
	end
	return nil
end

-- Raccoglie le parti di un modello con l'offset rispetto al suo pivot
local function visualOf(model: Model): Visual
	local pivot = model:GetPivot()
	local pieces = {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = true
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
			local hip = d:GetAttribute("Hip")
			table.insert(pieces, {
				part = d,
				offset = pivot:ToObjectSpace(d.CFrame),
				hip = if typeof(hip) == "Vector3" then hip else nil,
				phase = d:GetAttribute("Phase"),
			})
		end
	end
	model.Parent = folder
	return { model = model, pieces = pieces }
end

local function assemble(name: string, parts: { { part: BasePart, offset: CFrame } }): Visual
	local model = Instance.new("Model")
	model.Name = name
	for _, it in parts do
		it.part.CFrame = it.offset
		it.part.Parent = model
	end
	model.WorldPivot = CFrame.new()
	return visualOf(model)
end

-- Rotolanti: palla di neve, tronco con le facce tagliate, masso irregolare
local function buildRoller(r: Obstacles.Roller): Visual
	local rad = r.radius
	if r.kind == "Snowball" then
		local ball = newPart({
			Shape = Enum.PartType.Ball,
			Size = Vector3.one * rad * 2,
			Color = Color3.fromRGB(246, 251, 255),
			Material = Enum.Material.Snow,
		})
		local lump = newPart({
			Shape = Enum.PartType.Ball,
			Size = Vector3.one * rad * 1.1,
			Color = Color3.fromRGB(236, 245, 255),
			Material = Enum.Material.Snow,
		})
		local v = assemble(
			"Snowball",
			{ { part = ball, offset = CFrame.new() }, { part = lump, offset = CFrame.new(rad * 0.55, rad * 0.35, 0) } }
		)
		emitter(ball, {
			Texture = SMOKE,
			Color = ColorSequence.new(Color3.fromRGB(255, 255, 255)),
			Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.6), NumberSequenceKeypoint.new(1, 3.6) }),
			Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.5), NumberSequenceKeypoint.new(1, 1) }),
			Lifetime = NumberRange.new(0.6, 1.1),
			Speed = NumberRange.new(1, 3),
			Rate = if lowGfx then 6 else 18,
			Shape = Enum.ParticleEmitterShape.Sphere,
		})
		return v
	elseif r.kind == "Log" then
		local len = r.length or 16
		local body = newPart({
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(len, rad * 2, rad * 2),
			Color = WOOD,
			Material = Enum.Material.Wood,
		})
		local capA = newPart({
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(0.3, rad * 1.8, rad * 1.8),
			Color = WOOD_CUT,
			Material = Enum.Material.Wood,
		})
		local capB = capA:Clone()
		local ring = newPart({
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(0.34, rad * 0.9, rad * 0.9),
			Color = Color3.fromRGB(200, 150, 92),
			Material = Enum.Material.Wood,
		})
		local ringB = ring:Clone()
		return assemble("RollingLog", {
			{ part = body, offset = CFrame.new() },
			{ part = capA, offset = CFrame.new(len / 2, 0, 0) },
			{ part = capB, offset = CFrame.new(-len / 2, 0, 0) },
			{ part = ring, offset = CFrame.new(len / 2 + 0.03, 0, 0) },
			{ part = ringB, offset = CFrame.new(-len / 2 - 0.03, 0, 0) },
		})
	end
	local custom = prop("Boulder")
	if custom then
		local _, size = custom:GetBoundingBox()
		custom:ScaleTo(custom:GetScale() * (rad * 2) / math.max(size.X, size.Y, size.Z))
		return visualOf(custom)
	end
	local color = ROCK[r.zone] or Color3.fromRGB(150, 140, 130)
	local main = newPart({
		Shape = Enum.PartType.Ball,
		Size = Vector3.one * rad * 2,
		Color = color,
		Material = Enum.Material.Slate,
	})
	local parts = { { part = main, offset = CFrame.new() } }
	for i, o in { Vector3.new(0.6, 0.35, 0.2), Vector3.new(-0.45, 0.5, -0.4), Vector3.new(0.1, -0.3, 0.7) } do
		local lump = newPart({
			Shape = Enum.PartType.Ball,
			Size = Vector3.one * rad * (1.05 - i * 0.12),
			Color = color:Lerp(Color3.new(0, 0, 0), 0.06 * i),
			Material = Enum.Material.Slate,
		})
		table.insert(parts, { part = lump, offset = CFrame.new(o * rad) })
	end
	return assemble("Boulder", parts)
end

-- Tronco oscillante appeso a due corde
local function buildPendulum(p: Obstacles.Pendulum)
	local len = p.logLength
	local rad = p.radius
	local log = assemble("SwingLog", {
		{
			part = newPart({
				Shape = Enum.PartType.Cylinder,
				Size = Vector3.new(len, rad * 2, rad * 2),
				Color = WOOD,
				Material = Enum.Material.Wood,
			}),
			offset = CFrame.new(),
		},
		{
			part = newPart({
				Shape = Enum.PartType.Cylinder,
				Size = Vector3.new(0.3, rad * 1.8, rad * 1.8),
				Color = WOOD_CUT,
				Material = Enum.Material.Wood,
			}),
			offset = CFrame.new(len / 2, 0, 0),
		},
		{
			part = newPart({
				Shape = Enum.PartType.Cylinder,
				Size = Vector3.new(0.3, rad * 1.8, rad * 1.8),
				Color = WOOD_CUT,
				Material = Enum.Material.Wood,
			}),
			offset = CFrame.new(-len / 2, 0, 0),
		},
		-- fasce di metallo dove si legano le corde
		{
			part = newPart({
				Shape = Enum.PartType.Cylinder,
				Size = Vector3.new(0.8, rad * 2.1, rad * 2.1),
				Color = Color3.fromRGB(90, 90, 104),
				Material = Enum.Material.Metal,
			}),
			offset = CFrame.new(len / 2 - 3, 0, 0),
		},
		{
			part = newPart({
				Shape = Enum.PartType.Cylinder,
				Size = Vector3.new(0.8, rad * 2.1, rad * 2.1),
				Color = Color3.fromRGB(90, 90, 104),
				Material = Enum.Material.Metal,
			}),
			offset = CFrame.new(-len / 2 + 3, 0, 0),
		},
	})
	local ropes = {}
	for _, sx in { -1, 1 } do
		local rope = newPart({
			Size = Vector3.new(0.38, p.length, 0.38),
			Color = Color3.fromRGB(196, 160, 110),
			Material = Enum.Material.Fabric,
		})
		rope.Parent = folder
		table.insert(ropes, { part = rope, x = sx * (len / 2 - 3) })
	end
	return { log = log, ropes = ropes }
end

-- Capra (modello dedicato se disponibile, altrimenti costruita con parti arrotondate)
local function buildGoat(): Visual
	local custom = prop("Goat")
	if custom then
		return visualOf(custom)
	end
	local white = Color3.fromRGB(244, 240, 230)
	local horn = Color3.fromRGB(150, 116, 84)
	local hoof = Color3.fromRGB(70, 60, 64)
	local parts = {
		{ part = ellipsoid(Vector3.new(2.5, 2.3, 3.6), white), offset = CFrame.new(0, 2.3, 0.2) },
		{ part = ellipsoid(Vector3.new(1.6, 1.6, 1.9), white), offset = CFrame.new(0, 3.4, -1.8) },
		{
			part = ellipsoid(Vector3.new(1.1, 0.9, 1.0), Color3.fromRGB(255, 196, 196)),
			offset = CFrame.new(0, 3.05, -2.65),
		},
		{ part = ellipsoid(Vector3.new(0.5, 0.9, 0.5), white), offset = CFrame.new(0, 2.45, -2.4) }, -- barbetta
		{
			part = newPart({
				Shape = Enum.PartType.Ball,
				Size = Vector3.one * 0.42,
				Color = Color3.fromRGB(30, 24, 40),
			}),
			offset = CFrame.new(0.48, 3.65, -2.55),
		},
		{
			part = newPart({
				Shape = Enum.PartType.Ball,
				Size = Vector3.one * 0.42,
				Color = Color3.fromRGB(30, 24, 40),
			}),
			offset = CFrame.new(-0.48, 3.65, -2.55),
		},
		{
			part = ellipsoid(Vector3.new(0.5, 0.35, 1.0), white),
			offset = CFrame.new(0.95, 3.7, -1.6) * CFrame.Angles(0, 0, math.rad(-30)),
		}, -- orecchie
		{
			part = ellipsoid(Vector3.new(0.5, 0.35, 1.0), white),
			offset = CFrame.new(-0.95, 3.7, -1.6) * CFrame.Angles(0, 0, math.rad(30)),
		},
		{
			part = ellipsoid(Vector3.new(0.6, 0.6, 1.0), white),
			offset = CFrame.new(0, 2.9, 2.0) * CFrame.Angles(math.rad(-40), 0, 0),
		}, -- coda
	}
	-- corna ricurve (due segmenti per lato)
	for _, sx in { -1, 1 } do
		table.insert(parts, {
			part = newPart({ Shape = Enum.PartType.Cylinder, Size = Vector3.new(1.0, 0.42, 0.42), Color = horn }),
			offset = CFrame.new(sx * 0.45, 4.25, -1.6)
				* CFrame.Angles(0, math.rad(90), 0)
				* CFrame.Angles(0, 0, math.rad(-60)),
		})
		table.insert(parts, {
			part = newPart({ Shape = Enum.PartType.Cylinder, Size = Vector3.new(0.9, 0.34, 0.34), Color = horn }),
			offset = CFrame.new(sx * 0.5, 4.55, -1.0)
				* CFrame.Angles(0, math.rad(90), 0)
				* CFrame.Angles(0, 0, math.rad(20)),
		})
	end
	-- zampe con zoccoli (oscillano attorno all'anca, a coppie diagonali)
	for i, lp in
		{
			Vector3.new(0.75, 0, -0.9),
			Vector3.new(-0.75, 0, -0.9),
			Vector3.new(0.75, 0, 1.2),
			Vector3.new(-0.75, 0, 1.2),
		}
	do
		local hip = lp + Vector3.new(0, 1.7, 0)
		local phase = if i == 1 or i == 4 then 1 else -1
		local leg = newPart({ Shape = Enum.PartType.Cylinder, Size = Vector3.new(1.4, 0.5, 0.5), Color = white })
		local foot = newPart({ Shape = Enum.PartType.Cylinder, Size = Vector3.new(0.35, 0.56, 0.56), Color = hoof })
		for _, part in { leg, foot } do
			part:SetAttribute("Hip", hip)
			part:SetAttribute("Phase", phase)
		end
		table.insert(
			parts,
			{ part = leg, offset = CFrame.new(lp + Vector3.new(0, 0.95, 0)) * CFrame.Angles(0, 0, math.rad(90)) }
		)
		table.insert(
			parts,
			{ part = foot, offset = CFrame.new(lp + Vector3.new(0, 0.18, 0)) * CFrame.Angles(0, 0, math.rad(90)) }
		)
	end
	return assemble("Goat", parts)
end

---------------------------------------------------------------------------------------------
-- Terreno: quota del suolo (con cache dei soli risultati validi, il terreno arriva dopo l'avvio)
---------------------------------------------------------------------------------------------
local rayParams = RaycastParams.new()
rayParams.FilterType = Enum.RaycastFilterType.Include
rayParams.FilterDescendantsInstances = { workspace.Terrain }
local groundCache: { [string]: number } = {}

local function groundAt(pos: Vector3): number?
	local key = `{math.floor(pos.X)}_{math.floor(pos.Z)}`
	local cached = groundCache[key]
	if cached then
		return cached
	end
	local hit = workspace:Raycast(pos + Vector3.new(0, 45, 0), Vector3.new(0, -140, 0), rayParams)
	if hit then
		groundCache[key] = hit.Position.Y
		return hit.Position.Y
	end
	return nil
end

---------------------------------------------------------------------------------------------
-- Stato
---------------------------------------------------------------------------------------------
local rollers: { { def: Obstacles.Roller, active: { [number]: Visual }, pool: { Visual }, mid: Vector3 } } = {}
local pendulums: { { def: Obstacles.Pendulum, vis: any, wasNear: boolean } } = {}
local goats: { { def: Obstacles.Goat, vis: Visual, alert: BillboardGui, dust: ParticleEmitter, charging: boolean } } =
	{}
local pulses: { { def: Obstacles.Pulse, cf: CFrame?, state: string, vis: { [string]: any } } } = {}
local winds: { { def: Obstacles.Wind, streaks: ParticleEmitter, leaves: ParticleEmitter, part: Part, active: boolean } } =
	{}

local function moveVisual(v: Visual, cf: CFrame, parts: { BasePart }, cfs: { CFrame })
	for _, piece in v.pieces do
		table.insert(parts, piece.part)
		table.insert(cfs, cf * piece.offset)
	end
end

local function rootPart(): BasePart?
	local char = player.Character
	return char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
end

local function report(id: string)
	local now = os.clock()
	if now - lastReport < 1.3 or player:GetAttribute("Ragdolled") then
		return
	end
	if (player:GetAttribute("ProtectedUntil") or 0) > workspace:GetServerTimeNow() then
		return
	end
	lastReport = now
	hitEvent:FireServer(id)
end

local function nearCamera(pos: Vector3, range: number): boolean
	return (workspace.CurrentCamera.CFrame.Position - pos).Magnitude < range
end

---------------------------------------------------------------------------------------------
-- Impulsi (geyser, geyser di fuoco, colate di lava)
---------------------------------------------------------------------------------------------
local function buildPulse(p: Obstacles.Pulse)
	local vis: { [string]: any } = {}
	if p.kind == "Geyser" or p.kind == "FireGeyser" then
		local water = p.kind == "Geyser"
		local core = newPart({
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(0.1, p.size.X * 0.55, p.size.X * 0.55),
			Color = if water then Color3.fromRGB(150, 236, 255) else Color3.fromRGB(255, 170, 40),
			Material = Enum.Material.Neon,
			Transparency = if water then 0.25 else 0.1,
			CastShadow = false,
			Parent = folder,
		})
		local shell = newPart({
			Shape = Enum.PartType.Cylinder,
			Size = Vector3.new(0.1, p.size.X * 0.85, p.size.X * 0.85),
			Color = if water then Color3.fromRGB(210, 246, 255) else Color3.fromRGB(255, 90, 30),
			Material = if water then Enum.Material.Glass else Enum.Material.Neon,
			Transparency = if water then 0.45 else 0.55,
			CastShadow = false,
			Parent = folder,
		})
		local top = newPart({ Size = Vector3.new(1, 1, 1), Transparency = 1, Parent = folder })
		local base =
			newPart({ Size = Vector3.new(p.size.X * 0.7, 0.2, p.size.X * 0.7), Transparency = 1, Parent = folder })
		vis.core, vis.shell, vis.top, vis.base = core, shell, top, base
		-- spruzzo in cima alla colonna
		vis.spray = emitter(top, {
			Texture = if water then SMOKE else FIRE,
			Color = if water
				then ColorSequence.new(Color3.fromRGB(255, 255, 255))
				else ColorSequence.new(Color3.fromRGB(255, 220, 90), Color3.fromRGB(255, 70, 20)),
			LightEmission = if water then 0.2 else 1,
			Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 2.5), NumberSequenceKeypoint.new(1, 6) }),
			Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.3), NumberSequenceKeypoint.new(1, 1) }),
			Lifetime = NumberRange.new(0.6, 1.2),
			Speed = NumberRange.new(6, 12),
			SpreadAngle = Vector2.new(70, 70),
			Acceleration = Vector3.new(0, if water then -18 else 6, 0),
			Rate = 0,
		})
		-- gocce o scintille che ricadono
		vis.drops = emitter(top, {
			Texture = SPARKLE,
			Color = if water
				then ColorSequence.new(Color3.fromRGB(180, 240, 255))
				else ColorSequence.new(Color3.fromRGB(255, 200, 60)),
			LightEmission = 0.8,
			Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.5), NumberSequenceKeypoint.new(1, 0.1) }),
			Lifetime = NumberRange.new(0.8, 1.4),
			Speed = NumberRange.new(8, 16),
			SpreadAngle = Vector2.new(60, 60),
			Acceleration = Vector3.new(0, -40, 0),
			Rate = 0,
		})
		-- bolle/fumo durante l'avviso
		vis.warn = emitter(base, {
			Texture = SMOKE,
			Color = if water
				then ColorSequence.new(Color3.fromRGB(220, 240, 255))
				else ColorSequence.new(Color3.fromRGB(120, 100, 100)),
			Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(1, 3) }),
			Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.4), NumberSequenceKeypoint.new(1, 1) }),
			Lifetime = NumberRange.new(0.6, 1),
			Speed = NumberRange.new(3, 7),
			SpreadAngle = Vector2.new(20, 20),
			EmissionDirection = Enum.NormalId.Top,
			Rate = 0,
		})
		if not water then
			local l = Instance.new("PointLight")
			l.Color = Color3.fromRGB(255, 140, 50)
			l.Range = 18
			l.Brightness = 0
			l.Shadows = false
			l.Parent = top
			vis.light = l
		end
	else
		-- colata di lava: sale dal canale durante l'avviso, brucia quando e' attiva
		local lava = newPart({
			Size = Vector3.new(p.size.X, 1, p.size.Z),
			Color = Color3.fromRGB(255, 96, 24),
			Material = Enum.Material.CrackedLava,
			CastShadow = false,
			Parent = folder,
		})
		local glow = newPart({
			Size = Vector3.new(p.size.X - 0.4, 0.2, p.size.Z - 0.4),
			Color = Color3.fromRGB(255, 150, 40),
			Material = Enum.Material.Neon,
			Transparency = 1,
			CastShadow = false,
			Parent = folder,
		})
		vis.lava, vis.glow = lava, glow
		vis.fire = emitter(lava, {
			Texture = FIRE,
			Color = ColorSequence.new(Color3.fromRGB(255, 210, 80), Color3.fromRGB(255, 60, 20)),
			LightEmission = 1,
			Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.2), NumberSequenceKeypoint.new(1, 0) }),
			Lifetime = NumberRange.new(0.5, 1),
			Speed = NumberRange.new(2, 5),
			SpreadAngle = Vector2.new(25, 25),
			EmissionDirection = Enum.NormalId.Top,
			Shape = Enum.ParticleEmitterShape.Box,
			Rate = 0,
		})
		local l = Instance.new("PointLight")
		l.Color = Color3.fromRGB(255, 120, 40)
		l.Range = 24
		l.Brightness = 0
		l.Shadows = false
		l.Parent = lava
		vis.light = l
	end
	return vis
end

-- Avanzamento (0..1) dentro la fase attuale di un impulso
local function pulsePhase(p: Obstacles.Pulse, t: number): (string, number)
	local u = (t + p.phase) % p.period
	local idle = p.period - p.warn - p.active
	if u < idle then
		return "Idle", u / idle
	elseif u < idle + p.warn then
		return "Warn", (u - idle) / p.warn
	end
	return "Active", (u - idle - p.warn) / p.active
end

local function updatePulse(entry, t: number, hrpPos: Vector3?)
	local p = entry.def
	if not entry.cf then
		local g = groundAt(p.cframe.Position)
		if not g then
			return
		end
		entry.cf = CFrame.new(p.cframe.Position.X, g, p.cframe.Position.Z) * p.cframe.Rotation
	end
	local cf = entry.cf :: CFrame
	local state, f = pulsePhase(p, t)
	local vis = entry.vis
	local changed = state ~= entry.state
	entry.state = state
	if p.kind == "Geyser" or p.kind == "FireGeyser" then
		local h = 0.1
		if state == "Active" then
			-- sale di colpo, resta, e ricade alla fine
			local rise = math.clamp(f / 0.12, 0, 1)
			local fall = math.clamp((1 - f) / 0.18, 0, 1)
			h = p.size.Y * math.min(rise, fall) + 0.1
		end
		local wobble = 1 + math.sin(t * 24) * 0.06
		vis.core.Size = Vector3.new(h, p.size.X * 0.55 * wobble, p.size.X * 0.55 * wobble)
		vis.shell.Size = Vector3.new(h, p.size.X * 0.85 / wobble, p.size.X * 0.85 / wobble)
		local up = cf * CFrame.new(0, h / 2, 0) * CFrame.Angles(0, 0, math.rad(90))
		vis.core.CFrame = up
		vis.shell.CFrame = up
		vis.core.Transparency = if state == "Active" then (if p.kind == "Geyser" then 0.25 else 0.1) else 1
		vis.shell.Transparency = if state == "Active" then (if p.kind == "Geyser" then 0.45 else 0.55) else 1
		vis.top.CFrame = cf * CFrame.new(0, h, 0)
		vis.base.CFrame = cf * CFrame.new(0, 0.4, 0)
		if changed then
			local active = state == "Active"
			vis.spray.Rate = if active then (if lowGfx then 12 else 36) else 0
			vis.drops.Rate = if active and not lowGfx then 40 else 0
			vis.warn.Rate = if state == "Warn" then (if lowGfx then 6 else 18) else 0
			if vis.light then
				vis.light.Brightness = if active then 3 elseif state == "Warn" then 1 else 0
			end
			if active and nearCamera(cf.Position, SOUND_RANGE) then
				C.Audio.Play(if p.kind == "Geyser" then "GeyserBurst" else "FireBurst", cf.Position, 0.9)
			end
		end
		if state == "Warn" and vis.light then
			vis.light.Brightness = 0.6 + math.sin(t * 20) * 0.5
		end
	else
		-- lava: sotto il canale quando inattiva, emerge durante l'avviso
		local y
		if state == "Idle" then
			y = -0.8
		elseif state == "Warn" then
			y = -0.8 + 1.15 * f
		else
			y = 0.35
		end
		vis.lava.CFrame = cf * CFrame.new(0, y, 0)
		vis.glow.CFrame = cf * CFrame.new(0, y + 0.5, 0)
		vis.glow.Transparency = if state == "Active"
			then 0.55 + math.sin(t * 6) * 0.15
			elseif state == "Warn" then 0.9 - f * 0.3
			else 1
		if changed then
			vis.fire.Rate = if state == "Active" then (if lowGfx then 10 else 30) elseif state == "Warn" then 6 else 0
			vis.light.Brightness = if state == "Active" then 3 elseif state == "Warn" then 1.2 else 0
			if state == "Warn" and nearCamera(cf.Position, SOUND_RANGE) then
				C.Audio.Play("LavaFlow", cf.Position, 0.8)
			end
		end
	end
	-- contatto del giocatore locale
	if hrpPos and state == "Active" then
		local lp = cf:PointToObjectSpace(hrpPos)
		local margin = if p.kind == "Lava" then 0.5 else 0
		if
			math.abs(lp.X) <= p.size.X / 2 + margin
			and math.abs(lp.Z) <= p.size.Z / 2 + margin
			and lp.Y >= -2
			and lp.Y <= p.size.Y
		then
			report(p.id)
		end
	end
end

---------------------------------------------------------------------------------------------
-- Raffiche di vento
---------------------------------------------------------------------------------------------
local function buildWind(w: Obstacles.Wind)
	local part = newPart({ Size = Vector3.new(w.radius * 1.6, 14, w.radius * 1.6), Transparency = 1, Parent = folder })
	part.CFrame = CFrame.lookAt(
		w.center + Vector3.new(0, 7, 0),
		w.center + Vector3.new(0, 7, 0) + Vector3.new(w.direction.Z, 0, -w.direction.X)
	)
	-- con questo orientamento l'asse X locale (faccia Right) coincide con la direzione del vento
	local streaks = emitter(part, {
		Texture = SPARKLE,
		Color = ColorSequence.new(Color3.fromRGB(255, 255, 255)),
		LightEmission = 0.4,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.35), NumberSequenceKeypoint.new(1, 0.2) }),
		Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 1),
			NumberSequenceKeypoint.new(0.2, 0.3),
			NumberSequenceKeypoint.new(1, 1),
		}),
		Squash = NumberSequence.new(3),
		Orientation = Enum.ParticleOrientation.VelocityParallel,
		Lifetime = NumberRange.new(0.8, 1.3),
		Speed = NumberRange.new(50, 70),
		SpreadAngle = Vector2.new(4, 4),
		EmissionDirection = Enum.NormalId.Right,
		Shape = Enum.ParticleEmitterShape.Box,
		ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume,
		Rate = 0,
	})
	local leaves = emitter(part, {
		Texture = SMOKE,
		Color = ColorSequence.new(Color3.fromRGB(236, 190, 140)),
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 2), NumberSequenceKeypoint.new(1, 5) }),
		Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 1),
			NumberSequenceKeypoint.new(0.3, 0.75),
			NumberSequenceKeypoint.new(1, 1),
		}),
		Lifetime = NumberRange.new(1.2, 2),
		Speed = NumberRange.new(25, 40),
		SpreadAngle = Vector2.new(10, 10),
		EmissionDirection = Enum.NormalId.Right,
		Shape = Enum.ParticleEmitterShape.Box,
		ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume,
		Rate = 0,
	})
	return { def = w, streaks = streaks, leaves = leaves, part = part, active = false }
end

local function updateWind(entry, t: number, dt: number, hrp: BasePart?)
	local w = entry.def
	local active = Obstacles.WindActive(w, t)
	local soon = not active and ((t + 1) % w.period) < w.active -- avviso un secondo prima
	if active ~= entry.active then
		entry.active = active
		if active and nearCamera(w.center, SOUND_RANGE + 40) then
			C.Audio.Play("Wind", w.center, 1)
		end
	end
	entry.streaks.Rate = if active then (if lowGfx then 20 else 60) elseif soon then 8 else 0
	entry.leaves.Rate = if active then (if lowGfx then 4 else 12) else 0
	if active and hrp then
		local d = hrp.Position - w.center
		if Vector3.new(d.X, 0, d.Z).Magnitude < w.radius and math.abs(d.Y) < 22 then
			-- spinta costante: camminando controvento si resiste, fermi si viene trascinati
			hrp.CFrame += w.direction * (w.strength * 0.38) * dt
		end
	end
end

---------------------------------------------------------------------------------------------
-- Avvio e ciclo di aggiornamento
---------------------------------------------------------------------------------------------
local function build()
	for _, r in Obstacles.Rollers do
		local a = Obstacles.FrameAt(r.s0, 0).Position
		local b = Obstacles.FrameAt(r.s1, 0).Position
		table.insert(rollers, { def = r, active = {}, pool = {}, mid = (a + b) / 2 })
	end
	for _, p in Obstacles.Pendulums do
		table.insert(pendulums, { def = p, vis = buildPendulum(p), wasNear = false })
	end
	for _, g in Obstacles.Goats do
		local vis = buildGoat()
		-- il "!" sta sopra la testa: altezza presa dal riquadro del modello (ancora nell'origine)
		local anchor = vis.pieces[1].part
		local bbCf, bbSize = vis.model:GetBoundingBox()
		local above = bbCf.Position.Y + bbSize.Y / 2 + 1.4 - anchor.Position.Y
		local alert = C.UI.Kit.New("BillboardGui", {
			Size = UDim2.fromOffset(60, 60),
			StudsOffsetWorldSpace = Vector3.new(0, above, 0),
			AlwaysOnTop = true,
			MaxDistance = 120,
			LightInfluence = 0,
			Enabled = false,
			Adornee = anchor,
			Parent = vis.model,
		})
		C.UI.Kit.Text({ Text = "!", TextColor3 = Color3.fromRGB(255, 70, 60), Parent = alert })
		local dust = emitter(vis.pieces[1].part, {
			Texture = SMOKE,
			Color = ColorSequence.new(Color3.fromRGB(226, 214, 190)),
			Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.2), NumberSequenceKeypoint.new(1, 3) }),
			Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.5), NumberSequenceKeypoint.new(1, 1) }),
			Lifetime = NumberRange.new(0.5, 0.9),
			Speed = NumberRange.new(1, 3),
			Rate = 0,
		})
		table.insert(goats, { def = g, vis = vis, alert = alert, dust = dust, charging = false })
	end
	for _, p in Obstacles.Pulses do
		table.insert(pulses, { def = p, cf = nil, state = "", vis = buildPulse(p) })
	end
	for _, w in Obstacles.Winds do
		table.insert(winds, buildWind(w))
	end
end

local function update(dt: number)
	local t = workspace:GetServerTimeNow()
	local camPos = workspace.CurrentCamera.CFrame.Position
	local hrp = rootPart()
	local hrpPos = hrp and hrp.Position
	local parts, cfs = {}, {}

	-- rotolanti
	for _, entry in rollers do
		local r = entry.def
		local far = (entry.mid - camPos).Magnitude > DRAW_RANGE + (r.s1 - r.s0) / 2
		local seen = {}
		if not far then
			for _, st in Obstacles.RollerStates(r, t) do
				seen[st.index] = true
				local v = entry.active[st.index]
				if not v then
					v = table.remove(entry.pool) or buildRoller(r)
					v.model.Parent = folder
					entry.active[st.index] = v
				end
				moveVisual(v, st.cframe, parts, cfs)
				if hrpPos then
					local lp = st.cframe:PointToObjectSpace(hrpPos)
					if r.kind == "Log" then
						local half = (r.length or 16) / 2
						if math.abs(lp.X) < half + 0.8 and math.sqrt(lp.Y * lp.Y + lp.Z * lp.Z) < r.radius + 1.8 then
							report(r.id)
						end
					elseif lp.Magnitude < r.radius + 1.9 then
						report(r.id)
					end
				end
			end
		end
		for index, v in entry.active do
			if not seen[index] then
				entry.active[index] = nil
				v.model.Parent = nil
				table.insert(entry.pool, v)
			end
		end
	end

	-- tronchi oscillanti
	for _, entry in pendulums do
		local p = entry.def
		if (p.pivot.Position - camPos).Magnitude < DRAW_RANGE then
			local angle = p.amplitude * math.sin(t * 2 * math.pi / p.period + p.phase)
			local logCf = Obstacles.PendulumCFrame(p, t)
			moveVisual(entry.vis.log, logCf, parts, cfs)
			for _, rope in entry.vis.ropes do
				table.insert(parts, rope.part)
				table.insert(cfs, p.pivot * CFrame.Angles(angle, 0, 0) * CFrame.new(rope.x, -p.length / 2, 0))
			end
			if hrpPos then
				local lp = logCf:PointToObjectSpace(hrpPos)
				if math.abs(lp.X) < p.logLength / 2 + 0.5 and math.sqrt(lp.Y * lp.Y + lp.Z * lp.Z) < p.radius + 2 then
					report(p.id)
				end
				-- fruscio quando passa vicino
				local near = (logCf.Position - hrpPos).Magnitude < 14
				if near and not entry.wasNear then
					C.Audio.Play("Whoosh", logCf.Position, 0.7)
				end
				entry.wasNear = near
			end
		end
	end

	-- capre
	for _, entry in goats do
		local g = entry.def
		if (g.center.Position - camPos).Magnitude < DRAW_RANGE then
			local cf, charging = Obstacles.GoatCFrame(g, t)
			local s = t * (if charging then 16 else 8)
			local hop = math.abs(math.sin(s)) * (if charging then 0.45 else 0.2)
			local lean = if charging then math.rad(-10) else 0
			local body = cf * CFrame.new(0, hop, 0) * CFrame.Angles(lean, 0, math.sin(s) * math.rad(3))
			local swing = math.sin(s) * math.rad(if charging then 38 else 24)
			for _, piece in entry.vis.pieces do
				table.insert(parts, piece.part)
				local hip = piece.hip
				if hip then
					local h = CFrame.new(hip)
					table.insert(
						cfs,
						body * h * CFrame.Angles(swing * (piece.phase or 1), 0, 0) * h:Inverse() * piece.offset
					)
				else
					table.insert(cfs, body * piece.offset)
				end
			end
			if charging ~= entry.charging then
				entry.charging = charging
				entry.alert.Enabled = charging
				entry.dust.Rate = if charging and not lowGfx then 26 else 0
				if charging and nearCamera(cf.Position, SOUND_RANGE) then
					C.Audio.Play("GoatBleat", cf.Position, 1)
				end
			end
			if charging and hrpPos then
				local d = hrpPos - cf.Position
				if Vector3.new(d.X, 0, d.Z).Magnitude < 4.6 and d.Y > -2 and d.Y < 7 then
					report(g.id)
				end
			end
		end
	end

	if #parts > 0 then
		workspace:BulkMoveTo(parts, cfs, Enum.BulkMoveMode.FireCFrameChanged)
	end

	-- impulsi e vento
	for _, entry in pulses do
		if (entry.def.cframe.Position - camPos).Magnitude < DRAW_RANGE then
			updatePulse(entry, t, hrpPos)
		end
	end
	for _, entry in winds do
		updateWind(entry, t, dt, hrp)
	end
end

function ObstaclesController.Start()
	hitEvent = Net.Event("ObstacleHit")
	folder = Instance.new("Folder")
	folder.Name = "ClientObstacles"
	folder.Parent = workspace
	C.State.Watch("Settings", function(settings)
		lowGfx = settings ~= nil and settings.LowGfx == true
	end)
	build()
	RunService.RenderStepped:Connect(function(dt)
		local ok, err = pcall(update, dt)
		if not ok and os.clock() - lastWarn > 5 then
			lastWarn = os.clock()
			warn("[Obstacles] " .. tostring(err))
		end
	end)
end

return ObstaclesController
