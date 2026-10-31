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

-- strato piatto appoggiato alla faccia interna di una parete del laboratorio (off = distanza dalla parete)
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
	local a, b = s * (WALL_IN - off), s * (WALL_IN - off - t)
	local p = span(3, u0, u1, y0, y1, math.min(a, b), math.max(a, b), name, color, mat, tr)
	p.CastShadow = false
	return p
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

-- pannello luminoso con cornice
local function wallLight(s: number, u0: number, u1: number, y0: number, y1: number)
	onWall(s, u0, u1, y0, y1, 0, 0.2, "PanelFrame", WHITE, Mat.SmoothPlastic)
	onWall(s, u0 + 0.5, u1 - 0.5, y0 + 0.5, y1 - 0.5, 0.2, 0.08, "PanelLight", PALE, Mat.Neon)
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

-- Portale d'ingresso con la lampadina del genio
local function labGate()
	local u0, u1 = 3, 7
	for _, s in { -1, 1 } do
		span(3, u0, u1, 232, 290, s * 24, s * 28, "GatePillar", WHITE, Mat.SmoothPlastic)
		span(3, u0 - 1, u1 + 1, 229, 232, s * 23.5, s * 28.5, "GateFoot", DARK, Mat.DiamondPlate)
		span(3, u0 - 0.3, u0, 240, 286, s * 25.4, s * 26.6, "GateGlow", CYAN, Mat.Neon)
		-- antenne con la lucina in cima
		column(3, 5, s * 26, 296, 303, 0.4, "GateAntenna", STEEL, Mat.Metal)
		sphere("GateBlink", 1, at(3, 5, seatedY(303, 1, 0.2), s * 26), if s < 0 then RED else LIME, Mat.Neon)
	end
	span(3, u0 - 1, u1 + 1, 290, 296, -28, 28, "GateBeam", DARK, Mat.DiamondPlate)
	span(3, u0, u1, 289.7, 290, -24, 24, "GateUnderGlow", CYAN, Mat.Neon)
	local pos = at(3, u0 - 1.2, 293, 0)
	sign(CFrame.lookAt(pos, pos + Vector3.new(1, 0, 0)), Vector3.new(30, 4.4, 0.4), "Zone_Lab", CYAN, DARK)
	-- lampadina: attacco a vite e bulbo luminoso
	column(3, 5, 0, 296, 297, 4.6, "BulbBase", DARK, Mat.DiamondPlate)
	column(3, 5, 0, 297, 297.8, 4, "BulbThread", STEEL, Mat.Metal)
	column(3, 5, 0, 297.8, 298.6, 4.6, "BulbThread", STEEL, Mat.Metal)
	column(3, 5, 0, 298.6, 299.4, 4, "BulbThread", STEEL, Mat.Metal)
	local bulb = sphere("Bulb", 8, at(3, 5, seatedY(299.4, 8, 2), 0), rgb(255, 238, 150), Mat.Neon, 0.1)
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
		sphere("Flask", f.d, at(3, u, f.y, v), f.color, Mat.Neon, 0.15)
		-- collo e tappo
		local neckD = f.d * 0.3
		local neckBase = f.y + math.sqrt(r * r - (neckD / 2) ^ 2)
		column(3, u, v, neckBase, neckBase + 2, neckD, "FlaskNeck", GLASS, Mat.Glass, 0.45)
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
	local function vcylL(
		name: string,
		x: number,
		y0: number,
		y1: number,
		z: number,
		d: number,
		color: Color3,
		mat: Enum.Material
	)
		cyl(name, y1 - y0, d, L * CFrame.new(x, (y0 + y1) / 2, z) * CFrame.Angles(0, 0, RAD(90)), color, mat)
	end
	local function ballL(
		name: string,
		x: number,
		y: number,
		z: number,
		d: number,
		color: Color3,
		mat: Enum.Material,
		tr: number?
	)
		sphere(name, d, (L * CFrame.new(x, y, z)).Position, color, mat, tr)
	end
	-- corpo seduto, petto, zampe e cosce
	vcylL("CatBody", 0, 0, 14, 1, 12, FUR, Mat.SmoothPlastic)
	ballL("CatChest", 0, 9.5, -3.4, 9, CREAM, Mat.SmoothPlastic)
	for _, sx in { -1, 1 } do
		vcylL("CatLeg", sx * 2.6, 0, 8.2, -6.1, 3.2, FUR, Mat.SmoothPlastic)
		ballL("CatPaw", sx * 2.6, 1.75, -7, 3.8, CREAM, Mat.SmoothPlastic)
		ballL("CatHaunch", sx * 4.6, 3.7, 3, 8, FUR, Mat.SmoothPlastic)
	end
	-- testa, muso, naso
	ballL("CatHead", 0, 19.5, -1, 13, FUR, Mat.SmoothPlastic)
	ballL("CatMuzzle", 0, 17.6, -6.4, 5.6, CREAM, Mat.SmoothPlastic)
	ballL("CatNose", 0, 19.1, -8.9, 1.6, PINK, Mat.SmoothPlastic)
	-- occhiali: fascia attorno alla testa e due lenti luminose che sporgono davanti
	vcylL("CatStrap", 0, 21, 22.2, -1, 13, DARK, Mat.SmoothPlastic)
	for _, sx in { -1, 1 } do
		cyl(
			"CatLens",
			1.6,
			4,
			L * CFrame.new(sx * 2.5, 21.6, -7.2) * CFrame.Angles(0, RAD(90), 0),
			CYAN,
			Mat.Neon,
			0.15
		)
	end
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
	local t0 = (L * CFrame.new(2, 1.2, 5.6)).Position
	local t1 = (L * CFrame.new(7.4, 1.2, 3.6)).Position
	local t2 = (L * CFrame.new(8.6, 9, 2.4)).Position
	rod("CatTail", t0, t1, 2.4, FUR, Mat.SmoothPlastic)
	sphere("CatTailJoint", 2.4, t1, FUR, Mat.SmoothPlastic)
	rod("CatTail", t1, t2, 2.4, FUR, Mat.SmoothPlastic)
	sphere("CatTailTip", 2.4, t2, BLACK, Mat.SmoothPlastic)
	box(
		"CatHoloCube",
		Vector3.new(2.6, 2.6, 2.6),
		CFrame.new(t2 + Vector3.new(0, 2.4, 0)) * CFrame.Angles(RAD(35), RAD(45), 0),
		CYAN,
		Mat.Neon,
		0.35
	)
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
	for _, dv in { -1.1, 1.1 } do
		sphere("HoloBrain", 3.6, at(3, U, 305, dv), PINK, Mat.Neon, 0.3)
	end
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
		box("JarGlass", Vector3.new(w, y1 - y0, t), cf, rgb(220, 120, 255), Mat.Glass, 0.45)
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
local function buildInferno(folder: Instance)
	local model = Build.Model("Inferno", folder)
	target = model
	local _ = rng
	local _f = fire
	local _t = FIRE_TEX
end

function ExtremeDecorB.Build(folder: Instance)
	buildLab(folder)
	buildInferno(folder)
end

return ExtremeDecorB
