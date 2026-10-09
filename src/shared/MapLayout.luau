--!strict
-- Geometria della montagna, condivisa da server e client.
-- La vetta (con gli 8 lotti) e' al centro; il sentiero scende a tornanti sul versante +Z
-- attraversando 5 zone fino al cratere vulcanico. Tutte le misure sono in stud.

local MapLayout = {}

---------------------------------------------------------------------------------------------
-- Vetta
---------------------------------------------------------------------------------------------
MapLayout.SummitCenter = Vector3.new(0, 330, 0)
MapLayout.SummitY = 330
MapLayout.PlateauRadius = 178
MapLayout.PlazaRadius = 92 -- piazza centrale libera
MapLayout.PlotRadius = 130 -- distanza dal centro al centro di ogni lotto
MapLayout.PlotSize = Vector3.new(60, 0, 66) -- larghezza (tangenziale) x profondita' (radiale)
MapLayout.PlotCount = 8

-- Lotto i (1..8): il fronte (LookVector, asse -Z locale) guarda verso il centro della piazza.
-- Il settore 0 (verso +Z) resta libero per l'inizio del sentiero.
function MapLayout.PlotFrame(i: number): CFrame
	local angle = math.rad(40 * i)
	local dir = Vector3.new(math.sin(angle), 0, math.cos(angle))
	local center = MapLayout.SummitCenter + dir * MapLayout.PlotRadius
	-- con Angles(0, a, 0) il LookVector vale (-sin a, 0, -cos a) = -dir: verso il centro
	return CFrame.new(center) * CFrame.Angles(0, angle, 0)
end

-- Layout interno di un lotto (coordinate locali: -Z verso il cancello/fronte, Y=0 al pavimento)
MapLayout.Plot = {
	FloorHeight = 1.2,
	WallHeight = 12,
	GateWidth = 18,
	SpawnOffset = Vector3.new(0, 3, -20),
	-- 9 incubatrici in una griglia 3x3 nella parte anteriore sinistra
	Incubators = (function()
		local list = {}
		for row = 0, 2 do
			for col = 0, 2 do
				table.insert(list, Vector3.new(-24 + col * 7, 0, -26 + row * 7.5))
			end
		end
		return list
	end)(),
	-- 20 piedistalli 5x4 nella parte posteriore (in ordine di sblocco: dalla prima fila). Il posto
	-- centrale dell'ultima fila e' dell'altare del trono Ultra: quel piedistallo sta davanti a destra.
	Pedestals = (function()
		local list = {}
		for row = 0, 3 do
			for col = 0, 4 do
				if row == 3 and col == 2 then
					table.insert(list, Vector3.new(12, 0, -14))
				else
					table.insert(list, Vector3.new(-22 + col * 11, 0, -4 + row * 10))
				end
			end
		end
		return list
	end)(),
	-- Trono dei pet Ultra (giganti): torre dietro il muro di fondo con il pet in cima; l'altare con
	-- vendita/furto e la pedana di raccolta sono dentro il lotto, protetti dalla barriera
	Throne = {
		Altar = Vector3.new(0, 0, 26),
		Tower = Vector3.new(0, 0, 45),
		TowerRadius = 10,
		TowerTop = 14, -- quota della piattaforma sopra il pavimento del lotto
	},
	CollectPadOffset = Vector3.new(0, 0, -4.6), -- pedana di raccolta davanti a ogni piedistallo
	BarrierConsole = Vector3.new(20, 0, -25),
	Traps = { Vector3.new(-5, 0, -29), Vector3.new(5, 0, -29), Vector3.new(0, 0, -23) },
	Sign = Vector3.new(0, 17, -33),
}

---------------------------------------------------------------------------------------------
-- Sentiero a tornanti
---------------------------------------------------------------------------------------------
MapLayout.PathWidth = 44
MapLayout.LegX = 130 -- i tornanti sono a x = +-130
MapLayout.LegSpacing = 72
MapLayout.HairpinRadius = 36

export type Segment = {
	kind: "line" | "arc",
	zone: string,
	a: Vector3?, -- inizio (line)
	b: Vector3?, -- fine (line)
	center: Vector3?, -- centro (arc, y = quota iniziale)
	radius: number?,
	startAngle: number?,
	sweep: number?, -- radianti, segno = verso
	y0: number?,
	y1: number?,
	length: number,
	leg: number?,
}

local segments: { Segment } = {}

local function addLine(a: Vector3, b: Vector3, zone: string, leg: number?)
	table.insert(segments, { kind = "line", zone = zone, a = a, b = b, length = (b - a).Magnitude, leg = leg })
end

-- arco orizzontale attorno a center (piano XZ), angoli misurati da +X verso +Z
local function addArc(
	center: Vector3,
	radius: number,
	startAngle: number,
	sweep: number,
	y0: number,
	y1: number,
	zone: string
)
	local horiz = math.abs(sweep) * radius
	table.insert(segments, {
		kind = "arc",
		zone = zone,
		center = center,
		radius = radius,
		startAngle = startAngle,
		sweep = sweep,
		y0 = y0,
		y1 = y1,
		length = math.sqrt(horiz * horiz + (y1 - y0) ^ 2),
	})
end

-- Quote dei tratti (inizio -> fine) e zone
local LEGS = {
	{ z = 220, x0 = 0, x1 = 130, y0 = 318, y1 = 300, zone = "Meadow" },
	{ z = 292, x0 = 130, x1 = -130, y0 = 290, y1 = 252, zone = "Forest" },
	{ z = 364, x0 = -130, x1 = 130, y0 = 242, y1 = 204, zone = "Canyon" },
	{ z = 436, x0 = 130, x1 = -130, y0 = 194, y1 = 156, zone = "Crystal" },
	{ z = 508, x0 = -130, x1 = 40, y0 = 146, y1 = 124, zone = "Crater" },
}
MapLayout.Legs = LEGS

-- Rampa dalla piazza al primo tratto
addLine(Vector3.new(0, 330, 150), Vector3.new(0, 318, 220), "Meadow")
for i, leg in LEGS do
	addLine(Vector3.new(leg.x0, leg.y0, leg.z), Vector3.new(leg.x1, leg.y1, leg.z), leg.zone, i)
	local nextLeg = LEGS[i + 1]
	if nextLeg then
		-- tornante: semicerchio che porta dal tratto i al tratto i+1 (stesso lato x)
		local side = if leg.x1 > 0 then 1 else -1
		local cz = (leg.z + nextLeg.z) / 2
		local center = Vector3.new(leg.x1, 0, cz)
		-- parte dall'angolo -90 (verso -Z): a est gira passando da 0 (+X), a ovest passando da 180 (-X)
		local sweep = if side > 0 then math.pi else -math.pi
		addArc(center, MapLayout.HairpinRadius, -math.pi / 2, sweep, leg.y1, nextLeg.y0, leg.zone)
	end
end
-- Discesa nel cratere: termina alla quota del fondo, cosi' si puo' sempre risalire
addLine(Vector3.new(40, 124, 508), Vector3.new(70, 96, 560), "Crater")

MapLayout.Segments = segments

local totalLength = 0
for _, s in segments do
	totalLength += s.length
end
MapLayout.PathLength = totalLength

-- Punto sul sentiero alla distanza s (stud) dalla piazza: posizione, direzione (verso valle), zona
function MapLayout.PathPoint(s: number): (Vector3, Vector3, string)
	s = math.clamp(s, 0, totalLength)
	for _, seg in segments do
		if s <= seg.length or seg == segments[#segments] then
			local t = math.clamp(s / seg.length, 0, 1)
			if seg.kind == "line" then
				local a, b = seg.a :: Vector3, seg.b :: Vector3
				return a:Lerp(b, t), (b - a).Unit, seg.zone
			else
				local ang = (seg.startAngle :: number) + (seg.sweep :: number) * t
				local c = seg.center :: Vector3
				local r = seg.radius :: number
				local p = Vector3.new(
					c.X + math.cos(ang) * r,
					(seg.y0 :: number) + ((seg.y1 :: number) - (seg.y0 :: number)) * t,
					c.Z + math.sin(ang) * r
				)
				local sign = if (seg.sweep :: number) > 0 then 1 else -1
				local tan = Vector3.new(-math.sin(ang) * sign, 0, math.cos(ang) * sign)
				local dy = ((seg.y1 :: number) - (seg.y0 :: number)) / seg.length
				return p, (tan + Vector3.new(0, dy, 0)).Unit, seg.zone
			end
		end
		s -= seg.length
	end
	return MapLayout.SummitCenter, Vector3.zAxis, "Meadow"
end

-- Campiona il sentiero ogni 'step' stud
function MapLayout.SamplePath(step: number): { { pos: Vector3, dir: Vector3, zone: string, s: number } }
	local out = {}
	local s = 0
	while s <= totalLength do
		local p, d, z = MapLayout.PathPoint(s)
		table.insert(out, { pos = p, dir = d, zone = z, s = s })
		s += step
	end
	return out
end

-- Quota del tratto i in funzione di x
local function legHeight(leg: { x0: number, x1: number, y0: number, y1: number }, x: number): number
	local t = (x - leg.x0) / (leg.x1 - leg.x0)
	return leg.y0 + (leg.y1 - leg.y0) * math.clamp(t, 0, 1)
end
MapLayout.LegHeight = legHeight

---------------------------------------------------------------------------------------------
-- Cratere vulcanico (in fondo)
---------------------------------------------------------------------------------------------
MapLayout.Crater = {
	Center = Vector3.new(70, 96, 620),
	Radius = 92, -- fondo piatto percorribile
	RimRadius = 128,
	RimHeight = 132,
	LavaPools = {
		{ center = Vector3.new(30, 96, 650), radius = 14 },
		{ center = Vector3.new(118, 96, 600), radius = 11 },
	},
	VolcanoCone = Vector3.new(70, 96, 700), -- cono fumante sul lato sud del cratere
}

---------------------------------------------------------------------------------------------
-- Zona in cui si trova una posizione
---------------------------------------------------------------------------------------------
function MapLayout.ZoneAt(pos: Vector3): string
	local flat = Vector3.new(pos.X, 0, pos.Z)
	local summitFlat = Vector3.new(MapLayout.SummitCenter.X, 0, MapLayout.SummitCenter.Z)
	if (flat - summitFlat).Magnitude < MapLayout.PlateauRadius - 4 and pos.Y > 322 then
		return "Summit"
	end
	if pos.Z > 548 then
		return "Crater"
	end
	-- la zona dipende dalla quota (i tornanti si scendono in ordine)
	if pos.Y > 288 then
		return "Meadow"
	elseif pos.Y > 241 then
		return "Forest"
	elseif pos.Y > 193 then
		return "Canyon"
	elseif pos.Y > 145 then
		return "Crystal"
	end
	return "Crater"
end

---------------------------------------------------------------------------------------------
-- Oggetti lungo il sentiero (deterministici): rifugi, nidi, scorciatoie
---------------------------------------------------------------------------------------------
export type Placement = { cframe: CFrame, zone: string, s: number }

-- Punto sul bordo del sentiero alla distanza s: side = +1 lato a monte, -1 lato a valle
function MapLayout.EdgeFrame(s: number, side: number, inset: number): CFrame
	local p, dir, _ = MapLayout.PathPoint(s)
	local flatDir = Vector3.new(dir.X, 0, dir.Z).Unit
	local right = flatDir:Cross(Vector3.yAxis) -- a destra rispetto alla direzione di discesa
	-- lato a monte: verso -Z sui tratti, verso il centro nei tornanti
	local toUphill = if right.Z < 0 then right else -right
	if math.abs(p.X) > MapLayout.LegX - 2 then
		local inward = Vector3.new(-math.sign(p.X), 0, 0)
		toUphill = if right:Dot(inward) > 0 then right else -right
	end
	local offset = toUphill * side * (MapLayout.PathWidth / 2 - inset)
	local pos = p + offset
	return CFrame.lookAt(pos, pos - toUphill * side) -- guarda verso il centro del sentiero
end

-- Rifugi anti-valanga: due per tratto (uno solo sul primo, corto), sul lato a monte
MapLayout.Shelters = (function()
	local out = {}
	local acc = 0
	for _, seg in segments do
		if seg.kind == "line" and seg.leg then
			local fractions = if seg.leg == 1 then { 0.7 } else { 0.28, 0.74 }
			for _, f in fractions do
				table.insert(out, { s = acc + seg.length * f, zone = seg.zone })
			end
		end
		acc += seg.length
	end
	return out
end)()

MapLayout.ShelterSize = Vector3.new(16, 11, 12) -- interno: larghezza lungo il sentiero, altezza, profondita'

function MapLayout.ShelterFrame(i: number): CFrame
	local sh = MapLayout.Shelters[i]
	-- la capanna e' addossata al lato a monte, con l'apertura verso il sentiero
	return MapLayout.EdgeFrame(sh.s, 1, MapLayout.ShelterSize.Z / 2)
end

-- Vero se la posizione e' dentro un rifugio (o in vetta/cratere, dove la valanga non arriva)
function MapLayout.IsSheltered(pos: Vector3): boolean
	local zone = MapLayout.ZoneAt(pos)
	if zone == "Summit" then
		return true
	end
	if pos.Z > 545 then
		return true -- il cratere e' riparato dal suo bordo
	end
	for i = 1, #MapLayout.Shelters do
		local cf = MapLayout.ShelterFrame(i)
		local lp = cf:PointToObjectSpace(pos)
		local size = MapLayout.ShelterSize
		if
			math.abs(lp.X) <= size.X / 2 + 1
			and lp.Y >= -2
			and lp.Y <= size.Y + 2
			and math.abs(lp.Z) <= size.Z / 2 + 1.5
		then
			return true
		end
	end
	return false
end

-- Nidi: distribuiti lungo il sentiero, alternando i lati, evitando i rifugi
MapLayout.NestsPerZone = { Meadow = 10, Forest = 10, Canyon = 9, Crystal = 9, Crater = 6 }

MapLayout.Nests = (function()
	local out = {}
	local rng = Random.new(20261008)
	-- intervalli di s per zona
	local ranges: { [string]: { number } } = {}
	local acc = 0
	for _, seg in segments do
		local r = ranges[seg.zone]
		if not r then
			ranges[seg.zone] = { acc, acc + seg.length }
		else
			r[2] = acc + seg.length
		end
		acc += seg.length
	end
	for zone, count in MapLayout.NestsPerZone do
		local r = ranges[zone]
		local s0 = r[1] + (if zone == "Meadow" then 90 else 15)
		local s1 = r[2] - 15
		if zone == "Crater" then
			s1 = r[2] - 70
		end
		for k = 1, count do
			local s = s0 + (s1 - s0) * (k - 0.5) / count + rng:NextNumber(-8, 8)
			-- evita i rifugi
			for _, sh in MapLayout.Shelters do
				if math.abs(sh.s - s) < 14 then
					s += 16
				end
			end
			local side = if k % 2 == 0 then 1 else -1
			local cf = MapLayout.EdgeFrame(s, side, 5 + rng:NextNumber(0, 3))
			table.insert(out, { id = `{zone}{k}`, zone = zone, s = s, cframe = cf })
		end
	end
	-- nidi del cratere sul fondo (attorno al centro)
	local cc = MapLayout.Crater.Center
	for k = 1, 6 do
		local a = (k / 6) * math.pi * 2 + 0.3
		local p = cc + Vector3.new(math.cos(a) * 52, 0, math.sin(a) * 52)
		table.insert(out, { id = `CraterFloor{k}`, zone = "Crater", s = totalLength, cframe = CFrame.lookAt(p, cc) })
	end
	return out
end)()

-- Tane delle guardiane (nidi preziosi sorvegliati)
MapLayout.Lairs = {
	{
		id = "Crystal",
		zone = "Crystal",
		guardian = "CrystalMother",
		center = Vector3.new(-40, 0, 436), -- y calcolata dal sentiero
		radius = 26,
		leash = 70,
		nests = 3,
		eggs = { Epic = 30, Legendary = 50, Mythic = 18, Divine = 2 },
	},
	{
		id = "Crater",
		zone = "Crater",
		guardian = "DragonMother",
		center = Vector3.new(70, 96, 640),
		radius = 24,
		leash = 80,
		nests = 3,
		eggs = { Legendary = 45, Mythic = 40, Divine = 13, Secret = 2 },
	},
} :: { any }
do
	local lair = MapLayout.Lairs[1]
	local leg = LEGS[4]
	lair.center = Vector3.new(lair.center.X, legHeight(leg, lair.center.X) + 1, leg.z)
end

-- Scorciatoie rischiose: arrampicate che collegano un tratto al tratto superiore (salto della curva)
MapLayout.Shortcuts = {
	-- da tratto 2 (basso) a tratto 1 (alto) vicino a x = 60: scaletta di sporgenze che si sgretolano
	{ id = "ForestClimb", fromLeg = 2, toLeg = 1, x = 60, kind = "Ledges" },
	{ id = "CanyonBridge", fromLeg = 3, toLeg = 2, x = -60, kind = "Ledges" },
	{ id = "CrystalVines", fromLeg = 4, toLeg = 3, x = 40, kind = "Ledges" },
	{ id = "CraterSteps", fromLeg = 5, toLeg = 4, x = -40, kind = "Ledges" },
}

---------------------------------------------------------------------------------------------
-- Spawn e caduta nel vuoto
---------------------------------------------------------------------------------------------
MapLayout.VoidY = 40 -- sotto questa quota si torna in vetta (il mare di nuvole e' a ~70)
MapLayout.CloudSeaY = 70

return MapLayout
