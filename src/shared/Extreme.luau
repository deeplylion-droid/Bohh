-- Percorso Estremo: percorso alternativo, molto difficile. Parte con un bivio all'inizio del sentiero
-- normale (a destra della discesa dalla piazza, verso ovest) e attraversa un canyon sospeso in quattro
-- sezioni: Rapide degli Abissi, Tempio del Deserto, Laboratorio dei Geni, Inferno. In fondo a ogni
-- sezione c'e' un santuario con un uovo Estremo della sezione, un checkpoint e un portale di ritorno.
--
-- Tutto e' definito qui (condiviso): il server costruisce le parti e convalida, il client anima gli
-- elementi mobili in funzione del tempo del server e segnala i colpi.
-- Coordinate di sezione: u = distanza lungo il percorso (verso -X), v = spostamento laterale (z),
-- y = quota assoluta.

local Extreme = {}

Extreme.Z = 215 -- asse del percorso (si procede verso -X)
Extreme.HalfWidth = 19 -- meta' larghezza interna del canyon (fra i muri invisibili)
Extreme.StartX = -60 -- oltre questa x comincia il percorso (parte la corsa)
-- ponticello del bivio: dal bordo ovest della discesa del sentiero (quota del terreno) alla bocca del canyon
Extreme.BranchFrom = Vector3.new(-20, 319, 215)
Extreme.BranchTo = Vector3.new(-56, 331, 215)
Extreme.WallTop = 430 -- i muri invisibili arrivano fino a qui
-- il portale riporta in piazza, sul viale del sentiero, rivolti verso il centro (e i lotti)
Extreme.ReturnCFrame = CFrame.lookAt(Vector3.new(0, 334.5, 96), Vector3.new(0, 334.5, 0))
Extreme.WalkSpeed = 18 -- velocita' fissa per tutti durante la corsa (i potenziamenti non contano)
Extreme.BodyDown = 3 -- dal centro del HumanoidRootPart ai piedi

export type Section = {
	index: number,
	id: string, -- zona (uova e pet della sezione)
	theme: string,
	x0: number, -- inizio della sezione
	length: number, -- lunghezza degli ostacoli
	shrineLength: number, -- lunghezza del santuario in fondo
	floor: number, -- quota del pavimento del santuario
	killY: number, -- sotto questa quota (dentro la sezione) si torna al checkpoint
}

export type Piece = {
	id: string,
	kind: string, -- Solid | Kill | Mover | Spinner | Swing | Sweeper | Pulse | Faller | Bounce | Conveyor
	section: number,
	cframe: CFrame,
	size: Vector3,
	color: Color3?,
	material: string?,
	shape: string?, -- Block | Cylinder | Ball | Wedge
	transparency: number?,
	collide: boolean?,
	-- Mover: spostamento massimo e modo ("sine" avanti/indietro, "flow" scorre e ricomincia)
	offset: Vector3?,
	period: number?,
	phase: number?,
	mode: string?,
	-- Pulse: fase attiva e avviso (secondi), effetto "Kill" o "Knock"
	active: number?,
	warn: number?,
	effect: string?,
	-- Faller: secondi in cui e' solido in ogni periodo
	solid: number?,
	-- Bounce / Knock: forza
	power: number?,
	-- Conveyor: velocita'
	velocity: Vector3?,
	-- Swing: lunghezza della corda (perno in cframe, oscilla attorno all'asse X locale)
	length: number?,
	amplitude: number?,
	deco: boolean?,
	-- Pulse: aspetto ("Jet", "Crusher", "Laser", "Fire") e alzata della pressa
	style: string?,
	rise: number?,
	-- sponde e pareti del canyon (fuori dai muri invisibili: non sono appoggi)
	wall: boolean?,
}

Extreme.Sections = {
	{
		index = 1,
		id = "Abyss",
		theme = "Rapids",
		x0 = Extreme.StartX,
		length = 396,
		shrineLength = 60,
		floor = 278,
		killY = 268,
	},
	{
		index = 2,
		id = "Desert",
		theme = "Desert",
		x0 = Extreme.StartX - 456,
		length = 360,
		shrineLength = 60,
		floor = 262,
		killY = 250,
	},
	{
		index = 3,
		id = "Lab",
		theme = "Lab",
		x0 = Extreme.StartX - 876,
		length = 340,
		shrineLength = 60,
		floor = 246,
		killY = 232,
	},
	{
		index = 4,
		id = "Inferno",
		theme = "Inferno",
		x0 = Extreme.StartX - 1276,
		length = 360,
		shrineLength = 70,
		floor = 230,
		killY = 214,
	},
} :: { Section }

Extreme.EndX = Extreme.Sections[4].x0 - Extreme.Sections[4].length - Extreme.Sections[4].shrineLength

---------------------------------------------------------------------------------------------
-- Elementi
---------------------------------------------------------------------------------------------
local pieces: { Piece } = {}
local byId: { [string]: Piece } = {}
local counter = 0

local function add(p: Piece): Piece
	counter += 1
	if p.id == "" then
		p.id = `X{counter}`
	end
	table.insert(pieces, p)
	byId[p.id] = p
	return p
end

local function sec(i: number): Section
	return Extreme.Sections[i]
end

-- Punto del mondo da coordinate di sezione
local function at(s: Section, u: number, y: number, v: number): Vector3
	return Vector3.new(s.x0 - u, y, Extreme.Z + v)
end
Extreme.At = function(i: number, u: number, y: number, v: number): Vector3
	return at(sec(i), u, y, v)
end

local function rgb(r: number, g: number, b: number): Color3
	return Color3.fromRGB(r, g, b)
end

-- blocco con la faccia superiore a quota top, da u0 a u1 e da v0 a v1
local function slab(
	i: number,
	u0: number,
	u1: number,
	v0: number,
	v1: number,
	top: number,
	thick: number,
	color: Color3,
	material: string,
	extra: { [string]: any }?
): Piece
	local s = sec(i)
	local center = at(s, (u0 + u1) / 2, top - thick / 2, (v0 + v1) / 2)
	local p: any = {
		id = "",
		kind = "Solid",
		section = i,
		cframe = CFrame.new(center),
		size = Vector3.new(math.abs(u1 - u0), thick, math.abs(v1 - v0)),
		color = color,
		material = material,
	}
	if extra then
		for k, val in extra do
			p[k] = val
		end
	end
	return add(p)
end

-- colonna cilindrica verticale con la cima a quota top
local function pillar(
	i: number,
	u: number,
	v: number,
	top: number,
	radius: number,
	height: number,
	color: Color3,
	material: string,
	extra: { [string]: any }?
): Piece
	local s = sec(i)
	local p: any = {
		id = "",
		kind = "Solid",
		section = i,
		cframe = CFrame.new(at(s, u, top - height / 2, v)) * CFrame.Angles(0, 0, math.rad(90)),
		size = Vector3.new(height, radius * 2, radius * 2),
		color = color,
		material = material,
		shape = "Cylinder",
	}
	if extra then
		for k, val in extra do
			p[k] = val
		end
	end
	return add(p)
end

-- volume mortale (acqua, sabbie mobili, lava, vuoto): dalla quota top in giu'
local function kill(i: number, u0: number, u1: number, top: number, depth: number?)
	local s = sec(i)
	local d = depth or 40
	add({
		id = "",
		kind = "Kill",
		section = i,
		cframe = CFrame.new(at(s, (u0 + u1) / 2, top - d / 2, 0)),
		size = Vector3.new(math.abs(u1 - u0), d, Extreme.HalfWidth * 2 + 6),
	})
end

-- superficie visibile del liquido (non solida) e volume mortale poco sopra
local function liquid(i: number, u0: number, u1: number, level: number, color: Color3, material: string, alpha: number)
	slab(i, u0, u1, -Extreme.HalfWidth - 3, Extreme.HalfWidth + 3, level, 2, color, material, {
		collide = false,
		transparency = alpha,
		deco = true,
	})
	kill(i, u0, u1, level + 0.8)
end

-- pareti visibili ai due lati (sale dei santuari, laboratorio); sopra c'e' il muro invisibile
local function walls(i: number, u0: number, u1: number, bottom: number, top: number, color: Color3, material: string)
	for _, side in { -1, 1 } do
		local v0 = side * (Extreme.HalfWidth + 0.5)
		local v1 = side * (Extreme.HalfWidth + 6)
		local p = slab(i, u0, u1, math.min(v0, v1), math.max(v0, v1), top, top - bottom, color, material)
		p.wall = true
	end
end

local function shade(c: Color3, k: number): Color3
	return Color3.new(math.clamp(c.R * k, 0, 1), math.clamp(c.G * k, 0, 1), math.clamp(c.B * k, 0, 1))
end

-- Sponde di roccia irregolari ai due lati: blocchi di lunghezza, altezza e colore diversi, inclinati
-- verso l'esterno, alti 8-20 stud sopra il percorso (si vede il cielo; il confine vero e' il muro
-- invisibile). floorAt(u) = quota del percorso in quel punto; cap = colore della cima (muschio...)
local bankRng = Random.new(20261031)
local function banks(
	i: number,
	u0: number,
	u1: number,
	floorAt: (number) -> number,
	color: Color3,
	material: string,
	cap: Color3?,
	capMaterial: string?
)
	for _, side in { -1, 1 } do
		local u = u0
		while u < u1 - 0.01 do
			local uu = math.min(u + bankRng:NextNumber(9, 16), u1)
			local f = floorAt((u + uu) / 2)
			local top = f + bankRng:NextNumber(8, 20)
			local bottom = f - 46
			local inner = Extreme.HalfWidth + 0.6 + bankRng:NextNumber(0, 1.6)
			local depth = bankRng:NextNumber(6, 10)
			local v0, v1 = side * inner, side * (inner + depth)
			local p = slab(
				i,
				u - 0.6,
				uu + 0.6,
				math.min(v0, v1),
				math.max(v0, v1),
				top,
				top - bottom,
				shade(color, bankRng:NextNumber(0.86, 1.12)),
				material
			)
			p.wall = true
			-- inclinata verso l'esterno (rotazione attorno all'asse del percorso) e un po' storta
			local lean = math.rad(side * bankRng:NextNumber(1, 6))
			local yaw = math.rad(bankRng:NextNumber(-4, 4))
			p.cframe = p.cframe * CFrame.Angles(lean, yaw, 0)
			if cap then
				local c = add({
					id = "",
					kind = "Solid",
					section = i,
					cframe = p.cframe * CFrame.new(0, p.size.Y / 2 + 0.25, 0),
					size = Vector3.new(p.size.X + 0.4, 0.8, p.size.Z + 0.4),
					color = shade(cap, bankRng:NextNumber(0.9, 1.1)),
					material = capMaterial or material,
					deco = true,
					collide = false,
				})
				c.wall = true
			end
			u = uu
		end
	end
end

-- Quota del percorso lungo la sezione: dalla partenza al pavimento del santuario, a tratti
local function floorLine(points: { { number } }): (number) -> number
	return function(u: number): number
		if u <= points[1][1] then
			return points[1][2]
		end
		for k = 1, #points - 1 do
			local a, b = points[k], points[k + 1]
			if u <= b[1] then
				return a[2] + (b[2] - a[2]) * (u - a[1]) / (b[1] - a[1])
			end
		end
		return points[#points][2]
	end
end

-- Cascata: velo d'acqua sottile appena oltre il bordo u (dove finisce la vasca di sopra), dal pelo
-- dell'acqua di sotto (low) a quello di sopra (high), senza entrare nelle due vasche, piu' una striscia di
-- schiuma che galleggia dove cade. Quello che c'e' al bordo (sporgenze, rive) finisce prima di u e
-- ricomincia dopo u + FALL_THICK, per non attraversare il velo.
local FALL_THICK = 0.6
local function fall(i: number, u: number, high: number, low: number)
	local sheet = slab(
		i,
		u,
		u + FALL_THICK,
		-Extreme.HalfWidth - 3,
		Extreme.HalfWidth + 3,
		high,
		high - low,
		rgb(120, 200, 240),
		"Glass",
		{
			collide = false,
			transparency = 0.3,
			deco = true,
		}
	)
	sheet.style = "Fall"
	local foam = slab(
		i,
		u + FALL_THICK,
		u + FALL_THICK + 3.2,
		-Extreme.HalfWidth - 3,
		Extreme.HalfWidth + 3,
		low + 0.2,
		0.16,
		rgb(240, 250, 255),
		"SmoothPlastic",
		{
			collide = false,
			transparency = 0.2,
			deco = true,
		}
	)
	foam.style = "Foam"
end

---------------------------------------------------------------------------------------------
-- Sezione 1: le Rapide degli Abissi
---------------------------------------------------------------------------------------------
do
	local ROCK = rgb(104, 98, 92)
	local STONE = rgb(168, 160, 146) -- sassi chiari su cui saltare (si vedono bene sull'acqua)
	local STONE_SINK = rgb(112, 104, 96) -- quelli che affondano sono piu' scuri
	local MOSS = rgb(86, 124, 62)
	local WATER = rgb(38, 150, 212)
	local DEEP = rgb(20, 70, 130)
	local WOOD = rgb(132, 86, 48)

	banks(
		1,
		0,
		396,
		floorLine({ { 0, 331 }, { 110, 321 }, { 120, 307 }, { 232, 304 }, { 240, 292 }, { 336, 290 }, { 340, 278 } }),
		ROCK,
		"Slate",
		MOSS,
		"Grass"
	)
	-- partenza: piattaforma di roccia collegata al ponte
	slab(1, -4, 14, -10, 10, 331, 8, ROCK, "Slate")
	slab(1, -4, 14, -10.5, 10.5, 331.2, 0.4, MOSS, "Grass", { deco = true, collide = false })

	-- A) Sassi: pietre per saltare, alcune ondeggiano o affondano a intervalli
	liquid(1, 14, 116, 318, WATER, "SmoothPlastic", 0.2)
	slab(1, 14, 116, -Extreme.HalfWidth, Extreme.HalfWidth, 312, 6, DEEP, "Slate", { deco = true, collide = false })
	local stonesA = {
		{ 20, 0, 320.6, 3.2 },
		{ 28, -7, 321.2, 2.7 },
		{ 36, -13, 321.6, 2.4, "bob" },
		{ 44, -6, 320.8, 2.3 },
		{ 52, 1, 321.4, 2.2, "sink" },
		{ 60, 8, 321.8, 2.4 },
		{ 68, 14, 321.2, 2.1, "bob" },
		{ 76, 8, 320.6, 2.4 },
		{ 84, 1, 321.4, 2.1, "sink" },
		{ 92, -6, 321.0, 2.3 },
		{ 100, -12, 321.6, 2.1, "bob" },
		{ 107, -4, 321.2, 2.8 },
	}
	for k, st in stonesA do
		local u, v, top, r, mode = st[1], st[2], st[3], st[4], st[5]
		if mode == "bob" then
			local p = pillar(1, u, v, top, r, 12, STONE, "Slate")
			p.kind = "Mover"
			p.mode = "sine"
			p.offset = Vector3.new(0, 1.6, 0)
			p.period = 2.4 + (k % 3) * 0.4
			p.phase = k * 0.37
		elseif mode == "sink" then
			local p = pillar(1, u, v, top, r, 12, STONE_SINK, "Slate")
			p.kind = "Faller"
			p.period = 4.5
			p.solid = 2.8
			p.phase = k * 0.21
		else
			pillar(1, u, v, top, r, 12, STONE, "Slate")
		end
	end
	-- cascata 1: sporgenza in cima, poi giu' nel bacino dei tronchi
	slab(1, 108, 116, -6, 6, 321, 4, ROCK, "Slate")
	fall(1, 116, 318, 304)

	-- B) Tronchi: corsie di tronchi che scorrono verso valle; si sale a sinistra, si scende a destra
	liquid(1, 116, 232, 304, WATER, "SmoothPlastic", 0.2)
	slab(1, 116, 124, -Extreme.HalfWidth, -15, 307, 6, ROCK, "Slate") -- riva d'ingresso (sinistra)
	slab(1, 220, 232, 9, Extreme.HalfWidth, 307.5, 6, ROCK, "Slate") -- riva d'uscita (destra)
	local lanes = {
		{ v = -12, speed = 7, gap = 26, logLength = 13 },
		{ v = -4, speed = 9.5, gap = 30, logLength = 12 },
		{ v = 4, speed = 6, gap = 24, logLength = 11 },
	}
	local runStart, runEnd = 120, 232
	local runLen = runEnd - runStart
	for li, lane in lanes do
		local count = math.ceil(runLen / lane.gap)
		local period = runLen / lane.speed
		for n = 0, count - 1 do
			local s = sec(1)
			add({
				id = `Log{li}_{n}`,
				kind = "Mover",
				section = 1,
				mode = "flow",
				cframe = CFrame.new(at(s, runStart, 304.2, lane.v)),
				size = Vector3.new(lane.logLength, 3.2, 3.2),
				offset = Vector3.new(-runLen, 0, 0),
				period = period,
				phase = n / count + li * 0.13,
				color = WOOD,
				material = "Wood",
				shape = "Cylinder",
			})
		end
	end
	fall(1, 232, 304, 290)

	-- C) Vortici: dischi che girano sull'acqua, con qualche scoglio fra uno e l'altro
	liquid(1, 232, 336, 290, WATER, "SmoothPlastic", 0.2)
	slab(1, 232, 240, 9, Extreme.HalfWidth, 292, 6, ROCK, "Slate")
	local discs = {
		{ 248, 10, 5.5, 6 },
		{ 262, -2, 5.0, -7 },
		{ 276, -12, 5.5, 5.5 },
		{ 292, -3, 4.8, -6.5 },
		{ 304, 6, 5.2, 6 },
		{ 320, 0, 5.0, -5.5 },
	}
	for k, d in discs do
		local u, v, r, per = d[1], d[2], d[3], d[4]
		local p = pillar(1, u, v, 291.2, r, 2.4, rgb(70, 160, 200), "Slate")
		p.id = `Whirl{k}`
		p.kind = "Spinner"
		p.period = per -- negativo = senso opposto
		p.cframe = CFrame.new(at(sec(1), u, 290, v)) * CFrame.Angles(0, 0, math.rad(90))
	end
	pillar(1, 255, 4, 291.6, 1.6, 10, STONE, "Slate")
	pillar(1, 269, -8, 291.7, 1.5, 10, STONE, "Slate")
	pillar(1, 284, -8, 291.8, 1.5, 10, STONE, "Slate")
	pillar(1, 313, 4, 291.6, 1.6, 10, STONE, "Slate")
	-- getto d'acqua che lancia in aria chi ci passa sopra
	add({
		id = "Spout1",
		kind = "Pulse",
		section = 1,
		cframe = CFrame.new(at(sec(1), 299, 294, 1)),
		size = Vector3.new(5, 8, 5),
		period = 3.6,
		active = 1.1,
		warn = 0.9,
		phase = 0.3,
		effect = "Knock",
		power = 70,
		color = rgb(220, 240, 255),
	})
	slab(1, 326, 336, -5, 5, 292, 4, ROCK, "Slate")
	fall(1, 336, 290, 276)

	-- D) Rapide finali: dorsale di sassi stretta fra tronchi appesi che oscillano
	liquid(1, 336, 396, 276, WATER, "SmoothPlastic", 0.15)
	local spine = { { 338, 344 }, { 349, 354 }, { 359, 363 }, { 368, 373 }, { 378, 382 }, { 387, 396 } }
	for _, sg in spine do
		slab(1, sg[1], sg[2], -2.6, 2.6, 278, 10, STONE, "Slate")
	end
	for k, u in { 352, 366, 380 } do
		local s = sec(1)
		add({
			id = `Swing1_{k}`,
			kind = "Swing",
			section = 1,
			cframe = CFrame.new(at(s, u, 300, 0)),
			size = Vector3.new(9, 2.6, 2.6),
			length = 19,
			amplitude = math.rad(55),
			period = 2.8 + k * 0.25,
			phase = k * 0.31,
			power = 60,
			color = WOOD,
			material = "Wood",
		})
	end
end

-- elemento a impulsi (getto, pressa, laser, fiamma): attivo per 'active' secondi ogni 'period'
local function pulse(
	i: number,
	id: string,
	center: Vector3,
	size: Vector3,
	period: number,
	active: number,
	phase: number,
	effect: string,
	style: string,
	extra: { [string]: any }?
): Piece
	local p: any = {
		id = id,
		kind = "Pulse",
		section = i,
		cframe = CFrame.new(center),
		size = size,
		period = period,
		active = active,
		warn = 0.7,
		phase = phase,
		effect = effect,
		style = style,
		power = 70,
	}
	if extra then
		for k, val in extra do
			p[k] = val
		end
	end
	return add(p)
end

-- barra che gira attorno a un asse verticale (lame, raggi laser): colpisce chi tocca
local function sweeper(
	i: number,
	id: string,
	hub: Vector3,
	size: Vector3,
	period: number,
	phase: number,
	effect: string,
	color: Color3,
	material: string
): Piece
	return add({
		id = id,
		kind = "Sweeper",
		section = i,
		cframe = CFrame.new(hub),
		size = size,
		period = period,
		phase = phase,
		effect = effect,
		power = 75,
		color = color,
		material = material,
	})
end

---------------------------------------------------------------------------------------------
-- Sezione 2: il Tempio del Deserto
---------------------------------------------------------------------------------------------
do
	local SAND = rgb(222, 186, 118)
	local STONE = rgb(198, 160, 98)
	local STONE_DARK = rgb(150, 112, 64)
	local PLATFORM = rgb(240, 212, 156) -- pietra chiara: dove si salta (si stacca dalle sponde)
	local QUICK = rgb(150, 104, 52) -- sabbie mobili piu' scure
	local GOLD = rgb(255, 196, 60)
	local s2 = sec(2)

	banks(
		2,
		0,
		360,
		floorLine({ { 0, 278 }, { 92, 280 }, { 172, 278 }, { 176, 272 }, { 264, 272 }, { 270, 266 }, { 350, 263 } }),
		STONE,
		"Sandstone",
		SAND,
		"Sand"
	)
	slab(2, -2, 8, -8, 8, 278, 8, PLATFORM, "Sandstone")

	-- A) Pilastri sulle sabbie mobili, due presse che schiacciano a tempo
	liquid(2, 8, 92, 266, QUICK, "Sand", 0)
	local cols = {
		{ 14, 0, 277, 3 },
		{ 22, -7, 279, 2.6 },
		{ 30, -12, 281, 2.4 },
		{ 38, -5, 283, 2.4 },
		{ 46, 3, 281, 2.2 },
		{ 54, 10, 279, 2.4 },
		{ 62, 4, 280, 2.2 },
		{ 70, -3, 282, 2.4 },
		{ 78, -10, 280, 2.6 },
		{ 86, -4, 278, 3 },
	}
	for _, c in cols do
		local u, v, top, h = c[1], c[2], c[3], c[4]
		slab(2, u - h, u + h, v - h, v + h, top, 16, PLATFORM, "Sandstone")
		slab(2, u - h - 0.3, u + h + 0.3, v - h - 0.3, v + h + 0.3, top - 0.6, 0.8, STONE_DARK, "Sandstone", {
			deco = true,
			collide = false,
		})
	end
	for k, c in { cols[4], cols[8] } do
		pulse(
			2,
			`Crusher{k}`,
			at(s2, c[1], c[3] + 3, c[2]),
			Vector3.new(6, 6, 6),
			3.4,
			0.8,
			k * 0.45,
			"Kill",
			"Crusher",
			{
				color = STONE_DARK,
				material = "Sandstone",
				rise = 9,
			}
		)
	end

	-- B) Corridoio delle lame: passerella stretta, ai lati sabbie mobili
	liquid(2, 92, 172, 268, QUICK, "Sand", 0)
	slab(2, 92, 172, -5, 5, 278, 10, PLATFORM, "Sandstone")
	for k, u in { 104, 120, 136, 152, 166 } do
		pillar(2, u, 0, 279.6, 0.9, 1.6, GOLD, "Foil")
		sweeper(
			2,
			`Blade{k}`,
			at(s2, u, 279.8, 0),
			Vector3.new(11, 0.7, 0.9),
			if k % 2 == 0 then -2.2 else 2.5,
			k * 0.17,
			"Knock",
			rgb(220, 226, 236),
			"Metal"
		)
	end

	-- C) Mattonelle che sprofondano a ondate
	liquid(2, 172, 262, 262, QUICK, "Sand", 0)
	slab(2, 172, 176, -6, 6, 272, 6, PLATFORM, "Sandstone")
	for row = 0, 11 do
		for lane = -1, 1 do
			local u = 180 + row * 7
			local v = lane * 7 + (if row % 2 == 0 then 1.5 else -1.5)
			local t = slab(2, u - 2.6, u + 2.6, v - 2.6, v + 2.6, 272, 2, SAND, "Sandstone")
			t.kind = "Faller"
			t.period = 4.2
			t.solid = 2.6
			t.phase = row * 0.11 + (lane + 1) * 0.29
		end
	end
	slab(2, 258, 264, -6, 6, 272, 6, PLATFORM, "Sandstone")

	-- D) Piattaforme di pietra che vanno avanti e indietro sopra il vuoto (salti di 6 stud)
	kill(2, 264, 360, 254)
	for k, m in
		{
			{ 274, 266, 9, 4.2 },
			{ 290, 265, -9, 3.6 },
			{ 306, 264, 8, 4.6 },
			{ 322, 263.5, -8, 3.8 },
			{ 338, 263, 9, 4 },
		}
	do
		local p = slab(2, m[1] - 5, m[1] + 5, -4, 4, m[2], 2.4, PLATFORM, "Sandstone")
		p.id = `Shuttle2_{k}`
		p.kind = "Mover"
		p.mode = "sine"
		p.offset = Vector3.new(0, 0, m[3])
		p.period = m[4]
		p.phase = k * 0.23
	end
	slab(2, 348, 362, -6, 6, 262.5, 4, PLATFORM, "Sandstone")
	-- obelischi decorativi fuori dal percorso
	for k, u in { 40, 130, 220, 310 } do
		for _, side in { -1, 1 } do
			slab(
				2,
				u - 2,
				u + 2,
				side * 24 - 2,
				side * 24 + 2,
				300,
				40,
				STONE_DARK,
				"Sandstone",
				{ deco = true, collide = false }
			)
			add({
				id = "",
				kind = "Solid",
				section = 2,
				cframe = CFrame.new(at(s2, u, 302, side * 24)) * CFrame.Angles(0, math.rad(45), 0),
				size = Vector3.new(3.4, 4, 3.4),
				color = GOLD,
				material = "Foil",
				deco = true,
				collide = false,
			})
			local _ = k
		end
	end
end

---------------------------------------------------------------------------------------------
-- Sezione 3: il Laboratorio dei Geni
---------------------------------------------------------------------------------------------
do
	local METAL = rgb(186, 196, 210)
	local DARK = rgb(52, 58, 74)
	local NEON = rgb(80, 255, 220)
	local LASER = rgb(255, 40, 90)
	local s3 = sec(3)

	for _, side in { -1, 1 } do
		local v0, v1 = side * (Extreme.HalfWidth + 0.5), side * (Extreme.HalfWidth + 4)
		for k, seg in { { 0, 96, 278 }, { 96, 236, 286 }, { 236, 340, 268 } } do
			local w = slab(3, seg[1], seg[2], math.min(v0, v1), math.max(v0, v1), seg[3], 60, DARK, "DiamondPlate")
			w.wall = true
			local strip = slab(3, seg[1], seg[2], math.min(v0, v1), math.max(v0, v1), seg[3] + 0.6, 0.6, NEON, "Neon", {
				deco = true,
				collide = false,
			})
			strip.wall = true
			local _ = k
		end
	end
	-- vuoto elettrico: griglia luminosa in basso
	kill(3, 0, 340, 238)
	slab(
		3,
		0,
		340,
		-Extreme.HalfWidth,
		Extreme.HalfWidth,
		226,
		1,
		NEON,
		"Neon",
		{ deco = true, collide = false, transparency = 0.6 }
	)

	-- A) Griglia laser: raggi bassi da saltare e pareti laser che si accendono a tempo
	slab(3, -2, 92, -Extreme.HalfWidth, Extreme.HalfWidth, 262, 6, METAL, "DiamondPlate")
	local lasers = {
		{ 14, "low", 0 },
		{ 26, "wall", 0.0 },
		{ 38, "low", 0 },
		{ 46, "wall", 0.5 },
		{ 58, "low", 0 },
		{ 66, "wall", 0.25 },
		{ 74, "wall", 0.75 },
		{ 86, "low", 0 },
	}
	for k, l in lasers do
		local u, kind, ph = l[1], l[2], l[3]
		if kind == "low" then
			pulse(
				3,
				`LaserLow{k}`,
				at(s3, u, 263.4, 0),
				Vector3.new(0.6, 1, Extreme.HalfWidth * 2),
				1,
				1,
				0,
				"Kill",
				"Laser",
				{
					color = LASER,
				}
			)
		else
			pulse(
				3,
				`LaserWall{k}`,
				at(s3, u, 268, 0),
				Vector3.new(0.6, 12, Extreme.HalfWidth * 2),
				2.6,
				1.3,
				ph,
				"Kill",
				"Laser",
				{
					color = LASER,
				}
			)
		end
	end

	-- B) Nastri trasportatori al contrario sopra il vuoto, molle per salire
	for k, b in { { 96, 116, -6, 6 }, { 122, 140, -4, 8 }, { 146, 162, -8, 4 } } do
		local p = slab(3, b[1], b[2], b[3], b[4], 262, 3, rgb(40, 44, 56), "Fabric")
		p.kind = "Conveyor"
		p.velocity = Vector3.new(10, 0, 0) -- verso +X: all'indietro
		p.id = `Belt{k}`
	end
	local pad = slab(3, 164, 170, -3, 3, 262.5, 1, rgb(255, 210, 40), "Neon")
	pad.kind = "Bounce"
	pad.power = 95
	pad.id = "Spring3"
	slab(3, 176, 190, -8, 8, 276, 3, METAL, "DiamondPlate")

	-- C) Sala rotonda col doppio raggio rotante (basso: da saltare; alto: non saltare quando passa)
	pillar(3, 210, 0, 268, 18, 4, METAL, "DiamondPlate")
	pillar(3, 210, 0, 268.3, 2.2, 1.2, NEON, "Neon")
	sweeper(3, "BeamLow", at(s3, 210, 269.2, 0), Vector3.new(34, 0.8, 0.8), 3.4, 0, "Kill", LASER, "Neon")
	sweeper(3, "BeamHigh", at(s3, 210, 274.4, 0), Vector3.new(34, 0.8, 0.8), -4.6, 0.25, "Kill", LASER, "Neon")
	slab(3, 228, 236, -4, 4, 268, 3, METAL, "DiamondPlate")

	-- D) Piattaforme volanti: ascensore, navette e salto finale verso il santuario
	local lift = slab(3, 240, 248, -4, 4, 262, 2, METAL, "DiamondPlate")
	lift.id = "Lift3"
	lift.kind = "Mover"
	lift.mode = "sine"
	lift.offset = Vector3.new(0, 6, 0)
	lift.period = 3.2
	-- navette larghe 8 a 6 stud l'una dall'altra, sempre piu' basse, che scorrono di lato
	for k, m in
		{
			{ 258, 264, 9, 3.4 },
			{ 272, 261, -9, 3.0 },
			{ 286, 258, 8, 3.8 },
			{ 300, 255, -9, 3.2 },
			{ 314, 252, 8, 3.6 },
			{ 328, 249.5, -7, 3.3 },
		}
	do
		local p = slab(3, m[1] - 4, m[1] + 4, -3.5, 3.5, m[2], 2, METAL, "DiamondPlate")
		p.id = `Shuttle3_{k}`
		p.kind = "Mover"
		p.mode = "sine"
		p.offset = Vector3.new(0, 0, m[3])
		p.period = m[4]
		p.phase = k * 0.19
	end
	slab(3, 334, 342, -6, 6, 247, 3, METAL, "DiamondPlate")
end

---------------------------------------------------------------------------------------------
-- Sezione 4: l'Inferno
---------------------------------------------------------------------------------------------
do
	local BASALT = rgb(52, 40, 40)
	local BASALT_DARK = rgb(34, 26, 26)
	local LAVA = rgb(255, 92, 20)
	local CHAIN = rgb(90, 84, 84)
	local s4 = sec(4)

	banks(
		4,
		0,
		360,
		floorLine({ { 0, 246 }, { 96, 245 }, { 172, 244 }, { 262, 242 }, { 272, 240 }, { 360, 231 } }),
		BASALT,
		"Basalt",
		rgb(255, 90, 30),
		"Neon"
	)

	-- A) Fiume di lava con pietre di basalto (alcune sprofondano) e geyser di fuoco
	liquid(4, -2, 92, 236, LAVA, "Neon", 0)
	slab(4, -2, 6, -6, 6, 246, 8, BASALT, "Basalt")
	-- pietre piccole a zig-zag (salti di 4-5 stud); quelle scure sprofondano a turno nella lava, quindi
	-- bisogna aspettare sulla pietra prima che riaffiori
	local stones = {
		{ 12, 0, 245.4, 2.6 },
		{ 19, -5, 246.0, 2.2, "sink" },
		{ 26, -10, 246.6, 2.0 },
		{ 33, -5, 247.2, 2.0, "sink" },
		{ 40, 0, 246.6, 2.0 },
		{ 47, 5, 247.2, 2.0, "sink" },
		{ 54, 10, 246.6, 2.0 },
		{ 61, 5, 247.0, 2.0, "sink" },
		{ 68, 0, 246.4, 2.0 },
		{ 75, -5, 246.0, 2.2, "sink" },
		{ 82, -2, 245.6, 2.4 },
	}
	for k, st in stones do
		local p = pillar(4, st[1], st[2], st[3], st[4], 14, if st[5] then BASALT_DARK else BASALT, "Basalt")
		if st[5] then
			p.kind = "Faller"
			p.period = 3.6
			p.solid = 2.1
			p.phase = k * 0.27
		end
	end
	-- geyser di fuoco accanto alle pietre: chi salta largo ci finisce dentro
	for k, g in { { 23, 2 }, { 37, -12 }, { 50, -3 }, { 64, 12 }, { 78, 5 } } do
		pulse(4, `FireGeyser{k}`, at(s4, g[1], 246, g[2]), Vector3.new(4, 20, 4), 3.0, 0.9, k * 0.31, "Kill", "Fire", {
			color = LAVA,
		})
	end
	slab(4, 86, 96, -6, 6, 245, 8, BASALT, "Basalt")

	-- B) Ponte di basalto con getti di fuoco dai lati, alternati
	liquid(4, 96, 172, 232, LAVA, "Neon", 0)
	slab(4, 96, 172, -4, 4, 244, 6, BASALT, "Basalt")
	for k = 0, 6 do
		local u = 104 + k * 10
		local side = if k % 2 == 0 then -1 else 1
		pulse(4, `FireJet{k}`, at(s4, u, 247, side * 2), Vector3.new(4, 6, 8), 2.2, 0.9, k * 0.18, "Kill", "Fire", {
			color = LAVA,
		})
		slab(4, u - 1.5, u + 1.5, side * 6 - 1.5, side * 6 + 1.5, 252, 10, BASALT_DARK, "Basalt", { deco = true })
	end

	-- C) Ponte di catene strettissimo con uncini che oscillano
	liquid(4, 172, 262, 230, LAVA, "Neon", 0)
	slab(4, 172, 262, -1.6, 1.6, 242, 1.2, CHAIN, "Metal")
	for k, u in { 186, 202, 218, 234, 250 } do
		add({
			id = `Hook{k}`,
			kind = "Swing",
			section = 4,
			cframe = CFrame.new(at(s4, u, 264, 0)),
			size = Vector3.new(2.4, 4.8, 2.4),
			length = 19,
			amplitude = math.rad(60),
			period = 2.2 + (k % 3) * 0.3,
			phase = k * 0.27,
			power = 70,
			color = CHAIN,
			material = "Metal",
		})
	end
	slab(4, 262, 270, -5, 5, 242, 6, BASALT, "Basalt")

	-- D) Ponte che crolla a ondate: bisogna correre senza fermarsi fino alla sala del trono
	liquid(4, 270, 360, 226, LAVA, "Neon", 0)
	for k = 0, 14 do
		local u = 272 + k * 6
		local t = slab(4, u, u + 5.2, -3.5, 3.5, 240 - k * 0.6, 2, BASALT, "Basalt")
		t.kind = "Faller"
		t.period = 5
		t.solid = 3.2
		t.phase = -k * 0.07
	end
end

---------------------------------------------------------------------------------------------
-- Santuari: sala in fondo a ogni sezione con l'altare dell'uovo, il checkpoint e il portale
---------------------------------------------------------------------------------------------
local SHRINE_STYLE = {
	Rapids = { floor = rgb(104, 124, 160), wall = rgb(60, 72, 104), glow = rgb(60, 220, 255), material = "Slate" },
	Desert = { floor = rgb(214, 178, 112), wall = rgb(190, 150, 90), glow = rgb(255, 200, 60), material = "Sandstone" },
	Lab = { floor = rgb(200, 210, 222), wall = rgb(64, 72, 90), glow = rgb(120, 255, 220), material = "DiamondPlate" },
	Inferno = { floor = rgb(84, 54, 50), wall = rgb(96, 34, 28), glow = rgb(255, 80, 30), material = "Basalt" },
}

Extreme.Shrines = {}
for i, s in Extreme.Sections do
	local st = SHRINE_STYLE[s.theme]
	local u0 = s.length
	local u1 = s.length + s.shrineLength
	local y = s.floor
	slab(i, u0, u1, -Extreme.HalfWidth, Extreme.HalfWidth, y, 10, st.floor, st.material)
	walls(i, u0, u1, y - 10, y + 26, st.wall, st.material)
	-- tetto della sala
	local roof = slab(i, u0, u1, -Extreme.HalfWidth - 6, Extreme.HalfWidth + 6, y + 28, 2, st.wall, st.material)
	roof.wall = true
	local mid = (u0 + u1) / 2
	local shrine = {
		section = i,
		zone = s.id,
		altar = at(s, mid, y + 3.2, 0),
		portal = CFrame.lookAt(at(s, mid + 8, y + 5, -Extreme.HalfWidth + 2), at(s, mid + 8, y + 5, 0)),
		-- il checkpoint e' l'ingresso della sala; si rinasce davanti all'uscita, verso la sezione dopo
		checkpointX = s.x0 - u0 - 2,
		exitX = s.x0 - u1, -- oltre questa x si entra nella sezione dopo
		spawn = CFrame.lookAt(at(s, mid + 14, y + 3.5, 6), at(s, u1 + 20, y + 3.5, 6)),
		glow = st.glow,
	}
	slab(i, mid - 4, mid + 4, -4, 4, y + 1.4, 1.4, st.wall, st.material) -- base dell'altare
	pillar(i, mid, 0, y + 3, 2.4, 1.6, st.glow, "Neon")
	Extreme.Shrines[i] = shrine
end

-- partenza della corsa (checkpoint 0): sulla piattaforma di roccia della prima sezione
Extreme.StartSpawn = CFrame.lookAt(Extreme.At(1, 6, 334.5, 0), Extreme.At(1, 30, 334.5, 0))

-- Piani dei checkpoint (x): 0 = partenza, k = ingresso del santuario k
Extreme.CheckpointX = { [0] = Extreme.StartX }
for i, sh in Extreme.Shrines do
	Extreme.CheckpointX[i] = sh.checkpointX
end

Extreme.Pieces = pieces

-- indice per id rifatto a percorso completo: molti elementi ricevono il nome dopo add() (navette,
-- dischi, nastri, molla...) e senza questo il client non li troverebbe (resterebbero fermi)
table.clear(byId)
for _, p in pieces do
	byId[p.id] = p
end

function Extreme.Get(id: string): Piece?
	return byId[id]
end

---------------------------------------------------------------------------------------------
-- Stato degli elementi nel tempo (uguale sul server e sui client)
---------------------------------------------------------------------------------------------
local TAU = math.pi * 2

local function frac(x: number): number
	return x - math.floor(x)
end

-- CFrame e velocita' di un elemento mobile all'istante t
function Extreme.MoverState(p: Piece, t: number): (CFrame, Vector3)
	local per = p.period or 1
	local off = p.offset or Vector3.zero
	if p.mode == "flow" then
		local k = frac(t / per + (p.phase or 0))
		return p.cframe + off * k, off / per
	end
	local a = TAU * (t / per + (p.phase or 0))
	return p.cframe + off * math.sin(a), off * (math.cos(a) * TAU / per)
end

-- Rotazione dei dischi (attorno all'asse verticale del mondo)
function Extreme.SpinnerState(p: Piece, t: number): (CFrame, number)
	local per = p.period or 4
	local ang = TAU * t / per
	local pos = p.cframe.Position
	return CFrame.new(pos) * CFrame.Angles(0, ang, 0) * (p.cframe - pos), TAU / per
end

-- Tronco appeso: perno in cframe, oscilla attorno all'asse X locale del perno
function Extreme.SwingAngle(p: Piece, t: number): number
	return (p.amplitude or 0.8) * math.sin(TAU * (t / (p.period or 3) + (p.phase or 0)))
end

function Extreme.SwingState(p: Piece, t: number): CFrame
	return p.cframe * CFrame.Angles(Extreme.SwingAngle(p, t), 0, 0) * CFrame.new(0, -(p.length or 10), 0)
end

-- Fase di un elemento a impulsi: "idle", "warn" o "active"
function Extreme.PulsePhase(p: Piece, t: number): string
	local per = p.period or 3
	local k = frac(t / per + (p.phase or 0)) * per
	local active = p.active or 1
	local warn = p.warn or 0.6
	if k < active then
		return "active"
	elseif k > per - warn then
		return "warn"
	end
	return "idle"
end

-- Elemento che sparisce: true se in questo istante e' solido
function Extreme.FallerSolid(p: Piece, t: number): boolean
	local per = p.period or 4
	local k = frac(t / per + (p.phase or 0)) * per
	return k < (p.solid or per * 0.6)
end

-- Barra che gira attorno a un asse verticale passante per il mozzo (periodo negativo = senso opposto)
function Extreme.SweeperState(p: Piece, t: number): (CFrame, number)
	local per = p.period or 3
	local ang = TAU * (t / per + (p.phase or 0))
	return CFrame.new(p.cframe.Position) * CFrame.Angles(0, ang, 0), TAU / per
end

-- Posizione della pressa: giu' (sul pilastro) quando e' attiva, poi risale e aspetta in alto;
-- negli ultimi istanti dell'avviso piomba giu'
function Extreme.CrusherCFrame(p: Piece, t: number): CFrame
	local per = p.period or 3
	local k = frac(t / per + (p.phase or 0)) * per
	local active = p.active or 1
	local warn = p.warn or 0.6
	local rise = p.rise or 8
	local h
	if k < active then
		h = 0
	elseif k < active + 0.6 then
		h = rise * (k - active) / 0.6
	elseif k < per - 0.14 then
		h = rise
	else
		h = rise * (per - k) / 0.14
	end
	local _ = warn
	return p.cframe + Vector3.new(0, h, 0)
end

-- Volume (cframe, size) in cui un elemento a impulsi colpisce
function Extreme.PulseBox(p: Piece): (CFrame, Vector3)
	return p.cframe, p.size
end

---------------------------------------------------------------------------------------------
-- Regioni
---------------------------------------------------------------------------------------------

-- Vero se la posizione e' dentro il canyon del percorso (dopo l'inizio della corsa)
function Extreme.InCourse(pos: Vector3): boolean
	return pos.X < Extreme.StartX
		and pos.X * pos.X + pos.Z * pos.Z > 182 * 182
		and pos.X > Extreme.EndX - 10
		and math.abs(pos.Z - Extreme.Z) < Extreme.HalfWidth + 12
		and pos.Y > 150
		and pos.Y < Extreme.WallTop
end

-- Sezione (1..4) in cui si trova una x del percorso
function Extreme.SectionAt(x: number): number
	for i = #Extreme.Sections, 1, -1 do
		if x <= Extreme.Sections[i].x0 then
			return i
		end
	end
	return 1
end

local kills: { Piece } = {}
for _, p in pieces do
	if p.kind == "Kill" then
		table.insert(kills, p)
	end
end

-- Vero se la posizione e' dentro un volume mortale (acqua, sabbie mobili, lava, vuoto)
function Extreme.InKill(pos: Vector3): boolean
	for _, k in kills do
		local rel = k.cframe:PointToObjectSpace(pos)
		local h = k.size / 2
		if math.abs(rel.X) <= h.X and math.abs(rel.Y) <= h.Y and math.abs(rel.Z) <= h.Z then
			return true
		end
	end
	local s = Extreme.Sections[Extreme.SectionAt(pos.X)]
	return pos.Y < s.killY
end

---------------------------------------------------------------------------------------------
-- Controlli del server (anti-trucchi): appoggi, quota massima, elementi mortali
---------------------------------------------------------------------------------------------
local SUPPORT_KINDS = { Solid = true, Mover = true, Spinner = true, Faller = true, Bounce = true, Conveyor = true }

-- Elementi su cui si puo' stare in piedi, divisi per sezione
local supports: { [number]: { Piece } } = {}
for _, p in pieces do
	if SUPPORT_KINDS[p.kind] and p.collide ~= false and not p.deco and not p.wall then
		supports[p.section] = supports[p.section] or {}
		table.insert(supports[p.section], p)
	end
end
Extreme.Supports = supports

-- Ingombro in pianta (mezze misure lungo x e z del mondo) e quota della faccia superiore
local function footprint(p: Piece, cf: CFrame): (number, number, number)
	local sx, sy, sz = p.size.X / 2, p.size.Y / 2, p.size.Z / 2
	if p.shape == "Cylinder" then
		local axis = cf.RightVector -- asse del cilindro
		if math.abs(axis.Y) > 0.7 then
			-- colonna verticale: raggio = size.Y / 2, altezza = size.X
			return sy, sy, cf.Position.Y + sx
		end
		-- tronco orizzontale lungo x
		return sx, sy, cf.Position.Y + sy
	end
	-- blocchi (sempre allineati agli assi del mondo)
	return sx, sz, cf.Position.Y + sy
end

-- Posizione dell'elemento all'istante t (per gli appoggi mobili)
local function supportFrame(p: Piece, t: number): CFrame?
	if p.kind == "Mover" then
		return (Extreme.MoverState(p, t))
	elseif p.kind == "Faller" then
		-- conta anche se e' sparito da poco o sta per riapparire (ritardo di rete)
		if
			Extreme.FallerSolid(p, t)
			or Extreme.FallerSolid(p, t - 0.45)
			or Extreme.FallerSolid(p, t - 0.9)
			or Extreme.FallerSolid(p, t + 0.3)
		then
			return p.cframe
		end
		return nil
	end
	return p.cframe
end

-- Quota della superficie piu' alta sotto pos (entro 'depth' stud) fra gli appoggi della sezione
function Extreme.GroundBelow(pos: Vector3, t: number, depth: number, margin: number?): number?
	local m = margin or 2
	local best: number? = nil
	local s = Extreme.SectionAt(pos.X)
	local near: { { Piece } } = {}
	for k = s - 1, s + 1 do
		local list = supports[k]
		if list then
			table.insert(near, list)
		end
	end
	for _, list in near do
		for _, p in list do
			local reach = math.max(p.size.X, p.size.Z) / 2 + (if p.offset then p.offset.Magnitude else 0) + m
			local c = p.cframe.Position
			if math.abs(c.X - pos.X) <= reach and math.abs(c.Z - pos.Z) <= reach then
				-- le piattaforme mobili si controllano anche un po' indietro nel tempo (ritardo di rete)
				local times: { number } = if p.kind == "Mover" then { t, t - 0.25, t - 0.5, t - 0.8 } else { t }
				for _, tt in times do
					local cf = supportFrame(p, tt)
					if cf then
						local hx, hz, top = footprint(p, cf)
						local d = pos - cf.Position
						if
							math.abs(d.X) <= hx + m
							and math.abs(d.Z) <= hz + m
							and top <= pos.Y + 1
							and top >= pos.Y - depth
							and (best == nil or top > best)
						then
							best = top
						end
					end
				end
			end
		end
	end
	return best
end

-- Quota massima consentita (testa) lungo il percorso: superficie piu' alta nei dintorni + margine.
-- Le molle e i getti d'acqua concedono di piu' (Extreme.Boosts).
local CEIL_STEP = 4
local CEIL_REACH = 14
local ceilBuckets: { [number]: number } = {}
for _, list in supports do
	for _, p in list do
		local hx, _, top = footprint(p, p.cframe)
		local c = p.cframe.Position
		local extraX = if p.offset then math.abs(p.offset.X) else 0
		local extraY = if p.offset then math.max(0, p.offset.Y) else 0
		local x0 = math.floor((c.X - hx - extraX - CEIL_REACH) / CEIL_STEP)
		local x1 = math.floor((c.X + hx + extraX + CEIL_REACH) / CEIL_STEP)
		for b = x0, x1 do
			ceilBuckets[b] = math.max(ceilBuckets[b] or -math.huge, top + extraY)
		end
	end
end

Extreme.Boosts = {} :: { { x0: number, x1: number, extra: number } }
for _, p in pieces do
	if p.kind == "Bounce" or (p.kind == "Pulse" and p.effect == "Knock") then
		local c = p.cframe.Position
		local extra = if p.kind == "Bounce" then (p.power or 90) ^ 2 / (2 * 196.2) + 6 else 18
		table.insert(Extreme.Boosts, { x0 = c.X - p.size.X / 2 - 22, x1 = c.X + p.size.X / 2 + 6, extra = extra })
	end
end

-- Quota massima del HumanoidRootPart nel punto x (oltre: volo o super salto)
function Extreme.CeilingAt(x: number): number
	local top = ceilBuckets[math.floor(x / CEIL_STEP)]
	local extra = 0
	for _, b in Extreme.Boosts do
		if x >= b.x0 and x <= b.x1 then
			extra = math.max(extra, b.extra)
		end
	end
	if not top then
		return Extreme.WallTop
	end
	return top + Extreme.BodyDown + 10 + extra
end

-- Elementi a impulsi mortali (laser, fiamme, presse): il server li controlla da solo
local killPulses: { [number]: { Piece } } = {}
for _, p in pieces do
	if p.kind == "Pulse" and p.effect == "Kill" then
		killPulses[p.section] = killPulses[p.section] or {}
		table.insert(killPulses[p.section], p)
	end
end

local function pulseOn(p: Piece, t: number): boolean
	return Extreme.PulsePhase(p, t) == "active"
end

-- Elemento mortale che sta colpendo da almeno mezzo secondo il corpo in pos (HumanoidRootPart).
-- Il margine evita falsi positivi dovuti al ritardo di rete: chi passa al pelo non viene punito.
function Extreme.PulseKillAt(pos: Vector3, t: number): Piece?
	local s = Extreme.SectionAt(pos.X)
	local list = killPulses[s]
	if not list then
		return nil
	end
	for _, p in list do
		if pulseOn(p, t) and pulseOn(p, t - 0.25) and pulseOn(p, t - 0.5) then
			local cf, size = Extreme.PulseBox(p)
			local rel = cf:PointToObjectSpace(pos)
			local h = size / 2
			local feet = rel.Y - Extreme.BodyDown + 0.4
			local head = rel.Y + 1.6
			if math.abs(rel.X) <= h.X + 0.2 and math.abs(rel.Z) <= h.Z + 0.2 and feet < h.Y and head > -h.Y then
				return p
			end
		end
	end
	return nil
end

return Extreme
