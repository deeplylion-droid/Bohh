-- Costruisce il Percorso Estremo (definito in Shared.Extreme): il viale fra i lotti 6 e 7, l'arco
-- d'ingresso, il ponte sul vuoto, il canyon con i muri invisibili, gli elementi delle quattro sezioni,
-- i santuari con il portale di ritorno e gli effetti (cascate, lava, luci).
-- Gli elementi mobili restano fermi sul server: li anima ogni client in funzione del tempo del
-- server (tag "ExtremePiece", nome = id dell'elemento).

local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Assets = require(ReplicatedStorage.Shared.Assets)
local Extreme = require(ReplicatedStorage.Shared.Extreme)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Pets = require(ReplicatedStorage.Shared.Config.Pets)
local Visuals = require(ReplicatedStorage.Shared.Visuals)
local Build = require(script.Parent.Build)

local ExtremeBuild = {}

local DIR = Vector3.new(math.sin(Extreme.GateAngle), 0, math.cos(Extreme.GateAngle)) -- dalla piazza verso il percorso
local SIDE = Vector3.new(-DIR.Z, 0, DIR.X) -- perpendicolare, in orizzontale
local PAVE_TOP = MapLayout.SummitY + 0.76 -- un filo sotto la piazza (330.8)
local HAZARD_YELLOW = Color3.fromRGB(255, 200, 0)
local HAZARD_BLACK = Color3.fromRGB(34, 30, 30)
local STONE_DARK = Color3.fromRGB(70, 66, 72)
local WOOD = Color3.fromRGB(150, 98, 56)
local ROPE = Color3.fromRGB(196, 168, 120)

local ANIMATED = {
	Mover = true,
	Spinner = true,
	Swing = true,
	Sweeper = true,
	Pulse = true,
	Faller = true,
	Bounce = true,
	Conveyor = true,
}

local function material(name: string?): Enum.Material
	local ok, m = pcall(function()
		return (Enum.Material :: any)[name or "SmoothPlastic"]
	end)
	return if ok and m then m else Enum.Material.SmoothPlastic
end

local function shapeOf(name: string?): Enum.PartType?
	if name == "Cylinder" then
		return Enum.PartType.Cylinder
	elseif name == "Ball" then
		return Enum.PartType.Ball
	end
	return nil
end

local function light(parent: Instance, color: Color3, range: number, brightness: number)
	local l = Instance.new("PointLight")
	l.Color = color
	l.Range = range
	l.Brightness = brightness
	l.Shadows = false
	l.Parent = parent
end

local function emitter(parent: Instance, props: { [string]: any }): ParticleEmitter
	local e = Instance.new("ParticleEmitter")
	e.LightInfluence = 0
	for k, v in props do
		(e :: any)[k] = v
	end
	e.Parent = parent
	return e
end

local SMOKE = "rbxasset://textures/particles/smoke_main.dds"
local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"
local FIRE = "rbxasset://textures/particles/fire_main.dds"

local function seq(a: number, b: number): NumberSequence
	return NumberSequence.new(a, b)
end

---------------------------------------------------------------------------------------------
-- Elementi del percorso
---------------------------------------------------------------------------------------------
local function piecePart(p: Extreme.Piece, parent: Instance): BasePart?
	if p.kind == "Kill" then
		return nil -- i volumi mortali sono solo calcolo (server e client)
	end
	local solid = p.kind ~= "Swing" and p.kind ~= "Sweeper" and p.kind ~= "Pulse"
	local collide = solid and p.collide ~= false and not p.deco
	local color = p.color or Color3.fromRGB(150, 150, 150)
	local mat = material(p.material)
	local transparency = p.transparency
	if p.kind == "Pulse" then
		if p.style == "Laser" then
			mat = Enum.Material.Neon
			transparency = if p.size.Y > 2 then 0.45 else 0.15
		elseif p.style == "Fire" then
			mat = Enum.Material.Neon
			transparency = 1 -- il client lo accende quando e' attivo
		elseif p.style == "Crusher" then
			transparency = 0
		else
			-- getto d'acqua
			mat = Enum.Material.Glass
			transparency = 1
		end
	end
	local part = Build.Part({
		name = p.id,
		size = p.size,
		cframe = p.cframe,
		color = color,
		material = mat,
		shape = shapeOf(p.shape),
		transparency = transparency,
		collide = collide,
		query = collide,
		castShadow = not p.deco and p.kind ~= "Pulse",
		parent = parent,
	})
	if p.kind == "Swing" then
		-- il perno sta in cframe: il peso pende 'length' stud piu' in basso
		part.CFrame = Extreme.SwingState(p, 0)
		local rope = Build.Part({
			name = p.id .. "_Rope",
			size = Vector3.new(0.5, p.length or 10, 0.5),
			cframe = p.cframe * CFrame.new(0, -(p.length or 10) / 2, 0),
			color = if p.material == "Metal" then Color3.fromRGB(70, 66, 66) else ROPE,
			material = if p.material == "Metal" then Enum.Material.DiamondPlate else Enum.Material.Fabric,
			collide = false,
			parent = parent,
		})
		rope:SetAttribute("Piece", p.id)
		rope:SetAttribute("Rope", true)
		CollectionService:AddTag(rope, "ExtremePiece")
	elseif p.kind == "Conveyor" then
		part.AssemblyLinearVelocity = p.velocity or Vector3.zero
		-- strisce gialle che il client fa scorrere sul nastro
		for k = 0, 3 do
			local stripe = Build.Part({
				name = p.id .. "_Stripe",
				size = Vector3.new(0.8, 0.12, p.size.Z * 0.8),
				cframe = p.cframe * CFrame.new(-p.size.X / 2 + (k + 0.5) * p.size.X / 4, p.size.Y / 2 + 0.06, 0),
				color = HAZARD_YELLOW,
				material = Enum.Material.Neon,
				collide = false,
				castShadow = false,
				parent = parent,
			})
			stripe:SetAttribute("Piece", p.id)
			stripe:SetAttribute("Stripe", k)
			CollectionService:AddTag(stripe, "ExtremePiece")
		end
	elseif p.kind == "Bounce" then
		light(part, Color3.fromRGB(255, 220, 60), 14, 1.2)
	elseif p.kind == "Pulse" then
		if p.style == "Fire" then
			emitter(part, {
				Name = "Flames",
				Texture = FIRE,
				Color = ColorSequence.new(Color3.fromRGB(255, 200, 80), Color3.fromRGB(255, 60, 10)),
				LightEmission = 1,
				Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 2.2), NumberSequenceKeypoint.new(1, 0.4) }),
				Transparency = seq(0.1, 1),
				Lifetime = NumberRange.new(0.4, 0.7),
				Speed = NumberRange.new(14, 20),
				EmissionDirection = Enum.NormalId.Top,
				Rate = 60,
				Enabled = false,
			})
			-- ugello alla base
			local base = p.cframe.Position - Vector3.new(0, p.size.Y / 2, 0)
			Build.Part({
				name = "Nozzle",
				size = Vector3.new(1, 3, 3),
				cframe = CFrame.new(base) * CFrame.Angles(0, 0, math.rad(90)),
				color = Color3.fromRGB(40, 32, 30),
				material = Enum.Material.Basalt,
				shape = Enum.PartType.Cylinder,
				collide = false,
				parent = parent,
			})
		elseif p.style == "Laser" then
			-- emettitori sulle due pareti
			for _, side in { -1, 1 } do
				local pos = p.cframe.Position
				Build.Part({
					name = "LaserEmitter",
					size = Vector3.new(1.4, math.min(p.size.Y, 3) + 1, 1.4),
					cframe = CFrame.new(pos.X, pos.Y, Extreme.Z + side * (Extreme.HalfWidth - 0.4)),
					color = Color3.fromRGB(60, 64, 80),
					material = Enum.Material.DiamondPlate,
					collide = false,
					parent = parent,
				})
			end
		elseif p.style == "Crusher" then
			-- punte sotto la pressa
			part.CFrame = Extreme.CrusherCFrame(p, 0)
		else
			emitter(part, {
				Name = "Spray",
				Texture = SMOKE,
				Color = ColorSequence.new(Color3.fromRGB(235, 248, 255)),
				Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.5), NumberSequenceKeypoint.new(1, 4) }),
				Transparency = seq(0.3, 1),
				Lifetime = NumberRange.new(0.6, 1),
				Speed = NumberRange.new(20, 28),
				EmissionDirection = Enum.NormalId.Top,
				Rate = 40,
				Enabled = false,
			})
		end
	end
	if ANIMATED[p.kind] then
		part:SetAttribute("Piece", p.id)
		CollectionService:AddTag(part, "ExtremePiece")
	end
	return part
end

---------------------------------------------------------------------------------------------
-- Dalla piazza al canyon: viale, arco d'ingresso e ponte
---------------------------------------------------------------------------------------------
local function onRay(r: number, y: number, side: number?): Vector3
	return MapLayout.SummitCenter * Vector3.new(1, 0, 1) + DIR * r + SIDE * (side or 0) + Vector3.new(0, y, 0)
end

-- CFrame con -Z lungo il viale (verso il percorso) e X di lato
local function rayFrame(r: number, y: number, side: number?): CFrame
	local p = onRay(r, y, side)
	return CFrame.lookAt(p, p + DIR)
end

local function stripedPost(folder: Instance, base: CFrame, height: number, width: number)
	local bands = math.floor(height / 3)
	for k = 0, bands - 1 do
		Build.Part({
			name = "GatePost",
			size = Vector3.new(width, height / bands, width),
			cframe = base * CFrame.new(0, (k + 0.5) * height / bands, 0),
			color = if k % 2 == 0 then HAZARD_BLACK else HAZARD_YELLOW,
			material = Enum.Material.SmoothPlastic,
			parent = folder,
		})
	end
end

local function approach(folder: Instance)
	local c = MapLayout.SummitCenter
	-- viale lastricato fra i lotti 6 e 7
	local r0, r1 = 95, 178
	Build.Part({
		name = "ExtremeAvenue",
		size = Vector3.new(8, 4, r1 - r0),
		cframe = rayFrame((r0 + r1) / 2, PAVE_TOP - 2),
		color = Color3.fromRGB(96, 90, 98),
		material = Enum.Material.Slate,
		parent = folder,
	})
	-- strisce di pericolo ai bordi del viale
	for _, side in { -1, 1 } do
		Build.Part({
			name = "ExtremeAvenueEdge",
			size = Vector3.new(0.8, 0.1, r1 - r0),
			cframe = rayFrame((r0 + r1) / 2, PAVE_TOP + 0.03, side * 3.6),
			color = HAZARD_YELLOW,
			material = Enum.Material.SmoothPlastic,
			collide = false,
			castShadow = false,
			parent = folder,
		})
	end
	-- cartello con la freccia sul bordo della piazza
	local post = rayFrame(93, c.Y, 4.5)
	Build.Part({
		name = "ExtremeSignPost",
		size = Vector3.new(0.8, 9, 0.8),
		cframe = post * CFrame.new(0, 4.5, 0),
		color = HAZARD_BLACK,
		material = Enum.Material.Metal,
		parent = folder,
	})
	local boardPos = (post * CFrame.new(0, 8, 0)).Position
	Build.Sign(
		folder,
		CFrame.lookAt(boardPos, boardPos - DIR) * CFrame.new(0, 0, -0.5),
		Vector3.new(7, 2.4, 0.4),
		"ExtremeArrow",
		nil,
		{ bg = HAZARD_YELLOW, text = HAZARD_BLACK }
	)
	-- arco d'ingresso a strisce gialle e nere con il nome del percorso
	local archR = 170
	for _, side in { -1, 1 } do
		stripedPost(folder, rayFrame(archR, PAVE_TOP - 1, side * 6.5), 24, 3)
	end
	Build.Part({
		name = "GateBeam",
		size = Vector3.new(17, 3, 3),
		cframe = rayFrame(archR, PAVE_TOP + 23.5),
		color = HAZARD_BLACK,
		material = Enum.Material.Metal,
		parent = folder,
	})
	local signPos = onRay(archR - 1.6, PAVE_TOP + 19.5)
	Build.Sign(
		folder,
		CFrame.lookAt(signPos, signPos - DIR),
		Vector3.new(16, 4.6, 0.6),
		"ExtremeSign",
		nil,
		{ bg = Color3.fromRGB(220, 30, 50), text = Color3.fromRGB(255, 255, 255) }
	)
	local subPos = onRay(archR - 1.6, PAVE_TOP + 15.6)
	Build.Sign(
		folder,
		CFrame.lookAt(subPos, subPos - DIR),
		Vector3.new(12, 2.4, 0.4),
		"ExtremeSignSub",
		nil,
		{ bg = HAZARD_BLACK, text = HAZARD_YELLOW }
	)
	-- fiaccole in cima ai pali
	for _, side in { -1, 1 } do
		local top = rayFrame(archR, PAVE_TOP + 23.4, side * 6.5)
		local flame = Build.Part({
			name = "GateFlame",
			size = Vector3.new(1.2, 1.2, 1.2),
			cframe = top * CFrame.new(0, 0.9, 0),
			color = Color3.fromRGB(255, 120, 30),
			material = Enum.Material.Neon,
			collide = false,
			castShadow = false,
			parent = folder,
		})
		local fire = Instance.new("Fire")
		fire.Size = 4
		fire.Heat = 8
		fire.Color = Color3.fromRGB(255, 150, 50)
		fire.SecondaryColor = Color3.fromRGB(255, 50, 20)
		fire.Parent = flame
		light(flame, Color3.fromRGB(255, 150, 80), 24, 1.6)
	end
	-- ponte di legno sospeso fino alla bocca del canyon
	local b0, b1 = 176, 199.5
	local deckY = PAVE_TOP - 0.1
	Build.Part({
		name = "ExtremeBridge",
		size = Vector3.new(8, 1, b1 - b0),
		cframe = rayFrame((b0 + b1) / 2, deckY - 0.5),
		color = WOOD,
		material = Enum.Material.WoodPlanks,
		parent = folder,
	})
	for r = b0 + 1, b1, 3 do
		for _, side in { -1, 1 } do
			Build.Part({
				name = "BridgePost",
				size = Vector3.new(0.6, 3.6, 0.6),
				cframe = rayFrame(r, deckY + 1.8, side * 3.7),
				color = Color3.fromRGB(110, 72, 40),
				material = Enum.Material.Wood,
				parent = folder,
			})
		end
	end
	for _, side in { -1, 1 } do
		Build.Part({
			name = "BridgeRope",
			size = Vector3.new(0.35, 0.35, b1 - b0),
			cframe = rayFrame((b0 + b1) / 2, deckY + 3.2, side * 3.7),
			color = ROPE,
			material = Enum.Material.Fabric,
			collide = false,
			parent = folder,
		})
	end
	-- travi di sostegno che scendono sul fianco della montagna
	for _, r in { 184, 192 } do
		for _, side in { -1, 1 } do
			Build.Part({
				name = "BridgeLeg",
				size = Vector3.new(1.4, 46, 1.4),
				cframe = rayFrame(r, deckY - 24, side * 3),
				color = Color3.fromRGB(110, 72, 40),
				material = Enum.Material.Wood,
				parent = folder,
			})
		end
	end
end

---------------------------------------------------------------------------------------------
-- Canyon: bocca d'ingresso, muri invisibili, cartelli delle sezioni
---------------------------------------------------------------------------------------------
local function canyon(folder: Instance)
	local hw = Extreme.HalfWidth
	local s1 = Extreme.Sections[1]
	local rock = Color3.fromRGB(104, 98, 92)
	-- bocca d'ingresso: parete di roccia con un'apertura larga 12 e alta 12 sopra la partenza
	local u0, u1 = -4, 0
	local floorTop = 331
	for _, side in { -1, 1 } do
		local v0, v1 = side * 6, side * (hw + 6)
		local center = Extreme.At(1, (u0 + u1) / 2, (250 + 352) / 2, (v0 + v1) / 2)
		Build.Part({
			name = "CanyonMouth",
			size = Vector3.new(u1 - u0, 352 - 250, math.abs(v1 - v0)),
			cframe = CFrame.new(center),
			color = rock,
			material = Enum.Material.Slate,
			parent = folder,
		})
	end
	Build.Part({
		name = "CanyonLintel",
		size = Vector3.new(u1 - u0, 352 - (floorTop + 12), 12),
		cframe = CFrame.new(Extreme.At(1, (u0 + u1) / 2, (floorTop + 12 + 352) / 2, 0)),
		color = rock,
		material = Enum.Material.Slate,
		parent = folder,
	})
	Build.Part({
		name = "CanyonSill",
		size = Vector3.new(u1 - u0, floorTop - 250, 12),
		cframe = CFrame.new(Extreme.At(1, (u0 + u1) / 2, (250 + floorTop) / 2, 0)),
		color = rock,
		material = Enum.Material.Slate,
		parent = folder,
	})
	Build.Sign(
		folder,
		CFrame.lookAt(Extreme.At(1, -4.3, floorTop + 14.6, 0), Extreme.At(1, -10, floorTop + 14.6, 0)),
		Vector3.new(14, 3.4, 0.4),
		"ExtremeSign",
		nil,
		{ bg = Color3.fromRGB(220, 30, 50), text = Color3.fromRGB(255, 255, 255) }
	)
	-- muri invisibili: ai due lati per tutto il percorso, dal fondo fino a WallTop, e in fondo
	local xStart = s1.x0 + 4
	local xEnd = Extreme.EndX - 2
	local length = xStart - xEnd
	local bottom = 150
	local height = Extreme.WallTop - bottom
	for _, side in { -1, 1 } do
		local wall = Build.Part({
			name = "InvisibleWall",
			size = Vector3.new(length, height, 2),
			cframe = CFrame.new((xStart + xEnd) / 2, bottom + height / 2, Extreme.Z + side * (hw + 1)),
			transparency = 1,
			castShadow = false,
			parent = folder,
		})
		wall:SetAttribute("Invisible", true)
	end
	for _, x in { xEnd } do
		Build.Part({
			name = "InvisibleWall",
			size = Vector3.new(2, height, hw * 2 + 4),
			cframe = CFrame.new(x - 1, bottom + height / 2, Extreme.Z),
			transparency = 1,
			castShadow = false,
			parent = folder,
		})
	end
	-- sopra la bocca d'ingresso: nessuno scavalca la parete
	Build.Part({
		name = "InvisibleWall",
		size = Vector3.new(4, Extreme.WallTop - 352, hw * 2 + 12),
		cframe = CFrame.new(Extreme.At(1, -2, (352 + Extreme.WallTop) / 2, 0)),
		transparency = 1,
		castShadow = false,
		parent = folder,
	})
	-- cartello all'inizio di ogni sezione
	for i, s in Extreme.Sections do
		local startU = if i == 1 then 2 else -4 -- in fondo al santuario precedente, dove si riparte
		local floorY = if i == 1 then floorTop else Extreme.Sections[i - 1].floor
		local pos = Extreme.At(i, startU, floorY + 6, -(hw - 1))
		Build.Part({
			name = "SectionPost",
			size = Vector3.new(0.8, 6, 0.8),
			cframe = CFrame.new(pos - Vector3.new(0, 3, 0)),
			color = HAZARD_BLACK,
			material = Enum.Material.Metal,
			parent = folder,
		})
		Build.Sign(
			folder,
			CFrame.lookAt(pos + Vector3.new(0, 1.2, 0), pos + Vector3.new(10, 1.2, 0))
				* CFrame.Angles(0, math.rad(-25), 0),
			Vector3.new(9, 2.6, 0.4),
			"ExtremeSectionSign",
			{ n = i, zone = "Zone_" .. s.id },
			{ bg = HAZARD_YELLOW, text = HAZARD_BLACK }
		)
	end
end

---------------------------------------------------------------------------------------------
-- Effetti per tema: nebbia delle cascate, lava, luci del laboratorio
---------------------------------------------------------------------------------------------
-- Corrente: texture di schiuma che il client fa scorrere (tag "ExtremeFlow", attributo FlowSpeed)
local function flowTexture(part: BasePart, face: Enum.NormalId, speedU: number, speedV: number, tile: number)
	local id = Assets.Images.WaterFlow
	if not id then
		return
	end
	local tex = Instance.new("Texture")
	tex.Name = "Flow"
	tex.Texture = id
	tex.Face = face
	tex.StudsPerTileU = tile
	tex.StudsPerTileV = tile
	tex.Transparency = 0.15
	tex:SetAttribute("FlowU", speedU)
	tex:SetAttribute("FlowV", speedV)
	tex.Parent = part
	CollectionService:AddTag(tex, "ExtremeFlow")
end

local function themeFx(folder: Instance, partsById: { [string]: BasePart })
	for _, p in Extreme.Pieces do
		if not p.deco then
			continue
		end
		local part = partsById[p.id]
		if part and p.section == 1 and p.material == "SmoothPlastic" and p.size.Z > Extreme.HalfWidth * 2 then
			-- superficie delle rapide: la corrente scorre verso valle (-X); la texture ha U lungo x
			flowTexture(part, Enum.NormalId.Top, 14, 0, 18)
		elseif part and p.section == 1 and p.material == "Glass" then
			-- cascata: due facce verticali, la schiuma scende
			flowTexture(part, Enum.NormalId.Right, 0, 22, 12)
			flowTexture(part, Enum.NormalId.Left, 0, 22, 12)
		end
		if p.section == 1 and p.material == "Glass" then
			-- cascata: nebbia alla base
			local base = p.cframe.Position - Vector3.new(0, p.size.Y / 2 - 1, 0)
			local anchor = Build.Part({
				name = "FallMist",
				size = Vector3.new(4, 1, Extreme.HalfWidth * 2),
				cframe = CFrame.new(base),
				transparency = 1,
				collide = false,
				query = false,
				castShadow = false,
				parent = folder,
			})
			emitter(anchor, {
				Texture = SMOKE,
				Color = ColorSequence.new(Color3.fromRGB(240, 250, 255)),
				Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 3), NumberSequenceKeypoint.new(1, 7) }),
				Transparency = seq(0.55, 1),
				Lifetime = NumberRange.new(1.4, 2.2),
				Speed = NumberRange.new(4, 8),
				EmissionDirection = Enum.NormalId.Top,
				SpreadAngle = Vector2.new(30, 30),
				Rate = 18,
			})
		elseif p.material == "Neon" and p.section == 4 and p.size.Z > Extreme.HalfWidth then
			-- lava: luci rosse e braci lungo il fiume
			local length = p.size.X
			local n = math.max(1, math.floor(length / 36))
			for k = 0, n - 1 do
				local pos = p.cframe.Position + Vector3.new(-length / 2 + (k + 0.5) * length / n, 1, 0)
				local anchor = Build.Part({
					name = "LavaGlow",
					size = Vector3.new(8, 1, Extreme.HalfWidth * 2),
					cframe = CFrame.new(pos),
					transparency = 1,
					collide = false,
					query = false,
					castShadow = false,
					parent = folder,
				})
				light(anchor, Color3.fromRGB(255, 110, 40), 40, 2)
				emitter(anchor, {
					Texture = SPARKLE,
					Color = ColorSequence.new(Color3.fromRGB(255, 190, 80), Color3.fromRGB(255, 60, 20)),
					LightEmission = 1,
					Size = seq(0.35, 0.1),
					Transparency = seq(0, 1),
					Lifetime = NumberRange.new(1.5, 3),
					Speed = NumberRange.new(3, 7),
					EmissionDirection = Enum.NormalId.Top,
					SpreadAngle = Vector2.new(25, 25),
					Rate = 10,
				})
			end
		elseif p.material == "Neon" and p.section == 3 and p.size.X > 100 then
			-- griglia del vuoto elettrico: qualche luce
			for k = 0, 5 do
				local pos = p.cframe.Position + Vector3.new(-p.size.X / 2 + (k + 0.5) * p.size.X / 6, 4, 0)
				local anchor = Build.Part({
					name = "LabGlow",
					size = Vector3.new(1, 1, 1),
					cframe = CFrame.new(pos),
					transparency = 1,
					collide = false,
					query = false,
					castShadow = false,
					parent = folder,
				})
				light(anchor, Color3.fromRGB(80, 255, 220), 36, 1.4)
			end
		end
	end
end

---------------------------------------------------------------------------------------------
-- Santuari: arco del checkpoint, portale di ritorno, luci, statue dei pet della sezione
---------------------------------------------------------------------------------------------
local function petsOf(zone: string): { string }
	local out = {}
	for _, p in Pets.List do
		if p.rarity == "Extreme" and p.zone == zone then
			table.insert(out, p.id)
		end
	end
	return out
end

local function shrines(folder: Instance)
	local hw = Extreme.HalfWidth
	for i, sh in Extreme.Shrines do
		local s = Extreme.Sections[i]
		local y = s.floor
		local u0 = s.length
		local model = Build.Model(`Shrine{i}`, folder)
		-- arco luminoso all'ingresso (checkpoint)
		for _, side in { -1, 1 } do
			Build.Part({
				name = "CheckpointPost",
				size = Vector3.new(1.4, 14, 1.4),
				cframe = CFrame.new(Extreme.At(i, u0 + 1, y + 7, side * (hw - 1))),
				color = sh.glow,
				material = Enum.Material.Neon,
				collide = false,
				castShadow = false,
				parent = model,
			})
		end
		local beam = Build.Part({
			name = "CheckpointBeam",
			size = Vector3.new(1.4, 1.4, hw * 2),
			cframe = CFrame.new(Extreme.At(i, u0 + 1, y + 14, 0)),
			color = sh.glow,
			material = Enum.Material.Neon,
			collide = false,
			castShadow = false,
			parent = model,
		})
		beam:SetAttribute("Checkpoint", i)
		CollectionService:AddTag(beam, "ExtremeCheckpoint")
		Build.Sign(
			model,
			CFrame.lookAt(Extreme.At(i, u0 + 0.6, y + 17.4, 0), Extreme.At(i, u0 - 5, y + 17.4, 0)),
			Vector3.new(12, 2.6, 0.4),
			"ExtremeCheckpointSign",
			{ n = i },
			{ bg = Color3.fromRGB(30, 30, 36), text = sh.glow }
		)
		if i == #Extreme.Shrines then
			-- in fondo all'ultimo santuario: parete di roccia (oltre c'e' solo il muro invisibile)
			local u1 = s.length + s.shrineLength
			Build.Part({
				name = "ShrineEndWall",
				size = Vector3.new(4, 40, hw * 2 + 12),
				cframe = CFrame.new(Extreme.At(i, u1 + 2, y + 10, 0)),
				color = Color3.fromRGB(70, 20, 18),
				material = Enum.Material.Basalt,
				parent = model,
			})
		end
		-- luce sull'altare
		local altarGlow = Build.Part({
			name = "AltarGlow",
			size = Vector3.new(1, 1, 1),
			cframe = CFrame.new(sh.altar + Vector3.new(0, 6, 0)),
			transparency = 1,
			collide = false,
			query = false,
			castShadow = false,
			parent = model,
		})
		light(altarGlow, sh.glow, 30, 2)
		emitter(altarGlow, {
			Texture = SPARKLE,
			Color = ColorSequence.new(sh.glow, Color3.new(1, 1, 1)),
			LightEmission = 1,
			Size = seq(0.4, 0.1),
			Transparency = seq(0, 1),
			Lifetime = NumberRange.new(1.5, 2.5),
			Speed = NumberRange.new(1, 3),
			SpreadAngle = Vector2.new(180, 180),
			Rate = 14,
		})
		-- portale di ritorno: anello di pietra con un disco luminoso (attraversarlo riporta in piazza)
		local portal = sh.portal
		local frame = Build.Model("Portal", model)
		local ringR = 6
		for k = 0, 11 do
			local a = k / 12 * math.pi * 2
			Build.Part({
				name = "PortalStone",
				size = Vector3.new(3.4, 1.6, 1.6),
				cframe = portal
					* CFrame.new(math.cos(a) * ringR, math.sin(a) * ringR, 0)
					* CFrame.Angles(0, 0, a + math.pi / 2),
				color = STONE_DARK,
				material = Enum.Material.Slate,
				parent = frame,
			})
		end
		local disc = Build.Part({
			name = "PortalDisc",
			size = Vector3.new(0.4, ringR * 2 - 0.6, ringR * 2 - 0.6),
			cframe = portal * CFrame.Angles(0, math.rad(90), 0),
			color = sh.glow,
			material = Enum.Material.Neon,
			shape = Enum.PartType.Cylinder,
			transparency = 0.25,
			collide = false,
			castShadow = false,
			parent = frame,
		})
		disc:SetAttribute("Shrine", i)
		CollectionService:AddTag(disc, "ExtremePortal")
		light(disc, sh.glow, 22, 2)
		emitter(disc, {
			Texture = SPARKLE,
			Color = ColorSequence.new(Color3.new(1, 1, 1), sh.glow),
			LightEmission = 1,
			Size = seq(0.6, 0.1),
			Transparency = seq(0, 1),
			Lifetime = NumberRange.new(0.8, 1.4),
			Speed = NumberRange.new(2, 5),
			SpreadAngle = Vector2.new(180, 180),
			Rate = 30,
		})
		local signPos = (portal * CFrame.new(0, ringR + 2.6, -0.4)).Position
		Build.Sign(
			frame,
			CFrame.lookAt(signPos, signPos + portal.LookVector),
			Vector3.new(10, 2.2, 0.4),
			"ExtremePortalSign",
			nil,
			{ bg = Color3.fromRGB(30, 30, 36), text = Color3.fromRGB(255, 255, 255) }
		)
		-- i pet che si possono vincere in questa sezione, su tre piedistalli lungo la parete
		local ids = petsOf(s.id)
		for k, petId in ids do
			local u = u0 + 12 + (k - 1) * 16
			local base = Extreme.At(i, u, y, hw - 5)
			Build.Part({
				name = "TrophyBase",
				size = Vector3.new(2, 7, 7),
				cframe = CFrame.new(base + Vector3.new(0, 1, 0)) * CFrame.Angles(0, 0, math.rad(90)),
				color = STONE_DARK,
				material = Enum.Material.Slate,
				shape = Enum.PartType.Cylinder,
				parent = model,
			})
			local ok, pet = pcall(Visuals.MakePet, petId, "None", "Normal", 6.5)
			if ok and pet then
				for _, d in pet:GetDescendants() do
					if d:IsA("BasePart") then
						d.Anchored = true
						d.CanCollide = false
						d.CanTouch = false
						d.CanQuery = false
					end
				end
				pet.Name = "Trophy" .. petId
				pet:PivotTo(CFrame.lookAt(base + Vector3.new(0, 2, 0), base + Vector3.new(0, 2, -10)))
				pet.Parent = model
			end
		end
	end
end

---------------------------------------------------------------------------------------------
function ExtremeBuild.Build(parent: Instance)
	local folder = Build.Model("Extreme", parent)
	local pieces = Instance.new("Folder")
	pieces.Name = "Pieces"
	pieces.Parent = folder
	local partsById: { [string]: BasePart } = {}
	for _, p in Extreme.Pieces do
		local part = piecePart(p, pieces)
		if part then
			partsById[p.id] = part
		end
	end
	approach(folder)
	canyon(folder)
	themeFx(folder, partsById)
	shrines(folder)
	return folder
end

-- Vero se (x, z) e' vicino al viale o al ponte (le decorazioni della vetta non ci vanno)
function ExtremeBuild.NearApproach(x: number, z: number): boolean
	local rel = Vector3.new(x, 0, z) - MapLayout.SummitCenter * Vector3.new(1, 0, 1)
	local along = rel:Dot(DIR)
	local across = math.abs(rel:Dot(SIDE))
	return along > 80 and along < 215 and across < 16
end

return ExtremeBuild
