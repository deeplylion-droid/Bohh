-- Arredo del Percorso Estremo, sezioni 3 (Laboratorio dei Geni) e 4 (Inferno): solo decorazioni (le parti del percorso sono in
-- Shared.Extreme e le costruisce ExtremeBuild). Dentro i muri del percorso niente si puo' toccare.
--
-- Regole dell'arredo:
--  * tutte le parti sono ancorate e CanCollide = CanQuery = false: l'anti-cheat convalida solo i dati di Shared.Extreme e la
--    telecamera non deve sbattere contro le decorazioni;
--  * dentro il corridoio (|z - Extreme.Z| <= 21) solo dettagli sottili sulle pareti o strutture alte e irraggiungibili: niente
--    che sembri un appoggio, un laser o un pericolo; le scenografie grandi stanno fuori dai muri e dalle sponde;
--  * niente compenetrazioni: le parti si appoggiano faccia a faccia (le sfere si siedono sul bordo di chi le regge);
--  * niente Random (nei test offline e' diverso da quello di Roblox): le posizioni vengono da un generatore proprio, e vicino
--    alle sponde di roccia (casuali) si leggono i loro ingombri veri da Shared.Extreme.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Extreme = require(ReplicatedStorage.Shared.Extreme)
local Build = require(script.Parent.Build)

local ExtremeDecorB = {}

local HW = Extreme.HalfWidth
local WALL_IN = HW + 0.5 -- faccia interna delle pareti del laboratorio e dei santuari
local Mat = Enum.Material
local RAD = math.rad

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- Laboratorio: bianco, acciaio, ciano e colori accesi da giocattolo
local WHITE = rgb(238, 242, 248)
local LIGHT = rgb(196, 206, 222)
local STEEL = rgb(150, 160, 178)
local DARK = rgb(52, 58, 74)
local CYAN = rgb(80, 255, 220)
local PALE = rgb(200, 255, 248)
local GLASS = rgb(170, 235, 255)
local LIME = rgb(130, 255, 90)
local PURPLE = rgb(176, 90, 255)
local PINK = rgb(255, 120, 200)
local ORANGE = rgb(255, 150, 50)
local YELLOW = rgb(255, 205, 40)
local BLACK = rgb(34, 30, 30)
local COPPER = rgb(226, 122, 62)
local RED = rgb(236, 64, 56)
local BLUE = rgb(40, 130, 255)
local GREEN = rgb(60, 205, 110)
local SCREEN = rgb(22, 52, 120)
local CHALK = rgb(36, 84, 62)
local CREAM = rgb(255, 240, 214)
local FUR = rgb(244, 160, 70)
local GOLD = rgb(255, 196, 60)

---------------------------------------------------------------------------------------------
-- Costruzione delle parti
---------------------------------------------------------------------------------------------
local target: Instance = nil :: any -- modello in cui finiscono le parti create

local function make(
	class: string,
	shape: Enum.PartType?,
	name: string,
	size: Vector3,
	cf: CFrame,
	color: Color3,
	mat: Enum.Material,
	tr: number?,
	shadow: boolean?
): BasePart
	local big = math.max(size.X, size.Y, size.Z) >= 4
	return Build.Part({
		class = class,
		shape = shape,
		name = name,
		size = size,
		cframe = cf,
		color = color,
		material = mat,
		transparency = tr,
		collide = false,
		query = false,
		castShadow = if shadow ~= nil then shadow else (big and mat ~= Mat.Neon and (tr or 0) < 0.3),
		parent = target,
	})
end

local function box(name: string, size: Vector3, cf: CFrame, color: Color3, mat: Enum.Material, tr: number?): BasePart
	return make("Part", nil, name, size, cf, color, mat, tr)
end

-- cuneo di Roblox: faccia piena sotto e dietro (+Z locale), la rampa scende da dietro-in-alto a davanti-in-basso
local function wedge(name: string, size: Vector3, cf: CFrame, color: Color3, mat: Enum.Material, tr: number?): BasePart
	return make("WedgePart", nil, name, size, cf, color, mat, tr)
end

-- cilindro con l'asse lungo la X locale di cf
local function cyl(
	name: string,
	length: number,
	d: number,
	cf: CFrame,
	color: Color3,
	mat: Enum.Material,
	tr: number?
): BasePart
	return make("Part", Enum.PartType.Cylinder, name, Vector3.new(length, d, d), cf, color, mat, tr)
end

local function sphere(name: string, d: number, pos: Vector3, color: Color3, mat: Enum.Material, tr: number?): BasePart
	return make("Part", Enum.PartType.Ball, name, Vector3.new(d, d, d), CFrame.new(pos), color, mat, tr)
end

-- cilindro fra due punti
local function rod(
	name: string,
	a: Vector3,
	b: Vector3,
	d: number,
	color: Color3,
	mat: Enum.Material,
	tr: number?
): BasePart
	local cf = CFrame.lookAt((a + b) / 2, b) * CFrame.Angles(0, RAD(90), 0)
	return cyl(name, (b - a).Magnitude, d, cf, color, mat, tr)
end

-- cartello con testo (le formule e i simboli sono uguali in tutte le lingue: Strings restituisce la chiave)
local function sign(cf: CFrame, size: Vector3, text: string, bg: Color3, fg: Color3): BasePart
	local board = Build.Sign(target, cf, size, text, nil, { bg = bg, text = fg })
	board.CanCollide = false
	board.CanQuery = false
	board.CastShadow = false
	return board
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

local function fire(parent: Instance, size: number, heat: number, color: Color3, secondary: Color3)
	local f = Instance.new("Fire")
	f.Size = size
	f.Heat = heat
	f.Color = color
	f.SecondaryColor = secondary
	f.Parent = parent
end

local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"
local FIRE_TEX = "rbxasset://textures/particles/fire_main.dds"

local function seq(a: number, b: number): NumberSequence
	return NumberSequence.new(a, b)
end

-- generatore deterministico (Park-Miller): uguale in Roblox e nei test offline
local function rng(seed: number): (number, number) -> number
	local s = seed % 2147483646 + 1
	return function(a: number, b: number): number
		s = (s * 16807) % 2147483647
		return a + (b - a) * (s / 2147483647)
	end
end

---------------------------------------------------------------------------------------------
-- Coordinate di sezione (u lungo il percorso verso -X, v di lato verso +Z, y quota assoluta)
---------------------------------------------------------------------------------------------
local function at(i: number, u: number, y: number, v: number): Vector3
	return Extreme.At(i, u, y, v)
end

-- blocco allineato agli assi da (u0, y0, v0) a (u1, y1, v1)
local function span(
	i: number,
	u0: number,
	u1: number,
	y0: number,
	y1: number,
	v0: number,
	v1: number,
	name: string,
	color: Color3,
	mat: Enum.Material,
	tr: number?
): BasePart
	local c = at(i, (u0 + u1) / 2, (y0 + y1) / 2, (v0 + v1) / 2)
	return box(
		name,
		Vector3.new(math.abs(u1 - u0), math.abs(y1 - y0), math.abs(v1 - v0)),
		CFrame.new(c),
		color,
		mat,
		tr
	)
end

-- cilindro verticale da y0 a y1
local function column(
	i: number,
	u: number,
	v: number,
	y0: number,
	y1: number,
	d: number,
	name: string,
	color: Color3,
	mat: Enum.Material,
	tr: number?
): BasePart
	local cf = CFrame.new(at(i, u, (y0 + y1) / 2, v)) * CFrame.Angles(0, 0, RAD(90))
	return cyl(name, y1 - y0, d, cf, color, mat, tr)
end

-- cilindro orizzontale di traverso al percorso (asse z), da v0 a v1
local function crossbar(
	i: number,
	u: number,
	y: number,
	v0: number,
	v1: number,
	d: number,
	name: string,
	color: Color3,
	mat: Enum.Material,
	tr: number?
): BasePart
	local cf = CFrame.new(at(i, u, y, (v0 + v1) / 2)) * CFrame.Angles(0, RAD(90), 0)
	return cyl(name, math.abs(v1 - v0), d, cf, color, mat, tr)
end

-- cilindro orizzontale lungo il percorso (asse x), da u0 a u1
local function runbar(
	i: number,
	u0: number,
	u1: number,
	y: number,
	v: number,
	d: number,
	name: string,
	color: Color3,
	mat: Enum.Material,
	tr: number?
): BasePart
	return cyl(name, math.abs(u1 - u0), d, CFrame.new(at(i, (u0 + u1) / 2, y, v)), color, mat, tr)
end

-- sfera appoggiata sul bordo di un cilindro verticale di raggio rim con la faccia superiore a quota top
local function seatedY(top: number, d: number, rim: number): number
	local r = d / 2
	return top + math.sqrt(math.max(r * r - rim * rim, 0))
end

-- staffa a sbalzo sotto una piattaforma attaccata alla faccia esterna di un muro (side = lato del muro)
local function bracket(
	i: number,
	u0: number,
	u1: number,
	vWall: number,
	vOut: number,
	yTop: number,
	height: number,
	side: number,
	color: Color3,
	mat: Enum.Material
)
	local c = at(i, (u0 + u1) / 2, yTop - height / 2, (vWall + vOut) / 2)
	-- faccia piena contro il muro e sotto la piattaforma, rampa verso il basso e verso il muro
	local rot = if side > 0 then CFrame.Angles(math.pi, 0, 0) else CFrame.Angles(0, 0, math.pi)
	wedge("Bracket", Vector3.new(math.abs(u1 - u0), height, math.abs(vOut - vWall)), CFrame.new(c) * rot, color, mat)
end

-- piattaforma attaccata alla faccia esterna di un muro (vWall), con la staffa sotto
local function annex(
	i: number,
	u0: number,
	u1: number,
	vWall: number,
	vOut: number,
	yTop: number,
	side: number,
	color: Color3,
	mat: Enum.Material
)
	span(i, u0, u1, yTop - 3, yTop, math.min(vWall, vOut), math.max(vWall, vOut), "Annex", color, mat)
	bracket(i, u0 + 2, u1 - 2, vWall, vOut, yTop - 3, 8, side, color, mat)
end

-- quota piu' alta delle parti di muro (pareti, strisce, tetti) della sezione i sopra il punto u, sul lato side
local function wallTop(i: number, u: number, side: number): number
	local x = Extreme.Sections[i].x0 - u
	local best = -math.huge
	for _, p in Extreme.Pieces do
		if p.section == i and p.wall then
			local c, h = p.cframe.Position, p.size / 2
			if math.abs(x - c.X) <= h.X and (c.Z - Extreme.Z) * side >= -0.01 then
				best = math.max(best, c.Y + h.Y)
			end
		end
	end
	return best
end

---------------------------------------------------------------------------------------------
-- SEZIONE 3: Laboratorio dei Geni
---------------------------------------------------------------------------------------------

-- strato piatto appoggiato alla faccia interna di una parete (laboratorio e santuari; off = distanza dalla parete)
local function onWallAt(
	i: number,
	s: number,
	u0: number,
	u1: number,
	y0: number,
	y1: number,
	off: number,
	t: number,
	name: string,
	color: Color3,
	mat: Enum.Material,
	tr: number?
): BasePart
	local a, b = s * (WALL_IN - off), s * (WALL_IN - off - t)
	local p = span(i, u0, u1, y0, y1, math.min(a, b), math.max(a, b), name, color, mat, tr)
	p.CastShadow = false
	return p
end

local function onWall(
	s: number,
	u0: number,
	u1: number,
	y0: number,
	y1: number,
	off: number,
	t: number,
	name: string,
	color: Color3,
	mat: Enum.Material,
	tr: number?
): BasePart
	return onWallAt(3, s, u0, u1, y0, y1, off, t, name, color, mat, tr)
end

-- disco sulla parete (asse lungo z), off = distanza della faccia posteriore dalla parete
local function wallDisc(
	s: number,
	u: number,
	y: number,
	off: number,
	t: number,
	d: number,
	name: string,
	color: Color3,
	mat: Enum.Material
)
	local p =
		cyl(name, t, d, CFrame.new(at(3, u, y, s * (WALL_IN - off - t / 2))) * CFrame.Angles(0, RAD(90), 0), color, mat)
	p.CastShadow = false
	return p
end

-- schermo: cornice bianca, vetro blu e contenuto luminoso (istogramma o righe di codice)
local function wallScreen(s: number, u0: number, u1: number, y0: number, y1: number, kind: string, seed: number)
	onWall(s, u0, u1, y0, y1, 0, 0.2, "ScreenFrame", WHITE, Mat.SmoothPlastic)
	onWall(s, u0 + 0.4, u1 - 0.4, y0 + 0.4, y1 - 0.4, 0.2, 0.1, "Screen", SCREEN, Mat.SmoothPlastic)
	local r = rng(seed)
	local cols = { CYAN, LIME, YELLOW, PINK }
	if kind == "graph" then
		local n = 4
		local w = (u1 - u0 - 1.6) / n
		for k = 0, n - 1 do
			local h = (y1 - y0 - 1.8) * r(0.3, 1)
			local ua = u0 + 0.8 + k * w
			onWall(s, ua + 0.2, ua + w - 0.2, y0 + 0.8, y0 + 0.8 + h, 0.3, 0.06, "ScreenBar", cols[k + 1], Mat.Neon)
		end
	else
		local rows = math.floor((y1 - y0 - 1.4) / 1)
		for k = 0, rows - 1 do
			local y = y1 - 1.2 - k
			local indent = if k % 3 == 0 then 0 else 1
			local len = (u1 - u0 - 2.2 - indent) * r(0.35, 1)
			onWall(
				s,
				u0 + 0.8 + indent,
				u0 + 0.8 + indent + len,
				y - 0.45,
				y,
				0.3,
				0.06,
				"ScreenCode",
				cols[(k % 3) + 1],
				Mat.Neon
			)
		end
	end
end

-- lavagna con una formula
local function wallBoard(s: number, u0: number, u1: number, y0: number, y1: number, text: string)
	onWall(s, u0, u1, y0, y1, 0, 0.2, "BoardFrame", WHITE, Mat.SmoothPlastic)
	local pos = at(3, (u0 + u1) / 2, (y0 + y1) / 2, s * (WALL_IN - 0.25))
	sign(
		CFrame.lookAt(pos, pos + Vector3.new(0, 0, -s)),
		Vector3.new(math.abs(u1 - u0) - 0.8, y1 - y0 - 0.8, 0.1),
		text,
		CHALK,
		rgb(250, 250, 240)
	)
end

-- pannello luminoso con cornice e traversa
local function wallLight(s: number, u0: number, u1: number, y0: number, y1: number)
	onWall(s, u0, u1, y0, y1, 0, 0.2, "PanelFrame", WHITE, Mat.SmoothPlastic)
	local ym = (y0 + y1) / 2
	local glow = rgb(110, 225, 255)
	onWall(s, u0 + 0.5, u1 - 0.5, ym + 0.3, y1 - 0.5, 0.2, 0.08, "PanelLight", glow, Mat.Neon)
	onWall(s, u0 + 0.5, u1 - 0.5, y0 + 0.5, ym - 0.3, 0.2, 0.08, "PanelLight", glow, Mat.Neon)
end

-- tubo luminoso verticale con i due attacchi
local function wallTube(s: number, u: number, y0: number, y1: number, color: Color3)
	onWall(s, u - 0.6, u + 0.6, y0, y0 + 0.6, 0, 0.3, "TubeCap", STEEL, Mat.Metal)
	onWall(s, u - 0.25, u + 0.25, y0 + 0.6, y1 - 0.6, 0, 0.25, "Tube", color, Mat.Neon)
	onWall(s, u - 0.6, u + 0.6, y1 - 0.6, y1, 0, 0.3, "TubeCap", STEEL, Mat.Metal)
end

-- tre tubicini colorati con le fascette e una valvola
local function wallConduits(s: number, u: number, y0: number, y1: number)
	local cols = { RED, YELLOW, BLUE }
	for k = 0, 2 do
		local p = column(3, u + k * 0.6, s * (WALL_IN - 0.225), y0, y1, 0.45, "Conduit", cols[k + 1], Mat.SmoothPlastic)
		p.CastShadow = false
	end
	for _, y in { y0 + 1.6, y1 - 2 } do
		onWall(s, u - 0.35, u + 1.55, y, y + 0.4, 0.45, 0.12, "Clamp", STEEL, Mat.Metal)
	end
	wallDisc(s, u + 0.6, (y0 + y1) / 2, 0.45, 0.15, 1.6, "Valve", RED, Mat.SmoothPlastic)
end

-- fascio di tre tubi grossi dal fondo del vuoto alla cima della parete, con flange e valvola
local function wallPipes(s: number, u: number, y0: number, y1: number, seed: number)
	local cols = { RED, YELLOW, BLUE, GREEN }
	for k = 0, 2 do
		local uu = u + k * 1.8
		local col = cols[((k + seed) % 4) + 1]
		local p = column(3, uu, s * (WALL_IN - 0.8), y0, y1 - 0.6, 1.2, "Pipe", col, Mat.SmoothPlastic)
		p.CastShadow = false
		local f = column(3, uu, s * (WALL_IN - 0.8), y1 - 0.6, y1, 1.6, "PipeFlange", STEEL, Mat.Metal)
		f.CastShadow = false
	end
	-- valvola a volantino sul tubo centrale
	wallDisc(s, u + 1.8, y0 + (y1 - y0) * (0.55 + 0.1 * (seed % 3)), 1.4, 0.2, 2.4, "Valve", RED, Mat.SmoothPlastic)
end

-- oblo' del reattore: anello, vetro luminoso e mozzo
local function wallPorthole(s: number, u: number, y: number)
	wallDisc(s, u, y, 0, 0.3, 8, "PortRing", STEEL, Mat.Metal)
	wallDisc(s, u, y, 0.3, 0.12, 6.4, "PortGlow", CYAN, Mat.Neon)
	wallDisc(s, u, y, 0.42, 0.12, 3, "PortHub", WHITE, Mat.SmoothPlastic)
end

-- Pareti interne: schermi, lavagne, luci e tubi fra un laser e l'altro (mai a meno di 1.5 stud dai raggi)
local function labWalls()
	-- A) griglia laser: pavimento a 262, parete fino a 278
	local A = {
		[-1] = {
			{ "screen", 1.5, 11.5, 265, 274, "graph" },
			{ "board", 16, 24, 267, 272, "E=mc²" },
			{ "light", 28.5, 35.5, 264.5, 275.5 },
			{ "tube", 42, CYAN },
			{ "screen", 48, 56, 266, 273, "code" },
			{ "tube", 62, LIME },
			{ "tube", 70, CYAN },
			{ "board", 76, 84, 267, 272, "a²+b²=c²" },
			{ "conduits", 89.5 },
		},
		[1] = {
			{ "light", 1.5, 11.5, 264.5, 275.5 },
			{ "screen", 16, 24, 266, 273, "code" },
			{ "board", 28, 36, 267, 272, "F=ma" },
			{ "tube", 42, PINK },
			{ "light", 48.5, 55.5, 264.5, 275.5 },
			{ "tube", 62, CYAN },
			{ "tube", 70, LIME },
			{ "screen", 76, 84, 266, 273, "graph" },
			{ "conduits", 89.5 },
		},
	}
	for s, list in A do
		for k, m in list do
			local kind = m[1]
			if kind == "screen" then
				wallScreen(s, m[2], m[3], m[4], m[5], m[6], k * 7 + s)
			elseif kind == "board" then
				wallBoard(s, m[2], m[3], m[4], m[5], m[6])
			elseif kind == "light" then
				wallLight(s, m[2], m[3], m[4], m[5])
			elseif kind == "tube" then
				wallTube(s, m[2], 264, 276, m[3])
			else
				wallConduits(s, m[2], 262.2, 277.4)
			end
		end
	end
	-- B) nastri sopra il vuoto: tubi dal fondo (griglia a 226) fin quasi in cima (286) e due grandi schermi in alto
	for _, b in { { -1, 101, 0 }, { -1, 152, 1 }, { 1, 110, 2 }, { 1, 165, 3 } } do
		wallPipes(b[1], b[2], 226, 284.4, b[3])
	end
	wallScreen(-1, 120, 136, 272, 282, "graph", 11)
	wallScreen(1, 130, 146, 272, 282, "code", 12)
	-- C) sala rotonda: oblo' luminosi del reattore
	for _, s in { -1, 1 } do
		for _, u in { 198, 222 } do
			wallPorthole(s, u, 278)
		end
	end
	-- D) piattaforme volanti: altri fasci di tubi
	for _, b in { { -1, 252, 1 }, { 1, 280, 2 }, { -1, 306, 3 } } do
		wallPipes(b[1], b[2], 226, 266.4, b[3])
	end
end

-- Portale d'ingresso con la lampadina del genio: pilastri bianchi fuori dai muri, architrave alto sopra il corridoio
-- (visibile gia' dall'uscita del santuario 2) col nome della zona
local function labGate()
	local u0, u1 = 7.5, 12.5
	local um = (u0 + u1) / 2
	local top = 292
	for _, s in { -1, 1 } do
		span(3, u0, u1, 232, top - 6, s * 23.5, s * 28.5, "GatePillar", WHITE, Mat.SmoothPlastic)
		span(3, u0 - 1, u1 + 1, 229, 232, s * 23.5, s * 29.5, "GateFoot", DARK, Mat.DiamondPlate)
		span(3, u0 - 0.3, u0, 240, top - 8, s * 25.4, s * 26.6, "GateGlow", CYAN, Mat.Neon)
		-- antenne con la lucina in cima
		column(3, um, s * 26, top, top + 7, 0.4, "GateAntenna", STEEL, Mat.Metal)
		sphere("GateBlink", 1, at(3, um, seatedY(top + 7, 1, 0.2), s * 26), if s < 0 then RED else LIME, Mat.Neon)
	end
	span(3, u0 - 0.5, u1 + 0.5, top - 6, top, -28.5, 28.5, "GateBeam", DARK, Mat.DiamondPlate)
	span(3, u0, u1, top - 6.3, top - 6, -23.5, 23.5, "GateUnderGlow", CYAN, Mat.Neon)
	local pos = at(3, u0 - 0.7, top - 3, 0)
	sign(CFrame.lookAt(pos, pos + Vector3.new(1, 0, 0)), Vector3.new(30, 4.4, 0.4), "Zone_Lab", CYAN, DARK)
	-- lampadina: attacco a vite e bulbo luminoso
	column(3, um, 0, top, top + 1, 4.6, "BulbBase", DARK, Mat.DiamondPlate)
	column(3, um, 0, top + 1, top + 1.8, 4, "BulbThread", STEEL, Mat.Metal)
	column(3, um, 0, top + 1.8, top + 2.6, 4.6, "BulbThread", STEEL, Mat.Metal)
	column(3, um, 0, top + 2.6, top + 3.4, 4, "BulbThread", STEEL, Mat.Metal)
	local bulb = sphere("Bulb", 8, at(3, um, seatedY(top + 3.4, 8, 2), 0), rgb(255, 238, 150), Mat.Neon, 0.1)
	light(bulb, rgb(255, 230, 150), 30, 1.6)
end

-- Vasche col liquido luminoso (sopra, la parte vuota di vetro), su una terrazza attaccata al muro destro
local function labTanks()
	annex(3, 18, 46, 23, 37, 276, 1, LIGHT, Mat.DiamondPlate)
	local liquids = { LIME, rgb(255, 90, 200) }
	for k, u in { 26, 38 } do
		column(3, u, 30, 276, 278, 9, "TankBase", DARK, Mat.DiamondPlate)
		local liquid = column(3, u, 30, 278, 291 + k, 8, "TankLiquid", liquids[k], Mat.Neon, 0.12)
		column(3, u, 30, 291 + k, 296, 8, "TankGlass", GLASS, Mat.Glass, 0.6)
		column(3, u, 30, 296, 298, 9, "TankCap", DARK, Mat.DiamondPlate)
		column(3, u, 30, 298, 299.2, 4, "TankTop", STEEL, Mat.Metal)
		-- anelli di rinforzo fra base e liquido e fra vetro e coperchio sono le flange: niente dentro il vetro
		if k == 1 then
			light(liquid, LIME, 22, 1.4)
			emitter(liquid, {
				Texture = SPARKLE,
				Color = ColorSequence.new(rgb(230, 255, 220)),
				LightEmission = 0.6,
				Size = seq(0.35, 0.15),
				Transparency = seq(0.2, 1),
				Lifetime = NumberRange.new(0.8, 1.3),
				Speed = NumberRange.new(2, 3.5),
				EmissionDirection = Enum.NormalId.Top,
				SpreadAngle = Vector2.new(6, 6),
				Rate = 8,
			})
		end
	end
	runbar(3, 28, 36, 298.6, 30, 0.8, "TankPipe", YELLOW, Mat.SmoothPlastic)
end

-- Schermo gigante col muso della Lince Cibernetica, su una terrazza attaccata al muro sinistro
local function labCatScreen()
	annex(3, 48, 68, -23, -38, 274, -1, LIGHT, Mat.DiamondPlate)
	local center = at(3, 58, 292, -31)
	local face = Vector3.new(0.5, 0, 0.866) -- verso il corridoio e verso chi arriva
	local cf = CFrame.lookAt(center, center + face)
	local W, H = 20, 13
	box("CatScreenFrame", Vector3.new(W, H, 1.2), cf, WHITE, Mat.SmoothPlastic)
	for _, dx in { -7, 7 } do
		local legTop = cf * CFrame.new(dx, -H / 2, 0)
		local h = legTop.Position.Y - 274
		box("CatScreenLeg", Vector3.new(1, h, 1), legTop * CFrame.new(0, -h / 2, 0), STEEL, Mat.Metal)
	end
	-- strati sul fronte (la faccia anteriore del telaio e' a -0.6 lungo Z locale)
	local z = -0.6
	local function layer(
		name: string,
		w: number,
		h: number,
		x: number,
		y: number,
		depth: number,
		t: number,
		color: Color3,
		mat: Enum.Material
	)
		box(name, Vector3.new(w, h, t), cf * CFrame.new(x, y, z - depth - t / 2), color, mat)
	end
	layer("CatScreen", W - 1.2, H - 1.2, 0, 0, 0, 0.1, SCREEN, Mat.SmoothPlastic)
	-- orecchie (triangoli rettangoli col lato verticale all'esterno) con il ciuffo nero della lince sulla punta
	for _, sx in { -1, 1 } do
		local ear = cf * CFrame.new(sx * 2.9, 3, z - 0.1 - 0.03) * CFrame.Angles(0, sx * RAD(90), 0)
		wedge("CatEar", Vector3.new(0.06, 2.6, 2.4), ear, FUR, Mat.SmoothPlastic)
		local tuft = cf * CFrame.new(sx * 3.36, 3.9, z - 0.16 - 0.03) * CFrame.Angles(0, sx * RAD(90), 0)
		wedge("CatTuft", Vector3.new(0.06, 1.6, 1.48), tuft, BLACK, Mat.SmoothPlastic)
	end
	layer("CatHead", 8, 6.6, 0, -1.6, 0.1, 0.06, FUR, Mat.SmoothPlastic)
	layer("CatVisor", 9, 1.7, 0, -0.4, 0.16, 0.06, CYAN, Mat.Neon)
	layer("CatMuzzle", 3.6, 2, 0, -3.3, 0.16, 0.06, CREAM, Mat.SmoothPlastic)
	layer("CatNose", 1.2, 0.6, 0, -2.6, 0.22, 0.06, PINK, Mat.SmoothPlastic)
	layer("CatMouth", 1.8, 0.3, 0, -3.6, 0.22, 0.06, BLACK, Mat.SmoothPlastic)
	for _, sx in { -1, 1 } do
		layer("CatCheek", 1.6, 2.4, sx * 4.8, -3.4, 0.1, 0.06, CREAM, Mat.SmoothPlastic)
	end
end

-- Ponte di tubi sopra il corridoio, retto da due piloni sulle cime delle pareti
local function labPipeBridge(u: number, y: number)
	local cols = { RED, YELLOW, BLUE }
	for _, s in { -1, 1 } do
		local top = wallTop(3, u, s)
		span(3, u - 2.5, u + 2.5, top, y + 2.6, s * 21.6, s * 23, "PipePylon", LIGHT, Mat.DiamondPlate)
		span(3, u - 2.5, u + 2.5, top + 2, top + 3.2, s * 21.4, s * 21.6, "PylonStripe", YELLOW, Mat.SmoothPlastic)
		column(3, u, s * 22.3, y + 2.6, y + 3.4, 1, "PylonLamp", ORANGE, Mat.Neon)
	end
	for k = 0, 2 do
		crossbar(3, u - 1.5 + k * 1.5, y, -21.6, 21.6, 1.3, "BridgePipe", cols[k + 1], Mat.SmoothPlastic)
	end
end

-- Torre delle ampolle: tre ampolle di vetro col liquido colorato su un'asta, dietro il muro sinistro
local function labFlasks()
	annex(3, 104, 126, -23, -40, 286, -1, LIGHT, Mat.DiamondPlate)
	local U, V = 115, -31.5
	column(3, U, V, 286, 289, 6, "FlaskStand", DARK, Mat.DiamondPlate)
	column(3, U, V, 289, 320, 1.4, "FlaskPole", STEEL, Mat.Metal)
	local flasks = {
		{ du = -4.5, dv = 0, y = 297, d = 8, color = LIME },
		{ du = 3.5, dv = -2, y = 306, d = 6.4, color = PURPLE },
		{ du = -2, dv = 3, y = 313, d = 4.6, color = CYAN },
	}
	for _, f in flasks do
		local u, v = U + f.du, V + f.dv
		local r = f.d / 2
		-- anello che regge l'ampolla, con il braccio fino all'asta
		local ringTop = f.y - r * 0.8
		local rim = math.sqrt(r * r - (r * 0.8) ^ 2)
		column(3, u, v, ringTop - 0.5, ringTop, rim * 2, "FlaskRing", STEEL, Mat.Metal)
		rod("FlaskArm", at(3, U, ringTop - 0.25, V), at(3, u, ringTop - 0.25, v), 0.4, STEEL, Mat.Metal)
		sphere("Flask", f.d, at(3, u, f.y, v), f.color, Mat.Neon)
		-- collo e tappo
		local neckD = f.d * 0.3
		local neckBase = f.y + math.sqrt(r * r - (neckD / 2) ^ 2)
		column(3, u, v, neckBase, neckBase + 2, neckD, "FlaskNeck", GLASS, Mat.SmoothPlastic)
		column(3, u, v, neckBase + 2, neckBase + 2.6, neckD + 0.4, "FlaskCork", rgb(196, 140, 90), Mat.Wood)
	end
end

-- Statua della Lince Cibernetica seduta, con gli occhiali luminosi, su un piedistallo dietro il muro destro
local function labCatStatue()
	annex(3, 126, 154, 23, 47, 286, 1, LIGHT, Mat.DiamondPlate)
	column(3, 140, 36, 286, 290, 18, "StatuePlinth", WHITE, Mat.Marble)
	column(3, 140, 36, 290, 290.6, 16.4, "StatueRim", GOLD, Mat.Foil)
	local O = at(3, 140, 290.6, 36)
	local F = Vector3.new(0.65, 0, -1).Unit -- guarda il corridoio e chi arriva
	local L = CFrame.lookAt(O, O + F)
	local function vcylL(name: string, x: number, y0: number, y1: number, z: number, d: number, color: Color3)
		cyl(
			name,
			y1 - y0,
			d,
			L * CFrame.new(x, (y0 + y1) / 2, z) * CFrame.Angles(0, 0, RAD(90)),
			color,
			Mat.SmoothPlastic
		)
	end
	local function ballL(name: string, x: number, y: number, z: number, d: number, color: Color3)
		sphere(name, d, (L * CFrame.new(x, y, z)).Position, color, Mat.SmoothPlastic)
	end
	-- corpo seduto: busto, cosce larghe, petto chiaro, zampe davanti
	vcylL("CatBody", 0, 0, 14, 1.5, 9.6, FUR)
	ballL("CatChest", 0, 9.6, -2.2, 8.6, CREAM)
	for _, sx in { -1, 1 } do
		ballL("CatHaunch", sx * 3.6, 4.2, 2.4, 9, FUR)
		vcylL("CatLeg", sx * 2.2, 0, 8.4, -5, 2.8, FUR)
		ballL("CatPaw", sx * 2.2, 1.55, -6.2, 3.4, CREAM)
	end
	-- testa: cuscinetti dei baffi, mento e naso
	ballL("CatHead", 0, 19.5, -1, 13, FUR)
	for _, sx in { -1, 1 } do
		ballL("CatWhiskerPad", sx * 1.4, 17.6, -6.5, 3.6, CREAM)
	end
	ballL("CatChin", 0, 16.1, -6.1, 2.4, CREAM)
	ballL("CatNose", 0, 18.9, -8.1, 1.6, PINK)
	-- occhiali: due lenti luminose piantate nel muso, con la montatura e il ponticello
	for _, sx in { -1, 1 } do
		cyl(
			"CatLensRim",
			0.5,
			4.6,
			L * CFrame.new(sx * 2.5, 21.6, -6.35) * CFrame.Angles(0, RAD(90), 0),
			DARK,
			Mat.SmoothPlastic
		)
		cyl("CatLens", 1.2, 4, L * CFrame.new(sx * 2.5, 21.6, -7.2) * CFrame.Angles(0, RAD(90), 0), CYAN, Mat.Neon)
	end
	box("CatLensBridge", Vector3.new(1.2, 0.8, 0.8), L * CFrame.new(0, 21.8, -7.3), DARK, Mat.SmoothPlastic)
	-- orecchie a punta (lato verticale verso l'interno) col ciuffo nero che ne copre la punta
	for _, sx in { -1, 1 } do
		local ear = L
			* CFrame.new(sx * 3, 26.4, -0.6)
			* CFrame.Angles(0, 0, -sx * RAD(8))
			* CFrame.Angles(0, -sx * RAD(90), 0)
		wedge("CatEar", Vector3.new(1.6, 6, 4.4), ear, FUR, Mat.SmoothPlastic)
		wedge("CatTuft", Vector3.new(1.8, 1.6, 1.2), ear * CFrame.new(0, 2.65, 1.65), BLACK, Mat.SmoothPlastic)
	end
	-- coda che gira attorno al corpo e sale, con il cubo olografico in punta
	local t0 = (L * CFrame.new(2, 1.2, 5.4)).Position
	local t1 = (L * CFrame.new(7.4, 1.2, 3.6)).Position
	local t2 = (L * CFrame.new(8.6, 9, 2.4)).Position
	rod("CatTail", t0, t1, 2.4, FUR, Mat.SmoothPlastic)
	sphere("CatTailJoint", 2.4, t1, FUR, Mat.SmoothPlastic)
	rod("CatTail", t1, t2, 2.4, FUR, Mat.SmoothPlastic)
	sphere("CatTailTip", 2.4, t2, BLACK, Mat.SmoothPlastic)
	local cube = CFrame.new(t2 + Vector3.new(0, 2.6, 0)) * CFrame.Angles(RAD(35), RAD(45), 0)
	box("CatHoloCube", Vector3.new(2.6, 2.6, 2.6), cube, CYAN, Mat.Neon, 0.35)
end

-- Bobine di Tesla ai lati della sala rotonda, con le scintille
local function labTesla()
	for _, s in { -1, 1 } do
		local u, v = 210, s * 28.5
		annex(3, 202, 218, s * 23, s * 34, 280, s, LIGHT, Mat.DiamondPlate)
		column(3, u, v, 280, 283, 8, "TeslaBase", DARK, Mat.DiamondPlate)
		column(3, u, v, 283, 284, 7.6, "TeslaPrimary", COPPER, Mat.Foil)
		column(3, u, v, 284, 288, 3.6, "TeslaInsulator", WHITE, Mat.SmoothPlastic)
		local y = 288
		for k = 1, 3 do
			column(3, u, v, y, y + 5.6, 4.4, "TeslaCoil", COPPER, Mat.Foil)
			y += 5.6
			if k < 3 then
				column(3, u, v, y, y + 0.6, 4.8, "TeslaBand", WHITE, Mat.SmoothPlastic)
				y += 0.6
			end
		end
		column(3, u, v, y, y + 1, 3, "TeslaNeck", STEEL, Mat.Metal)
		local torus = column(3, u, v, y + 1, y + 3.4, 10, "TeslaTorus", STEEL, Mat.Metal)
		local glow = if s < 0 then CYAN else PURPLE
		sphere("TeslaOrb", 3.2, at(3, u, seatedY(y + 3.4, 3.2, 0.8), v), glow, Mat.Neon)
		light(torus, glow, 24, 1.8)
		emitter(torus, {
			Texture = SPARKLE,
			Color = ColorSequence.new(Color3.new(1, 1, 1), glow),
			LightEmission = 1,
			Size = seq(0.7, 0.1),
			Transparency = seq(0, 1),
			Lifetime = NumberRange.new(0.15, 0.35),
			Speed = NumberRange.new(10, 18),
			SpreadAngle = Vector2.new(180, 180),
			Rate = 26,
		})
	end
end

-- Anelli olografici sopra la sala rotonda, con un cervello e due pianetini (come i felini geniali)
local function labHolo()
	local U = 210
	local function ring(y: number, R: number, n: number, color: Color3, tilt: number)
		local chord = 2 * R * math.sin(math.pi / n)
		local base = CFrame.new(at(3, U, y, 0)) * CFrame.Angles(tilt, 0, 0)
		for k = 0, n - 1 do
			local a = (k + 0.5) / n * math.pi * 2
			local cf = base * CFrame.Angles(0, a, 0) * CFrame.new(0, 0, -R * math.cos(math.pi / n))
			box("HoloRing", Vector3.new(chord * 0.72, 0.4, 0.5), cf, color, Mat.Neon, 0.25)
		end
	end
	ring(301, 13, 10, CYAN, 0)
	ring(305, 8.5, 8, PURPLE, RAD(16))
	sphere("HoloBrain", 4.2, at(3, U, 305, 0), PINK, Mat.Neon, 0.3)
	sphere("HoloPlanet", 1.6, at(3, U + 13 * math.cos(RAD(40)), 302.6, 13 * math.sin(RAD(40))), PINK, Mat.Neon)
	sphere("HoloPlanet", 1.2, at(3, U - 8.5, 307.4, -1), CYAN, Mat.Neon)
end

-- Cervello gigante in un barattolo di vetro rosa (otto lastre attorno, vuoto dentro), sulla terrazza del muro sinistro
local function labBrainJar()
	annex(3, 258, 286, -23, -47, 268, -1, LIGHT, Mat.DiamondPlate)
	local U, V = 272, -35
	local c = at(3, U, 0, V)
	column(3, U, V, 268, 271, 16, "JarBase", DARK, Mat.DiamondPlate)
	column(3, U, V, 271, 271.6, 15.4, "JarRing", GOLD, Mat.Foil)
	local y0, y1 = 271.6, 295.6
	local R, t = 6.6, 0.3 -- apotema del piano medio delle lastre, spessore
	local w = 2 * (R - t / 2) * math.tan(math.pi / 8) -- le facce interne si toccano negli spigoli
	for k = 0, 7 do
		local a = k * math.pi / 4
		local cf = CFrame.new(c.X, (y0 + y1) / 2, c.Z) * CFrame.Angles(0, a, 0) * CFrame.new(0, 0, -R)
		box("JarGlass", Vector3.new(w, y1 - y0, t), cf, rgb(220, 120, 255), Mat.Glass, 0.55)
	end
	-- cervello a due lobi sul suo sostegno
	column(3, U, V, 271.6, 276, 3, "BrainStand", STEEL, Mat.Metal)
	column(3, U, V, 276, 279.7, 2, "BrainStem", rgb(240, 120, 180), Mat.SmoothPlastic)
	local brain = nil
	for _, dv in { -1.8, 1.8 } do
		brain = sphere("Brain", 8, at(3, U, 283.4, V + dv), rgb(255, 140, 200), Mat.SmoothPlastic)
	end
	light(brain :: BasePart, rgb(230, 130, 255), 30, 1.8)
	column(3, U, V, y1, y1 + 2, 15.4, "JarLid", STEEL, Mat.Metal)
	sphere("JarDome", 8, at(3, U, seatedY(y1 + 2, 8, 3), V), STEEL, Mat.Metal)
	for _, du in { -5, 5 } do
		column(3, U + du, V, y1 + 2, y1 + 9.4, 0.6, "Electrode", COPPER, Mat.Foil)
		sphere("ElectrodeTip", 1.4, at(3, U + du, seatedY(y1 + 9.4, 1.4, 0.3), V), CYAN, Mat.Neon)
	end
end

-- Antenna parabolica sulla terrazza del muro destro
local function labDish()
	annex(3, 284, 302, 23, 43, 268, 1, LIGHT, Mat.DiamondPlate)
	local U, V = 293, 33
	column(3, U, V, 268, 272, 7, "DishPedestal", DARK, Mat.DiamondPlate)
	column(3, U, V, 272, 281, 2, "DishMast", STEEL, Mat.Metal)
	-- piatto inclinato verso il cielo e il corridoio
	local n = Vector3.new(0.35, 0.75, -0.56).Unit
	local hub = at(3, U, 281, V)
	local c = hub + n * 1.6
	local dishCf = CFrame.lookAt(c, c + n) * CFrame.Angles(0, RAD(90), 0)
	sphere("DishJoint", 2.4, hub, STEEL, Mat.Metal)
	cyl("Dish", 1, 16, dishCf, WHITE, Mat.SmoothPlastic)
	cyl("DishInner", 0.2, 12, dishCf * CFrame.new(0.6, 0, 0), LIGHT, Mat.SmoothPlastic)
	local front = c + n * 0.7
	rod("DishFeed", front, front + n * 7, 0.5, STEEL, Mat.Metal)
	sphere("DishReceiver", 1.6, front + n * 7.6, RED, Mat.Neon)
end

-- Santuario 3: plafoniere, travi, vetrine luminose dietro i trofei e schermi; sul tetto la torre di Tesla
local function labShrine()
	local s3 = Extreme.Sections[3]
	local u0, u1 = s3.length, s3.length + s3.shrineLength
	local y = s3.floor
	local ceil = y + 26
	-- travi del soffitto e plafoniere sopra le luci del santuario
	for _, u in { u0 + 5, u0 + 20, u0 + 40, u0 + 55 } do
		span(3, u - 0.6, u + 0.6, ceil - 1.4, ceil, -WALL_IN, WALL_IN, "CeilingBeam", STEEL, Mat.DiamondPlate)
	end
	for k = 0, 2 do
		local u = u0 + (k + 0.5) * s3.shrineLength / 3
		span(3, u - 3, u + 3, ceil - 0.3, ceil, -2, 2, "CeilingLamp", PALE, Mat.Neon)
	end
	-- vetrine luminose dietro i tre trofei (lato destro)
	for k = 0, 2 do
		local u = u0 + 12 + k * 16
		onWall(1, u - 4, u + 4, y + 1.5, y + 13.5, 0, 0.2, "DisplayBack", WHITE, Mat.SmoothPlastic)
		onWall(1, u - 3.4, u + 3.4, y + 12.4, y + 13.1, 0.2, 0.08, "DisplayLight", CYAN, Mat.Neon)
	end
	-- lato sinistro: schermo grande prima del portale e una lavagna dopo
	wallScreen(-1, u0 + 6, u0 + 22, y + 5, y + 14, "graph", 31)
	wallBoard(-1, u1 - 14, u1 - 8, y + 7, y + 12, "π")
	-- torre di Tesla sul tetto (punto di riferimento da tutto il laboratorio)
	local roof = wallTop(3, (u0 + u1) / 2, 1)
	local U = (u0 + u1) / 2 + 2
	span(3, U - 7, U + 7, roof, roof + 3, -7, 7, "TowerBase", DARK, Mat.DiamondPlate)
	local yy = roof + 3
	for k = 1, 4 do
		column(3, U, 0, yy, yy + 7, 5, "TowerColumn", WHITE, Mat.SmoothPlastic)
		yy += 7
		if k < 4 then
			column(3, U, 0, yy, yy + 1, 6, "TowerGlow", CYAN, Mat.Neon)
			yy += 1
		end
	end
	column(3, U, 0, yy, yy + 3, 16, "TowerTorus", STEEL, Mat.Metal)
	local domeY = seatedY(yy + 3, 9, 3.4)
	sphere("TowerDome", 9, at(3, U, domeY, 0), STEEL, Mat.Metal)
	local orb = sphere("TowerOrb", 3.6, at(3, U, domeY + 4.5 + 1.5, 0), PALE, Mat.Neon)
	light(orb, CYAN, 40, 2.4)
	emitter(orb, {
		Texture = SPARKLE,
		Color = ColorSequence.new(Color3.new(1, 1, 1), CYAN),
		LightEmission = 1,
		Size = seq(1, 0.1),
		Transparency = seq(0, 1),
		Lifetime = NumberRange.new(0.2, 0.45),
		Speed = NumberRange.new(14, 24),
		SpreadAngle = Vector2.new(180, 180),
		Rate = 30,
	})
end

local function buildLab(folder: Instance)
	local model = Build.Model("Laboratorio", folder)
	target = model
	labGate()
	labWalls()
	labTanks()
	labCatScreen()
	labPipeBridge(90, 297)
	labPipeBridge(232, 300)
	labFlasks()
	labCatStatue()
	labTesla()
	labHolo()
	labBrainJar()
	labDish()
	labShrine()
end

---------------------------------------------------------------------------------------------
-- SEZIONE 4: Inferno
---------------------------------------------------------------------------------------------
-- rocce rosso scuro, ossidiana, lava, ossa e oro
local ROCK = rgb(126, 42, 34)
local ROCK_DARK = rgb(88, 30, 28)
local OBSIDIAN = rgb(46, 26, 62)
local LAVA = rgb(255, 128, 32)
local LAVA_HOT = rgb(255, 205, 90)
local BONE = rgb(242, 230, 204)
local IRON = rgb(78, 70, 72)
local VELVET = rgb(196, 26, 46)
local EMBER = rgb(255, 84, 30)
local EYE = rgb(255, 40, 40)

-- quota del percorso dell'Inferno lungo u (come floorLine in Shared.Extreme), poi il pavimento del santuario
local INF_FLOOR = { { 0, 246 }, { 96, 245 }, { 172, 244 }, { 262, 242 }, { 272, 240 }, { 360, 231 } }
local function infFloor(u: number): number
	if u <= INF_FLOOR[1][1] then
		return INF_FLOOR[1][2]
	end
	for k = 1, #INF_FLOOR - 1 do
		local a, b = INF_FLOOR[k], INF_FLOOR[k + 1]
		if u <= b[1] then
			return a[2] + (b[2] - a[2]) * (u - a[1]) / (b[1] - a[1])
		end
	end
	return Extreme.Sections[4].floor
end

-- Ingombri dei pezzi di muro della sezione 4 (sponde di roccia casuali, pareti e tetto del santuario), dai vertici veri
type Bounds = { u0: number, u1: number, v0: number, v1: number, y0: number, y1: number }
local infWalls: { Bounds } = {}
local function readWalls()
	table.clear(infWalls)
	local x0 = Extreme.Sections[4].x0
	for _, p in Extreme.Pieces do
		if p.section == 4 and p.wall then
			local h = p.size / 2
			local b =
				{ u0 = math.huge, u1 = -math.huge, v0 = math.huge, v1 = -math.huge, y0 = math.huge, y1 = -math.huge }
			for _, sx in { -1, 1 } do
				for _, sy in { -1, 1 } do
					for _, sz in { -1, 1 } do
						local w = p.cframe * Vector3.new(sx * h.X, sy * h.Y, sz * h.Z)
						local u, v = x0 - w.X, w.Z - Extreme.Z
						b.u0, b.u1 = math.min(b.u0, u), math.max(b.u1, u)
						b.v0, b.v1 = math.min(b.v0, v), math.max(b.v1, v)
						b.y0, b.y1 = math.min(b.y0, w.Y), math.max(b.y1, w.Y)
					end
				end
			end
			table.insert(infWalls, b)
		end
	end
end

-- |v| esterna massima e quota massima dei muri sul lato side fra u0 e u1
local function wallReach(side: number, u0: number, u1: number): (number, number)
	local reach, top = 0, -math.huge
	for _, b in infWalls do
		if b.u1 > u0 and b.u0 < u1 then
			local out = if side > 0 then b.v1 else -b.v0
			if out > 0 then
				reach = math.max(reach, out)
				top = math.max(top, b.y1)
			end
		end
	end
	return reach, top
end

-- quota massima dei muri dentro il rettangolo (u0..u1, v0..v1)
local function wallTopIn(u0: number, u1: number, v0: number, v1: number): number
	local top = -math.huge
	for _, b in infWalls do
		if b.u1 > u0 and b.u0 < u1 and b.v1 > v0 and b.v0 < v1 then
			top = math.max(top, b.y1)
		end
	end
	return top
end

-- scheggia di ossidiana dritta (parallelepipedo e punta a cuneo), appoggiata sulla quota y
local function shard(i: number, u: number, v: number, y: number, w: number, h: number, yaw: number, color: Color3)
	local base = CFrame.new(at(i, u, y + h / 2, v)) * CFrame.Angles(0, yaw, 0)
	box("ObsidianShard", Vector3.new(w, h, w), base, color, Mat.Glass)
	local tip = w * 1.7
	wedge("ObsidianTip", Vector3.new(w, tip, w), base * CFrame.new(0, h / 2 + tip / 2, 0), color, Mat.Glass)
end

-- cascata di lava sulla faccia interna di una rupe (vIn = |v| della faccia), dal labbro in cima fino in fondo
local function lavafall(s: number, um: number, w: number, top: number, bottom: number, vIn: number, glow: boolean)
	local a, b = s * (vIn - 0.6), s * vIn
	local sheet =
		span(4, um - w / 2, um + w / 2, bottom, top, math.min(a, b), math.max(a, b), "Lavafall", LAVA, Mat.Neon)
	local c, d = s * (vIn - 0.9), s * (vIn - 0.6)
	span(
		4,
		um - w * 0.18,
		um + w * 0.18,
		bottom,
		top,
		math.min(c, d),
		math.max(c, d),
		"LavafallCore",
		LAVA_HOT,
		Mat.Neon
	)
	-- labbro: la lava scorre sulla cima della rupe e si affaccia
	local e, f = s * (vIn - 0.9), s * (vIn + 5)
	span(4, um - w / 2, um + w / 2, top, top + 0.5, math.min(e, f), math.max(e, f), "LavaLip", LAVA, Mat.Neon)
	if glow then
		light(sheet, rgb(255, 120, 40), 34, 1.6)
		emitter(sheet, {
			Texture = SPARKLE,
			Color = ColorSequence.new(LAVA_HOT, EMBER),
			LightEmission = 1,
			Size = seq(0.5, 0.1),
			Transparency = seq(0, 1),
			Lifetime = NumberRange.new(1.5, 2.6),
			Speed = NumberRange.new(3, 6),
			EmissionDirection = if s > 0 then Enum.NormalId.Right else Enum.NormalId.Left,
			SpreadAngle = Vector2.new(30, 30),
			Acceleration = Vector3.new(0, 5, 0),
			Rate = 10,
		})
	end
end

-- Rupi esterne del canyon (oltre le sponde): blocchi rosso scuro di altezza diversa, con creste a cuneo, cascate di
-- lava che colano dalla cima e schegge di ossidiana. Lasciano liberi i posti del portale e dei piloni degli uncini.
local function infernoCliffs()
	local r = rng(66613)
	local s4 = Extreme.Sections[4]
	local uEnd = s4.length + s4.shrineLength
	local reserved = { { 6, 20 }, { 172, 184 }, { 252, 264 } } -- portale e piloni del ponte degli uncini
	local lavaAt = { [-1] = { 64, 214, 334 }, [1] = { 128, 292, 404 } }
	for _, s in { -1, 1 } do
		local u = if s > 0 then -2 else -2 + 9
		local n = 0
		local uStop = uEnd + 58 -- inizio della rupe di fondo
		while u < uStop - 6 do
			local L = r(22, 34)
			local ua, ub = u, math.min(u + L, uStop)
			-- salta i tratti riservati
			for _, res in reserved do
				if ub > res[1] and ua < res[2] then
					if ua < res[1] - 6 then
						ub = res[1]
					else
						ua, ub = res[2], math.max(res[2] + 14, ub)
					end
				end
			end
			n += 1
			local um = (ua + ub) / 2
			local f = infFloor(um)
			local reach = wallReach(s, ua - 1, ub + 1)
			local vIn = math.max(reach + r(2, 3.5), if ua > uEnd + 4 then 33 elseif ua > s4.length + 4 then 31 else 35)
			local D = r(16, 24)
			local H = r(20, 32) + math.clamp(um / uEnd, 0, 1) * 12
			local top = f + H
			local bottom = f - 54 - (n % 3) * 0.7
			local isLava = false
			for _, lu in lavaAt[s] do
				if lu >= ua and lu < ub then
					isLava = true
				end
			end
			local cracked = n % 3 == 0
			local color = if cracked then ROCK_DARK else ROCK
			local a, b = s * vIn, s * (vIn + D)
			span(
				4,
				ua + 0.05,
				ub - 0.05,
				bottom,
				top,
				math.min(a, b),
				math.max(a, b),
				"Cliff",
				color,
				if cracked then Mat.CrackedLava else Mat.Basalt
			)
			if isLava then
				lavafall(s, um, math.min(L * 0.35, 9), top, bottom, vIn, um < 140 or (um > 280 and um < 340))
			elseif n % 2 == 0 then
				-- cresta a cuneo che sale verso una delle due estremita'
				local hh = r(6, 14)
				local rot = if n % 4 == 0 then CFrame.Angles(0, RAD(90), 0) else CFrame.Angles(0, RAD(-90), 0)
				local c = at(4, um, top + hh / 2, s * (vIn + D / 2))
				wedge("CliffCrest", Vector3.new(D - 0.1, hh, ub - ua - 0.3), CFrame.new(c) * rot, color, Mat.Basalt)
			else
				-- schegge di ossidiana sulla cima piatta
				local k = math.floor(r(1, 3.99))
				local placed = {}
				for j = 1, k do
					local w = r(2.4, 4)
					local margin = w + 0.5
					for _ = 1, 8 do
						local su = r(ua + margin, ub - margin)
						local sv = r(vIn + margin, vIn + D - margin)
						local free = true
						for _, q in placed do
							if
								math.abs(q[1] - su) < (q[3] + w) * 0.75 + 0.4
								and math.abs(q[2] - sv) < (q[3] + w) * 0.75 + 0.4
							then
								free = false
							end
						end
						if free then
							table.insert(placed, { su, sv, w })
							local color = if j == 2 then rgb(70, 30, 90) else OBSIDIAN
							shard(4, su, s * sv, top, w, r(8, 20), r(0, math.pi), color)
							break
						end
					end
				end
			end
			-- venatura di lava sulla faccia verso il percorso (sopra le sponde)
			if not isLava and n % 3 == 1 then
				local vy = top - r(5, 9)
				local vv = s * (vIn - 0.15)
				for j, ang in { 28, -24 } do
					local len = r(6, 9)
					local cu = um + (j - 1.5) * 3
					local cf = CFrame.new(at(4, cu, vy - (j - 1) * 4.5, vv)) * CFrame.Angles(0, 0, RAD(ang))
					box("LavaVein", Vector3.new(0.7, len, 0.3), cf, LAVA, Mat.Neon)
				end
			end
			u = ub
		end
	end
end

-- corno ricurvo d'osso: segmenti sempre piu' sottili con i giunti arrotondati e la punta luminosa
local function horn(name: string, pts: { Vector3 }, ds: { number }): BasePart
	for k = 1, #ds do
		local tip = k == #ds
		rod(name, pts[k], pts[k + 1], ds[k], if tip then LAVA else BONE, if tip then Mat.Neon else Mat.SmoothPlastic)
		if not tip then
			sphere(name .. "Joint", ds[k], pts[k + 1], BONE, Mat.SmoothPlastic)
		end
	end
	return sphere(name .. "Tip", ds[#ds], pts[#pts], LAVA_HOT, Mat.Neon)
end

-- teschio: occhi rossi nelle orbite, naso nero e mascella (dir = verso dove guarda)
local function skull(prefix: string, c: Vector3, d: number, dir: Vector3)
	sphere(prefix, d, c, BONE, Mat.SmoothPlastic)
	local r = d / 2
	local side = dir:Cross(Vector3.yAxis).Unit
	for _, sv in { -1, 1 } do
		local e = (dir + Vector3.new(0, 0.18, 0) + side * sv * 0.42).Unit
		local p = c + e * r
		cyl(
			prefix .. "Socket",
			0.05 * d,
			0.3 * d,
			CFrame.lookAt(p, p + e) * CFrame.Angles(0, RAD(90), 0),
			BLACK,
			Mat.SmoothPlastic
		)
		local q = c + e * (r + 0.0375 * d)
		cyl(prefix .. "Eye", 0.025 * d, 0.15 * d, CFrame.lookAt(q, q + e) * CFrame.Angles(0, RAD(90), 0), EYE, Mat.Neon)
	end
	local n = (dir + Vector3.new(0, -0.12, 0)).Unit
	local np = c + n * (r + 0.02 * d)
	box(
		prefix .. "Nose",
		Vector3.new(0.12 * d, 0.12 * d, 0.04 * d),
		CFrame.lookAt(np, np + n) * CFrame.Angles(0, 0, RAD(45)),
		BLACK,
		Mat.SmoothPlastic
	)
end

-- Portale dell'Inferno all'uscita del laboratorio: pilastri neri oltre le sponde, architrave appena sopra le sponde
-- (si vede gia' dal santuario 3) col nome della zona, teschio in cima e due corna di Behemoth con la punta in fiamme
local function infernoGate()
	local u0, u1 = 9, 16
	local um = (u0 + u1) / 2
	local reachL = wallReach(-1, u0 - 2, u1 + 2)
	local reachR = wallReach(1, u0 - 2, u1 + 2)
	local vg = math.max(36, reachL + 2, reachR + 2)
	local yb = math.max(268, wallTopIn(u0 - 1.5, u1 + 1.5, -(vg + 8), vg + 8) + 1.5) -- fondo dell'architrave
	local GATE = rgb(54, 30, 40)
	for _, s in { -1, 1 } do
		span(4, u0, u1, 198, yb, s * vg, s * (vg + 7), "GatePillar", GATE, Mat.Basalt)
		span(4, um - 0.6, um + 0.6, 236, yb - 3, s * (vg - 0.3), s * vg, "GateInlay", EMBER, Mat.Neon)
	end
	span(4, u0 - 1, u1 + 1, yb, yb + 8, -(vg + 8), vg + 8, "GateBeam", GATE, Mat.Basalt)
	span(4, u0, u1, yb - 0.3, yb, -vg, vg, "GateUnderGlow", EMBER, Mat.Neon)
	local pos = at(4, u0 - 1.2, yb + 4, 0)
	sign(
		CFrame.lookAt(pos, pos + Vector3.new(1, 0, 0)),
		Vector3.new(26, 4.6, 0.4),
		"Zone_Inferno",
		rgb(120, 18, 22),
		LAVA_HOT
	)
	-- corna di toro sulle estremita' dell'architrave, con il fuoco in punta
	for _, s in { -1, 1 } do
		local top = yb + 8
		local tip = horn("GateHorn", {
			at(4, um, top - 1, s * (vg + 3)),
			at(4, um, top + 3, s * (vg + 8)),
			at(4, um, top + 10, s * (vg + 12)),
			at(4, um, top + 18, s * (vg + 13)),
			at(4, um, top + 24, s * (vg + 10.5)),
		}, { 4.4, 3.6, 2.8, 2.1 })
		fire(tip, 5, 9, rgb(255, 170, 60), rgb(255, 60, 20))
		light(tip, rgb(255, 140, 60), 30, 1.6)
	end
	-- teschio sull'architrave che guarda chi arriva, con la mascella appoggiata
	local skullC = at(4, um, seatedY(yb + 8, 8, 2.6), 0)
	skull("GateSkull", skullC, 8, Vector3.new(1, 0, 0))
	local jaw = at(4, u0 + 1.6, yb + 8 + 0.9, 0)
	box("SkullJaw", Vector3.new(4.4, 1.8, 4.6), CFrame.new(jaw), BONE, Mat.SmoothPlastic)
	box("SkullMouth", Vector3.new(0.1, 0.5, 3.4), CFrame.new(jaw + Vector3.new(2.25, 0.1, 0)), BLACK, Mat.SmoothPlastic)
end

-- Ponte degli uncini: due portali di ferro arrugginito oltre le sponde reggono la trave da cui pendono gli uncini
-- (forcelle attorno al perno di ognuno); dai portali pendono due gabbie sopra le sponde
local function infernoGantry()
	local pivots = {}
	for _, p in Extreme.Pieces do
		if p.section == 4 and p.kind == "Swing" then
			table.insert(pivots, p)
		end
	end
	if #pivots == 0 then
		return
	end
	local x0 = Extreme.Sections[4].x0
	local umin, umax, py = math.huge, -math.huge, 0
	for _, p in pivots do
		local u = x0 - p.cframe.Position.X
		umin, umax = math.min(umin, u), math.max(umax, u)
		py = p.cframe.Position.Y
	end
	local ua, ub = umin - 8, umax + 8
	local _, topL = wallReach(-1, ua - 6, ub + 6)
	local _, topR = wallReach(1, ua - 6, ub + 6)
	local beamY = math.max(py + 12, topL + 10, topR + 10)
	local girderBottom = py + 1.4
	for _, u in { ua, ub } do
		local reach = math.max(wallReach(-1, u - 3, u + 3), wallReach(1, u - 3, u + 3))
		local vp = math.max(36, reach + 2)
		for _, s in { -1, 1 } do
			span(4, u - 2, u + 2, 200, beamY, s * vp, s * (vp + 4), "GantryPillar", IRON, Mat.CorrodedMetal)
			span(4, u - 0.5, u + 0.5, beamY - 14, beamY - 2, s * (vp - 0.3), s * vp, "GantryGlow", EMBER, Mat.Neon)
		end
		span(4, u - 2, u + 2, beamY, beamY + 4, -(vp + 4), vp + 4, "GantryBeam", IRON, Mat.CorrodedMetal)
		span(4, u - 0.5, u + 0.5, girderBottom + 2.6, beamY, -0.5, 0.5, "GantryHanger", IRON, Mat.Metal)
		-- punte sulla trave
		for _, sv in { -0.6, 0, 0.6 } do
			local c = at(4, u, beamY + 4 + 2, sv * vp)
			wedge("GantrySpike", Vector3.new(1.6, 4, 3), CFrame.new(c), BONE, Mat.SmoothPlastic)
		end
	end
	span(4, ua - 2, ub + 2, girderBottom, girderBottom + 2.6, -0.9, 0.9, "HookGirder", IRON, Mat.CorrodedMetal)
	-- forcella attorno al perno di ogni uncino (la corda gira fra le due piastre)
	for _, p in pivots do
		local u = x0 - p.cframe.Position.X
		for _, d in { -1, 1 } do
			local a, b = u + d * 0.35, u + d * 0.55
			span(4, math.min(a, b), math.max(a, b), py - 0.6, girderBottom, -0.6, 0.6, "HookClevis", IRON, Mat.Metal)
		end
	end
	-- gabbie appese sopra le sponde, con un teschio dentro
	for k, u in { ua, ub } do
		local s = if k == 1 then -1 else 1
		local v = s * 28
		local bankTop = wallTopIn(u - 3, u + 3, math.min(v, s * 25) - 3, math.max(v, s * 25) + 3)
		local y0 = math.max(bankTop + 1.5, py)
		local y1 = y0 + 6.5
		local cu = u
		column(4, cu, v, y0, y0 + 0.5, 4.6, "CageFloor", IRON, Mat.Metal)
		column(4, cu, v, y1 - 0.5, y1, 4.6, "CageTop", IRON, Mat.Metal)
		for j = 0, 5 do
			local a = j / 6 * math.pi * 2
			local c = at(4, cu + math.cos(a) * 1.95, (y0 + y1) / 2, v + math.sin(a) * 1.95)
			box("CageBar", Vector3.new(0.3, y1 - y0 - 1, 0.3), CFrame.new(c), IRON, Mat.Metal)
		end
		span(4, cu - 0.2, cu + 0.2, y1, beamY, v - 0.2, v + 0.2, "CageChain", IRON, Mat.DiamondPlate)
		-- teschio a blocchetti sul fondo della gabbia
		span(4, cu - 0.8, cu + 0.8, y0 + 0.5, y0 + 2.1, v - 0.8, v + 0.8, "CageSkull", BONE, Mat.SmoothPlastic)
		for _, ev in { -0.4, 0.4 } do
			span(
				4,
				cu - 0.86,
				cu - 0.8,
				y0 + 1.2,
				y0 + 1.6,
				v + ev - 0.2,
				v + ev + 0.2,
				"CageSkullEye",
				EMBER,
				Mat.Neon
			)
		end
	end
end

-- Trono del re dei diavoli in fondo all'Inferno (dietro la parete del santuario 4): basamento, seggio e schienale
-- d'ossidiana, cuscino di velluto, teschio cornuto, corona d'oro, bracieri; dietro la rupe di fondo con due
-- cascate di lava. E' il punto di riferimento di tutta la sezione.
local function infernoThrone()
	local s4 = Extreme.Sections[4]
	local uEnd = s4.length + s4.shrineLength -- 430: poi la parete di fondo (4 stud)
	local U = uEnd + 10 -- inizio del basamento
	span(4, U, U + 44, 214, 240, -30, 30, "ThronePlinth", ROCK_DARK, Mat.Basalt)
	span(4, U - 0.4, U + 44.4, 236, 240.4, -30.4, 30.4, "ThronePlinthRim", rgb(255, 110, 40), Mat.CrackedLava)
	span(4, U + 8, U + 44, 240.4, 244, -22, 22, "ThroneDais", OBSIDIAN, Mat.Glass)
	span(4, U + 4, U + 8, 240.4, 242.2, -14, 14, "ThroneStep", OBSIDIAN, Mat.Glass)
	local seat0, seat1 = U + 18, U + 34
	span(4, seat0, seat1, 244, 262, -13, 13, "ThroneSeat", OBSIDIAN, Mat.Glass)
	span(4, seat0 + 0.5, seat1 - 0.5, 262, 264, -11, 11, "ThroneCushion", VELVET, Mat.Fabric)
	span(4, seat1, seat1 + 8, 244, 314, -13, 13, "ThroneBack", OBSIDIAN, Mat.Glass)
	span(4, seat1 - 0.4, seat1, 264, 306, -10, 10, "ThroneBackVelvet", VELVET, Mat.Fabric)
	span(4, seat1 - 0.5, seat1 + 8.5, 314, 315.6, -13.5, 13.5, "ThroneBackCap", GOLD, Mat.Foil)
	for _, s in { -1, 1 } do
		span(4, seat0, seat1, 244, 268, s * 13, s * 18, "ThroneArm", OBSIDIAN, Mat.Glass)
		span(4, seat0 - 0.5, seat1, 268, 269.2, s * 12.6, s * 18.4, "ThroneArmCap", GOLD, Mat.Foil)
		-- braciere sul bracciolo
		local bu = seat0 + 3
		column(4, bu, s * 15.5, 269.2, 271.6, 4.4, "Brazier", IRON, Mat.Metal)
		local coals = column(4, bu, s * 15.5, 271.6, 271.9, 3.6, "BrazierCoals", LAVA, Mat.Neon)
		fire(coals, 4, 7, rgb(255, 170, 60), rgb(255, 60, 20))
	end
	-- corona d'oro sullo schienale: tre punte (ognuna due cunei a specchio)
	for k, sv in { -7, 0, 7 } do
		local h = if k == 2 then 10 else 7
		for _, m in { -1, 1 } do
			local c = at(4, seat1 + 4, 315.6 + h / 2, sv + m * 1.5)
			local rot = if m < 0 then CFrame.new() else CFrame.Angles(0, math.pi, 0)
			wedge("CrownSpike", Vector3.new(3, h, 3), CFrame.new(c) * rot, GOLD, Mat.Foil)
		end
	end
	-- teschio cornuto sullo schienale (guarda il percorso), mascella appoggiata al velluto
	local skullC = at(4, seat1 - 3, 296, 0)
	skull("ThroneSkull", skullC, 12, Vector3.new(1, 0, 0))
	span(4, seat1 - 8.4, seat1 - 0.4, 286, 290.4, -3.8, 3.8, "ThroneSkullJaw", BONE, Mat.SmoothPlastic)
	span(4, seat1 - 8.5, seat1 - 8.4, 287.6, 288.4, -2.8, 2.8, "ThroneSkullMouth", BLACK, Mat.SmoothPlastic)
	for _, s in { -1, 1 } do
		horn("ThroneHorn", {
			skullC + Vector3.new(0, 2.5, s * 4.4),
			at(4, seat1 - 3, 299.5, s * 10.5),
			at(4, seat1 - 3, 305, s * 15.5),
			at(4, seat1 - 3, 312, s * 17),
			at(4, seat1 - 3, 318, s * 15),
		}, { 4.4, 3.6, 2.8, 2.1 })
	end
	local glow = span(4, U - 6, U - 5, 270, 271, -0.5, 0.5, "ThroneGlow", WHITE, Mat.SmoothPlastic, 1)
	light(glow, rgb(255, 120, 60), 50, 2)
	-- rupe di fondo con due cascate di lava ai lati del trono
	local B0 = U + 48
	span(4, B0, B0 + 20, 196, 322, -66, 66, "BackCliff", ROCK, Mat.Basalt)
	for k, sv in { -50, -12, 12, 50 } do
		local hh = 10 + (k % 2) * 8
		local rot = if k % 2 == 0 then CFrame.Angles(0, 0, 0) else CFrame.Angles(0, math.pi, 0)
		wedge(
			"BackCrest",
			Vector3.new(20, hh, 16),
			CFrame.new(at(4, B0 + 10, 322 + hh / 2, sv)) * rot,
			ROCK,
			Mat.Basalt
		)
	end
	for _, s in { -1, 1 } do
		local vv = s * 26
		local a, b = B0 - 0.6, B0
		span(4, a, b, 196, 322, vv - 3.5, vv + 3.5, "Lavafall", LAVA, Mat.Neon)
		span(4, a - 0.3, a, 196, 322, vv - 1.2, vv + 1.2, "LavafallCore", LAVA_HOT, Mat.Neon)
		local lip = span(4, a - 0.3, B0 + 6, 322, 322.5, vv - 3.5, vv + 3.5, "LavaLip", LAVA, Mat.Neon)
		if s > 0 then
			emitter(lip, {
				Texture = SPARKLE,
				Color = ColorSequence.new(LAVA_HOT, EMBER),
				LightEmission = 1,
				Size = seq(0.8, 0.1),
				Transparency = seq(0, 1),
				Lifetime = NumberRange.new(2, 3.5),
				Speed = NumberRange.new(4, 8),
				SpreadAngle = Vector2.new(60, 60),
				Acceleration = Vector3.new(0, 4, 0),
				Rate = 14,
			})
		end
	end
end

-- Santuario 4 (sala del trono): stendardi di velluto dietro i trofei e sulla parete del portale, bracieri a muro e
-- un lampadario di ferro con le candele sopra l'altare
local function infernoShrine()
	local s4 = Extreme.Sections[4]
	local u0 = s4.length
	local y = s4.floor
	local ceil = y + 26
	local function banner(s: number, u: number)
		onWallAt(4, s, u - 3, u + 3, y + 3, y + 16, 0, 0.2, "Banner", VELVET, Mat.Fabric)
		onWallAt(4, s, u - 1, u + 1, y + 11, y + 13, 0.2, 0.1, "BannerEmblem", GOLD, Mat.Foil)
		local rodV = s * (WALL_IN - 0.3)
		local p = runbar(4, u - 3.6, u + 3.6, y + 16.3, rodV, 0.6, "BannerRod", GOLD, Mat.Foil)
		p.CastShadow = false
	end
	for k = 0, 2 do
		banner(1, u0 + 12 + k * 16)
	end
	banner(-1, u0 + 8)
	banner(-1, u0 + 62)
	-- bracieri a muro (alti, fuori portata)
	local function sconce(s: number, u: number)
		onWallAt(4, s, u - 0.6, u + 0.6, y + 15, y + 16, 0, 1.4, "SconceArm", IRON, Mat.Metal)
		local cv = s * (WALL_IN - 0.7)
		column(4, u, cv, y + 16, y + 17, 1.4, "SconceBowl", IRON, Mat.Metal)
		column(4, u, cv, y + 17, y + 17.25, 1, "SconceFlame", LAVA, Mat.Neon)
	end
	for _, u in { u0 + 4, u0 + 20, u0 + 36, u0 + 52, u0 + 66 } do
		sconce(1, u)
	end
	for _, u in { u0 + 18, u0 + 28, u0 + 54 } do
		sconce(-1, u)
	end
	-- lampadario sopra l'altare
	local uc = u0 + s4.shrineLength / 2
	local ring = ceil - 5
	column(4, uc, 0, ring, ring + 0.6, 10, "ChandelierRing", IRON, Mat.Metal)
	for k = 0, 2 do
		local a = k / 3 * math.pi * 2
		local cu, cv = uc + math.cos(a) * 3.6, math.sin(a) * 3.6
		span(4, cu - 0.2, cu + 0.2, ring + 0.6, ceil, cv - 0.2, cv + 0.2, "ChandelierChain", IRON, Mat.DiamondPlate)
	end
	for k = 0, 5 do
		local a = (k + 0.5) / 6 * math.pi * 2
		local cu, cv = uc + math.cos(a) * 4.3, math.sin(a) * 4.3
		column(4, cu, cv, ring + 0.6, ring + 1.8, 0.5, "Candle", BONE, Mat.SmoothPlastic)
		column(4, cu, cv, ring + 1.8, ring + 2.3, 0.35, "CandleFlame", LAVA_HOT, Mat.Neon)
	end
end

local function buildInferno(folder: Instance)
	local model = Build.Model("Inferno", folder)
	target = model
	readWalls()
	infernoCliffs()
	infernoGate()
	infernoGantry()
	infernoThrone()
	infernoShrine()
end

function ExtremeDecorB.Build(folder: Instance)
	buildLab(folder)
	buildInferno(folder)
end

return ExtremeDecorB
