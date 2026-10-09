--!strict
-- Ostacoli deterministici: la posizione/stato di ognuno e' una funzione del tempo del server
-- (workspace:GetServerTimeNow()). Il client li disegna e controlla i propri contatti;
-- il server usa le stesse funzioni per convalidare i colpi segnalati.

local MapLayout = require(script.Parent.MapLayout)

local Obstacles = {}

export type Roller = {
	id: string,
	kind: "Snowball" | "Log" | "Boulder",
	zone: string,
	s0: number, -- inizio della corsia (in alto)
	s1: number, -- fine della corsia (in basso)
	speed: number,
	period: number, -- secondi fra un rotolante e il successivo
	radius: number,
	lanes: { number }, -- spostamenti laterali (stud) usati a rotazione
	length: number?, -- per i tronchi
}

export type Pendulum = {
	id: string,
	zone: string,
	pivot: CFrame, -- perno (orientato con X attraverso il sentiero, Z lungo il sentiero)
	length: number, -- lunghezza delle corde
	logLength: number,
	radius: number,
	period: number,
	amplitude: number, -- radianti
	phase: number,
}

export type Goat = {
	id: string,
	zone: string,
	center: CFrame, -- X attraverso il sentiero
	halfWidth: number,
	period: number,
	phase: number,
}

export type Pulse = {
	id: string,
	kind: "Geyser" | "FireGeyser" | "Lava",
	zone: string,
	cframe: CFrame,
	size: Vector3, -- area d'effetto (box locale)
	period: number,
	warn: number, -- durata dell'avviso prima dell'attivazione
	active: number, -- durata della fase attiva
	phase: number,
}

export type Wind = {
	id: string,
	zone: string,
	center: Vector3,
	radius: number,
	direction: Vector3,
	strength: number,
	period: number,
	active: number,
}

-- Intervallo di s di un tratto (i = indice del tratto)
local function legRange(i: number): (number, number)
	local acc = 0
	for _, seg in MapLayout.Segments do
		if seg.kind == "line" and seg.leg == i then
			return acc, acc + seg.length
		end
		acc += seg.length
	end
	return 0, 0
end
Obstacles.LegRange = legRange

local function frameAt(s: number, lateral: number): CFrame
	local p, dir = MapLayout.PathPoint(s)
	local flat = Vector3.new(dir.X, 0, dir.Z).Unit
	local right = flat:Cross(Vector3.yAxis)
	local pos = p + right * lateral
	-- X locale = attraverso il sentiero, Z locale = lungo il sentiero (verso valle = -Z)
	return CFrame.fromMatrix(pos, right, Vector3.yAxis)
end
Obstacles.FrameAt = frameAt

local function lerp(a: number, b: number, t: number): number
	return a + (b - a) * t
end

---------------------------------------------------------------------------------------------
-- Definizioni
---------------------------------------------------------------------------------------------
Obstacles.Rollers = {} :: { Roller }
Obstacles.Pendulums = {} :: { Pendulum }
Obstacles.Goats = {} :: { Goat }
Obstacles.Pulses = {} :: { Pulse }
Obstacles.Winds = {} :: { Wind }

do
	local s0, s1 = legRange(1)
	table.insert(Obstacles.Rollers, {
		id = "Snow1",
		kind = "Snowball",
		zone = "Meadow",
		s0 = s0 + 4,
		s1 = s1 + 60,
		speed = 22,
		period = 4.2,
		radius = 3,
		lanes = { -12, 4, -4, 13, -15, 9 },
	})
	local a, b = legRange(2)
	table.insert(Obstacles.Rollers, {
		id = "Log2",
		kind = "Log",
		zone = "Forest",
		s0 = a + 4,
		s1 = b - 6,
		speed = 20,
		period = 6.5,
		radius = 2.2,
		length = 16,
		lanes = { -10, 8, 0, -12, 11 },
	})
	local c, d = legRange(3)
	table.insert(Obstacles.Rollers, {
		id = "Rock3",
		kind = "Boulder",
		zone = "Canyon",
		s0 = c + 4,
		s1 = d - 4,
		speed = 27,
		period = 3.4,
		radius = 4.2,
		lanes = { -11, 6, -2, 13, -14, 10, 0 },
	})
	local e, f = legRange(5)
	table.insert(Obstacles.Rollers, {
		id = "Rock5",
		kind = "Boulder",
		zone = "Crater",
		s0 = e + 4,
		s1 = f - 4,
		speed = 30,
		period = 4.6,
		radius = 3.8,
		lanes = { 8, -10, 2, 13, -5 },
	})

	-- tronchi oscillanti nel bosco (attraverso il sentiero)
	for k, frac in { 0.22, 0.5, 0.78 } do
		local s = lerp(a, b, frac)
		local base = frameAt(s, 0)
		table.insert(Obstacles.Pendulums, {
			id = `Swing{k}`,
			zone = "Forest",
			pivot = base * CFrame.new(0, 19, 0),
			length = 15,
			logLength = 34,
			radius = 2,
			period = 3.2 + k * 0.35,
			amplitude = math.rad(58),
			phase = k * 1.3,
		})
	end

	-- capre che vanno avanti e indietro (e caricano) sul primo tratto e nel tornante
	for k, frac in { 0.45, 0.85 } do
		local s = lerp(s0, s1, frac)
		table.insert(Obstacles.Goats, {
			id = `Goat{k}`,
			zone = "Meadow",
			center = frameAt(s, 0),
			halfWidth = 17,
			period = 5.5 + k,
			phase = k * 2.1,
		})
	end

	-- geyser nelle grotte di cristallo
	local g0, g1 = legRange(4)
	local lateral = { -10, 9, -2, 12, -13, 4 }
	for k = 1, 6 do
		local s = lerp(g0, g1, 0.1 + 0.8 * (k - 1) / 5)
		table.insert(Obstacles.Pulses, {
			id = `Geyser{k}`,
			kind = "Geyser",
			zone = "Crystal",
			cframe = frameAt(s, lateral[k]),
			size = Vector3.new(7, 22, 7),
			period = 6,
			warn = 1.2,
			active = 1.3,
			phase = k * 0.9,
		})
	end

	-- colate di lava che attraversano l'ultimo tratto
	for k, frac in { 0.3, 0.58, 0.84 } do
		local s = lerp(e, f, frac)
		table.insert(Obstacles.Pulses, {
			id = `Lava{k}`,
			kind = "Lava",
			zone = "Crater",
			cframe = frameAt(s, 0),
			size = Vector3.new(MapLayout.PathWidth + 2, 3, 7),
			period = 8,
			warn = 1.6,
			active = 2.2,
			phase = k * 2.6,
		})
	end

	-- geyser di fuoco sul fondo del cratere
	local cc = MapLayout.Crater.Center
	for k = 1, 5 do
		local ang = k / 5 * math.pi * 2 + 0.6
		local pos = cc + Vector3.new(math.cos(ang) * 30, 0, math.sin(ang) * 30)
		table.insert(Obstacles.Pulses, {
			id = `FireGeyser{k}`,
			kind = "FireGeyser",
			zone = "Crater",
			cframe = CFrame.new(pos),
			size = Vector3.new(8, 24, 8),
			period = 7,
			warn = 1.3,
			active = 1.6,
			phase = k * 1.4,
		})
	end

	-- raffiche di vento nel tornante del canyon (spingono verso l'esterno)
	local leg3 = MapLayout.Legs[3]
	local leg4 = MapLayout.Legs[4]
	table.insert(Obstacles.Winds, {
		id = "Wind1",
		zone = "Canyon",
		center = Vector3.new(leg3.x1, (leg3.y1 + leg4.y0) / 2, (leg3.z + leg4.z) / 2),
		radius = 64,
		direction = Vector3.new(1, 0, 0),
		strength = 34,
		period = 7,
		active = 2.4,
	})
end

---------------------------------------------------------------------------------------------
-- Movimento
---------------------------------------------------------------------------------------------

-- Rotolanti attivi al tempo t: lista di { index, cframe } (cframe gia' ruotato per il rotolamento)
function Obstacles.RollerStates(r: Roller, t: number): { { index: number, cframe: CFrame, s: number } }
	local out = {}
	local travel = (r.s1 - r.s0) / r.speed -- secondi per percorrere la corsia
	local first = math.floor((t - travel) / r.period)
	local last = math.floor(t / r.period)
	for k = first, last do
		local born = k * r.period
		local age = t - born
		if age >= 0 and age <= travel then
			local s = r.s0 + age * r.speed
			local lane = r.lanes[(k % #r.lanes) + 1]
			local base = frameAt(s, lane)
			local spin = (age * r.speed) / r.radius
			local cf = base * CFrame.new(0, r.radius, 0)
			if r.kind == "Log" then
				cf = cf * CFrame.Angles(-spin, 0, 0)
			else
				cf = cf * CFrame.Angles(-spin, 0, 0)
			end
			table.insert(out, { index = k, cframe = cf, s = s })
		end
	end
	return out
end

-- CFrame del tronco oscillante (centro del tronco) al tempo t
function Obstacles.PendulumCFrame(p: Pendulum, t: number): CFrame
	local angle = p.amplitude * math.sin(t * 2 * math.pi / p.period + p.phase)
	return p.pivot * CFrame.Angles(angle, 0, 0) * CFrame.new(0, -p.length, 0)
end

-- Capra: posizione attraverso il sentiero e se sta caricando (fase veloce)
function Obstacles.GoatCFrame(g: Goat, t: number): (CFrame, boolean)
	local u = ((t + g.phase) % g.period) / g.period
	-- 0-0.55 cammina lenta verso destra, 0.55-0.7 pausa, 0.7-0.85 carica verso sinistra, poi pausa
	local x, facing, charging
	if u < 0.55 then
		x = lerp(-g.halfWidth, g.halfWidth, u / 0.55)
		facing = 1
		charging = false
	elseif u < 0.7 then
		x = g.halfWidth
		facing = -1
		charging = false
	elseif u < 0.85 then
		x = lerp(g.halfWidth, -g.halfWidth, (u - 0.7) / 0.15)
		facing = -1
		charging = true
	else
		x = -g.halfWidth
		facing = 1
		charging = false
	end
	local cf = g.center * CFrame.new(x, 0, 0) * CFrame.Angles(0, if facing > 0 then -math.pi / 2 else math.pi / 2, 0)
	return cf, charging
end

-- Stato di un impulso: "Idle", "Warn" o "Active"
function Obstacles.PulseState(p: Pulse, t: number): string
	local u = (t + p.phase) % p.period
	local idle = p.period - p.warn - p.active
	if u < idle then
		return "Idle"
	elseif u < idle + p.warn then
		return "Warn"
	end
	return "Active"
end

function Obstacles.WindActive(w: Wind, t: number): boolean
	return (t % w.period) < w.active
end

-- Vero se la posizione e' dentro l'area (box) di un impulso
function Obstacles.InPulse(p: Pulse, pos: Vector3): boolean
	local lp = p.cframe:PointToObjectSpace(pos)
	return math.abs(lp.X) <= p.size.X / 2 and math.abs(lp.Z) <= p.size.Z / 2 and lp.Y >= -2 and lp.Y <= p.size.Y
end

function Obstacles.ById(id: string): any
	for _, list in
		{ Obstacles.Rollers, Obstacles.Pendulums, Obstacles.Goats, Obstacles.Pulses, Obstacles.Winds } :: { any }
	do
		for _, o in list :: { any } do
			if o.id == id then
				return o
			end
		end
	end
	return nil
end

return Obstacles
