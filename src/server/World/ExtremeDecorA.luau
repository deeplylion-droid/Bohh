-- Arredo del Percorso Estremo, sezioni 1 (Rapide degli Abissi) e 2 (Tempio del Deserto): solo decorazioni (le parti del
-- percorso sono in Shared.Extreme e le costruisce ExtremeBuild). Dentro i muri del percorso niente si puo' toccare.
--
-- Regole che seguono tutti gli ornamenti:
--  * CanCollide, CanQuery e CanTouch spenti: il controllo anti-trucchi del server conosce solo gli appoggi di
--    Shared.Extreme, chi stesse in piedi su un ornamento verrebbe rimandato al checkpoint;
--  * dentro il canyon solo dettagli piatti sulle pareti delle sponde (stelle marine, alghe, stendardi, geroglifici) e
--    sopra le sponde; i pezzi grossi (rana pescatrice, relitto, meduse, sfinge, piramidi, piloni) stanno oltre le
--    sponde, sopra i santuari o in alto;
--  * niente compenetrazioni: ogni oggetto e' controllato (scatole orientate) contro gli elementi del percorso, compreso
--    lo spazio spazzato da quelli mobili, contro le altre parti di ExtremeBuild e contro gli ornamenti gia' piazzati;
--    se tocca qualcosa non viene costruito (gli ornamenti delle sponde provano un altro punto). Tutto cio' che sta
--    sulle sponde si appoggia alle sponde vere lette da Shared.Extreme;
--  * le scelte casuali usano Shared.Util.Rng (come le sponde): nel gioco viene esattamente quello che si controlla
--    offline con tests/extreme_dump.luau e tests/extreme_overlap.py.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Extreme = require(ReplicatedStorage.Shared.Extreme)
local Rng = require(ReplicatedStorage.Shared.Util.Rng)
local Build = require(script.Parent.Build)
local Terrain = require(script.Parent.Terrain)

local ExtremeDecorA = {}
ExtremeDecorA.Debug = nil :: { any }? -- tabella: elenco degli ornamenti scartati e di cosa toccavano (solo per i test)

local HW = Extreme.HalfWidth
local M = Enum.Material
local BALL = Enum.PartType.Ball
local CYL = Enum.PartType.Cylinder
local V3 = Vector3.new
local CF = CFrame.new
local ANG = CFrame.Angles
local rad = math.rad
local UPRIGHT = ANG(0, 0, math.pi / 2) -- cilindro in piedi (l'asse X locale diventa Y)
local FORWARD = ANG(0, math.pi / 2, 0) -- cilindro con l'asse lungo Z locale (disco rivolto in avanti)
local FLIP = ANG(0, math.pi, 0)
local WEDGE = "WedgePart"

-- limiti per i giocatori su mobile (le due sezioni insieme)
local MAX_PARTS = 880
local MAX_LIGHTS = 14
local MAX_EMITTERS = 10
local MAX_FIRES = 4

local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"
local SMOKE = "rbxasset://textures/particles/smoke_main.dds"

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

local C = {
	-- abissi
	coralPink = rgb(255, 92, 158),
	coralOrange = rgb(255, 136, 46),
	coralYellow = rgb(255, 214, 56),
	coralPurple = rgb(170, 96, 255),
	coralRed = rgb(240, 62, 82),
	coralTip = rgb(255, 232, 214),
	kelp = rgb(56, 188, 88),
	kelpDark = rgb(34, 138, 74),
	kelpLight = rgb(140, 224, 84),
	anemone = rgb(48, 214, 196),
	shell = rgb(255, 230, 204),
	shellPink = rgb(255, 156, 184),
	pearl = rgb(250, 248, 255),
	navy = rgb(38, 42, 104),
	navyLight = rgb(70, 78, 160),
	indigo = rgb(62, 40, 128),
	glowCyan = rgb(110, 244, 255),
	glowPink = rgb(255, 96, 214),
	fin = rgb(128, 76, 236),
	glassFin = rgb(84, 232, 176),
	teeth = rgb(248, 248, 238),
	mouth = rgb(128, 28, 76),
	eye = rgb(255, 214, 40),
	pupil = rgb(24, 22, 30),
	rock = rgb(104, 98, 92),
	rockDark = rgb(84, 80, 80),
	moss = rgb(86, 124, 62),
	water = rgb(120, 200, 240),
	foam = rgb(240, 250, 255),
	log = rgb(132, 86, 48),
	wood = rgb(152, 94, 52),
	woodDark = rgb(104, 64, 38),
	deck = rgb(200, 152, 98),
	sail = rgb(250, 244, 228),
	red = rgb(228, 56, 56),
	gold = rgb(255, 196, 60),
	iron = rgb(72, 74, 84),
	slateBlue = rgb(60, 72, 104),
	brass = rgb(214, 164, 64),
	porthole = rgb(80, 220, 255),
	-- deserto
	sand = rgb(222, 186, 118),
	sandstone = rgb(198, 160, 98),
	sandLight = rgb(242, 216, 162),
	sandDark = rgb(150, 112, 64),
	lapis = rgb(38, 84, 222),
	turquoise = rgb(36, 204, 196),
	terracotta = rgb(210, 104, 56),
	papyrus = rgb(112, 200, 76),
	papyrusTop = rgb(196, 228, 92),
	palmLeaf = rgb(70, 196, 70),
	palmDark = rgb(40, 150, 64),
	trunk = rgb(156, 106, 62),
	coconut = rgb(118, 78, 42),
	black = rgb(40, 38, 50),
	ember = rgb(255, 120, 30),
	sun = rgb(255, 168, 36),
	sunRed = rgb(238, 74, 36),
	bannerRed = rgb(222, 50, 52),
	sphinx = rgb(244, 188, 64),
	sphinxFace = rgb(255, 208, 110),
	pond = rgb(54, 176, 236),
}

---------------------------------------------------------------------------------------------
-- Scatole orientate e controllo delle compenetrazioni
---------------------------------------------------------------------------------------------
type Box = {
	cf: CFrame,
	h: Vector3,
	x0: number,
	x1: number,
	y0: number,
	y1: number,
	z0: number,
	z1: number,
	owner: any,
}

local EPS = 0.03 -- compenetrazione tollerata (contatto fra facce)
local GRID = 16
local grid: { [number]: { Box } } = {}

local function boxOf(cf: CFrame, size: Vector3, owner: any): Box
	local h = size * 0.5
	local r, u, l = cf.RightVector, cf.UpVector, cf.LookVector
	local ex = math.abs(r.X) * h.X + math.abs(u.X) * h.Y + math.abs(l.X) * h.Z
	local ey = math.abs(r.Y) * h.X + math.abs(u.Y) * h.Y + math.abs(l.Y) * h.Z
	local ez = math.abs(r.Z) * h.X + math.abs(u.Z) * h.Y + math.abs(l.Z) * h.Z
	local p = cf.Position
	return {
		cf = cf,
		h = h,
		x0 = p.X - ex,
		x1 = p.X + ex,
		y0 = p.Y - ey,
		y1 = p.Y + ey,
		z0 = p.Z - ez,
		z1 = p.Z + ez,
		owner = owner,
	}
end

-- scatola allineata agli assi fra due angoli
local function aabb(lo: Vector3, hi: Vector3, owner: any): Box
	return boxOf(CF((lo + hi) / 2), hi - lo, owner)
end

local function addBox(b: Box)
	for k = math.floor(b.x0 / GRID), math.floor(b.x1 / GRID) do
		local list = grid[k]
		if not list then
			list = {}
			grid[k] = list
		end
		table.insert(list, b)
	end
end

-- teorema degli assi separatori (Ericson, Real-Time Collision Detection): vero se le due scatole si compenetrano
-- per piu' di EPS
local function sat(a: Box, b: Box): boolean
	local A = { a.cf.RightVector, a.cf.UpVector, a.cf.LookVector }
	local B = { b.cf.RightVector, b.cf.UpVector, b.cf.LookVector }
	local ea = { a.h.X, a.h.Y, a.h.Z }
	local eb = { b.h.X, b.h.Y, b.h.Z }
	local d = b.cf.Position - a.cf.Position
	local R = { {}, {}, {} }
	local AR = { {}, {}, {} }
	for i = 1, 3 do
		for j = 1, 3 do
			local v = A[i]:Dot(B[j])
			R[i][j] = v
			AR[i][j] = math.abs(v) + 1e-6
		end
	end
	local T = { d:Dot(A[1]), d:Dot(A[2]), d:Dot(A[3]) }
	for i = 1, 3 do
		if math.abs(T[i]) > ea[i] + eb[1] * AR[i][1] + eb[2] * AR[i][2] + eb[3] * AR[i][3] - EPS then
			return false
		end
	end
	for j = 1, 3 do
		local t = T[1] * R[1][j] + T[2] * R[2][j] + T[3] * R[3][j]
		if math.abs(t) > ea[1] * AR[1][j] + ea[2] * AR[2][j] + ea[3] * AR[3][j] + eb[j] - EPS then
			return false
		end
	end
	for i = 1, 3 do
		local i1, i2 = i % 3 + 1, (i + 1) % 3 + 1
		for j = 1, 3 do
			local j1, j2 = j % 3 + 1, (j + 1) % 3 + 1
			local ra = ea[i1] * AR[i2][j] + ea[i2] * AR[i1][j]
			local rb = eb[j1] * AR[i][j2] + eb[j2] * AR[i][j1]
			local t = T[i2] * R[i1][j] - T[i1] * R[i2][j]
			local len = math.sqrt(math.max(0, 1 - R[i][j] * R[i][j]))
			if len > 1e-3 and math.abs(t) > ra + rb - EPS * len then
				return false
			end
		end
	end
	return true
end

local lastBlocker: any = nil

local function blocked(b: Box, ignore: { [any]: boolean }?): boolean
	for k = math.floor(b.x0 / GRID), math.floor(b.x1 / GRID) do
		local list = grid[k]
		if list then
			for _, o in list do
				if
					o.owner ~= b.owner
					and not (ignore and ignore[o.owner])
					and o.x0 < b.x1 - EPS
					and o.x1 > b.x0 + EPS
					and o.y0 < b.y1 - EPS
					and o.y1 > b.y0 + EPS
					and o.z0 < b.z1 - EPS
					and o.z1 > b.z0 + EPS
					and sat(o, b)
				then
					lastBlocker = o.owner
					return true
				end
			end
		end
	end
	return false
end

-- Ostacoli: gli elementi del percorso (quelli mobili con tutto lo spazio che spazzano) e le altre parti visibili
-- costruite da ExtremeBuild (bocca del canyon, cartelli, santuari...)
local function addObstacles(root: Instance, mine: Instance)
	for _, p in Extreme.Pieces do
		if p.section > 3 or p.kind == "Kill" then
			continue
		end
		local base = boxOf(p.cframe, p.size, p)
		local lo, hi = V3(base.x0, base.y0, base.z0), V3(base.x1, base.y1, base.z1)
		if p.kind == "Mover" and p.offset then
			local o = p.offset
			if p.mode == "flow" then
				lo += V3(math.min(0, o.X), math.min(0, o.Y), math.min(0, o.Z))
				hi += V3(math.max(0, o.X), math.max(0, o.Y), math.max(0, o.Z))
			else
				local a = V3(math.abs(o.X), math.abs(o.Y), math.abs(o.Z))
				lo -= a
				hi += a
			end
			addBox(aabb(lo, hi, p))
		elseif p.kind == "Spinner" or p.kind == "Sweeper" then
			local c = p.cframe.Position
			local r = math.sqrt((hi.X - lo.X) ^ 2 + (hi.Z - lo.Z) ^ 2) / 2
			addBox(aabb(V3(c.X - r, lo.Y, c.Z - r), V3(c.X + r, hi.Y, c.Z + r), p))
		elseif p.kind == "Swing" then
			-- oscilla attorno all'asse X del perno: fin dove arriva il peso di lato e in basso
			local c = p.cframe.Position
			local h = math.max(p.size.Y, p.size.Z) / 2
			local L = (p.length or 10) + h
			local amp = math.min(p.amplitude or 1, math.pi / 2)
			local side = L * math.sin(amp) + h * math.cos(amp) + 0.3
			local hx = p.size.X / 2 + 0.5
			addBox(aabb(V3(c.X - hx, c.Y - L - 0.3, c.Z - side), V3(c.X + hx, c.Y + 0.4, c.Z + side), p))
		elseif p.kind == "Pulse" and p.style == "Crusher" then
			addBox(aabb(lo, hi + V3(0, (p.rise or 8) + 1, 0), p))
		else
			addBox(base)
		end
	end
	-- le parti degli elementi hanno come proprietario l'elemento (cosi' la sponda su cui si appoggia un ornamento si
	-- puo' escludere dal controllo insieme ai suoi dati)
	for _, d in root:GetDescendants() do
		if d:IsA("BasePart") and d.Transparency < 0.99 and not d:IsDescendantOf(mine) then
			local id = d:GetAttribute("Piece")
			local owner = Extreme.Get(if type(id) == "string" then id else d.Name) or d
			addBox(boxOf(d.CFrame, d.Size, owner))
		end
	end
end

---------------------------------------------------------------------------------------------
-- Costruzione degli oggetti: ogni ornamento e' un Model, controllato tutto insieme prima di restare
---------------------------------------------------------------------------------------------
type Opts = {
	shape: Enum.PartType?,
	class: string?,
	alpha: number?,
	shadow: boolean?,
	shine: number?,
}

local stats = { parts = 0, lights = 0, emitters = 0, fires = 0, skipped = 0 }
local partLimit = MAX_PARTS -- limite della fase in corso (gli ornamenti delle sponde hanno una quota per sezione)
local group: Instance = nil :: any
local obj: Model? = nil
local objParts: { BasePart } = {}
local objShadow = false
local pending = { lights = 0, emitters = 0, fires = 0 }

local function begin(name: string, shadow: boolean?)
	local m = Instance.new("Model")
	m.Name = name
	m.Parent = group
	obj = m
	objParts = {}
	objShadow = shadow == true
	pending.lights, pending.emitters, pending.fires = 0, 0, 0
end

local function P(name: string, size: Vector3, cf: CFrame, color: Color3, material: Enum.Material?, o: Opts?): BasePart
	local opts: Opts = o or {}
	local part = Build.Part({
		name = name,
		size = size,
		cframe = cf,
		color = color,
		material = material or M.SmoothPlastic,
		shape = opts.shape,
		class = opts.class,
		transparency = opts.alpha,
		collide = false,
		query = false,
		castShadow = if opts.shadow == nil then objShadow else opts.shadow,
		parent = obj,
	})
	if opts.shine then
		part.Reflectance = opts.shine
	end
	table.insert(objParts, part)
	return part
end

-- sfera (sempre con le tre misure uguali, come le fa Roblox)
local function ball(
	name: string,
	d: number,
	pos: Vector3 | CFrame,
	color: Color3,
	material: Enum.Material?,
	o: Opts?
): BasePart
	local opts: Opts = o or {}
	opts.shape = BALL
	local cf = if typeof(pos) == "CFrame" then pos else CF(pos)
	return P(name, V3(d, d, d), cf, color, material, opts)
end

-- cilindro dal punto a al punto b (coordinate del mondo)
local function rod(
	name: string,
	a: Vector3,
	b: Vector3,
	d: number,
	color: Color3,
	material: Enum.Material?,
	o: Opts?
): BasePart
	local opts: Opts = o or {}
	opts.shape = CYL
	local mid = (a + b) / 2
	local dir = b - a
	local cf
	if math.abs(dir.Unit.Y) > 0.999 then
		cf = CF(mid) * UPRIGHT
	else
		cf = CFrame.lookAt(mid, b) * FORWARD
	end
	return P(name, V3(dir.Magnitude, d, d), cf, color, material, opts)
end

local function light(part: BasePart, color: Color3, range: number, brightness: number)
	if stats.lights + pending.lights >= MAX_LIGHTS then
		return
	end
	pending.lights += 1
	local l = Instance.new("PointLight")
	l.Color = color
	l.Range = range
	l.Brightness = brightness
	l.Shadows = false
	l.Parent = part
end

local function emitter(part: BasePart, props: { [string]: any })
	if stats.emitters + pending.emitters >= MAX_EMITTERS then
		return
	end
	pending.emitters += 1
	local e = Instance.new("ParticleEmitter")
	e.LightInfluence = 0
	for k, v in props do
		(e :: any)[k] = v
	end
	e.Parent = part
end

local function fire(part: BasePart, size: number)
	if stats.fires + pending.fires >= MAX_FIRES then
		return
	end
	pending.fires += 1
	local f = Instance.new("Fire")
	f.Size = size
	f.Heat = 9
	f.Color = rgb(255, 170, 60)
	f.SecondaryColor = rgb(255, 70, 20)
	f.Parent = part
end

-- Tiene l'oggetto solo se non tocca niente (ignore: proprietari da non controllare) e se sta nel budget. Con pad
-- controlla anche che resti ad almeno pad stud dagli altri (tranne padIgnore: la sponda su cui e' appoggiato), cosi'
-- non ci sono facce quasi complanari con le sponde vicine
local function commit(ignore: { [any]: boolean }?, pad: number?, padIgnore: { [any]: boolean }?): boolean
	local m = obj :: Model
	obj = nil
	local ok = stats.parts + #objParts <= math.min(partLimit, MAX_PARTS)
	lastBlocker = if ok then nil else "budget"
	local boxes = {}
	if ok then
		local grow = V3(2, 2, 2) * (pad or 0)
		for _, part in objParts do
			local b = boxOf(part.CFrame, part.Size, m)
			if blocked(b, ignore) or (pad and blocked(boxOf(part.CFrame, part.Size + grow, m), padIgnore)) then
				ok = false
				break
			end
			table.insert(boxes, b)
		end
	end
	if not ok then
		if ExtremeDecorA.Debug then
			table.insert(ExtremeDecorA.Debug, { m.Name, lastBlocker })
		end
		m:Destroy()
		stats.skipped += 1
		return false
	end
	for _, b in boxes do
		addBox(b)
	end
	stats.parts += #objParts
	stats.lights += pending.lights
	stats.emitters += pending.emitters
	stats.fires += pending.fires
	return true
end

-- Vero se la parte piu' bassa dell'oggetto in costruzione resta ben sopra il terreno (vicino alla montagna; il
-- rumore del terreno vero e' diverso da quello dei test, da qui il margine)
local function aboveTerrain(margin: number): boolean
	local lo = math.huge
	local x0, x1, z0, z1 = math.huge, -math.huge, math.huge, -math.huge
	for _, part in objParts do
		local b = boxOf(part.CFrame, part.Size, nil)
		lo = math.min(lo, b.y0)
		x0, x1 = math.min(x0, b.x0), math.max(x1, b.x1)
		z0, z1 = math.min(z0, b.z0), math.max(z1, b.z1)
	end
	if x1 < -330 then
		return true -- oltre il bordo del terreno
	end
	for _, x in { x0, (x0 + x1) / 2, x1 } do
		for _, z in { z0, (z0 + z1) / 2, z1 } do
			if Terrain.HeightAt(x, z) + margin > lo then
				return false
			end
		end
	end
	return true
end

---------------------------------------------------------------------------------------------
-- Sponde: blocchi di roccia casuali ai lati (Shared.Extreme), con la loro copertura (muschio, sabbia)
---------------------------------------------------------------------------------------------
type Bank = {
	piece: any,
	cap: any,
	cf: CFrame,
	size: Vector3,
	side: number,
	uMin: number,
	uMax: number,
	top: number, -- quota locale (asse Y del blocco) della faccia superiore della copertura
	under: number, -- quota locale del bordo inferiore della copertura (sporge un po' dalle facce)
	hx: number,
	hz: number,
}

local function banksOf(i: number): { [number]: { Bank } }
	local s = Extreme.Sections[i]
	local caps = {}
	for _, p in Extreme.Pieces do
		if p.section == i and p.wall and p.deco then
			table.insert(caps, p)
		end
	end
	local out: { [number]: { Bank } } = { [-1] = {}, [1] = {} }
	for _, p in Extreme.Pieces do
		if p.section ~= i or not p.wall or p.deco or p.kind ~= "Solid" then
			continue
		end
		local c = p.cframe.Position
		local v = c.Z - Extreme.Z
		if s.x0 - c.X >= s.length or math.abs(v) <= HW or p.size.Z > 20 then
			continue -- pareti e tetto del santuario
		end
		local box = boxOf(p.cframe, p.size, p)
		local b: Bank = {
			piece = p,
			cap = nil,
			cf = p.cframe,
			size = p.size,
			side = if v > 0 then 1 else -1,
			uMin = s.x0 - box.x1,
			uMax = s.x0 - box.x0,
			top = p.size.Y / 2,
			under = p.size.Y / 2,
			hx = p.size.X / 2,
			hz = p.size.Z / 2,
		}
		for _, cp in caps do
			local rel = p.cframe:ToObjectSpace(cp.cframe).Position
			if math.abs(rel.X) < 1 and math.abs(rel.Z) < 1 and rel.Y > 0 and rel.Y < p.size.Y / 2 + 3 then
				b.cap = cp
				b.top = math.max(b.top, rel.Y + cp.size.Y / 2)
				b.under = math.min(b.under, rel.Y - cp.size.Y / 2)
				b.hx = math.max(b.hx, cp.size.X / 2)
				b.hz = math.max(b.hz, cp.size.Z / 2)
				break
			end
		end
		table.insert(out[b.side], b)
	end
	for _, list in out do
		table.sort(list, function(a: Bank, b: Bank)
			return a.uMin < b.uMin
		end)
	end
	return out
end

-- Riferimento sulla sponda (assi del blocco, sguardo verso il centro del canyon)
local function bankFrame(b: Bank, lx: number, ly: number, lz: number): CFrame
	local cf = b.cf * CF(lx, ly, lz)
	return if b.side == 1 then cf else cf * FLIP
end

-- sulla copertura; out = distanza dalla mezzeria del blocco verso l'esterno
local function onTop(b: Bank, lx: number, out: number): CFrame
	return bankFrame(b, lx, b.top, b.side * out)
end

-- sulla faccia interna (rivolta al percorso): avanti (-Z) = verso il centro del canyon
local function onFace(b: Bank, lx: number, ly: number): CFrame
	return bankFrame(b, lx, ly, -b.side * b.size.Z / 2)
end

-- quota locale (asse del blocco) della faccia interna alla quota del mondo y
local function faceLocalY(b: Bank, lx: number, y: number): number
	local base = b.cf * V3(lx, 0, -b.side * b.size.Z / 2)
	return (y - base.Y) / b.cf.UpVector.Y
end

-- Pelo dei liquidi (acqua, sabbie mobili) lungo la sezione: superfici larghe quanto il canyon
local function liquidLevels(i: number): { { number } }
	local s = Extreme.Sections[i]
	local out = {}
	for _, p in Extreme.Pieces do
		if p.section == i and p.deco and not p.wall and p.size.Z >= HW * 2 and p.size.Y <= 3 and p.style == nil then
			local c = p.cframe.Position
			table.insert(out, { s.x0 - c.X - p.size.X / 2, s.x0 - c.X + p.size.X / 2, c.Y + p.size.Y / 2 })
		end
	end
	return out
end

local function levelAt(levels: { { number } }, u: number): number
	local best = -math.huge
	for _, l in levels do
		if u >= l[1] - 1 and u <= l[2] + 1 then
			best = math.max(best, l[3])
		end
	end
	return best
end

-- Santuario della sezione i: quota della faccia superiore del tetto e distanza (|v|) della faccia interna delle
-- pareti, lette dagli elementi (se cambiano in Shared.Extreme gli ornamenti restano appoggiati)
local function shrineShell(i: number): (number, number)
	local s = Extreme.Sections[i]
	local roofTop = s.floor + 28
	local wallFace = HW + 0.5
	for _, p in Extreme.Pieces do
		if p.section == i and p.wall and not p.deco and s.x0 - p.cframe.X > s.length then
			local v = math.abs(p.cframe.Z - Extreme.Z)
			if p.size.Z > HW * 2 then
				roofTop = p.cframe.Y + p.size.Y / 2
			elseif v > HW then
				wallFace = v - p.size.Z / 2
			end
		end
	end
	return roofTop, wallFace
end

---------------------------------------------------------------------------------------------
-- Pezzi comuni
---------------------------------------------------------------------------------------------
-- Pinnacolo di roccia sospeso: blocchi sovrapposti sempre piu' stretti verso il basso e una punta. top = centro della
-- faccia superiore (orientata come il riferimento), w x d = pianta in cima, h = altezza fino alla punta
local function pinnacle(
	top: CFrame,
	w: number,
	d: number,
	h: number,
	color: Color3,
	material: Enum.Material,
	cap: Color3?
)
	local h1 = h * 0.3
	P("Rock", V3(w, h1, d), top * CF(0, -h1 / 2, 0), color, material)
	local h2 = h * 0.32
	P(
		"Rock",
		V3(w * 0.78, h2, d * 0.8),
		top * CF(w * 0.04, -h1 - h2 / 2 + 0.6, -d * 0.03) * ANG(0, rad(9), 0),
		color,
		material
	)
	local h3 = h * 0.26
	P(
		"Rock",
		V3(w * 0.52, h3, d * 0.56),
		top * CF(-w * 0.05, -h1 - h2 - h3 / 2 + 1.2, d * 0.04) * ANG(0, rad(-12), 0),
		color,
		material
	)
	local tip = math.min(w, d) * 0.36
	P(
		"Rock",
		V3(tip, tip, tip),
		top * CF(0, -h1 - h2 - h3 + 1.4 - tip * 0.3, 0) * ANG(rad(45), 0, rad(35)),
		color,
		material
	)
	if cap then
		P("Moss", V3(w + 0.4, 0.6, d + 0.4), top * CF(0, 0.3, 0), cap, M.Grass)
	end
end

-- Isola sospesa rotonda (sabbia o roccia sopra, roccia sotto): top = centro della faccia superiore
local function island(top: CFrame, d: number, color: Color3, material: Enum.Material, under: Color3)
	P("Island", V3(4, d, d), top * CF(0, -2, 0) * UPRIGHT, color, material, { shape = CYL })
	local h2 = d * 0.3
	P(
		"IslandRock",
		V3(d * 0.66, h2, d * 0.66),
		top * CF(0, -4 - h2 / 2 + 0.5, 0) * ANG(0, rad(20), 0),
		under,
		M.Sandstone
	)
	local h3 = d * 0.26
	P(
		"IslandRock",
		V3(d * 0.38, h3, d * 0.38),
		top * CF(d * 0.03, -4 - h2 - h3 / 2 + 1, 0) * ANG(0, rad(-15), 0),
		under,
		M.Sandstone
	)
	local tip = d * 0.22
	P(
		"IslandRock",
		V3(tip, tip, tip),
		top * CF(0, -4 - h2 - h3 + 1.2 - tip * 0.25, 0) * ANG(rad(45), 0, rad(35)),
		under,
		M.Sandstone
	)
end

-- Ventaglio di conchiglia (pettine) nel piano XY locale: cerniera in hinge, coste di lunghezza len, tutte dello
-- stesso colore (si sovrappongono vicino alla cerniera) ma girate a turno sul proprio asse: la luce fa vedere i solchi
local function scallop(hinge: CFrame, len: number, ribs: number, spread: number, col: Color3, thick: number)
	for k = 0, ribs - 1 do
		local a = -spread / 2 + spread * k / (ribs - 1)
		local w = len * 0.3
		local rib = hinge * ANG(0, 0, rad(a))
		P(
			"ShellRib",
			V3(w, len, thick),
			rib * CF(0, len / 2, 0) * ANG(0, rad(if k % 2 == 0 then 16 else -16), 0),
			col,
			M.SmoothPlastic
		)
		ball("ShellRim", w * 1.08, rib * CF(0, len, 0), col, M.SmoothPlastic)
	end
end

---------------------------------------------------------------------------------------------
-- Sezione 1: le Rapide degli Abissi
---------------------------------------------------------------------------------------------

-- Ornamenti in cima alle sponde (cf = sulla copertura, sguardo verso il canyon); r = ingombro in pianta
local function coralTree(cf: CFrame, col: Color3, s: number)
	P("CoralBase", V3(0.8 * s, 2 * s, 2 * s), cf * CF(0, 0.4 * s, 0) * UPRIGHT, col, M.SmoothPlastic, { shape = CYL })
	for k, br in { { 10, 20, 4.8 }, { 140, 30, 3.6 }, { 250, 24, 4.2 } } do
		local len = br[3] * s
		local root = cf * CF(0, 0.65 * s, 0) * ANG(0, rad(br[1]), 0) * ANG(rad(br[2]), 0, 0)
		P(
			"Coral",
			V3(len, 0.75 * s, 0.75 * s),
			root * CF(0, len / 2, 0) * UPRIGHT,
			col,
			M.SmoothPlastic,
			{ shape = CYL }
		)
		if k ~= 2 then
			ball("CoralTip", 1.15 * s, root * CF(0, len, 0), C.coralTip, M.SmoothPlastic)
		end
	end
end

local function sponges(cf: CFrame, cols: { Color3 }, s: number)
	for k, t in { { 0, 0, 4.6, 1.5 }, { 1.45, 0.6, 3.1, 1.2 }, { -1.15, 0.95, 2.2, 1.1 } } do
		local h, d = t[3] * s, t[4] * s
		P(
			"Sponge",
			V3(h, d, d),
			cf * CF(t[1] * s, h / 2, t[2] * s) * UPRIGHT,
			cols[k],
			M.SmoothPlastic,
			{ shape = CYL }
		)
	end
end

local function fanCoral(cf: CFrame, col: Color3, s: number)
	P("FanStem", V3(1.4 * s, 0.6 * s, 0.6 * s), cf * CF(0, 0.7 * s, 0) * UPRIGHT, col, M.SmoothPlastic, { shape = CYL })
	local d = 5.2 * s
	P("Fan", V3(0.3 * s, d, d), cf * CF(0, 1.2 * s + d / 2, 0) * FORWARD, col, M.SmoothPlastic, { shape = CYL })
	local d2 = 3.4 * s
	P(
		"Fan",
		V3(0.3 * s, d2, d2),
		cf * CF(1.5 * s, 1.0 * s + d2 / 2, 0.45 * s) * ANG(0, rad(-28), 0) * FORWARD,
		col,
		M.SmoothPlastic,
		{ shape = CYL }
	)
end

local function kelp(cf: CFrame, s: number)
	P(
		"KelpRoot",
		V3(0.6 * s, 2 * s, 2 * s),
		cf * CF(0, 0.3 * s, 0) * UPRIGHT,
		C.kelpDark,
		M.SmoothPlastic,
		{ shape = CYL }
	)
	local col = if math.floor(s * 10 + 0.5) % 2 == 0 then C.kelp else C.kelpLight
	for k, st in { { -0.4, 0.1, 8.5, -7, 13 }, { 0.45, -0.2, 10.5, 6, -10 } } do
		local l1, l2 = st[3] * 0.55 * s, st[3] * 0.5 * s
		local a = cf * CF(st[1] * s, 0.4 * s, st[2] * s) * ANG(0, rad(k * 70), rad(st[4]))
		P("Kelp", V3(1.1 * s, l1, 0.25 * s), a * CF(0, l1 / 2, 0), col, M.SmoothPlastic)
		local b = a * CF(0, l1 - 0.3 * s, 0) * ANG(0, 0, rad(st[5]))
		P("Kelp", V3(0.9 * s, l2, 0.25 * s), b * CF(0, l2 / 2, 0), col, M.SmoothPlastic)
	end
end

local function brainCoral(cf: CFrame, col: Color3, s: number)
	P(
		"CoralBase",
		V3(0.5 * s, 2.4 * s, 2.4 * s),
		cf * CF(0, 0.25 * s, 0) * UPRIGHT,
		C.rockDark,
		M.Slate,
		{ shape = CYL }
	)
	ball("BrainCoral", 3 * s, cf * CF(0, 1.65 * s, 0), col, M.Sand)
end

local function anemone(cf: CFrame, col: Color3, tip: Color3, s: number)
	P("Anemone", V3(1.4 * s, 1.6 * s, 1.6 * s), cf * CF(0, 0.7 * s, 0) * UPRIGHT, col, M.SmoothPlastic, { shape = CYL })
	for k = 0, 3 do
		local root = cf * CF(0, 1.2 * s, 0) * ANG(0, rad(k * 90 + 20), 0) * ANG(rad(38), 0, 0)
		P(
			"Tentacle",
			V3(1.7 * s, 0.42 * s, 0.42 * s),
			root * CF(0, 0.85 * s, 0) * UPRIGHT,
			tip,
			M.SmoothPlastic,
			{ shape = CYL }
		)
	end
end

-- vongola aperta con la perla: la valva di sopra tocca quella di sotto solo lungo la cerniera
local function clamPearl(cf: CFrame, s: number)
	local d = 3.2 * s
	P("Clam", V3(0.5 * s, d, d), cf * CF(0, 0.25 * s, 0) * UPRIGHT, C.shellPink, M.SmoothPlastic, { shape = CYL })
	local hinge = cf * CF(0, 0.5 * s, d / 2 - 0.1 * s) * ANG(rad(52), 0, 0)
	P("Clam", V3(0.45 * s, d, d), hinge * CF(0, 0.225 * s, -d / 2) * UPRIGHT, C.shell, M.SmoothPlastic, { shape = CYL })
	ball("Pearl", 1.3 * s, cf * CF(0, 1.1 * s, -0.2 * s), C.pearl, M.SmoothPlastic, { shine = 0.25 })
end

-- Ornamenti sulla faccia interna delle sponde (f = sulla faccia, avanti = verso il canyon)
local function starfish(f: CFrame, col: Color3, s: number, turn: number)
	for k = 0, 4 do
		P(
			"Starfish",
			V3(0.75 * s, 1.75 * s, 0.32),
			f * ANG(0, 0, turn + rad(k * 72)) * CF(0, 0.8 * s, -0.16),
			col,
			M.SmoothPlastic
		)
	end
end

-- spugne incrostanti: tre dischi colorati accostati (senza sovrapporsi)
local function crust(f: CFrame, rng: Rng.Rng)
	local cols = { C.coralPurple, C.coralOrange, C.coralPink, C.coralYellow }
	local first = rng:NextInteger(1, #cols)
	for k = 1, 3 do
		local d = rng:NextNumber(1.7, 2.4)
		local t = 0.32 + k * 0.08
		local off = V3((k - 2) * 2.6, (if k == 2 then 0.9 else -0.4) + rng:NextNumber(-0.2, 0.2), -t / 2)
		P("Crust", V3(t, d, d), f * CF(off) * FORWARD, cols[(first + k) % #cols + 1], M.SmoothPlastic, { shape = CYL })
	end
end

-- Abbellimento delle sponde della sezione 1, a gruppi: ogni quattro sponde una ha un ornamento grande in cima e
-- uno sulla faccia (stella marina o spugne poco sopra l'acqua), un'altra alghe che pendono dal muschio
local function dressBanks1()
	local banks = banksOf(1)
	local levels = liquidLevels(1)
	local rng = Rng.new(1101)
	-- { nome, raggio in pianta, costruttore }
	local tops: { { any } } = {
		{
			"Coral",
			1.6,
			function(cf: CFrame, k: number)
				coralTree(cf, if k % 2 == 0 then C.coralPink else C.coralOrange, 1.55)
			end,
		},
		{
			"Kelp",
			1.6,
			function(cf: CFrame, k: number)
				kelp(cf, if k % 2 == 0 then 1.6 else 1.4)
			end,
		},
		{
			"Sponges",
			2.4,
			function(cf: CFrame, k: number)
				sponges(
					cf,
					if k % 2 == 0
						then { C.coralYellow, C.coralOrange, C.coralPurple }
						else { C.coralPurple, C.coralPink, C.coralYellow },
					1.5
				)
			end,
		},
		{
			"FanCoral",
			1.2,
			function(cf: CFrame, k: number)
				fanCoral(cf, if k % 2 == 0 then C.coralPurple else C.coralRed, 1.5)
			end,
		},
		{
			"Anemone",
			1.6,
			function(cf: CFrame, _k: number)
				anemone(cf, C.anemone, C.glowPink, 1.5)
			end,
		},
		{
			"Kelp",
			1.6,
			function(cf: CFrame, _k: number)
				kelp(cf, 1.5)
			end,
		},
		{
			"BrainCoral",
			2,
			function(cf: CFrame, k: number)
				brainCoral(cf, if k % 2 == 0 then C.coralPink else C.coralPurple, 1.6)
			end,
		},
		{
			"Clam",
			2.7,
			function(cf: CFrame, _k: number)
				clamPearl(cf, 1.7)
			end,
		},
	}
	local count = { [1] = 0, [-1] = 0 }
	for _, side in { 1, -1 } do
		for k, b in banks[side] do
			local phase = (k + (if side == 1 then 0 else 2)) % 4
			if phase == 1 or (phase == 3 and k % 8 >= 4) then
				continue
			end
			local host = { [b.piece] = true }
			if b.cap then
				host[b.cap] = true
			end
			local uc = (b.uMin + b.uMax) / 2
			local water = levelAt(levels, uc)
			local hi = b.under - 0.03
			if phase == 0 then
				-- in cima
				count[side] += 1
				local which = (count[side] * 3 + (if side == 1 then 0 else 2)) % #tops + 1
				local r = tops[which][2]
				local maxX, maxZ = b.hx - 1.9 - r, b.hz - 0.4 - r
				if maxX > 0 and maxZ > 0 then
					for _ = 1, 5 do
						begin(tops[which][1])
						tops[which][3](
							onTop(b, rng:NextNumber(-maxX, maxX), rng:NextNumber(-maxZ, maxZ * 0.3)),
							count[side]
						)
						if commit(nil, 0.15, host) then
							break
						end
					end
				end
				-- sulla faccia, poco sopra l'acqua
				for _ = 1, 4 do
					local big = count[side] % 3 == 0
					local reach = if big then 4.4 else 3.6
					local lx = rng:NextNumber(-b.size.X / 2 + 1.8 + reach, b.size.X / 2 - 1.8 - reach)
					local lo = if water > -math.huge then faceLocalY(b, lx, water + 1.2) else hi - 12
					local y = lo + reach + rng:NextNumber(0, 2)
					if y > hi - reach or b.size.X < 2 * (1.8 + reach) then
						break
					end
					if count[side] % 2 == 0 then
						begin("Starfish")
						local cols = { C.coralOrange, C.coralRed, C.coralYellow, C.coralPink }
						starfish(
							onFace(b, lx, y),
							cols[rng:NextInteger(1, #cols)],
							if big then 2.3 else 1.8,
							rng:NextNumber(0, 1.2)
						)
					else
						begin("Sponges")
						crust(onFace(b, lx, y), rng)
					end
					if commit(nil, 0.15, host) then
						break
					end
				end
			else
				-- alghe: 3 strisce appese sotto il muschio
				for _ = 1, 3 do
					local lx = rng:NextNumber(-b.size.X / 2 + 4, b.size.X / 2 - 4)
					local lo = if water > -math.huge then faceLocalY(b, lx, water + 1.5) else hi - 12
					local maxL = math.min(10, hi - lo)
					if maxL < 3.5 then
						break
					end
					begin("Seaweed")
					for j = 1, 3 do
						local L = rng:NextNumber(math.max(3.5, maxL * 0.5), maxL)
						P(
							"Seaweed",
							V3(rng:NextNumber(0.95, 1.25), L, 0.16),
							onFace(b, lx + (j - 2) * 1.5, hi - L / 2) * CF(0, 0, -0.08),
							if j == 2 then C.kelpLight else C.kelp,
							M.SmoothPlastic
						)
					end
					if commit(nil, 0.15, host) then
						break
					end
				end
			end
		end
	end
end

-- Rana pescatrice gigante (AbyssAngler) su uno scoglio sospeso: base = punto sotto la mascella, sguardo = muso
local function angler(base: CFrame)
	begin("GiantAngler", true)
	local body = base * CF(0, 10.25, 0)
	ball("AnglerBody", 20, body, C.navy, M.SmoothPlastic)
	P("AnglerJaw", V3(16, 3.5, 13), body * CF(0, -8.5, -4.5), C.navyLight, M.SmoothPlastic)
	P("AnglerLip", V3(15, 2, 3), body * CF(0, -2.5, -8.9), C.navyLight, M.SmoothPlastic)
	local mouth = P("AnglerMouth", V3(14, 3.25, 1), body * CF(0, -5.125, -8.6), C.mouth, M.SmoothPlastic)
	emitter(mouth, {
		Texture = SPARKLE,
		Color = ColorSequence.new(rgb(200, 250, 255), rgb(120, 220, 255)),
		LightEmission = 0.6,
		Size = NumberSequence.new(0.5, 1.1),
		Transparency = NumberSequence.new(0.1, 1),
		Lifetime = NumberRange.new(3, 5),
		Speed = NumberRange.new(2.5, 4.5),
		EmissionDirection = Enum.NormalId.Top,
		SpreadAngle = Vector2.new(25, 25),
		Rate = 5,
	})
	-- denti: sopra appesi al labbro, sotto sulla mascella (triangoli visti da davanti)
	for k, x in { -6, -3, 0, 3, 6 } do
		local mirror = if x < 0 or (x == 0 and k % 2 == 0) then ANG(0, math.pi, 0) else CFrame.identity
		P(
			"Tooth",
			V3(1, 2.4, 1.3),
			body * CF(x, -3.5 - 1.2, -9.9) * mirror * ANG(0, math.pi / 2, 0) * ANG(math.pi, 0, 0),
			C.teeth,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
	end
	for _, x in { -4.5, -1.5, 1.5, 4.5 } do
		local mirror = if x < 0 then ANG(0, math.pi, 0) else CFrame.identity
		P(
			"Tooth",
			V3(1, 2.2, 1.2),
			body * CF(x, -6.75 + 1.1, -10.3) * mirror * ANG(0, math.pi / 2, 0),
			C.teeth,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
	end
	-- occhi gialli con la pupilla
	for _, sx in { -1, 1 } do
		local e = V3(5.2 * sx, 4.6, -7.2)
		local n = e.Unit
		ball("Eye", 4.4, body * CF(e), C.eye, M.SmoothPlastic)
		ball("Pupil", 2.2, body * CF(e + n * 1.45), C.pupil, M.SmoothPlastic)
	end
	-- esca luminosa sulla canna
	local p0, p1, p2, p3 =
		body * V3(0, 9.3, -1.5), body * V3(0, 15, -6), body * V3(0, 15.6, -12), body * V3(0, 12.8, -15.2)
	rod("Lure", p0, p1, 0.9, C.navyLight, M.SmoothPlastic)
	rod("Lure", p1, p2, 0.9, C.navyLight, M.SmoothPlastic)
	rod("Lure", p2, p3, 0.8, C.navyLight, M.SmoothPlastic)
	ball("LureJoint", 1.3, p1, C.glowCyan, M.Neon)
	ball("LureJoint", 1.3, p2, C.glowCyan, M.Neon)
	local bulb = ball("LureBulb", 3.4, body * V3(0, 11.3, -15.6), rgb(200, 252, 255), M.Neon)
	light(bulb, C.glowCyan, 26, 2.2)
	-- pinne: dorsale a punte, pettorali e coda
	for k, f in { { 9.2, 2.5, 22, 4.6 }, { 8.2, 5.8, 40, 4 }, { 6.2, 8.4, 58, 3.4 } } do
		P(
			"Fin",
			V3(0.6, f[4], 2.6),
			body * CF(0, f[1], f[2]) * ANG(rad(f[3]), 0, 0) * CF(0, f[4] / 2 - 0.6, 0),
			if k == 2 then C.glowCyan else C.fin,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
	end
	for _, sx in { -1, 1 } do
		P(
			"Fin",
			V3(0.5, 4.2, 4),
			body * CF(9.3 * sx, -1.5, 2.5) * ANG(0, 0, rad(-50 * sx)) * CF(0, 1.6, 0),
			C.fin,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
		P(
			"Tail",
			V3(0.7, 6, 4.4),
			body * CF(1.5 * sx, 0.5, 9.3) * ANG(rad(70), rad(30 * sx), 0) * CF(0, 2.4, 0),
			C.fin,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
	end
	-- puntini luminosi sui fianchi
	for _, d in { V3(-0.9, 0.05, 0.43), V3(0.9, 0.05, 0.43) } do
		ball("GlowSpot", 1.1, body * CF(d.Unit * 9.9), C.glowCyan, M.Neon)
	end
	-- scoglio sotto la mascella (la mascella poggia sul muschio)
	pinnacle(base * CF(0, -0.6, -2), 18, 16, 64, C.rock, M.Slate, C.moss)
	return commit()
end

-- Relitto di un galeone incagliato su uno scoglio sospeso: frame = centro dello scafo, sguardo = prua
local function shipwreck(frame: CFrame)
	begin("Shipwreck", true)
	P("Hull", V3(9, 6, 26), frame, C.wood, M.WoodPlanks)
	P("Bow", V3(6.4, 6, 6.4), frame * CF(0, 0, -13) * ANG(0, rad(45), 0), C.wood, M.WoodPlanks)
	-- carena a V: due cunei sotto il fondo piatto dello scafo
	for _, sx in { -1, 1 } do
		P(
			"Keel",
			V3(24, 2.4, 4.5),
			frame * CFrame.fromMatrix(V3(2.25 * sx, -4.2, 0.5), V3(0, 0, -sx), V3(0, -1, 0)),
			C.woodDark,
			M.WoodPlanks,
			{ class = WEDGE }
		)
	end
	-- fascia dipinta sotto il parapetto, sul fianco verso il canyon
	P("HullStripe", V3(0.16, 0.9, 24), frame * CF(-4.58, 2.1, 0), C.coralYellow, M.SmoothPlastic)
	-- ponte e parapetti fino al cassero (ci entrano un poco)
	P("Deck", V3(8, 0.4, 17.8), frame * CF(0, 3.2, -3.1), C.deck, M.WoodPlanks)
	for _, sx in { -1, 1 } do
		P("Rail", V3(0.5, 1.2, 17.8), frame * CF(4.25 * sx, 3.6, -3.1), C.woodDark, M.Wood)
	end
	P("SternCastle", V3(9, 4, 7.6), frame * CF(0, 5, 9.6), C.wood, M.WoodPlanks)
	for _, sx in { -1, 1 } do
		P("SternWindow", V3(1.6, 1.4, 0.2), frame * CF(2.2 * sx, 5.3, 13.5), C.coralYellow, M.Neon)
	end
	-- oblo' e squarcio sul fianco verso il canyon (-X locale)
	for _, z in { -6, 0, 6 } do
		P("Porthole", V3(0.3, 1.4, 1.4), frame * CF(-4.65, 0.9, z), C.brass, M.Metal, { shape = CYL })
	end
	P("Hole", V3(0.2, 2.6, 3.4), frame * CF(-4.6, -1.3, 3.2) * ANG(rad(14), 0, 0), rgb(34, 26, 20), M.SmoothPlastic)
	-- albero, pennone e vela strappata davanti all'albero, coffa e bandiera
	local deckTop = 3.4
	rod(
		"Mast",
		(frame * CF(0, deckTop, -1)).Position,
		(frame * CF(0, deckTop + 24, -1)).Position,
		1.3,
		C.woodDark,
		M.Wood
	)
	local yardY = deckTop + 18
	rod(
		"Yard",
		(frame * CF(-6.5, yardY, -2.05)).Position,
		(frame * CF(6.5, yardY, -2.05)).Position,
		0.8,
		C.woodDark,
		M.Wood
	)
	local sail = frame * CF(0, yardY - 0.35 - 4.25, -2.05)
	P("Sail", V3(12, 8.5, 0.25), sail, C.sail, M.Fabric)
	P("SailStripe", V3(12, 1.4, 0.12), sail * CF(0, 1.4, -0.185), C.red, M.Fabric)
	P("SailRag", V3(4.4, 3.2, 0.25), sail * CF(3.4, -5, 0) * ANG(0, 0, rad(16)), C.sail, M.Fabric)
	P(
		"CrowsNest",
		V3(1.4, 3.2, 3.2),
		frame * CF(0, deckTop + 21.5, -1) * UPRIGHT,
		C.wood,
		M.WoodPlanks,
		{ shape = CYL }
	)
	P("Flag", V3(3.2, 2, 0.15), frame * CF(1.65, deckTop + 23, -1), rgb(30, 28, 34), M.Fabric)
	P(
		"Skull",
		V3(0.15, 0.9, 0.9),
		frame * CF(1.9, deckTop + 23.1, -1.15) * FORWARD,
		C.teeth,
		M.SmoothPlastic,
		{ shape = CYL }
	)
	rod(
		"Foremast",
		(frame * CF(0, deckTop, -8.5)).Position,
		(frame * CF(0, deckTop + 8, -13)).Position,
		1.1,
		C.woodDark,
		M.Wood
	)
	rod("Bowsprit", (frame * CF(0, 1.8, -16.5)).Position, (frame * CF(0, 5.6, -24)).Position, 0.8, C.woodDark, M.Wood)
	-- forziere del tesoro sul ponte
	local chest = frame * CF(1.6, deckTop + 0.9, 2.2)
	P("Chest", V3(3, 1.8, 2), chest, C.woodDark, M.WoodPlanks)
	P("ChestBand", V3(3.3, 0.35, 2.3), chest * CF(0, 0.2, 0), C.gold, M.Foil)
	P("ChestLid", V3(3, 0.6, 2), chest * CF(0, 0.9, 1) * ANG(rad(-62), 0, 0) * CF(0, 0.3, -1), C.woodDark, M.WoodPlanks)
	local gold = ball("Gold", 1.9, chest * CF(0, 0.35, 0), C.gold, M.Foil)
	light(gold, C.gold, 12, 1.2)
	-- ancora appesa alla prua, sul fianco verso il canyon
	local hang = frame * CF(-3.4, 2.4, -13.5)
	local a0 = hang.Position
	local a1 = (hang * CF(-1.2, -9, 0)).Position
	rod("Chain", a0, a1, 0.5, C.iron, M.DiamondPlate)
	local anchor = CF(a1) * (frame - frame.Position)
	P(
		"AnchorRing",
		V3(0.4, 1.4, 1.4),
		anchor * CF(0, -0.5, 0) * ANG(0, math.pi / 2, 0),
		C.iron,
		M.DiamondPlate,
		{ shape = CYL }
	)
	P("AnchorShank", V3(0.8, 6, 0.8), anchor * CF(0, -4.1, 0), C.iron, M.DiamondPlate)
	P("AnchorStock", V3(4.4, 0.6, 0.6), anchor * CF(0, -2, 0), C.iron, M.DiamondPlate)
	for _, sx in { -1, 1 } do
		P(
			"AnchorArm",
			V3(0.8, 3.4, 0.8),
			anchor * CF(0, -7, 0) * ANG(0, 0, rad(-52 * sx)) * CF(0, 1.4, 0),
			C.iron,
			M.DiamondPlate
		)
	end
	-- scoglio sotto la chiglia, inclinato come lo scafo
	local rockTop = frame * CF(0, -5.4, 1)
	P("Rock", V3(14, 8, 22), rockTop * CF(0, -4, 0), C.rock, M.Slate)
	P("Rock", V3(12, 26, 16), rockTop * CF(0.5, -19, 0) * ANG(rad(-5), rad(14), rad(4)), C.rock, M.Slate)
	P("Rock", V3(8, 20, 10), rockTop * CF(-0.4, -38, 0.6) * ANG(rad(6), rad(-10), rad(-5)), C.rock, M.Slate)
	P("Rock", V3(6, 6, 6), rockTop * CF(0, -48.5, 0) * ANG(rad(45), 0, rad(35)), C.rock, M.Slate)
	return commit()
end

-- Medusa luminosa sospesa nel vuoto: c = centro della campana (tutta opaca: niente parti trasparenti incrociate)
local function jellyfish(c: Vector3, bell: Color3, glow: Color3)
	begin("Jellyfish")
	local cf = CF(c)
	ball("Bell", 7, cf, bell, M.Glass, { shine = 0.15 })
	P("BellRim", V3(0.8, 7.8, 7.8), cf * CF(0, -0.7, 0) * UPRIGHT, bell, M.Glass, { shape = CYL, shine = 0.15 })
	local crown = ball("Crown", 3.4, cf * CF(0, 2.5, 0), glow, M.Neon)
	light(crown, glow, 18, 1.6)
	for k = 0, 2 do
		local a = rad(k * 120 + 30)
		local top = cf * V3(math.cos(a) * 2.5, -1.4, math.sin(a) * 2.5)
		local mid = top + V3(math.cos(a) * 1.1, -5, math.sin(a) * 1.1)
		local bottom = mid + V3(-math.cos(a) * 0.8, -5.4, -math.sin(a) * 0.8)
		rod("Tentacle", top, mid, 0.34, glow, M.Neon)
		rod("Tentacle", mid, bottom, 0.3, glow, M.Neon)
	end
	for k = 0, 1 do
		local s = if k == 0 then 1 else -1
		local top = cf * V3(0.7 * s, -2.2, 0.4 * s)
		rod("OralArm", top, top + V3(0.6 * s, -7, -0.4 * s), 1, bell, M.Glass)
	end
	if not aboveTerrain(16) then
		(obj :: Model):Destroy()
		obj = nil
		return false
	end
	return commit()
end

-- Cascata che scende dal lato di un pinnacolo verso l'abisso. lip = bordo superiore della faccia da cui cade,
-- avanti (-Z) = fuori dalla roccia; la cima del pinnacolo e' coperta di muschio (spesso 0.6)
local function sideFall(lip: CFrame, width: number, drop: number)
	local foam = P("FallLip", V3(width + 0.8, 0.6, 2.2), lip * CF(0, 0.9, -0.1), C.foam, M.SmoothPlastic)
	local y = 0.6
	for _, sg in { { 0.2, 0.42 }, { 0.42, 0.33 }, { 0.65, 0.25 } } do
		local h = drop * sg[2]
		P("SideFall", V3(width, h, 0.5), lip * CF(0, y - h / 2, -0.9), C.water, M.Glass, { alpha = sg[1] })
		y -= h
	end
	emitter(foam, {
		Texture = SMOKE,
		Color = ColorSequence.new(rgb(240, 250, 255)),
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 2), NumberSequenceKeypoint.new(1, 5) }),
		Transparency = NumberSequence.new(0.5, 1),
		Lifetime = NumberRange.new(1.2, 2),
		Speed = NumberRange.new(2, 5),
		EmissionDirection = Enum.NormalId.Bottom,
		SpreadAngle = Vector2.new(25, 25),
		Rate = 10,
	})
end

-- Pinnacolo con la vongola gigante e la perla, da cui scende una cascata (sezione 1, vortici).
-- top = centro della cima della roccia, sguardo verso chi arriva
local function clamFalls(top: CFrame)
	begin("GiantClam", true)
	pinnacle(top, 16, 14, 70, C.rock, M.Slate, C.moss)
	local cap = top * CF(0, 0.6, 0)
	-- vongola: due valve rotonde (quella di sopra tocca l'altra solo alla cerniera), coste e perla luminosa
	local clam = cap * CF(0, 0, 0.6) * ANG(0, rad(-20), 0)
	local d, h = 10, 1.2
	P("ClamShell", V3(h, d, d), clam * CF(0, h / 2, 0) * UPRIGHT, C.shellPink, M.SmoothPlastic, { shape = CYL })
	local hinge = clam * CF(0, h, d / 2 - 0.3) * ANG(rad(50), 0, 0)
	P("ClamShell", V3(1, d, d), hinge * CF(0, 0.5, -d / 2) * UPRIGHT, C.shell, M.SmoothPlastic, { shape = CYL })
	for k = -2, 2 do
		P(
			"ClamRib",
			V3(0.8, 0.25, d * 0.42),
			hinge * CF(0, 1.125, -d / 2) * ANG(0, rad(k * 26), 0) * CF(0, 0, -d * 0.24),
			C.shellPink,
			M.SmoothPlastic
		)
	end
	local pearl = ball("Pearl", 3.6, clam * CF(0, h + 1.65, -0.8), C.pearl, M.SmoothPlastic, { shine = 0.3 })
	light(pearl, rgb(220, 240, 255), 20, 1.6)
	emitter(pearl, {
		Texture = SPARKLE,
		Color = ColorSequence.new(rgb(255, 255, 255), rgb(150, 230, 255)),
		LightEmission = 1,
		Size = NumberSequence.new(0.5, 0.1),
		Transparency = NumberSequence.new(0, 1),
		Lifetime = NumberRange.new(1, 1.8),
		Speed = NumberRange.new(1, 3),
		SpreadAngle = Vector2.new(180, 180),
		Rate = 8,
	})
	-- la cascata scende dal lato rivolto ai giocatori
	sideFall(top * CF(0, 0, -7), 6, 66)
	return commit()
end

-- Pinnacolo con cascata, alghe e corallo in cima (sezione 1, tratto finale)
local function rockFalls(top: CFrame)
	begin("SideFalls", true)
	pinnacle(top, 14, 12, 64, C.rock, M.Slate, C.moss)
	local cap = top * CF(0, 0.6, 0)
	kelp(cap * CF(-3.4, 0, 2.2), 1.3)
	coralTree(cap * CF(3.2, 0, 1.8), C.coralPink, 1.3)
	sideFall(top * CF(0, 0, -6), 5, 62)
	return commit()
end

-- Portale di travi sopra i tronchi appesi del tratto finale (le corde partono a quota 300 senza appiglio)
local function swingRig(banks: { [number]: { Bank } })
	local s = Extreme.Sections[1]
	local swings = {}
	local ignore = {}
	for _, p in Extreme.Pieces do
		if p.section == 1 and p.kind == "Swing" then
			table.insert(swings, p)
			ignore[p] = true
		end
	end
	if #swings == 0 then
		return
	end
	table.sort(swings, function(a, b)
		return a.cframe.X > b.cframe.X
	end)
	local pivotY = swings[1].cframe.Y
	local firstU = s.x0 - swings[1].cframe.X
	local lastU = s.x0 - swings[#swings].cframe.X
	-- una sponda per lato alla stessa u, con spazio per il palo
	local function bankAt(side: number, u: number): Bank?
		for _, b in banks[side] do
			if u > b.uMin + 2.4 and u < b.uMax - 2.4 then
				return b
			end
		end
		return nil
	end
	local function findU(target: number): (number?, Bank?, Bank?)
		for d = 0, 8, 0.5 do
			for _, sgn in { 1, -1 } do
				local u = target + d * sgn
				local l, r = bankAt(1, u), bankAt(-1, u)
				if l and r then
					return u, l, r
				end
			end
		end
		return nil, nil, nil
	end
	local beamBottom = pivotY + 0.22
	local beamTop = beamBottom + 1.6
	local ends = {}
	for _, target in { firstU - 7, lastU + 7 } do
		local u, bl, br = findU(target)
		if u then
			table.insert(ends, { u, bl, br })
		end
	end
	if #ends < 2 then
		return
	end
	begin("SwingRig", true)
	local u0, u1 = ends[1][1], ends[2][1]
	local a = Extreme.At(1, u0, beamBottom + 0.8, 0)
	local b = Extreme.At(1, u1, beamBottom + 0.8, 0)
	P("RigBeam", V3((b - a).Magnitude + 3, 1.6, 1.8), CF((a + b) / 2), C.log, M.Wood)
	for _, e in ends do
		local u = e[1]
		local tops = {}
		for _, bank in { e[2], e[3] } do
			-- palo verticale con un piede appoggiato alla copertura della sponda
			local lx = (bank.cf:PointToObjectSpace(Extreme.At(1, u, 0, 0))).X
			local foot = onTop(bank, lx, 0)
			P("RigFoot", V3(2.6, 0.5, 2.6), foot * CF(0, 0.25, 0), C.woodDark, M.Wood)
			local base = (foot * CF(0, 0.3, 0)).Position
			local topY = beamTop + 1.6
			rod("RigPost", base, V3(base.X, topY, base.Z), 1.6, C.log, M.Wood)
			table.insert(tops, V3(base.X, topY, base.Z))
		end
		local mid = (tops[1] + tops[2]) / 2
		P("RigCross", V3(1.8, 1.6, (tops[1] - tops[2]).Magnitude + 2.4), CF(mid.X, beamTop + 0.8, mid.Z), C.log, M.Wood)
		-- fasce di ferro ai due lati dell'incrocio con la trave lunga
		for _, dz in { 1.35, -1.35 } do
			P("RigBand", V3(2.1, 1.86, 0.4), CF(mid.X, beamTop + 0.8, Extreme.Z + dz), C.iron, M.DiamondPlate)
		end
	end
	commit(ignore)
end

-- Santuario 1: conchiglia gigante con la perla sopra l'ingresso, statue del Testa di Vetro e della Vipera Abissale
-- (base = sopra il tetto, sguardo verso chi arriva)
local function pedestal(base: CFrame, glow: Color3)
	P("Pedestal", V3(1.6, 4.4, 4.4), base * CF(0, 0.8, 0) * UPRIGHT, C.slateBlue, M.Slate, { shape = CYL })
	P("PedestalRing", V3(0.3, 4.8, 4.8), base * CF(0, 1.3, 0) * UPRIGHT, glow, M.Neon, { shape = CYL })
end

local function glassHeadStatue(base: CFrame)
	pedestal(base, C.glowCyan)
	rod("Stand", (base * CF(0, 1.4, 0)).Position, (base * CF(0, 3.6, 0)).Position, 0.6, C.iron, M.Metal)
	local body = base * CF(0, 5.6, 0)
	ball("Body", 5, body, C.navy, M.SmoothPlastic)
	ball("Dome", 3.9, body * CF(0, 1.5, -0.9), C.glassFin, M.Glass, { shine = 0.2 })
	for _, sx in { -1, 1 } do
		ball("Eye", 1.3, body * CF(0.8 * sx, 2.75, -1.95), rgb(220, 255, 80), M.Neon)
	end
	ball("Mouth", 0.8, body * CF(0, -0.6, -2.35), C.coralOrange, M.SmoothPlastic)
	for _, sx in { -1, 1 } do
		P(
			"Tail",
			V3(0.4, 3.4, 2.6),
			body * CF(0.5 * sx, 0, 2.2) * ANG(rad(60), rad(14 * sx), 0) * CF(0, 1.2, 0),
			C.glassFin,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
	end
	P(
		"Fin",
		V3(0.4, 2.2, 2.4),
		body * CF(0, 2.1, 1.3) * ANG(rad(35), 0, 0) * CF(0, 0.5, 0),
		C.glassFin,
		M.SmoothPlastic,
		{ class = WEDGE }
	)
end

local function viperStatue(base: CFrame)
	pedestal(base, C.glowPink)
	local pts = {
		(base * CF(0, 1.3, 1.2)).Position,
		(base * CF(0, 4.6, 2.2)).Position,
		(base * CF(0, 7.2, 0.6)).Position,
		(base * CF(0, 8.6, -1.2)).Position,
	}
	for k = 1, 3 do
		rod("Body", pts[k], pts[k + 1], 2.2 - k * 0.15, C.indigo, M.SmoothPlastic)
		ball("Joint", 2.2 - k * 0.15, pts[k + 1], C.indigo, M.SmoothPlastic)
	end
	local head = base * CF(0, 9.3, -2.3)
	P("Head", V3(2.4, 2, 3), head, C.indigo, M.SmoothPlastic)
	P("Jaw", V3(2.2, 0.8, 2.6), head * CF(0, -1.6, 0.35) * ANG(rad(-24), 0, 0), C.navy, M.SmoothPlastic)
	for _, sx in { -1, 1 } do
		P(
			"Fang",
			V3(0.3, 2.2, 0.6),
			head * CF(0.75 * sx, -1.6, -1.25) * ANG(0, math.pi / 2, 0) * ANG(math.pi, 0, 0),
			C.teeth,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
		ball("Eye", 0.7, head * CF(1.15 * sx, 0.35, -0.7), C.glowPink, M.Neon)
	end
	P("Fin", V3(0.4, 2.4, 2), base * CF(0, 5.8, 2.7) * ANG(rad(20), 0, 0), C.fin, M.SmoothPlastic, { class = WEDGE })
	ball("Dot", 0.5, base * CF(0.95, 4.6, 2.1), C.glowPink, M.Neon)
	ball("Dot", 0.5, base * CF(-0.95, 6.4, 1.4), C.glowPink, M.Neon)
end

local function shrineCrest1()
	local sh = Extreme.Shrines[1]
	local s = Extreme.Sections[1]
	local u0 = s.length
	local roof = shrineShell(1)
	local facing = ANG(0, -math.pi / 2, 0) -- sguardo verso +X (verso chi arriva)
	begin("ShrineCrest", true)
	local base = CF(Extreme.At(1, u0 + 3, roof, 0)) * facing
	P("CrestBase", V3(14, 2, 4), base * CF(0, 1, 0), C.slateBlue, M.Slate)
	P("CrestTrim", V3(14.2, 0.4, 4.2), base * CF(0, 1.4, 0), C.glowCyan, M.Neon)
	scallop(base * CF(0, 2.6, 0.3), 10.5, 7, 150, C.shellPink, 1)
	local pearl = ball("Pearl", 3.4, base * CF(0, 3.4, -1.6), C.pearl, M.SmoothPlastic, { shine = 0.3 })
	light(pearl, sh.glow, 22, 1.8)
	commit()
	for _, side in { 1, -1 } do
		begin(if side == 1 then "GlassHeadStatue" else "AbyssViperStatue", true)
		local b = CF(Extreme.At(1, u0 + 3.5, roof, side * 17)) * facing
		if side == 1 then
			glassHeadStatue(b)
		else
			viperStatue(b)
		end
		commit()
	end
end

-- Oblo' luminosi sulle pareti interne del santuario 1 (lontano dal portale)
local function shrinePortholes1()
	local s = Extreme.Sections[1]
	local sh = Extreme.Shrines[1]
	local u0 = s.length
	local portalU = s.x0 - sh.portal.Position.X
	local _, wall = shrineShell(1)
	for _, side in { 1, -1 } do
		for _, du in { 13, 43 } do
			local u = u0 + du
			if side == -1 and math.abs(u - portalU) < 10 then
				continue
			end
			begin("Porthole")
			local f = CF(Extreme.At(1, u, s.floor + 13, side * wall)) * (if side == 1 then CFrame.identity else FLIP)
			P("PortholeRim", V3(0.3, 4.6, 4.6), f * CF(0, 0, -0.15) * FORWARD, C.brass, M.Metal, { shape = CYL })
			P("PortholeGlass", V3(0.2, 3.6, 3.6), f * CF(0, 0, -0.35) * FORWARD, C.porthole, M.Neon, { shape = CYL })
			commit()
		end
	end
end

-- Bocca del canyon (lato del ponticello): fauci di rana pescatrice attorno all'ingresso
local function canyonJaws(root: Instance)
	-- architrave sopra l'apertura: la sua faccia verso il ponticello (+X) e' quella delle fauci
	local lintel = root:FindFirstChild("CanyonLintel")
	if not lintel or not lintel:IsA("BasePart") then
		return
	end
	local lp = lintel.CFrame.Position
	local faceX = lp.X + lintel.Size.X / 2
	local Z = lp.Z
	local lintelY = lp.Y - lintel.Size.Y / 2
	local topY = lp.Y + lintel.Size.Y / 2
	begin("CanyonJaws", true)
	for _, v in { -4.5, -2.7, -0.9, 0.9, 2.7, 4.5 } do
		local mirror = if v < 0 then FLIP else CFrame.identity
		P(
			"Fang",
			V3(1, 2.4, 1.6),
			CF(faceX - 0.4, lintelY - 1.2, Z + v) * mirror * ANG(math.pi, 0, 0),
			C.teeth,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
	end
	for _, side in { -1, 1 } do
		local c = V3(faceX, lintelY + 3.6, Z + side * 12.5)
		local face = CFrame.lookAt(c, c + V3(1, 0, 0))
		P("Eye", V3(0.5, 6.4, 6.4), face * CF(0, 0, -0.25) * FORWARD, C.eye, M.SmoothPlastic, { shape = CYL })
		P(
			"Pupil",
			V3(0.4, 3.2, 3.2),
			face * CF(0.5 * side, -0.6, -0.55) * FORWARD,
			C.pupil,
			M.SmoothPlastic,
			{ shape = CYL }
		)
		P(
			"Glint",
			V3(0.3, 1, 1),
			face * CF(-0.4 * side, 0.3, -0.8) * FORWARD,
			C.teeth,
			M.SmoothPlastic,
			{ shape = CYL }
		)
		P("Brow", V3(6, 1.1, 0.7), face * CF(0, 4, -0.35) * ANG(0, 0, rad(16 * side)), C.navy, M.SmoothPlastic)
	end
	-- esca luminosa che pende davanti all'ingresso
	local knob = V3(faceX - 2, topY + 0.4, Z)
	P("LureBase", V3(0.8, 2, 2), CF(knob) * UPRIGHT, C.navy, M.SmoothPlastic, { shape = CYL })
	local p1, p2, p3 = V3(faceX - 1.6, topY + 8, Z), V3(faceX + 5, topY + 10.4, Z), V3(faceX + 8.6, topY + 7.4, Z)
	rod("Lure", knob + V3(0, 0.4, 0), p1, 0.9, C.navyLight, M.SmoothPlastic)
	rod("Lure", p1, p2, 0.9, C.navyLight, M.SmoothPlastic)
	rod("Lure", p2, p3, 0.8, C.navyLight, M.SmoothPlastic)
	ball("LureJoint", 0.9, p1, C.navyLight, M.SmoothPlastic)
	ball("LureJoint", 0.9, p2, C.navyLight, M.SmoothPlastic)
	local bulb = ball("LureBulb", 3, p3 + V3(0.6, -1.5, 0), rgb(200, 252, 255), M.Neon)
	light(bulb, C.glowCyan, 24, 2)
	commit()
end

local function section1(root: Instance)
	group = Build.Model("Abyss", root)
	local function at(u: number, y: number, v: number): Vector3
		return Extreme.At(1, u, y, v)
	end
	-- fauci all'ingresso del canyon
	canyonJaws(root.Parent or root)
	-- rana pescatrice gigante a destra del bacino dei tronchi, rivolta al canyon e a chi arriva
	do
		local p = at(190, 323.75, -50)
		angler(CFrame.lookAt(p, p + V3(0.6, 0, 1)))
	end
	-- relitto a sinistra dei vortici, con la prua verso chi arriva
	do
		local c = at(283, 311, 52)
		local frame = CFrame.lookAt(c, c + V3(1, 0, -0.28)) * ANG(rad(6), 0, rad(-12))
		shipwreck(frame)
	end
	-- vongola gigante con cascata a destra dei vortici, pinnacolo con cascata a sinistra del tratto finale
	do
		local t = at(312, 311, -46)
		clamFalls(CFrame.lookAt(t, t + V3(1, 0, 0)))
		local t2 = at(366, 300, 45)
		rockFalls(CFrame.lookAt(t2, t2 + V3(1, 0, 0)))
	end
	-- meduse sospese sopra le sponde
	jellyfish(at(64, 362, 29), rgb(255, 120, 214), rgb(255, 190, 240))
	jellyfish(at(166, 341, -30), rgb(120, 220, 255), rgb(190, 248, 255))
	jellyfish(at(258, 327, -31), rgb(184, 128, 255), rgb(226, 196, 255))
	local banks = banksOf(1)
	swingRig(banks)
	-- santuario
	shrineCrest1()
	shrinePortholes1()
end

---------------------------------------------------------------------------------------------
-- Sezione 2: il Tempio del Deserto
---------------------------------------------------------------------------------------------

-- prisma triangolare (timpano, piramidion): base larga w e alta h, visto di fronte (-Z) e' un triangolo
local function gable(name: string, cf: CFrame, w: number, h: number, d: number, color: Color3, material: Enum.Material)
	P(name, V3(d, h, w / 2), cf * CF(w / 4, h / 2, 0) * ANG(0, -math.pi / 2, 0), color, material, { class = WEDGE })
	P(name, V3(d, h, w / 2), cf * CF(-w / 4, h / 2, 0) * ANG(0, math.pi / 2, 0), color, material, { class = WEDGE })
end

-- Ornamenti in cima alle sponde di sabbia (cf = sulla copertura, sguardo verso il canyon)
local function urn(cf: CFrame, body: Color3, trim: Color3, s: number)
	P(
		"UrnFoot",
		V3(0.4 * s, 1.4 * s, 1.4 * s),
		cf * CF(0, 0.2 * s, 0) * UPRIGHT,
		trim,
		M.SmoothPlastic,
		{ shape = CYL }
	)
	ball("Urn", 2.2 * s, cf * CF(0, 1.3 * s, 0), body, M.SmoothPlastic)
	P("UrnNeck", V3(1 * s, 0.9 * s, 0.9 * s), cf * CF(0, 2.6 * s, 0) * UPRIGHT, trim, M.SmoothPlastic, { shape = CYL })
end

local function urns(cf: CFrame, s: number)
	urn(cf * CF(-1.4 * s, 0, 0), C.terracotta, C.lapis, s)
	urn(cf * CF(1.3 * s, 0, 0.5 * s), C.turquoise, C.gold, 0.8 * s)
end

-- gatta nera (Bastet) col collare d'oro
local function catStatue(cf: CFrame, s: number)
	P("CatBase", V3(2.2 * s, 0.6 * s, 3 * s), cf * CF(0, 0.3 * s, 0), C.sandLight, M.Sandstone)
	P(
		"CatBody",
		V3(2.8 * s, 1.7 * s, 1.7 * s),
		cf * CF(0, 2 * s, 0.2 * s) * UPRIGHT,
		C.black,
		M.SmoothPlastic,
		{ shape = CYL }
	)
	P(
		"CatCollar",
		V3(0.35 * s, 1.95 * s, 1.95 * s),
		cf * CF(0, 3.1 * s, 0.2 * s) * UPRIGHT,
		C.gold,
		M.Foil,
		{ shape = CYL }
	)
	ball("CatHead", 1.6 * s, cf * CF(0, 3.9 * s, 0.1 * s), C.black, M.SmoothPlastic)
	for _, sx in { -1, 1 } do
		local mirror = if sx < 0 then FLIP else CFrame.identity
		P(
			"CatEar",
			V3(0.3 * s, 1.1 * s, 0.7 * s),
			cf * CF(0.42 * sx * s, 4.85 * s, 0.15 * s) * mirror * ANG(0, math.pi / 2, 0),
			C.black,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
	end
end

local function papyrus(cf: CFrame, s: number)
	P(
		"PapyrusRoot",
		V3(0.5 * s, 1.6 * s, 1.6 * s),
		cf * CF(0, 0.25 * s, 0) * UPRIGHT,
		C.palmDark,
		M.SmoothPlastic,
		{ shape = CYL }
	)
	for _, st in { { 0, 6.5, 8 }, { 125, 5.2, 16 }, { 245, 4.4, 12 } } do
		local root = cf * CF(0, 0.35 * s, 0) * ANG(0, rad(st[1]), 0) * ANG(rad(st[3]), 0, 0)
		local len = st[2] * s
		P(
			"Papyrus",
			V3(len, 0.32 * s, 0.32 * s),
			root * CF(0, len / 2, 0) * UPRIGHT,
			C.papyrus,
			M.SmoothPlastic,
			{ shape = CYL }
		)
		ball("PapyrusHead", 1.3 * s, root * CF(0, len + 0.35 * s, 0), C.papyrusTop, M.SmoothPlastic)
	end
end

-- braciere d'oro con le braci; lit = fuoco vero e luce (pochi: costano)
local function brazier(cf: CFrame, s: number, lit: boolean)
	P(
		"BrazierFoot",
		V3(0.4 * s, 1.8 * s, 1.8 * s),
		cf * CF(0, 0.2 * s, 0) * UPRIGHT,
		C.sandDark,
		M.Sandstone,
		{ shape = CYL }
	)
	P("BrazierStand", V3(2.2 * s, 0.7 * s, 0.7 * s), cf * CF(0, 1.4 * s, 0) * UPRIGHT, C.gold, M.Foil, { shape = CYL })
	P("Brazier", V3(0.9 * s, 2.6 * s, 2.6 * s), cf * CF(0, 2.95 * s, 0) * UPRIGHT, C.gold, M.Foil, { shape = CYL })
	local coals = ball("Embers", 1.9 * s, cf * CF(0, 3.5 * s, 0), C.ember, M.Neon)
	if lit then
		fire(coals, 4 * s)
		light(coals, rgb(255, 150, 60), 20, 1.6)
	end
end

local function miniObelisk(cf: CFrame, s: number)
	P("ObeliskBase", V3(2.4 * s, 0.6 * s, 2.4 * s), cf * CF(0, 0.3 * s, 0), C.sandDark, M.Sandstone)
	local h = 6.5 * s
	P("Obelisk", V3(1.3 * s, h, 1.3 * s), cf * CF(0, 0.6 * s + h / 2, 0), C.sandLight, M.Sandstone)
	gable("ObeliskTip", cf * CF(0, 0.6 * s + h, 0), 1.3 * s, 1.1 * s, 1.3 * s, C.gold, M.Foil)
	P(
		"ObeliskGlyph",
		V3(0.3 * s, h * 0.55, 0.15),
		cf * CF(-0.25 * s, 0.6 * s + h * 0.55, -0.65 * s - 0.075),
		C.lapis,
		M.SmoothPlastic
	)
	P(
		"ObeliskGlyph",
		V3(0.3 * s, h * 0.4, 0.15),
		cf * CF(0.3 * s, 0.6 * s + h * 0.62, -0.65 * s - 0.075),
		C.bannerRed,
		M.SmoothPlastic
	)
end

-- palma: tronco in due tratti che pende verso -Z locale, ciuffo di foglie e noci di cocco
local function palm(base: CFrame, h: number, lean: number, s: number, leaf: Color3)
	P("PalmFoot", V3(0.4 * s, 2.2 * s, 2.2 * s), base * CF(0, 0.2 * s, 0) * UPRIGHT, C.trunk, M.Wood, { shape = CYL })
	local p0 = (base * CF(0, 0.25 * s, 0)).Position
	local p1 = (base * CF(0, h * 0.5, -lean * 0.3)).Position
	local p2 = (base * CF(0, h, -lean)).Position
	rod("PalmTrunk", p0, p1, 1.3 * s, C.trunk, M.Wood)
	rod("PalmTrunk", p1, p2 - V3(0, 0.75 * s, 0), 1.1 * s, C.trunk, M.Wood)
	local crown = CF(p2) * base.Rotation
	ball("PalmCrown", 1.9 * s, crown, C.palmDark, M.SmoothPlastic)
	for k = 0, 4 do
		local L = 7.5 * s
		local f = crown * ANG(0, rad(k * 72 + 15), 0) * ANG(rad(-24 - (k % 2) * 12), 0, 0)
		P("Frond", V3(1.6 * s, 0.25 * s, L), f * CF(0, 0, -L / 2), leaf, M.SmoothPlastic)
	end
	ball("Coconut", 0.9 * s, crown * CF(0.62 * s, -1.25 * s, 0.3 * s), C.coconut, M.SmoothPlastic)
	ball("Coconut", 0.9 * s, crown * CF(-0.55 * s, -1.3 * s, -0.4 * s), C.coconut, M.SmoothPlastic)
end

-- Ornamenti piatti sulle facce interne (f = sulla faccia, avanti = verso il canyon)
local function glyphPanel(f: CFrame)
	P("GlyphPanel", V3(5, 3.6, 0.2), f * CF(0, 0, -0.1), C.sandLight, M.Sandstone)
	local z = -0.275
	-- glifi come blocchi con gli stessi assi della lastra (niente facce quasi parallele)
	P("Glyph", V3(1.3, 1.3, 0.15), f * CF(-1.2, 0.2, z), C.sunRed, M.SmoothPlastic)
	-- ankh d'oro
	P("Glyph", V3(0.3, 1.7, 0.15), f * CF(1.05, -0.35, z), C.gold, M.Foil)
	P("Glyph", V3(1.2, 0.3, 0.15), f * CF(1.05, 0.45, z), C.gold, M.Foil)
	P("Glyph", V3(0.8, 0.7, 0.15), f * CF(1.05, 0.95, z), C.gold, M.Foil)
end

local function scarabRelief(f: CFrame)
	P("Scarab", V3(0.2, 2.2, 2.2), f * CF(0, -0.3, -0.1) * FORWARD, C.gold, M.Foil, { shape = CYL })
	P("Scarab", V3(0.2, 1, 1), f * CF(0, 1.1, -0.1) * FORWARD, C.gold, M.Foil, { shape = CYL })
	for _, sx in { -1, 1 } do
		P("ScarabWing", V3(2.6, 0.8, 0.2), f * CF(1.6 * sx, 0, -0.1) * ANG(0, 0, rad(22 * sx)), C.gold, M.Foil)
	end
	P("ScarabSun", V3(0.2, 1.5, 1.5), f * CF(0, 2.6, -0.1) * FORWARD, C.sunRed, M.SmoothPlastic, { shape = CYL })
end

-- stendardo appeso sotto la copertura: asta d'oro, telo e sole d'oro
local function banner(b: Bank, lx: number, len: number, col: Color3)
	local rodY = b.under - 0.03 - 0.19
	P("BannerRod", V3(3.6, 0.36, 0.36), onFace(b, lx, rodY) * CF(0, 0, -0.18), C.gold, M.Foil, { shape = CYL })
	P("Banner", V3(2.8, len, 0.12), onFace(b, lx, rodY - len / 2) * CF(0, 0, -0.06), col, M.Fabric)
	P(
		"BannerSun",
		V3(0.16, 1.3, 1.3),
		onFace(b, lx, rodY - len * 0.42) * CF(0, 0, -0.2) * FORWARD,
		C.gold,
		M.Foil,
		{ shape = CYL }
	)
end

-- Abbellimento delle sponde della sezione 2: ogni quattro sponde una ha un ornamento in cima e un rilievo sulla
-- faccia, un'altra uno stendardo
local function dressBanks2()
	local banks = banksOf(2)
	local levels = liquidLevels(2)
	local rng = Rng.new(2202)
	local tops = {
		{
			"Urns",
			function(cf: CFrame, _k: number)
				urns(cf, 1.25)
			end,
		},
		{
			"Palm",
			function(cf: CFrame, k: number)
				palm(cf, 15 + (k % 3) * 2, 2.5, 1, if k % 2 == 0 then C.palmLeaf else C.palmDark)
			end,
		},
		{
			"CatStatue",
			function(cf: CFrame, _k: number)
				catStatue(cf, 1.35)
			end,
		},
		{
			"Brazier",
			function(cf: CFrame, _k: number)
				brazier(cf, 1.3, false)
			end,
		},
		{
			"Papyrus",
			function(cf: CFrame, _k: number)
				papyrus(cf, 1.3)
			end,
		},
		{
			"Obelisk",
			function(cf: CFrame, _k: number)
				miniObelisk(cf, 1.2)
			end,
		},
	}
	local count = { [1] = 0, [-1] = 0 }
	for _, side in { 1, -1 } do
		for k, b in banks[side] do
			local phase = (k + (if side == 1 then 0 else 2)) % 4
			if phase == 1 or phase == 3 then
				continue
			end
			local host = { [b.piece] = true }
			if b.cap then
				host[b.cap] = true
			end
			local uc = (b.uMin + b.uMax) / 2
			local level = levelAt(levels, uc)
			local hi = b.under - 0.03
			local lowLocal = function(lx: number): number
				return if level > -math.huge then faceLocalY(b, lx, level + 1.5) else hi - 14
			end
			if phase == 0 then
				count[side] += 1
				local which = (count[side] + (if side == 1 then 0 else 3)) % #tops + 1
				local maxX, maxZ = b.hx - 3.2, b.hz - 2.8
				if maxX > 0 and maxZ > 0 then
					for _ = 1, 5 do
						begin(tops[which][1])
						local cf = onTop(b, rng:NextNumber(-maxX, maxX), rng:NextNumber(-maxZ, maxZ * 0.2))
						tops[which][2](cf, count[side])
						if commit(nil, 0.15, host) then
							break
						end
					end
				end
				for _ = 1, 4 do
					local lx = rng:NextNumber(-b.size.X / 2 + 4.8, b.size.X / 2 - 4.8)
					local y = math.max(lowLocal(lx) + 3, hi - 6.5) + rng:NextNumber(-0.8, 0.8)
					if y > hi - 2.4 then
						y = hi - 2.4
					end
					if y < lowLocal(lx) + 2.2 then
						break
					end
					if count[side] % 2 == 0 then
						begin("Glyphs")
						glyphPanel(onFace(b, lx, y))
					else
						begin("ScarabRelief")
						scarabRelief(onFace(b, lx, y - 0.6))
					end
					if commit(nil, 0.15, host) then
						break
					end
				end
			else
				for _ = 1, 3 do
					local lx = rng:NextNumber(-b.size.X / 2 + 3.4, b.size.X / 2 - 3.4)
					local len = math.min(8, hi - lowLocal(lx) - 0.6)
					if len < 4 then
						break
					end
					begin("Banner")
					banner(b, lx, len, if (k + side) % 4 < 2 then C.bannerRed else C.lapis)
					if commit(nil, 0.15, host) then
						break
					end
				end
			end
		end
	end
end

-- Sfinge d'oro (GoldenSphinx) sdraiata su un piedistallo sospeso: top = centro della faccia superiore del
-- piedistallo, sguardo = muso (verso chi arriva); X locale = lontano dal canyon
local function sphinx(top: CFrame)
	begin("GoldenSphinx", true)
	P("Plinth", V3(16, 6, 44), top * CF(0, -3, -2), C.sandstone, M.Sandstone)
	P("PlinthBand", V3(16.3, 1, 44.3), top * CF(0, -1.6, -2), C.lapis, M.SmoothPlastic)
	P("Plinth", V3(12, 20, 32), top * CF(0, -15.5, -2), C.sandstone, M.Sandstone)
	P("Plinth", V3(8, 16, 18), top * CF(0.4, -31, -1) * ANG(0, rad(12), 0), C.sandstone, M.Sandstone)
	P("Plinth", V3(6, 6, 6), top * CF(0, -39, -1) * ANG(rad(45), 0, rad(35)), C.sandstone, M.Sandstone)
	-- corpo sdraiato e zampe
	P("Body", V3(10, 7, 20), top * CF(0, 3.5, 3), C.sphinx, M.SmoothPlastic)
	P("Haunch", V3(11, 8.5, 9), top * CF(0, 4.25, 10.5), C.sphinx, M.SmoothPlastic)
	P("Chest", V3(10.5, 11, 7), top * CF(0, 5.5, -7.5), C.sphinx, M.SmoothPlastic)
	for _, sx in { -1, 1 } do
		P("Paw", V3(3.2, 2.6, 12), top * CF(3.4 * sx, 1.3, -16), C.sphinx, M.SmoothPlastic)
	end
	P("Collar", V3(11.1, 1.4, 7.6), top * CF(0, 7.3, -7.5), C.lapis, M.SmoothPlastic)
	-- testa col copricapo a strisce
	P("Head", V3(7.6, 8, 7), top * CF(0, 15, -8.5), C.sphinxFace, M.SmoothPlastic)
	P("Nemes", V3(9.6, 7.6, 7.4), top * CF(0, 16.4, -7.6), C.gold, M.Foil)
	P("NemesStripe", V3(9.8, 1, 7.6), top * CF(0, 17.6, -7.6), C.lapis, M.SmoothPlastic)
	for _, sx in { -1, 1 } do
		P("Lappet", V3(2, 6.8, 2), top * CF(3.9 * sx, 11.7, -10.6), C.lapis, M.SmoothPlastic)
		P("Eye", V3(1.5, 0.7, 0.2), top * CF(1.7 * sx, 16, -12.1), C.black, M.SmoothPlastic)
	end
	P("Uraeus", V3(2.2, 1, 1), top * CF(0, 20.3, -11.3) * UPRIGHT, C.gold, M.Foil, { shape = CYL })
	P("Nose", V3(1.2, 1.8, 1), top * CF(0, 14.4, -12.5), C.sphinxFace, M.SmoothPlastic, { class = WEDGE })
	P("Mouth", V3(2, 0.35, 0.15), top * CF(0, 12.8, -12.075), rgb(150, 70, 40), M.SmoothPlastic)
	P("Beard", V3(1.6, 3.4, 1.2), top * CF(0, 10.2, -12), C.lapis, M.SmoothPlastic)
	-- coda lungo il fianco
	rod("Tail", (top * CF(5.6, 0.45, 14.2)).Position, (top * CF(5.6, 0.45, 3)).Position, 0.9, C.sphinx, M.SmoothPlastic)
	ball("TailTip", 1.5, top * CF(5.6, 0.75, 2.4), C.lapis, M.SmoothPlastic)
	-- ali ripiegate all'insu', come il pet (la piuma d'oro sta un poco piu' in fuori)
	for _, sx in { -1, 1 } do
		local root = top * CF(4.4 * sx, 6.5, -1) * ANG(0, 0, rad(-14 * sx))
		for k, f in { { 14, 30 }, { 12, 48 }, { 10, 66 } } do
			local out = if k == 2 then 0.3 * sx else 0
			P(
				"Feather",
				V3(0.7, f[1], 2.6),
				root * CF(out, 0, 0) * ANG(rad(f[2]), 0, 0) * CF(0, f[1] / 2, 0),
				if k == 2 then C.gold else C.lapis,
				M.SmoothPlastic
			)
		end
	end
	return commit()
end

-- Piramide a gradoni su un'isola di sabbia sospesa: top = centro della base
local function pyramidIsland(top: CFrame, size: number, height: number, steps: number)
	begin("Pyramid", true)
	island(top, size * 1.42 + 4, C.sand, M.Sand, C.sandstone)
	local h = height / steps
	for k = 0, steps - 1 do
		local w = size * (1 - k / steps)
		local last = k == steps - 1
		P(
			"PyramidStep",
			V3(w, h, w),
			top * CF(0, (k + 0.5) * h, 0),
			if last then C.gold else C.sandLight,
			if last then M.Foil else M.Sandstone
		)
	end
	return commit()
end

-- Oasi su un'isola sospesa: laghetto, palme e papiri
local function oasis(top: CFrame)
	begin("Oasis", true)
	island(top, 30, C.sand, M.Sand, C.sandstone)
	P("Pond", V3(0.4, 12, 12), top * CF(-1, 0, 1) * UPRIGHT, C.pond, M.SmoothPlastic, { shape = CYL, shine = 0.2 })
	palm(top * CF(-9, 0, -4) * ANG(0, rad(40), 0), 17, 3, 1, C.palmLeaf)
	palm(top * CF(7.5, 0, -6) * ANG(0, rad(-120), 0), 20, 4, 1.1, C.palmDark)
	papyrus(top * CF(-6.5, 0, 7.5), 1.2)
	return commit()
end

-- colonna con base, fascia dipinta e capitello a loto (capital = false: spezzata)
local function column(base: CFrame, h: number, capital: boolean)
	P("ColumnBase", V3(1, 4.2, 4.2), base * CF(0, 0.5, 0) * UPRIGHT, C.sandDark, M.Sandstone, { shape = CYL })
	P("Column", V3(h, 3.2, 3.2), base * CF(0, 0.9 + h / 2, 0) * UPRIGHT, C.sandLight, M.Sandstone, { shape = CYL })
	P(
		"ColumnBand",
		V3(0.8, 3.5, 3.5),
		base * CF(0, 0.9 + h - 1.6, 0) * UPRIGHT,
		C.lapis,
		M.SmoothPlastic,
		{ shape = CYL }
	)
	if capital then
		P(
			"Capital",
			V3(1.6, 4.4, 4.4),
			base * CF(0, h + 1.6, 0) * UPRIGHT,
			C.turquoise,
			M.SmoothPlastic,
			{ shape = CYL }
		)
		P("Abacus", V3(4.6, 1, 4.6), base * CF(0, h + 2.9, 0), C.sandLight, M.Sandstone)
	end
end

-- Colonnato in rovina su una piattaforma sospesa: top = centro della piattaforma, X locale lungo il canyon
local function colonnade(top: CFrame)
	begin("Colonnade", true)
	P("Platform", V3(34, 3, 12), top * CF(0, -1.5, 0), C.sandstone, M.Sandstone)
	P("Platform", V3(26, 14, 9), top * CF(0, -9.25, 0) * ANG(0, rad(4), 0), C.sandstone, M.Sandstone)
	P("Platform", V3(15, 13, 7), top * CF(0.5, -21.5, 0) * ANG(0, rad(-7), 0), C.sandstone, M.Sandstone)
	P("Platform", V3(5, 5, 5), top * CF(0, -28.5, 0) * ANG(rad(45), 0, rad(35)), C.sandstone, M.Sandstone)
	local h = 17
	for k, x in { -11, -3.5, 4, 11.5 } do
		column(top * CF(x, 0, 0), if k == 3 then 7 else h, k ~= 3)
	end
	P("Lintel", V3(12.1, 2.2, 4.6), top * CF(-7.25, h + 3.4 + 1.1, 0), C.sandLight, M.Sandstone)
	P("LintelStripe", V3(12.1, 0.6, 0.16), top * CF(-7.25, h + 4.5, -2.38), C.lapis, M.SmoothPlastic)
	P(
		"Drum",
		V3(3.6, 3.2, 3.2),
		top * CF(7.8, 1.6, 3.6) * ANG(0, rad(70), 0),
		C.sandLight,
		M.Sandstone,
		{ shape = CYL }
	)
	return commit()
end

-- Disco alato (sole rosso con le ali) sulla faccia f (avanti = fuori dal muro)
local function wingedSun(f: CFrame, s: number)
	P("WingedSun", V3(0.5, 3.4 * s, 3.4 * s), f * CF(0, 0, -0.25) * FORWARD, C.sunRed, M.SmoothPlastic, { shape = CYL })
	for _, sx in { -1, 1 } do
		P(
			"Wing",
			V3(10 * s, 1.5 * s, 0.4),
			f * CF(sx * 7.2 * s, 0.3 * s, -0.2) * ANG(0, 0, rad(7 * sx)),
			C.lapis,
			M.SmoothPlastic
		)
		P(
			"WingGold",
			V3(8 * s, 0.5 * s, 0.16),
			f * CF(sx * 7.4 * s, 0.3 * s, -0.2) * ANG(0, 0, rad(7 * sx)) * CF(0, -0.1 * s, -0.28),
			C.gold,
			M.Foil
		)
	end
end

-- Porta del deserto all'uscita del santuario 1: due pilastri, architrave col disco alato, bracieri accesi
local function desertGate()
	local u = 7
	local top = 308
	local facing = ANG(0, -math.pi / 2, 0) -- verso +X: verso chi esce dal santuario
	begin("DesertGate", true)
	for _, side in { -1, 1 } do
		P("GatePillar", V3(6, top - 254, 6), CF(Extreme.At(2, u, (254 + top) / 2, side * 40)), C.sandstone, M.Sandstone)
		P(
			"GatePillar",
			V3(5, 5, 5),
			CF(Extreme.At(2, u, 256, side * 40)) * ANG(rad(45), 0, rad(35)),
			C.sandstone,
			M.Sandstone
		)
		P("GateBand", V3(6.4, 1.2, 6.4), CF(Extreme.At(2, u, top - 3, side * 40)), C.lapis, M.SmoothPlastic)
		P("GateCapital", V3(7, 1.6, 7), CF(Extreme.At(2, u, top + 0.8, side * 40)), C.gold, M.Foil)
	end
	local lintelY = top + 1.6
	P("GateLintel", V3(6, 4, 87), CF(Extreme.At(2, u, lintelY + 2, 0)), C.sandstone, M.Sandstone)
	wingedSun(CF(Extreme.At(2, u - 3, lintelY + 2, 0)) * facing, 1)
	for _, side in { -1, 1 } do
		-- stendardi appesi all'architrave, sopra le sponde
		local f = CF(Extreme.At(2, u - 3, lintelY + 3.6, side * 28)) * facing
		P("Banner", V3(3, 7, 0.12), f * CF(0, -3.5, -0.06), C.bannerRed, M.Fabric)
		P("BannerBand", V3(3, 0.6, 0.16), f * CF(0, -6, -0.2), C.gold, M.Foil)
	end
	commit()
	for _, side in { -1, 1 } do
		begin("GateBrazier", true)
		brazier(CF(Extreme.At(2, u, lintelY + 4, side * 40)) * facing, 1.5, true)
		commit()
	end
end

-- Anubi (AnubisGuard) in piedi: base = sopra il cornicione, sguardo verso chi arriva
local function anubis(base: CFrame)
	P("AnubisPlinth", V3(5, 1.2, 5), base * CF(0, 0.6, 0), C.sandLight, M.Sandstone)
	for _, sx in { -1, 1 } do
		P("AnubisLeg", V3(1.3, 6, 1.6), base * CF(0.9 * sx, 4.2, 0), C.black, M.SmoothPlastic)
		P("AnubisArm", V3(1.1, 4.4, 1.2), base * CF(2.45 * sx, 11.2, 0), C.black, M.SmoothPlastic)
		P(
			"AnubisEar",
			V3(0.5, 3.2, 1.2),
			base * CF(0.75 * sx, 17.85, 0.2) * (if sx < 0 then FLIP else CFrame.identity) * ANG(0, math.pi / 2, 0),
			C.black,
			M.SmoothPlastic,
			{ class = WEDGE }
		)
		P("AnubisEye", V3(0.55, 0.25, 0.1), base * CF(0.65 * sx, 15.5, -1.45), C.glowCyan, M.Neon)
	end
	P("AnubisKilt", V3(3.8, 2.6, 2.4), base * CF(0, 7.6, 0), C.gold, M.Foil)
	P("AnubisKiltStripe", V3(3.6, 0.6, 0.16), base * CF(0, 7.3, -1.28), C.lapis, M.SmoothPlastic)
	P("AnubisTorso", V3(3.8, 4.6, 2.2), base * CF(0, 11.2, 0), C.black, M.SmoothPlastic)
	P("AnubisCollar", V3(0.9, 4.6, 4.6), base * CF(0, 13.2, 0) * UPRIGHT, C.lapis, M.SmoothPlastic, { shape = CYL })
	P("AnubisHead", V3(2.4, 2.6, 2.8), base * CF(0, 14.95, 0), C.black, M.SmoothPlastic)
	P("AnubisSnout", V3(1.3, 1.2, 2.4), base * CF(0, 14.5, -2.4), C.black, M.SmoothPlastic)
	rod(
		"AnubisStaff",
		(base * CF(2.3, 1.2, -1.6)).Position,
		(base * CF(2.3, 17.5, -1.6)).Position,
		0.5,
		C.lapis,
		M.SmoothPlastic
	)
	P("AnubisStaffTop", V3(1.4, 0.6, 0.6), base * CF(2.3, 17.6, -1.6) * ANG(0, 0, rad(-20)), C.gold, M.Foil)
end

-- Scarabeo del sole (SunScarab) che regge il sole: base = sopra l'architrave
local function sunScarab(base: CFrame)
	ball("ScarabBody", 5, base * CF(0, 2.9, 0.4), C.turquoise, M.SmoothPlastic, { shine = 0.15 })
	ball("ScarabHead", 2.4, base * CF(0, 2.7, -2.4), C.navy, M.SmoothPlastic)
	for _, sx in { -1, 1 } do
		for _, sz in { -1, 1 } do
			local a = (base * CF(1.4 * sx, 2.1, 0.4 + 1.2 * sz)).Position
			local b = (base * CF(2.9 * sx, 0.25, 0.4 + 2.3 * sz)).Position
			rod("ScarabLeg", a, b, 0.45, C.navy, M.SmoothPlastic)
		end
		rod(
			"ScarabArm",
			(base * CF(0.8 * sx, 3.2, -2.2)).Position,
			(base * CF(1.2 * sx, 7.4, -2.6)).Position,
			0.45,
			C.navy,
			M.SmoothPlastic
		)
		P(
			"ScarabWing",
			V3(0.2, 3.6, 5),
			base * CF(2.3 * sx, 3.6, 1.4) * ANG(rad(-10), 0, rad(-28 * sx)),
			rgb(150, 224, 255),
			M.SmoothPlastic
		)
	end
	local sun = ball("Sun", 4.4, base * CF(0, 9.4, -2.6), C.sun, M.Neon)
	light(sun, C.sun, 26, 2)
	emitter(sun, {
		Texture = SPARKLE,
		Color = ColorSequence.new(rgb(255, 236, 140), rgb(255, 150, 40)),
		LightEmission = 1,
		Size = NumberSequence.new(0.6, 0.1),
		Transparency = NumberSequence.new(0, 1),
		Lifetime = NumberRange.new(1.2, 2),
		Speed = NumberRange.new(2, 4),
		SpreadAngle = Vector2.new(180, 180),
		Rate = 12,
	})
end

-- Facciata del santuario 2: due piloni con i rilievi, architrave col disco alato e lo scarabeo, Anubi e bracieri
local function shrineFacade2()
	local s = Extreme.Sections[2]
	local uc = s.length - 2
	local towerTop = 318
	local facing = ANG(0, -math.pi / 2, 0)
	begin("TemplePylons", true)
	for _, side in { -1, 1 } do
		local v = side * 45
		P("Pylon", V3(16, towerTop - 238, 16), CF(Extreme.At(2, uc, (238 + towerTop) / 2, v)), C.sandstone, M.Sandstone)
		P("Pylon", V3(11, 11, 11), CF(Extreme.At(2, uc, 240, v)) * ANG(rad(45), 0, rad(35)), C.sandstone, M.Sandstone)
		P("PylonBand", V3(16.4, 1.2, 16.4), CF(Extreme.At(2, uc, towerTop - 2.4, v)), C.lapis, M.SmoothPlastic)
		P("PylonCornice", V3(17.6, 2.4, 17.6), CF(Extreme.At(2, uc, towerTop + 1.2, v)), C.sandLight, M.Sandstone)
		local face = CF(Extreme.At(2, uc - 8, 0, v)) * facing
		P("PylonPanel", V3(10, 24, 0.3), face * CF(0, 298, -0.15), C.lapis, M.SmoothPlastic)
		P("PylonSun", V3(0.3, 6, 6), face * CF(0, 303, -0.45) * FORWARD, C.gold, M.Foil, { shape = CYL })
		P("PylonStripe", V3(10, 1, 0.3), face * CF(0, 292, -0.45), C.gold, M.Foil)
	end
	P("PylonLintel", V3(10, 6, 74), CF(Extreme.At(2, uc, 303, 0)), C.sandstone, M.Sandstone)
	P("PylonLintelTop", V3(11, 1.4, 74), CF(Extreme.At(2, uc, 306.7, 0)), C.sandLight, M.Sandstone)
	wingedSun(CF(Extreme.At(2, uc - 5, 302.6, 0)) * facing, 1.2)
	commit()
	begin("SunScarabStatue", true)
	sunScarab(CF(Extreme.At(2, uc, 307.4, 0)) * facing)
	commit()
	for _, side in { -1, 1 } do
		begin("AnubisStatue", true)
		anubis(CF(Extreme.At(2, uc + 1, towerTop + 2.4, side * 45)) * facing)
		commit()
		begin("PylonBrazier", true)
		brazier(CF(Extreme.At(2, uc - 5.5, towerTop + 2.4, side * 50.5)) * facing, 1.3, true)
		commit()
	end
end

-- Stendardi sulle pareti interne del santuario 2 (lontano dal portale e dai trofei)
local function shrineBanners2()
	local s = Extreme.Sections[2]
	local sh = Extreme.Shrines[2]
	local u0 = s.length
	local portalU = s.x0 - sh.portal.Position.X
	local _, wall = shrineShell(2)
	for _, side in { 1, -1 } do
		for k, du in { 9, 32 } do
			local u = u0 + du
			if side == -1 and math.abs(u - portalU) < 11 then
				u = u0 + 20
			end
			begin("ShrineBanner")
			local f = CF(Extreme.At(2, u, s.floor + 19.6, side * wall)) * (if side == 1 then CFrame.identity else FLIP)
			P("BannerRod", V3(3.6, 0.36, 0.36), f * CF(0, 0, -0.18), C.gold, M.Foil, { shape = CYL })
			P("Banner", V3(2.8, 8, 0.12), f * CF(0, -4, -0.06), if k % 2 == 0 then C.lapis else C.bannerRed, M.Fabric)
			P("BannerBand", V3(2.8, 0.5, 0.16), f * CF(0, -7.1, -0.2), C.gold, M.Foil)
			P("BannerSun", V3(0.16, 1.3, 1.3), f * CF(0, -3.4, -0.2) * FORWARD, C.gold, M.Foil, { shape = CYL })
			commit()
		end
	end
end

local function section2(root: Instance)
	group = Build.Model("Desert", root)
	local function at(u: number, y: number, v: number): Vector3
		return Extreme.At(2, u, y, v)
	end
	desertGate()
	-- sfinge a sinistra del corridoio delle lame, rivolta a chi arriva
	do
		local p = at(122, 296, 52)
		sphinx(CFrame.lookAt(p, p + V3(1, 0, -0.22)))
	end
	-- colonnato in rovina a destra dei pilastri
	do
		local p = at(66, 284, -48)
		colonnade(CFrame.lookAt(p, p + V3(0, 0, 1)))
	end
	-- oasi a sinistra delle mattonelle
	oasis(CF(at(230, 281, 56)))
	-- piramidi lontane
	pyramidIsland(CF(at(70, 282, -150)), 64, 50, 7)
	pyramidIsland(CF(at(210, 276, -110)), 56, 44, 7)
	pyramidIsland(CF(at(305, 270, 125)), 72, 56, 8)
	shrineFacade2()
	shrineBanners2()
end

---------------------------------------------------------------------------------------------
function ExtremeDecorA.Build(folder: Instance)
	Terrain.Prepare()
	table.clear(grid)
	stats = { parts = 0, lights = 0, emitters = 0, fires = 0, skipped = 0 }
	partLimit = MAX_PARTS
	local root = folder.Parent or folder
	addObstacles(root, folder)
	-- prima i pezzi grossi di tutte e due le sezioni, poi gli ornamenti delle sponde (girano attorno al resto),
	-- ciascuna sezione con la sua quota di parti
	section1(folder)
	section2(folder)
	partLimit = stats.parts + math.floor((MAX_PARTS - stats.parts) * 0.5)
	group = folder:FindFirstChild("Abyss") :: Instance
	dressBanks1()
	partLimit = MAX_PARTS
	group = folder:FindFirstChild("Desert") :: Instance
	dressBanks2()
	folder:SetAttribute("Parts", stats.parts)
	folder:SetAttribute("Lights", stats.lights)
	folder:SetAttribute("Emitters", stats.emitters)
	folder:SetAttribute("Fires", stats.fires)
	folder:SetAttribute("Skipped", stats.skipped)
end

return ExtremeDecorA
