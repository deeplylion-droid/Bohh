-- Elementi fissi della mappa: piazza della vetta, rifugi anti-valanga, mare di nuvole, decorazioni.

local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Assets = require(ReplicatedStorage.Shared.Assets)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)
local Visuals = require(ReplicatedStorage.Shared.Visuals)
local Build = require(script.Parent.Build)
local ExtremeBuild = require(script.Parent.ExtremeBuild)

local Scenery = {}

local WOOD = Color3.fromRGB(168, 112, 64)
local WOOD_DARK = Color3.fromRGB(122, 78, 44)
local ROOF = Color3.fromRGB(226, 72, 54)

---------------------------------------------------------------------------------------------
-- Piazza della vetta
---------------------------------------------------------------------------------------------
-- Colori: lastre chiare e pulite con accenti accesi, come l'interfaccia "Vetta Pop"
local PZ = {
	paving = Color3.fromRGB(246, 238, 222), -- lastre della piazza e del viale
	inner = Color3.fromRGB(240, 226, 202), -- disco centrale attorno al monumento
	stone = Color3.fromRGB(250, 246, 238), -- monumento, bordi delle aiuole, vasche
	stoneShade = Color3.fromRGB(230, 220, 202),
	white = Color3.fromRGB(255, 255, 255),
	gold = Color3.fromRGB(255, 198, 46),
	goldDark = Color3.fromRGB(240, 146, 30),
	sky = Color3.fromRGB(96, 194, 255),
	skyDark = Color3.fromRGB(40, 136, 226),
	skyPale = Color3.fromRGB(190, 230, 252),
	royal = Color3.fromRGB(48, 86, 186),
	silver = Color3.fromRGB(212, 222, 240),
	coral = Color3.fromRGB(244, 100, 84),
	velvet = Color3.fromRGB(206, 38, 72),
	leaf = Color3.fromRGB(96, 196, 84),
	water = Color3.fromRGB(110, 206, 255),
	pool = Color3.fromRGB(40, 150, 226),
	ink = Color3.fromRGB(40, 30, 72),
}
-- vialetti verso i cancelli: le tinte dei lotti (i temi di PlotService), un po' piu' accese
local PLOT_TINTS = {
	Color3.fromRGB(240, 94, 94),
	Color3.fromRGB(250, 150, 62),
	Color3.fromRGB(250, 204, 70),
	Color3.fromRGB(104, 200, 98),
	Color3.fromRGB(60, 192, 204),
	Color3.fromRGB(86, 134, 236),
	Color3.fromRGB(160, 108, 232),
	Color3.fromRGB(238, 112, 184),
}
-- stendardi e bandierine
local FESTIVE = { PZ.coral, PZ.gold, PZ.sky, Color3.fromRGB(72, 206, 150), Color3.fromRGB(160, 108, 236) }
local GEMS = {
	Color3.fromRGB(236, 52, 76),
	Color3.fromRGB(60, 144, 255),
	Color3.fromRGB(64, 204, 112),
	Color3.fromRGB(172, 92, 244),
}

-- Direzione orizzontale a 'deg' gradi da +Z verso +X (come gli angoli dei lotti)
local function dirAt(deg: number): Vector3
	local a = math.rad(deg)
	return Vector3.new(math.sin(a), 0, math.cos(a))
end

-- Cilindro con l'asse verticale fra due quote (dischi stesi a terra, pali, vasche)
type Cyl = {
	name: string,
	at: Vector3, -- centro (contano solo x e z)
	radius: number,
	bottom: number,
	top: number,
	color: Color3,
	material: Enum.Material?,
	collide: boolean?,
	castShadow: boolean?,
	transparency: number?,
	parent: Instance,
}
local function vcyl(p: Cyl): BasePart
	return Build.Part({
		name = p.name,
		size = Vector3.new(p.top - p.bottom, p.radius * 2, p.radius * 2),
		cframe = CFrame.new(p.at.X, (p.top + p.bottom) / 2, p.at.Z) * CFrame.Angles(0, 0, math.rad(90)),
		color = p.color,
		material = p.material,
		shape = Enum.PartType.Cylinder,
		collide = p.collide,
		castShadow = p.castShadow,
		transparency = p.transparency,
		parent = p.parent,
	})
end

-- Intarsio rotondo nel pavimento: non si tocca, non ferma i raggi e non fa ombra. La faccia di sopra
-- sta a quota 'top' (qualche centesimo sopra le lastre, mai alla stessa quota: niente sfarfallio), il
-- resto e' affondato nelle lastre
local function inlayDisc(
	parent: Instance,
	name: string,
	at: Vector3,
	radius: number,
	top: number,
	color: Color3,
	material: Enum.Material?
): BasePart
	return vcyl({
		name = name,
		at = at,
		radius = radius,
		bottom = top - 0.3,
		top = top,
		color = color,
		material = material,
		collide = false,
		castShadow = false,
		parent = parent,
	})
end

-- Striscia dritta nel pavimento (intarsio come sopra) lungo la direzione orizzontale d, da 'from' a
-- 'to' stud dal punto o, larga 'width'
local function inlayStrip(
	parent: Instance,
	name: string,
	o: Vector3,
	d: Vector3,
	from: number,
	to: number,
	width: number,
	top: number,
	color: Color3
): BasePart
	local mid = o + d * ((from + to) / 2)
	local pos = Vector3.new(mid.X, top - 0.15, mid.Z)
	return Build.Part({
		name = name,
		size = Vector3.new(width, 0.3, to - from),
		cframe = CFrame.lookAt(pos, pos + d),
		color = color,
		collide = false,
		castShadow = false,
		parent = parent,
	})
end

-- Triangolo (WedgePart) con l'angolo retto in p e gli altri due vertici in a e b (a - p e b - p
-- perpendicolari), spesso 'depth' attorno al piano dei tre punti
local function triangle(
	parent: Instance,
	name: string,
	p: Vector3,
	a: Vector3,
	b: Vector3,
	depth: number,
	color: Color3,
	material: Enum.Material?,
	collide: boolean?
): BasePart
	local d1, d2 = a - p, b - p
	return Build.Part({
		name = name,
		class = "WedgePart",
		size = Vector3.new(depth, d2.Magnitude, d1.Magnitude),
		cframe = CFrame.fromMatrix(p + d1 / 2 + d2 / 2, d2.Unit:Cross(-d1.Unit), d2.Unit),
		color = color,
		material = material,
		collide = collide == true,
		castShadow = collide == true,
		parent = parent,
	})
end

-- Triangolo isoscele (due triangoli rettangoli, uno per meta' con il suo colore): base da b1 a b2,
-- punta in tip
local function spike(
	parent: Instance,
	name: string,
	b1: Vector3,
	b2: Vector3,
	tip: Vector3,
	depth: number,
	colorA: Color3,
	colorB: Color3,
	material: Enum.Material?,
	collide: boolean?
)
	local m = (b1 + b2) / 2
	triangle(parent, name, m, tip, b1, depth, colorA, material, collide)
	triangle(parent, name, m, tip, b2, depth, colorB, material, collide)
end

-- Muretto dritto fra due punti (contano solo x e z), dalla quota bottom alla quota top
local function wallBetween(
	parent: Instance,
	name: string,
	a: Vector3,
	b: Vector3,
	thick: number,
	bottom: number,
	top: number,
	color: Color3,
	material: Enum.Material?
): BasePart
	local flat = Vector3.new(b.X - a.X, 0, b.Z - a.Z)
	local mid = Vector3.new((a.X + b.X) / 2, (bottom + top) / 2, (a.Z + b.Z) / 2)
	return Build.Part({
		name = name,
		size = Vector3.new(thick, top - bottom, flat.Magnitude),
		cframe = CFrame.lookAt(mid, mid + flat),
		color = color,
		material = material,
		parent = parent,
	})
end

-- Sfera decorativa (non si tocca)
local function ball(
	parent: Instance,
	name: string,
	at: Vector3,
	diameter: number,
	color: Color3,
	material: Enum.Material?
)
	return Build.Part({
		name = name,
		size = Vector3.one * diameter,
		cframe = CFrame.new(at),
		color = color,
		material = material,
		shape = Enum.PartType.Ball,
		collide = false,
		parent = parent,
	})
end

-- Uovo (sfera allungata con una SpecialMesh) appoggiato con la punta in basso nel punto 'at'
local function eggShape(parent: Instance, name: string, at: Vector3, width: number, height: number, color: Color3)
	local part = Build.Part({
		name = name,
		size = Vector3.new(width, height, width),
		cframe = CFrame.new(at + Vector3.new(0, height / 2, 0)),
		color = color,
		material = Enum.Material.Foil,
		collide = false,
		parent = parent,
	})
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Parent = part
	return part
end

-- Stendardo appeso a un braccio orizzontale: rettangolo di stoffa con la punta in basso. 'top' e' il
-- punto del braccio sopra il centro dello stendardo, 'along' la direzione del braccio (orizzontale)
local function banner(parent: Instance, top: Vector3, along: Vector3, width: number, height: number, color: Color3)
	local frame = CFrame.fromMatrix(top, along, Vector3.yAxis)
	-- il bordo di sopra sta dentro il braccio, come una stoffa infilata nell'asta
	Build.Part({
		name = "Banner",
		size = Vector3.new(width, height, 0.16),
		cframe = frame * CFrame.new(0, -height / 2, 0),
		color = color,
		material = Enum.Material.Fabric,
		collide = false,
		parent = parent,
	})
	local m = frame.Position - Vector3.yAxis * height
	local tip = m - Vector3.yAxis * (width * 0.42)
	spike(
		parent,
		"BannerTip",
		m - along * (width / 2),
		m + along * (width / 2),
		tip,
		0.16,
		color,
		color,
		Enum.Material.Fabric
	)
end

-- Pavimento decorato: bordo bianco del disco centrale, rosa dei venti attorno al monumento,
-- vialetti colorati verso i cancelli dei lotti e passatoia del viale fino all'arco del sentiero.
-- Sono intarsi che non si toccano: si cammina sulle lastre di sempre, alla stessa quota
local function paving(folder: Instance, c: Vector3, top: number, innerTop: number, avenueTop: number, slope: number)
	local model = Build.Model("Paving", folder)
	-- bordo bianco attorno al disco centrale (affiora fra 60 e 61 stud dal centro)
	inlayDisc(model, "InnerEdge", c, 61, top + 0.06, PZ.white)
	-- rosa dei venti: 8 punte corte (sotto), 4 medie sotto le scale del monumento e 4 lunghe sui punti
	-- cardinali (sopra); la base di ogni punta e' nascosta sotto il collare del monumento
	local rose = Build.Model("CompassRose", model)
	local kinds = {
		{ from = 22.5, step = 45, length = 34, top = innerTop + 0.05, a = PZ.sky, b = PZ.skyDark },
		{ from = 45, step = 90, length = 41, top = innerTop + 0.1, a = PZ.white, b = PZ.silver },
		{ from = 0, step = 90, length = 50, top = innerTop + 0.15, a = PZ.gold, b = PZ.goldDark },
	}
	for _, kind in kinds do
		local y = kind.top - 0.15
		local o = Vector3.new(c.X, y, c.Z)
		for deg = kind.from, 359, kind.step do
			spike(
				rose,
				"RosePoint",
				o + dirAt(deg - 45) * 20,
				o + dirAt(deg + 45) * 20,
				o + dirAt(deg) * kind.length,
				0.3,
				kind.a,
				kind.b
			)
		end
	end
	-- collare blu attorno al monumento: ci poggiano le scale e le aiuole
	inlayDisc(model, "Collar", c, 27, innerTop + 0.2, PZ.royal)
	-- vialetti dal disco centrale ai cancelli, del colore del lotto, su una striscia bianca piu' larga
	-- (sotto) che fa da bordo
	for i = 1, MapLayout.PlotCount do
		local d = dirAt(40 * i)
		inlayStrip(model, "PlotPathBorder", c, d, 61.7, 95.4, 12.4, top + 0.06, PZ.white)
		inlayStrip(model, "PlotPath", c, d, 62.2, 95, 11, top + 0.12, PLOT_TINTS[i])
	end
	-- passatoia blu del viale (come il collare del monumento): dal disco centrale alla fine del viale,
	-- poi un tratto sulla discesa lastricata
	inlayStrip(model, "RunnerBorder", c, Vector3.zAxis, 61.7, 150, 13.4, top + 0.06, PZ.white)
	inlayStrip(model, "Runner", c, Vector3.zAxis, 62.2, 149.9, 12, top + 0.12, PZ.royal)
	-- sulla discesa (inclinate come le lastre): la striscia blu comincia e finisce un filo dentro quella
	-- bianca, cosi' le teste delle due strisce non stanno sullo stesso piano
	local ramp = CFrame.new(c.X, avenueTop, 150) * CFrame.Angles(slope, 0, 0)
	local function rampStrip(name: string, width: number, lift: number, from: number, to: number, color: Color3)
		Build.Part({
			name = name,
			size = Vector3.new(width, 0.3, to - from),
			cframe = ramp * CFrame.new(0, lift - 0.15, (from + to) / 2),
			color = color,
			collide = false,
			castShadow = false,
			parent = model,
		})
	end
	rampStrip("RunnerRampBorder", 13.4, 0.1, 0, 6, PZ.white)
	rampStrip("RunnerRamp", 12, 0.16, 0.1, 5.5, PZ.royal)
end

-- Monumento del re della collina: tappeto rosso e oro in cima, gemme sul tamburo e quattro aiuole
-- fiorite fra le scale (le scale le costruisce Scenery.Plaza: qui si lascia libero il loro spicchio)
local function monumentDecor(folder: Instance, c: Vector3, innerTop: number, assets)
	local model = Build.Model("MonumentDecor", folder)
	local hillTop = c.Y + 6 -- cima del monumento (KingService.TopY)
	inlayDisc(model, "TopTrim", c, 13, hillTop + 0.05, PZ.gold)
	inlayDisc(model, "TopCarpet", c, 12.3, hillTop + 0.1, PZ.velvet, Enum.Material.Fabric)
	local center = inlayDisc(model, "TopCenter", c, 7, hillTop + 0.15, PZ.gold)
	-- luce calda sotto l'uovo d'oro
	local glow = Instance.new("PointLight")
	glow.Color = Color3.fromRGB(255, 206, 120)
	glow.Range = 20
	glow.Brightness = 1
	glow.Shadows = false
	glow.Parent = center
	-- gemme incastonate nel tamburo, tre per ogni spicchio fra le scale
	for k = 0, 3 do
		for j = -1, 1 do
			local d = dirAt(90 * k + 15 * j)
			local pos = c + d * 15 + Vector3.new(0, 3.9, 0)
			Build.Part({
				name = "Gem",
				size = Vector3.new(1.3, 1.3, 0.5),
				cframe = CFrame.lookAt(pos, pos + d) * CFrame.Angles(0, 0, math.rad(45)),
				color = GEMS[(k + j + 4) % #GEMS + 1],
				material = Enum.Material.Glass,
				collide = false,
				parent = model,
			})
		end
	end
	-- aiuole: spicchi di prato fra le scale (a 0, 90, 180 e 270 gradi), con il bordo di pietra bianca
	-- a segmenti, i paletti negli angoli (sfere d'oro ai lati delle scale) e i fiori
	local RIM_R, LAWN_R = 21, 20.9
	local SEG, HALF = 4, 26 -- segmenti del bordo e mezza apertura dello spicchio (gradi)
	local rimTop, lawnTop = innerTop + 1.15, innerTop + 0.75
	local base = innerTop - 0.4
	for k = 0, 3 do
		local bed = Build.Model("Flowerbed", model)
		local angles = {}
		for j = 0, SEG do
			table.insert(angles, 90 * k - HALF + 2 * HALF * j / SEG)
		end
		for j = 1, SEG + 1 do
			local p = c + dirAt(angles[j]) * RIM_R
			vcyl({
				name = "BedPost",
				at = p,
				radius = 0.62,
				bottom = base,
				top = rimTop + 0.3,
				color = PZ.stone,
				material = Enum.Material.Slate,
				parent = bed,
			})
			if j == 1 or j == SEG + 1 then
				ball(bed, "BedFinial", Vector3.new(p.X, rimTop + 0.68, p.Z), 0.95, PZ.gold, Enum.Material.Foil)
				-- lato verso la scala: muretto dritto fino al tamburo
				wallBetween(
					bed,
					"BedEnd",
					c + dirAt(angles[j]) * 14.6,
					p,
					0.8,
					base,
					rimTop,
					PZ.stone,
					Enum.Material.Slate
				)
			end
			if j <= SEG then
				local q = c + dirAt(angles[j + 1]) * RIM_R
				wallBetween(bed, "BedRim", p, q, 0.8, base, rimTop, PZ.stone, Enum.Material.Slate)
				-- prato: triangoli dal centro del monumento fino a dentro il bordo (le punte sono nel tamburo)
				local o = Vector3.new(c.X, lawnTop - 0.45, c.Z)
				spike(
					bed,
					"Lawn",
					o + dirAt(angles[j]) * LAWN_R,
					o + dirAt(angles[j + 1]) * LAWN_R,
					o,
					0.9,
					PZ.leaf,
					PZ.leaf,
					Enum.Material.Grass,
					true
				)
			end
		end
		-- quattro mazzi di fiori in fila (posizioni e misura scelte perche' i petali restino ad almeno
		-- 0.2 stud dal bordo, dal tamburo e dal mazzo vicino)
		for j, off in { -17.5, -6, 6, 17.5 } do
			local flowers = assets.Clone("Props", if (j + k) % 2 == 0 then "Flowers1" else "Flowers2")
			if flowers then
				flowers:ScaleTo(1.4)
				local deg = 90 * k + off
				local p = c + dirAt(deg) * 18.2
				-- asse X del modello lungo la tangente (Angles(0, a, 0) porta X in (cos a, 0, -sin a))
				local turn = math.rad(deg) + (if j % 2 == 0 then math.pi else 0)
				flowers:PivotTo(CFrame.new(p.X, lawnTop - 0.05, p.Z) * CFrame.Angles(0, turn, 0))
				CollectionService:AddTag(flowers, "SmallDecor")
				flowers.Parent = bed
			end
		end
	end
end

-- Fontana ottagonale: vasca di marmo bianco con paletti e sfere d'oro, acqua azzurra, colonna con il
-- piatto e un uovo d'oro in cima che zampilla. 'center' e' alla quota del pavimento
local function fountain(folder: Instance, center: Vector3, toward: Vector3, assets)
	local model = Build.Model("Fountain", folder)
	local floor = center.Y
	local RC, THICK = 7, 0.9 -- distanza dal centro alla mezzeria dei muretti, spessore dei muretti
	local vertex = RC / math.cos(math.rad(22.5)) -- distanza dei vertici (e dei paletti)
	local wallTop = floor + 1.6
	inlayDisc(model, "FountainApron", center, 10.6, floor + 0.06, PZ.skyPale)
	-- fondo della vasca (ci si puo' entrare: l'acqua non si tocca); il bordo e' nascosto nei muretti
	vcyl({
		name = "PoolFloor",
		at = center,
		radius = RC + 0.3,
		bottom = floor - 0.4,
		top = floor + 0.2,
		color = PZ.pool,
		parent = model,
	})
	-- bordo: otto muretti fra i vertici dell'ottagono, con un paletto e una sfera d'oro su ogni vertice
	-- (le teste dei muretti finiscono dentro i paletti)
	for k = 0, 7 do
		local v1 = center + dirAt(45 * k - 22.5) * vertex
		local v2 = center + dirAt(45 * k + 22.5) * vertex
		wallBetween(model, "BasinWall", v1, v2, THICK, floor - 0.4, wallTop, PZ.stone, Enum.Material.Marble)
		vcyl({
			name = "BasinPost",
			at = v2,
			radius = 0.7,
			bottom = floor - 0.4,
			top = wallTop + 0.3,
			color = PZ.stone,
			material = Enum.Material.Marble,
			parent = model,
		})
		ball(model, "BasinFinial", Vector3.new(v2.X, wallTop + 0.7, v2.Z), 0.95, PZ.gold, Enum.Material.Foil)
	end
	-- acqua: arriva negli angoli dell'ottagono, il bordo del disco resta dentro i muretti e i paletti
	local water = vcyl({
		name = "Water",
		at = center,
		radius = RC + 0.25,
		bottom = floor + 0.35,
		top = wallTop - 0.45,
		color = PZ.water,
		material = Enum.Material.Glass,
		transparency = 0.35,
		collide = false,
		castShadow = false,
		parent = model,
	})
	water.Reflectance = 0.15
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(170, 226, 255)
	light.Range = 16
	light.Brightness = 1.2
	light.Shadows = false
	light.Parent = water
	-- colonna, piatto con l'acqua e uovo d'oro
	vcyl({
		name = "Column",
		at = center,
		radius = 0.85,
		bottom = floor - 0.2,
		top = floor + 4.6,
		color = PZ.stone,
		material = Enum.Material.Marble,
		parent = model,
	})
	vcyl({
		name = "Dish",
		at = center,
		radius = 3,
		bottom = floor + 4.2,
		top = floor + 4.8,
		color = PZ.gold,
		collide = false,
		parent = model,
	})
	local dishWater = vcyl({
		name = "DishWater",
		at = center,
		radius = 2.65,
		bottom = floor + 4.7,
		top = floor + 4.95,
		color = PZ.water,
		material = Enum.Material.Glass,
		transparency = 0.3,
		collide = false,
		castShadow = false,
		parent = model,
	})
	dishWater.Reflectance = 0.15
	vcyl({
		name = "Spout",
		at = center,
		radius = 0.48,
		bottom = floor + 4.8,
		top = floor + 6,
		color = PZ.stone,
		material = Enum.Material.Marble,
		collide = false,
		parent = model,
	})
	eggShape(model, "FountainEgg", Vector3.new(center.X, floor + 5.95, center.Z), 1.7, 2.3, PZ.gold)
	-- zampillo dall'uovo e velo d'acqua che cade dal piatto (particelle: niente parti in piu' da vedere)
	local jet = Build.Part({
		name = "JetEmitter",
		size = Vector3.new(0.4, 0.4, 0.4),
		cframe = CFrame.new(center.X, floor + 8.2, center.Z),
		transparency = 1,
		collide = false,
		castShadow = false,
		parent = model,
	})
	local spray = Instance.new("ParticleEmitter")
	spray.Texture = "rbxasset://textures/particles/sparkles_main.dds"
	spray.Color = ColorSequence.new(Color3.fromRGB(232, 248, 255), Color3.fromRGB(150, 214, 255))
	spray.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.38), NumberSequenceKeypoint.new(1, 0.16) })
	spray.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.1),
		NumberSequenceKeypoint.new(0.8, 0.35),
		NumberSequenceKeypoint.new(1, 1),
	})
	spray.Lifetime = NumberRange.new(0.9, 1.1)
	spray.Rate = 40
	spray.Speed = NumberRange.new(9, 11)
	spray.SpreadAngle = Vector2.new(14, 14)
	spray.Acceleration = Vector3.new(0, -26, 0)
	spray.EmissionDirection = Enum.NormalId.Top
	spray.LightEmission = 0.4
	spray.LightInfluence = 0.6
	spray.Parent = jet
	local rim = Build.Part({
		name = "CurtainEmitter",
		size = Vector3.new(0.2, 5.8, 5.8),
		cframe = CFrame.new(center.X, floor + 4.75, center.Z) * CFrame.Angles(0, 0, math.rad(90)),
		transparency = 1,
		collide = false,
		castShadow = false,
		shape = Enum.PartType.Cylinder,
		parent = model,
	})
	local curtain = spray:Clone()
	curtain.Shape = Enum.ParticleEmitterShape.Disc
	curtain.ShapeStyle = Enum.ParticleEmitterShapeStyle.Surface
	curtain.ShapeInOut = Enum.ParticleEmitterShapeInOut.Outward
	curtain.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.3), NumberSequenceKeypoint.new(1, 0.2) })
	curtain.Lifetime = NumberRange.new(0.5, 0.55)
	curtain.Rate = 60
	curtain.Speed = NumberRange.new(1.5, 2.5)
	curtain.Parent = rim
	-- due panchine rivolte alla fontana, ai lati verso il monumento
	local inward = (toward - center).Unit
	for _, side in { -1, 1 } do
		local bench = assets.Clone("Props", "Bench")
		if bench then
			bench:ScaleTo(1.2)
			local p = center + inward:Cross(Vector3.yAxis) * side * 16.5 + inward * 3
			local at = Vector3.new(p.X, floor - 0.2, p.Z)
			bench:PivotTo(CFrame.lookAt(at, Vector3.new(center.X, at.Y, center.Z)))
			bench.Parent = model
		end
	end
end

-- Aiuola rotonda con un alberello potato a due palle (vaso bianco su un anello blu)
local function topiary(folder: Instance, at: Vector3)
	local model = Build.Model("Topiary", folder)
	local floor = at.Y
	vcyl({
		name = "PotBase",
		at = at,
		radius = 2.75,
		bottom = floor - 0.4,
		top = floor + 0.45,
		color = PZ.royal,
		material = Enum.Material.Slate,
		parent = model,
	})
	vcyl({
		name = "Pot",
		at = at,
		radius = 2.45,
		bottom = floor - 0.4,
		top = floor + 1.8,
		color = PZ.stone,
		material = Enum.Material.Slate,
		parent = model,
	})
	vcyl({
		name = "PotSoil",
		at = at,
		radius = 2.1,
		bottom = floor + 1.6,
		top = floor + 1.9,
		color = PZ.leaf,
		material = Enum.Material.Grass,
		parent = model,
	})
	-- il tronco passa nella palla grande e finisce in quella piccola: fra le due resta un pezzo di tronco
	vcyl({
		name = "Trunk",
		at = at,
		radius = 0.34,
		bottom = floor + 1.7,
		top = floor + 11,
		color = WOOD,
		material = Enum.Material.Wood,
		parent = model,
	})
	ball(model, "Crown", at + Vector3.new(0, 7.6, 0), 4.6, Color3.fromRGB(70, 176, 76))
	ball(model, "CrownTop", at + Vector3.new(0, 11.7, 0), 2.6, PZ.leaf)
end

-- Viale verso il sentiero: pali con gli stendardi ai due lati e festoni di bandierine sopra il
-- passaggio (in alto, non si toccano)
local function avenueFlags(folder: Instance, c: Vector3)
	local model = Build.Model("AvenueFlags", folder)
	local X = 21.8 -- sulla neve, appena fuori dalle lastre del viale (larghe 40)
	local snow = c.Y - 1
	local poleTop = c.Y + 14.6
	for zi, z in { 112, 136 } do
		for _, sx in { -1, 1 } do
			local at = Vector3.new(sx * X, 0, z)
			vcyl({
				name = "FlagFooting",
				at = at,
				radius = 0.95,
				bottom = snow - 0.6,
				top = snow + 0.5,
				color = PZ.stoneShade,
				material = Enum.Material.Slate,
				parent = model,
			})
			vcyl({
				name = "FlagPole",
				at = at,
				radius = 0.32,
				bottom = snow + 0.3,
				top = poleTop,
				color = PZ.white,
				parent = model,
			})
			ball(model, "FlagPoleCap", Vector3.new(at.X, poleTop + 0.4, z), 1, PZ.gold, Enum.Material.Foil)
			-- braccio verso il centro del viale e stendardo
			local inward = Vector3.new(-sx, 0, 0)
			local armY = poleTop - 1.2
			Build.Part({
				name = "FlagArm",
				size = Vector3.new(3.4, 0.24, 0.24),
				cframe = CFrame.new(at.X + inward.X * 1.7, armY, z),
				color = PZ.gold,
				shape = Enum.PartType.Cylinder,
				collide = false,
				parent = model,
			})
			banner(
				model,
				Vector3.new(at.X + inward.X * 1.95, armY, z),
				inward,
				2.6,
				4.2,
				if zi == 1 then PZ.sky else PZ.coral
			)
		end
		-- festone di bandierine a rombo fra i due pali (la corda entra nei pali e fa la pancia)
		local half = X - 0.1
		local y0, sag = poleTop - 0.35, 1.8
		local function cordY(x: number): number
			return y0 - sag * (1 - (x / half) ^ 2)
		end
		local SEGS = 6
		for s = 0, SEGS - 1 do
			local x0 = -half + 2 * half * s / SEGS
			local x1 = -half + 2 * half * (s + 1) / SEGS
			local a, b = Vector3.new(x0, cordY(x0), z), Vector3.new(x1, cordY(x1), z)
			Build.Part({
				name = "BuntingCord",
				size = Vector3.new((b - a).Magnitude, 0.12, 0.12),
				cframe = CFrame.fromMatrix((a + b) / 2, (b - a).Unit, Vector3.zAxis:Cross((b - a).Unit)),
				color = PZ.ink,
				shape = Enum.PartType.Cylinder,
				collide = false,
				castShadow = false,
				parent = model,
			})
		end
		local FLAGS, reach = 14, 17.2 -- fra gli stendardi (il bordo interno e' a 18.55 dal centro)
		for f = 0, FLAGS - 1 do
			local x = -reach + 2 * reach * f / (FLAGS - 1)
			Build.Part({
				name = "Bunting",
				size = Vector3.new(1.3, 1.3, 0.1),
				cframe = CFrame.new(x, cordY(x) - 0.92, z) * CFrame.Angles(0, 0, math.rad(45)),
				color = FESTIVE[(f + zi) % #FESTIVE + 1],
				material = Enum.Material.Fabric,
				collide = false,
				castShadow = false,
				parent = model,
			})
		end
	end
end

function Scenery.Summit(parent: Instance, assets)
	local folder = Build.Model("Summit", parent)
	local c = MapLayout.SummitCenter
	-- quota calpestabile di piazza e viale; le lastre sono spesse 4 stud, cosi' i bordi affondano
	-- nella neve invece di galleggiare sul terreno
	local top = c.Y + 0.8
	-- pavimentazione circolare della piazza (si unisce ai cancelli dei lotti)
	Build.Part({
		name = "Plaza",
		size = Vector3.new(4, 206, 206),
		cframe = CFrame.new(c.X, top - 2, c.Z) * CFrame.Angles(0, 0, math.rad(90)),
		color = PZ.paving,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	-- disco centrale, un filo piu' alto (0.1 stud) e di un tono piu' caldo
	Build.Part({
		name = "PlazaRing",
		size = Vector3.new(1.3, 120, 120),
		cframe = CFrame.new(c + Vector3.new(0, 0.25, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = PZ.inner,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	local innerTop = c.Y + 0.9
	-- viale verso la rampa del sentiero (un filo piu' basso della piazza dove si sovrappongono,
	-- cosi' le due superfici non sfarfallano)
	local avenueTop = top - 0.04
	Build.Part({
		name = "Avenue",
		size = Vector3.new(40, 4, 52),
		cframe = CFrame.new(c.X, avenueTop - 2, 124),
		color = PZ.paving,
		material = Enum.Material.Slate,
		parent = folder,
	})
	-- discesa lastricata: dalla fine del viale (z=150) scende piu' ripida della rampa di terra
	-- e ci si infila sotto verso z=161, cosi' non resta nessun gradino sospeso (un filo piu' stretta del
	-- viale: dove si sovrappongono i fianchi non stanno sullo stesso piano)
	local slope = math.atan(0.25)
	Build.Part({
		name = "AvenueRamp",
		size = Vector3.new(39.9, 4, 28),
		cframe = CFrame.new(c.X, avenueTop, 150) * CFrame.Angles(slope, 0, 0) * CFrame.new(0, -2, 14),
		color = PZ.paving,
		material = Enum.Material.Slate,
		parent = folder,
	})
	paving(folder, c, top, innerTop, avenueTop, slope)
	-- arco d'ingresso al sentiero con il nome del gioco (i pali affondano nella rampa di terra)
	for _, sx in { -1, 1 } do
		Build.Part({
			name = "ArchPost",
			size = Vector3.new(4, 32, 4),
			cframe = CFrame.new(sx * 23, c.Y + 10, 158),
			color = WOOD,
			material = Enum.Material.Wood,
			parent = folder,
		})
	end
	Build.Part({
		name = "ArchBeam",
		size = Vector3.new(54, 4, 5),
		cframe = CFrame.new(0, c.Y + 26, 158),
		color = WOOD_DARK,
		material = Enum.Material.Wood,
		parent = folder,
	})
	Build.Sign(folder, CFrame.new(0, c.Y + 22, 155.4), Vector3.new(40, 7, 1), "TrailSign", nil, {
		bg = Color3.fromRGB(255, 214, 72),
		text = Color3.fromRGB(70, 36, 10),
	})
	avenueFlags(folder, c)
	-- monumento centrale: piedistallo con uovo gigante (rotazione animata dal client)
	Build.Part({
		name = "MonumentBase",
		size = Vector3.new(6, 30, 30),
		cframe = CFrame.new(c + Vector3.new(0, 3, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = PZ.stone,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	local egg = assets.Clone("Eggs", "EggLegendary")
	if egg then
		egg.Name = "MonumentEgg"
		egg:ScaleTo(5)
		-- appoggiato sul disco d'oro in cima al monumento (MonumentDecor)
		egg:PivotTo(CFrame.new(c + Vector3.new(0, 6.15, 0)))
		egg.Parent = folder
		CollectionService:AddTag(egg, "Spinner")
	end
	monumentDecor(folder, c, innerTop, assets)
	-- alberelli fra i tabelloni delle classifiche (a 125, 180 e 235 gradi, 58 stud dal centro)
	for _, deg in { 152.5, 207.5 } do
		local p = c + dirAt(deg) * 58
		topiary(folder, Vector3.new(p.X, innerTop, p.Z))
	end
	-- fontane a est e a ovest, fra i cancelli dei lotti
	for _, deg in { 100, 260 } do
		local p = c + dirAt(deg) * 76
		fountain(folder, Vector3.new(p.X, top, p.Z), Vector3.new(c.X, top, c.Z), assets)
	end
	-- lampioni fra i cancelli dei lotti (ognuno con il suo stendardo) e panchine rivolte al monumento
	for k = 0, 8 do
		local deg = 20 + 40 * k
		local dir = dirAt(deg)
		local lamp = assets.Clone("Props", "LampPost")
		if lamp then
			lamp:ScaleTo(1.25)
			lamp:PivotTo(CFrame.lookAt(c + dir * 92, c + dir * 91) + Vector3.new(0, 0.6, 0))
			local light = Instance.new("PointLight")
			light.Color = Color3.fromRGB(255, 214, 150)
			light.Range = 22
			light.Brightness = 1.2
			light.Shadows = false
			light.Parent = lamp.PrimaryPart or lamp:FindFirstChildWhichIsA("BasePart")
			lamp.Parent = folder
			-- braccio sotto la lanterna con lo stendardo (simmetrici rispetto al viale: verso l'esterno
			-- ai due lati del viale, stesso colore per ogni coppia), sopra la testa di chi passa
			local along = dirAt(if deg < 180 then deg + 90 else deg - 90)
			local armAt = c + dir * 92 + Vector3.new(0, 9, 0)
			Build.Part({
				name = "LampArm",
				size = Vector3.new(3, 0.2, 0.2),
				cframe = CFrame.fromMatrix(armAt + along * 1.5, along, Vector3.yAxis),
				color = PZ.ink,
				shape = Enum.PartType.Cylinder,
				collide = false,
				parent = folder,
			})
			banner(folder, armAt + along * 1.85, along, 1.9, 2.1, FESTIVE[math.min(k, 8 - k) + 1])
		end
		-- panchine dove non ci sono la ruota, la bacheca, i tabelloni o le fontane
		if deg == 20 or deg == 60 or deg == 300 or deg == 340 then
			local bench = assets.Clone("Props", "Bench")
			if bench then
				bench:ScaleTo(1.2)
				-- la panchina guarda il monumento
				bench:PivotTo(CFrame.lookAt(c + dir * 72, c) + Vector3.new(0, 0.6, 0))
				bench.Parent = folder
			end
		end
	end
	return folder
end

---------------------------------------------------------------------------------------------
-- Piazza: ruota della fortuna, bacheca delle missioni, scale e anello del re della collina
---------------------------------------------------------------------------------------------
local function plazaPrompt(parent: BasePart, name: string, action: string, distance: number)
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = name
	prompt.ActionText = action
	prompt.HoldDuration = 0
	prompt.MaxActivationDistance = distance
	prompt.RequiresLineOfSight = false
	prompt.Style = Enum.ProximityPromptStyle.Custom
	prompt.Parent = parent
	return prompt
end

function Scenery.Plaza(parent: Instance, _assets)
	local folder = Build.Model("Plaza", parent)
	local c = MapLayout.SummitCenter
	local floorY = c.Y + 0.8
	local GOLD = Color3.fromRGB(255, 196, 40)
	local PURPLE = Color3.fromRGB(40, 30, 72)

	-- ruota della fortuna su un palco rotondo, rivolta verso lo spawn
	local wcfg = Plaza.Wheel
	local wpos = Vector3.new(wcfg.Position.X, floorY, wcfg.Position.Y)
	local wlook = Vector3.new(wcfg.FaceToward.X, floorY, wcfg.FaceToward.Y)
	local base = CFrame.lookAt(wpos, wlook)
	local wheel = Build.Model("FortuneWheel", folder)
	local stageTop = floorY + 0.8
	Build.Part({
		name = "Stage",
		size = Vector3.new(1.6, 15, 15),
		cframe = base * CFrame.new(0, 0, 0) * CFrame.Angles(0, 0, math.rad(90)),
		color = Color3.fromRGB(216, 48, 60),
		material = Enum.Material.SmoothPlastic,
		shape = Enum.PartType.Cylinder,
		parent = wheel,
	})
	Build.Part({
		name = "StageRim",
		size = Vector3.new(1.2, 15.6, 15.6),
		cframe = base * CFrame.new(0, -0.3, 0) * CFrame.Angles(0, 0, math.rad(90)),
		color = GOLD,
		material = Enum.Material.SmoothPlastic,
		shape = Enum.PartType.Cylinder,
		parent = wheel,
	})
	local R = wcfg.Radius
	local axleY = stageTop + R + 1.6
	local axle = base * CFrame.new(0, axleY - floorY, 0)
	wheel:SetAttribute("Axle", axle)
	-- pilastro dietro la ruota (regge anche l'insegna) e due puntoni
	local signY = axleY + R + 2.6
	Build.Part({
		name = "Pillar",
		size = Vector3.new(2.4, signY - stageTop, 2.4),
		cframe = base * CFrame.new(0, (stageTop + signY) / 2 - floorY, 2.1),
		color = PURPLE,
		parent = wheel,
	})
	for _, sx in { -1, 1 } do
		local a = (base * CFrame.new(sx * 5.5, stageTop - floorY, 2.1)).Position
		local b = (base * CFrame.new(0, axleY - floorY - 3, 2.1)).Position
		Build.Part({
			name = "Brace",
			size = Vector3.new(1.2, 1.2, (b - a).Magnitude),
			cframe = CFrame.lookAt((a + b) / 2, b),
			color = PURPLE,
			parent = wheel,
		})
	end
	Build.Part({
		name = "Axle",
		size = Vector3.new(3.6, 1.6, 1.6),
		cframe = axle * CFrame.new(0, 0, 0.4) * CFrame.Angles(0, math.rad(90), 0),
		color = GOLD,
		material = Enum.Material.Metal,
		shape = Enum.PartType.Cylinder,
		parent = wheel,
	})
	-- ruota: disco (contorno scuro) e faccia trasparente con l'immagine; le girano i client
	local disc = Build.Part({
		name = "WheelDisc",
		size = Vector3.new(1.2, 2 * R + 0.6, 2 * R + 0.6),
		cframe = axle * CFrame.Angles(0, math.rad(90), 0),
		color = PURPLE,
		shape = Enum.PartType.Cylinder,
		parent = wheel,
	})
	local face = Build.Part({
		name = "WheelFace",
		size = Vector3.new(2 * R, 2 * R, 0.05),
		cframe = axle * CFrame.new(0, 0, -0.64),
		transparency = 1,
		collide = false,
		parent = wheel,
	})
	local gui = Instance.new("SurfaceGui")
	gui.Name = "WheelGui"
	gui.Face = Enum.NormalId.Front
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 40
	gui.LightInfluence = 0.15
	gui.Parent = face
	local image = Instance.new("ImageLabel")
	image.Name = "Face"
	image.BackgroundTransparency = 1
	image.Size = UDim2.fromScale(1, 1)
	image.Image = Assets.Images.WheelFace or ""
	image.Parent = gui
	disc:SetAttribute("Spin", true)
	face:SetAttribute("Spin", true)
	-- freccia: rombo rosso in cima, con la punta dentro la ruota
	Build.Part({
		name = "Pointer",
		size = Vector3.new(2.2, 2.2, 0.9),
		cframe = axle * CFrame.new(0, R + 0.5, -1.1) * CFrame.Angles(0, 0, math.rad(45)),
		color = Color3.fromRGB(216, 27, 43),
		parent = wheel,
	})
	Build.Part({
		name = "PointerCap",
		size = Vector3.new(1.1, 1.1, 1.1),
		cframe = axle * CFrame.new(0, R + 1.9, -1.1),
		color = GOLD,
		shape = Enum.PartType.Ball,
		parent = wheel,
	})
	local signCf = base * CFrame.new(0, signY + 1.2 - floorY, 0.6)
	Build.Sign(wheel, signCf, Vector3.new(17, 3.6, 0.8), "WheelSign", nil, {
		bg = GOLD,
		text = Color3.fromRGB(90, 30, 10),
	})
	-- cornice da giostra dietro l'insegna, con le lampadine accese sul bordo che sporge
	Build.Part({
		name = "SignFrame",
		size = Vector3.new(18.6, 5.2, 0.5),
		cframe = signCf * CFrame.new(0, 0, 0.65),
		color = PURPLE,
		collide = false,
		parent = wheel,
	})
	local bulbs = {}
	for i = 0, 8 do
		local x = -8.9 + 17.8 * i / 8
		table.insert(bulbs, Vector3.new(x, 2.2, 0.4))
		if i ~= 4 then -- in basso al centro passa il pilastro che regge l'insegna
			table.insert(bulbs, Vector3.new(x, -2.2, 0.4))
		end
	end
	for _, sx in { -8.9, 8.9 } do
		for _, y in { -0.75, 0.75 } do
			table.insert(bulbs, Vector3.new(sx, y, 0.4))
		end
	end
	for i, p in bulbs do
		Build.Part({
			name = "Bulb",
			size = Vector3.new(0.5, 0.5, 0.5),
			cframe = signCf * CFrame.new(p),
			color = if i % 2 == 0 then Color3.fromRGB(255, 244, 200) else GOLD,
			material = Enum.Material.Neon,
			shape = Enum.PartType.Ball,
			collide = false,
			castShadow = false,
			parent = wheel,
		})
	end
	local light = Instance.new("PointLight")
	light.Color = Color3.fromRGB(255, 220, 160)
	light.Range = 18
	light.Brightness = 0.8
	light.Shadows = false
	light.Parent = face
	local wprompt = Build.Part({
		name = "WheelPromptAnchor",
		size = Vector3.new(1, 1, 1),
		cframe = base * CFrame.new(0, 3.5, -4),
		transparency = 1,
		collide = false,
		parent = wheel,
	})
	plazaPrompt(wprompt, "WheelPrompt", "SPIN", 12)
	CollectionService:AddTag(wheel, "FortuneWheel")

	-- bacheca delle missioni (il client ci scrive le missioni del giocatore)
	local bpos = Vector3.new(-wcfg.Position.X, floorY, wcfg.Position.Y)
	local blook = Vector3.new(-wcfg.FaceToward.X, floorY, wcfg.FaceToward.Y)
	local bbase = CFrame.lookAt(bpos, blook)
	local boardModel = Build.Model("QuestBoard", folder)
	for _, sx in { -1, 1 } do
		Build.Part({
			name = "Post",
			size = Vector3.new(1.4, 14, 1.4),
			cframe = bbase * CFrame.new(sx * 8, 6, 0.4),
			color = WOOD_DARK,
			material = Enum.Material.Wood,
			parent = boardModel,
		})
	end
	local board = Build.Part({
		name = "Board",
		size = Vector3.new(15, 9.6, 0.8),
		cframe = bbase * CFrame.new(0, 7.6, 0),
		color = PURPLE,
		parent = boardModel,
	})
	Build.Part({
		name = "BoardFrame",
		size = Vector3.new(15.8, 10.4, 0.6),
		cframe = bbase * CFrame.new(0, 7.6, 0.25),
		color = WOOD,
		material = Enum.Material.Wood,
		parent = boardModel,
	})
	Build.Part({
		name = "Roof",
		size = Vector3.new(18.4, 0.9, 3.4),
		cframe = bbase * CFrame.new(0, 13.3, 0.2) * CFrame.Angles(math.rad(-12), 0, 0),
		color = ROOF,
		material = Enum.Material.Wood,
		parent = boardModel,
	})
	local bgui = Instance.new("SurfaceGui")
	bgui.Name = "BoardGui"
	bgui.Face = Enum.NormalId.Front
	bgui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	bgui.PixelsPerStud = 30
	bgui.LightInfluence = 0
	bgui.Parent = board
	local bprompt = Build.Part({
		name = "QuestPromptAnchor",
		size = Vector3.new(1, 1, 1),
		cframe = bbase * CFrame.new(0, 3.5, -3),
		transparency = 1,
		collide = false,
		parent = boardModel,
	})
	plazaPrompt(bprompt, "QuestPrompt", "MISSIONS", 12)
	CollectionService:AddTag(board, "QuestBoard")

	-- re della collina: scale verso la cima del monumento e anello luminoso sul bordo
	local kcfg = Plaza.King
	local top = floorY + kcfg.Height
	local rise = kcfg.Height / kcfg.Steps
	for _, deg in kcfg.StairAngles do
		local a = math.rad(deg)
		local dir = Vector3.new(math.sin(a), 0, math.cos(a))
		for k = 1, kcfg.Steps do
			-- l'ultimo scalino un filo sotto la cima: dove entra nel monumento le due facce non sfarfallano
			local stepTop = floorY + rise * k - (if k == kcfg.Steps then 0.04 else 0)
			-- ogni scalino occupa solo la sua pedata (dal bordo dello scalino sopra al suo): i fianchi
			-- di due scalini vicini non si sovrappongono sullo stesso piano
			local r0 = if k == kcfg.Steps then 13.5 else 15 + (kcfg.Steps - k) * 1.5
			local r1 = 15 + (kcfg.Steps + 1 - k) * 1.5
			local rc = (r0 + r1) / 2
			local h = stepTop - (floorY - 1)
			local pos = Vector3.new(c.X, (stepTop + floorY - 1) / 2, c.Z) + dir * rc
			Build.Part({
				name = "Step",
				size = Vector3.new(7, h, r1 - r0),
				cframe = CFrame.lookAt(pos, pos + dir),
				color = if k % 2 == 0 then Color3.fromRGB(232, 222, 204) else Color3.fromRGB(250, 246, 238),
				material = Enum.Material.Slate,
				parent = folder,
			})
		end
	end
	local band = Build.Part({
		name = "HillBand",
		size = Vector3.new(1, 30.6, 30.6),
		cframe = CFrame.new(c.X, top - 0.6, c.Z) * CFrame.Angles(0, 0, math.rad(90)),
		color = GOLD,
		material = Enum.Material.Neon,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	CollectionService:AddTag(band, "HillBand")
	local anchor = Build.Part({
		name = "HillSignAnchor",
		size = Vector3.new(1, 1, 1),
		cframe = CFrame.new(c.X, top + 22, c.Z),
		transparency = 1,
		collide = false,
		parent = folder,
	})
	CollectionService:AddTag(anchor, "HillSign")
	return folder
end

---------------------------------------------------------------------------------------------
-- Rifugi anti-valanga: capanne di legno aperte verso il sentiero
---------------------------------------------------------------------------------------------
function Scenery.Shelters(parent: Instance)
	local folder = Build.Model("Shelters", parent)
	local size = MapLayout.ShelterSize
	for i = 1, #MapLayout.Shelters do
		local cf = MapLayout.ShelterFrame(i)
		local hut = Build.Model(`Shelter{i}`, folder)
		-- pavimento
		Build.Part({
			name = "Floor",
			size = Vector3.new(size.X + 2, 0.6, size.Z + 2),
			cframe = cf * CFrame.new(0, 0.3, 0),
			color = WOOD,
			material = Enum.Material.WoodPlanks,
			parent = hut,
		})
		-- pali agli angoli
		for _, sx in { -1, 1 } do
			for _, sz in { -1, 1 } do
				Build.Part({
					name = "Post",
					size = Vector3.new(1.4, size.Y, 1.4),
					cframe = cf * CFrame.new(sx * size.X / 2, size.Y / 2, sz * size.Z / 2),
					color = WOOD_DARK,
					material = Enum.Material.Wood,
					parent = hut,
				})
			end
		end
		-- parete di fondo (lato a monte) e pareti laterali basse
		Build.Part({
			name = "Back",
			size = Vector3.new(size.X, size.Y, 0.8),
			cframe = cf * CFrame.new(0, size.Y / 2, size.Z / 2),
			color = WOOD,
			material = Enum.Material.WoodPlanks,
			parent = hut,
		})
		for _, sx in { -1, 1 } do
			Build.Part({
				name = "Side",
				size = Vector3.new(0.8, size.Y * 0.55, size.Z),
				cframe = cf * CFrame.new(sx * size.X / 2, size.Y * 0.275, 0),
				color = WOOD,
				material = Enum.Material.WoodPlanks,
				parent = hut,
			})
		end
		-- tetto a due falde
		for _, sz in { -1, 1 } do
			Build.Part({
				name = "Roof",
				size = Vector3.new(size.X + 4, 0.8, size.Z * 0.62),
				cframe = cf * CFrame.new(0, size.Y + 1.6, sz * size.Z * 0.26) * CFrame.Angles(math.rad(-24 * sz), 0, 0),
				color = ROOF,
				material = Enum.Material.SmoothPlastic,
				parent = hut,
			})
		end
		-- cartello luminoso sopra l'apertura
		local sign = Build.Sign(
			hut,
			cf * CFrame.new(0, size.Y + 0.2, -size.Z / 2 - 0.5),
			Vector3.new(10, 2.6, 0.4),
			"Shelter",
			nil,
			{
				bg = Color3.fromRGB(110, 230, 120),
				text = Color3.fromRGB(20, 70, 30),
			}
		)
		local light = Instance.new("PointLight")
		light.Color = Color3.fromRGB(150, 255, 160)
		light.Range = 16
		light.Brightness = 1.2
		light.Parent = sign
		hut:SetAttribute("ShelterIndex", i)
		CollectionService:AddTag(hut, "Shelter")
	end
	return folder
end

---------------------------------------------------------------------------------------------
-- Mare di nuvole attorno alla montagna (si cade attraverso e si torna in vetta)
---------------------------------------------------------------------------------------------
function Scenery.CloudSea(parent: Instance)
	local folder = Build.Model("CloudSea", parent)
	local y = MapLayout.CloudSeaY
	Build.Part({
		name = "CloudBase",
		size = Vector3.new(4000, 4, 4000),
		cframe = CFrame.new(0, y - 6, 200),
		color = Color3.fromRGB(246, 250, 255),
		material = Enum.Material.SmoothPlastic,
		collide = false,
		query = false,
		castShadow = false,
		parent = folder,
	})
	local rng = Random.new(42)
	local volcano = MapLayout.Den.Volcano.center
	for _ = 1, 260 do
		local a = rng:NextNumber(0, math.pi * 2)
		local r = rng:NextNumber(200, 1100)
		local x, z = math.cos(a) * r, 200 + math.sin(a) * r * 1.2
		local d = rng:NextNumber(40, 110)
		local size = Vector3.new(d * rng:NextNumber(1.2, 1.8), d * 0.55, d)
		local cf = CFrame.new(x, y - 4 + rng:NextNumber(0, 10), z) * CFrame.Angles(0, rng:NextNumber(0, 6.28), 0)
		-- niente nuvole dentro il vulcano della Tana (finirebbero nella grotta)
		if Vector2.new(x - volcano.X, z - volcano.Z).Magnitude < 170 then
			continue
		end
		Build.Part({
			name = "Puff",
			size = size,
			cframe = cf,
			color = Color3.fromRGB(255, 255, 255),
			material = Enum.Material.SmoothPlastic,
			shape = Enum.PartType.Ball,
			collide = false,
			query = false,
			castShadow = false,
			parent = folder,
		})
	end
	return folder
end

---------------------------------------------------------------------------------------------
-- Decorazioni sparse (alberi, rocce, fiori) per zona, lontano dal sentiero
---------------------------------------------------------------------------------------------
type DecorItem = {
	name: string,
	count: number,
	scale: { number },
	edge: boolean?,
	cliff: boolean?,
	tint: Color3?,
	light: { Color3 | number }?,
}

-- colore della roccia per zona (le guglie e le schegge di roccia prendono il colore del posto)
local ROCK_TINT = {
	Meadow = Color3.fromRGB(128, 132, 142),
	Forest = Color3.fromRGB(116, 118, 124),
	Canyon = Color3.fromRGB(178, 104, 70),
	Crystal = Color3.fromRGB(98, 92, 124),
	Crater = Color3.fromRGB(62, 56, 64),
}

local DECOR: { [string]: { DecorItem } } = {
	Summit = {
		{ name = "PineSnowy", count = 46, scale = { 1.4, 2.2 } },
		{ name = "SnowRock", count = 22, scale = { 1.0, 2.0 } },
		{ name = "Rock2", count = 10, scale = { 1.2, 2.4 } },
	},
	Meadow = {
		{ name = "RockShards", count = 14, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Meadow },
		{ name = "RockSpire", count = 6, scale = { 1.0, 1.6 }, cliff = true, tint = ROCK_TINT.Meadow },
		{ name = "PineTree", count = 30, scale = { 1.3, 2.0 } },
		{ name = "Bush1", count = 26, scale = { 1.0, 1.5 } },
		{ name = "Flowers1", count = 40, scale = { 1.4, 2.0 } },
		{ name = "Flowers2", count = 40, scale = { 1.4, 2.0 } },
		{ name = "Grass1", count = 90, scale = { 2.0, 3.0 } },
		{ name = "Rock1", count = 26, scale = { 0.8, 1.6 }, edge = true },
	},
	Forest = {
		{ name = "RockSpire", count = 10, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Forest },
		{ name = "RockShards", count = 14, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Forest },
		{ name = "OakTree", count = 46, scale = { 1.2, 1.9 } },
		{ name = "PineTree", count = 40, scale = { 1.8, 2.8 } },
		{ name = "Bush1", count = 30, scale = { 1.2, 1.8 } },
		{ name = "Mushrooms", count = 40, scale = { 1.2, 2.0 }, edge = true },
		{ name = "Fern", count = 60, scale = { 1.2, 2.0 } },
		{ name = "FallenLog", count = 14, scale = { 1.0, 1.4 } },
		{ name = "Grass1", count = 60, scale = { 2.0, 3.0 } },
		{ name = "Rock3", count = 20, scale = { 0.8, 1.6 }, edge = true },
	},
	Canyon = {
		{ name = "RockSpire", count = 24, scale = { 1.2, 2.4 }, cliff = true, tint = ROCK_TINT.Canyon },
		{ name = "RockShards", count = 20, scale = { 1.0, 2.0 }, cliff = true, tint = ROCK_TINT.Canyon },
		{ name = "Mesa", count = 16, scale = { 1.4, 2.6 } },
		{ name = "Cactus", count = 30, scale = { 1.0, 1.6 } },
		{ name = "DryBush", count = 50, scale = { 1.2, 2.0 }, edge = true },
		{ name = "CanyonRock", count = 34, scale = { 1.0, 2.4 } },
		{ name = "Rock3", count = 16, scale = { 0.8, 1.6 }, edge = true },
	},
	Crystal = {
		{ name = "RockSpire", count = 12, scale = { 1.0, 2.0 }, cliff = true, tint = ROCK_TINT.Crystal },
		{ name = "RockShards", count = 16, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Crystal },
		{ name = "CrystalCluster1", count = 26, scale = { 1.0, 2.2 }, light = { Color3.fromRGB(190, 120, 255), 18 } },
		{
			name = "CrystalCluster2",
			count = 34,
			scale = { 0.9, 1.6 },
			edge = true,
			light = { Color3.fromRGB(110, 230, 255), 14 },
		},
		{ name = "GlowShroom", count = 40, scale = { 1.0, 1.8 }, edge = true },
		{ name = "Rock1", count = 18, scale = { 1.0, 2.0 } },
	},
	Crater = {
		{ name = "RockSpire", count = 10, scale = { 1.0, 2.0 }, cliff = true, tint = ROCK_TINT.Crater },
		{ name = "RockShards", count = 14, scale = { 1.0, 1.8 }, cliff = true, tint = ROCK_TINT.Crater },
		{ name = "LavaRock", count = 34, scale = { 1.0, 2.4 }, light = { Color3.fromRGB(255, 120, 40), 16 } },
		{ name = "DeadTree", count = 18, scale = { 1.0, 1.6 } },
		{ name = "ObsidianSpikes", count = 26, scale = { 1.0, 2.0 } },
		{ name = "Rock3", count = 14, scale = { 1.0, 2.6 } },
	},
}

-- una luce ogni LIGHT_EVERY oggetti luminosi (le luci costano: poche ma ben distribuite)
local LIGHT_EVERY = 3

local SMALL = {
	Grass1 = true,
	Flowers1 = true,
	Flowers2 = true,
	Fern = true,
	Mushrooms = true,
	DryBush = true,
	GlowShroom = true,
}

-- Ingombro a terra dei lotti, da cui stanno lontani alberi e sassi della vetta: il pavimento, il recinto
-- che ne sporge fino a 0.4 stud e la torre del trono con il basamento a gradoni (fino a 3.3 stud oltre
-- il raggio della torre, come in PlotService), piu' un margine
local PLOT_FENCE_OUT = 0.4
local TOWER_BASE_OUT = 3.3
local PLOT_MARGIN = 0.6

-- Vero se il modello (gia' al suo posto) arriva nell'ingombro di un lotto
local function touchesPlot(model: Model): boolean
	local cf, size = model:GetBoundingBox()
	local reach = math.sqrt(size.X * size.X + size.Z * size.Z) / 2 + PLOT_MARGIN
	local hx = MapLayout.PlotSize.X / 2 + PLOT_FENCE_OUT
	local hz = MapLayout.PlotSize.Z / 2 + PLOT_FENCE_OUT
	local throne = MapLayout.Plot.Throne
	for i = 1, MapLayout.PlotCount do
		local p = MapLayout.PlotFrame(i):PointToObjectSpace(cf.Position)
		local dx, dz = math.max(math.abs(p.X) - hx, 0), math.max(math.abs(p.Z) - hz, 0)
		if dx * dx + dz * dz < reach * reach then
			return true
		end
		local tx, tz = p.X - throne.Tower.X, p.Z - throne.Tower.Z
		if math.sqrt(tx * tx + tz * tz) < throne.TowerRadius + TOWER_BASE_OUT + reach then
			return true
		end
	end
	return false
end

function Scenery.Decor(parent: Instance, assets, terrainHeight: (number, number) -> (number, string, string))
	local folder = Build.Model("Decor", parent)
	local rng = Random.new(7)
	for zone, items in DECOR do
		for _, item in items do
			local template = assets.Clone("Props", item.name)
			if not template then
				continue
			end
			template:Destroy()
			local placed, tries = 0, 0
			while placed < item.count and tries < item.count * 30 do
				tries += 1
				local x, z
				if zone == "Summit" then
					local a = rng:NextNumber(0, math.pi * 2)
					local r = rng:NextNumber(MapLayout.PlateauRadius - 12, MapLayout.PlateauRadius + 18)
					x, z = math.cos(a) * r, math.sin(a) * r
					if z > 120 and math.abs(x) < 50 then
						continue -- lascia libero l'inizio del sentiero
					end
				else
					x, z = rng:NextNumber(-300, 300), rng:NextNumber(150, 780)
				end
				if ExtremeBuild.NearApproach(x, z) or ExtremeBuild.NearCourse(x, z) then
					continue -- niente sul ponticello del bivio ne' sotto il Percorso Estremo
				end
				local h, kind, zn = terrainHeight(x, z)
				if zone ~= "Summit" and zn ~= zone then
					continue
				end
				-- non sopra la trincea e il tunnel della Tana dei Mostri (scavati dopo il terreno)
				local _, tunnelDist = MapLayout.DenTunnelAt(x, z)
				if tunnelDist < MapLayout.Den.TunnelRadius + 8 then
					continue
				end
				if kind == "path" or kind == "crater" or h < MapLayout.CloudSeaY + 4 then
					continue
				end
				if item.edge then
					-- sassi a bordo sentiero: solo vicino al bordo
					local hn = terrainHeight(x + 3, z)
					if math.abs(hn - h) > 4 then
						continue
					end
				end
				-- evita pendii troppo ripidi (gli oggetti sembrerebbero sospesi); le rocce di scarpata
				-- invece vanno proprio sui pendii ripidi
				local h2 = terrainHeight(x + 2, z + 2)
				local steep = math.abs(h2 - h) > 2.5
				if item.cliff ~= nil and item.cliff ~= steep then
					continue
				elseif not item.cliff and math.abs(h2 - h) > 3.2 then
					continue
				end
				local model = assets.Clone("Props", item.name)
				if not model then
					break
				end
				local s = rng:NextNumber(item.scale[1], item.scale[2])
				model:ScaleTo(s)
				local sink = if item.cliff then 1.6 * s else 0.4
				model:PivotTo(CFrame.new(x, h - sink, z) * CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), 0))
				-- in vetta niente alberi o sassi contro i recinti dei lotti o le torri dei troni: il modello si
				-- scarta dopo le estrazioni casuali (e conta come messo), cosi' la sequenza dei numeri non
				-- cambia e tutte le altre decorazioni restano esattamente dov'erano
				if zone == "Summit" and touchesPlot(model) then
					model:Destroy()
					placed += 1
					continue
				end
				if item.tint then
					for _, d in model:GetDescendants() do
						if d:IsA("BasePart") and d:GetAttribute("Role") == "skin" then
							d.Color = item.tint
						end
					end
				end
				if item.light and placed % LIGHT_EVERY == 0 then
					local light = Instance.new("PointLight")
					light.Color = item.light[1] :: Color3
					light.Range = item.light[2] :: number
					light.Brightness = 1.4
					light.Shadows = false
					light.Parent = model.PrimaryPart or model:FindFirstChildWhichIsA("BasePart")
				end
				if SMALL[item.name] then
					-- dettagli piccoli: il client li nasconde con la grafica leggera
					CollectionService:AddTag(model, "SmallDecor")
				end
				model.Parent = folder
				placed += 1
			end
		end
	end
	return folder
end

---------------------------------------------------------------------------------------------
-- Bordi del sentiero: file di sassi e tronchi semi-interrati lungo i margini (solo decorazione)
---------------------------------------------------------------------------------------------
local EDGE_PROPS = {
	Meadow = { "EdgeStones", "LogBorder" },
	Forest = { "LogBorder", "LogBorder", "EdgeStones" },
	Canyon = { "EdgeStones" },
	Crystal = { "EdgeStones" },
	Crater = { "EdgeStones" },
}

function Scenery.TrailEdges(parent: Instance, assets, terrainHeight: (number, number) -> number)
	local folder = Build.Model("TrailEdges", parent)
	local rng = Random.new(11)
	local function blocked(s: number, side: number): boolean
		for _, sh in MapLayout.Shelters do
			if side > 0 and math.abs(sh.s - s) < 14 then
				return true
			end
		end
		for _, n in MapLayout.Nests do
			if math.abs(n.s - s) < 7 then
				return true
			end
		end
		return false
	end
	local s = 24
	local count = 0
	while s < MapLayout.PathLength - 12 do
		for _, side in { 1, -1 } do
			local at = s + (if side < 0 then 8 else 0) + rng:NextNumber(-3, 3)
			local _, _, zone = MapLayout.PathPoint(at)
			local names = EDGE_PROPS[zone]
			if names and not blocked(at, side) then
				local name = names[rng:NextInteger(1, #names)]
				local model = assets.Clone("Props", name)
				if model then
					-- l'asse lungo del modello (X) segue il bordo del sentiero
					local cf = MapLayout.EdgeFrame(at, side, 1.4)
					if ExtremeBuild.NearApproach(cf.Position.X, cf.Position.Z) then
						model:Destroy() -- lascia libero l'imbocco del bivio per il Percorso Estremo
						continue
					end
					local y = terrainHeight(cf.Position.X, cf.Position.Z)
					model:ScaleTo(rng:NextNumber(0.9, 1.25))
					model:PivotTo(
						CFrame.new(cf.Position.X, y - 0.25, cf.Position.Z)
							* cf.Rotation
							* CFrame.Angles(0, rng:NextNumber(-0.15, 0.15), 0)
					)
					if name == "EdgeStones" and ROCK_TINT[zone] then
						for _, d in model:GetDescendants() do
							if d:IsA("BasePart") and d:GetAttribute("Role") == "skin" then
								d.Color = ROCK_TINT[zone]
							end
						end
					end
					CollectionService:AddTag(model, "SmallDecor")
					model.Parent = folder
					count += 1
				end
			end
		end
		s += 16
	end
	folder:SetAttribute("Count", count)
	return folder
end

---------------------------------------------------------------------------------------------
-- Tana dei Mostri: portale con il cancello in fondo al cratere, puntelli e lanterne lungo il
-- tunnel, e la grotta con l'altare dell'uovo Ultra, le statue dei cinque giganti, cristalli e
-- occhi che brillano nel buio
---------------------------------------------------------------------------------------------
local DEN_STONE = Color3.fromRGB(58, 50, 64)
local DEN_STONE_LIGHT = Color3.fromRGB(92, 82, 100)
local DEN_LAVA = Color3.fromRGB(255, 104, 34)
local DEN_EYES = Color3.fromRGB(255, 36, 64)
local DEN_BONE = Color3.fromRGB(238, 226, 200)

local function denLight(parent: Instance, color: Color3, range: number, brightness: number)
	local l = Instance.new("PointLight")
	l.Color = color
	l.Range = range
	l.Brightness = brightness
	l.Shadows = false
	l.Parent = parent
end

-- Torcia: bastone con fiamma, fuoco e luce (cf = base)
local function denTorch(folder: Instance, cf: CFrame)
	Build.Part({
		name = "TorchStick",
		size = Vector3.new(0.7, 4, 0.7),
		cframe = cf * CFrame.new(0, 2, 0),
		color = WOOD_DARK,
		material = Enum.Material.Wood,
		collide = false,
		parent = folder,
	})
	local flame = Build.Part({
		name = "TorchFlame",
		size = Vector3.new(1, 1.1, 1),
		cframe = cf * CFrame.new(0, 4.4, 0),
		color = DEN_LAVA,
		material = Enum.Material.Neon,
		collide = false,
		castShadow = false,
		parent = folder,
	})
	local fire = Instance.new("Fire")
	fire.Size = 3
	fire.Heat = 7
	fire.Color = Color3.fromRGB(255, 140, 50)
	fire.SecondaryColor = Color3.fromRGB(255, 60, 20)
	fire.Parent = flame
	denLight(flame, Color3.fromRGB(255, 150, 80), 26, 1.6)
end

-- Coppia di occhi luminosi (cf: centro fra i due occhi, rivolto verso chi guarda)
local function denEyes(folder: Instance, cf: CFrame, size: number, color: Color3)
	for _, sx in { -1, 1 } do
		Build.Part({
			name = "Eye",
			size = Vector3.new(size, size, size),
			cframe = cf * CFrame.new(sx * size * 0.9, 0, 0),
			color = color,
			material = Enum.Material.Neon,
			shape = Enum.PartType.Ball,
			collide = false,
			castShadow = false,
			parent = folder,
		})
	end
end

-- Statua di pietra di un gigante Ultra: stesso modello del pet, pietra scura e occhi accesi
local function denStatue(folder: Instance, petId: string, cf: CFrame, height: number)
	local model = Visuals.MakePet(petId, "None", "Normal", height)
	model.Name = "Statue" .. petId
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			local role = d:GetAttribute("Role")
			d.Anchored = true
			d.CanCollide = false
			d.CanTouch = false
			if role == "eye" or role == "glow" then
				d.Material = Enum.Material.Neon
				d.Color = if role == "eye" then DEN_EYES else DEN_LAVA
			else
				local shade = if role == "detail" then 0.8 elseif role == "shine" then 0.65 else 1
				d.Material = Enum.Material.Slate
				d.Color = Color3.new(0.43 * shade, 0.39 * shade, 0.46 * shade)
				d.Reflectance = 0
			end
		elseif d:IsA("ParticleEmitter") or d:IsA("Beam") or d:IsA("Light") or d:IsA("Trail") then
			d:Destroy()
		end
	end
	model:SetAttribute("Giant", false)
	model:PivotTo(cf)
	model.Parent = folder
	-- dentro la statua non si passa: un cilindro invisibile al centro
	local _, size = model:GetBoundingBox()
	local r = math.min(size.X, size.Z) * 0.32
	Build.Part({
		name = "StatueCollider",
		size = Vector3.new(size.Y * 0.8, r * 2, r * 2),
		cframe = cf * CFrame.new(0, size.Y * 0.4, 0) * CFrame.Angles(0, 0, math.rad(90)),
		shape = Enum.PartType.Cylinder,
		transparency = 1,
		query = false,
		castShadow = false,
		parent = folder,
	})
	return model
end

function Scenery.Den(parent: Instance, assets)
	local folder = Build.Model("Den", parent)
	local den = MapLayout.Den
	local cave = den.Cave
	local floorY = cave.center.Y

	-- portale: due colonne, architrave con la faccia di un mostro (occhi e denti), insegna, torce
	local gate = MapLayout.DenGateFrame()
	for _, sx in { -1, 1 } do
		Build.Part({
			name = "PortalPillar",
			size = Vector3.new(5, 24, 5),
			cframe = gate * CFrame.new(sx * 11, 9, 0),
			color = DEN_STONE,
			material = Enum.Material.Slate,
			parent = folder,
		})
		Build.Part({
			name = "PortalBase",
			size = Vector3.new(6.4, 1.6, 6.4),
			cframe = gate * CFrame.new(sx * 11, 0.8, 0),
			color = DEN_STONE_LIGHT,
			material = Enum.Material.Slate,
			parent = folder,
		})
		denTorch(folder, gate * CFrame.new(sx * 15.5, 0, -2.5))
	end
	Build.Part({
		name = "PortalLintel",
		size = Vector3.new(30, 6, 6),
		cframe = gate * CFrame.new(0, 21, 0),
		color = DEN_STONE,
		material = Enum.Material.Slate,
		parent = folder,
	})
	denEyes(folder, gate * CFrame.new(0, 22, -3.1), 2.4, DEN_EYES)
	for k = -3, 3 do
		Build.Part({
			name = "Tooth",
			class = "WedgePart",
			size = Vector3.new(1.4, 2.6, 1.2),
			cframe = gate * CFrame.new(k * 2.4, 16.7, -2.2) * CFrame.Angles(math.rad(180), 0, 0),
			color = DEN_BONE,
			material = Enum.Material.SmoothPlastic,
			collide = false,
			parent = folder,
		})
	end
	for _, sx in { -1, 1 } do
		local spikes = assets.Clone("Props", "ObsidianSpikes")
		if spikes then
			spikes:ScaleTo(1.6)
			spikes:PivotTo(gate * CFrame.new(sx * 9, 24, 0) * CFrame.Angles(0, sx * 0.6, 0))
			spikes.Parent = folder
		end
	end
	Build.Sign(folder, gate * CFrame.new(0, 27.5, -1.5), Vector3.new(26, 5, 1), "DenSign", nil, {
		bg = Color3.fromRGB(44, 12, 28),
		text = Color3.fromRGB(255, 72, 96),
	})
	-- barriera: rossa e solida per chi non ha sbloccato la Tana (il client la apre a chi l'ha sbloccata)
	local barrier = Build.Part({
		name = "DenGate",
		size = Vector3.new(18, 16, 0.8),
		cframe = gate * CFrame.new(0, 8, 0),
		color = Color3.fromRGB(255, 50, 70),
		material = Enum.Material.ForceField,
		transparency = 0.25,
		castShadow = false,
		parent = folder,
	})
	CollectionService:AddTag(barrier, "DenGate")
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "DenPrompt"
	prompt.ActionText = "UNLOCK"
	prompt.ObjectText = tostring(den.UnlockPrice)
	prompt.HoldDuration = 0.6
	prompt.MaxActivationDistance = 14
	prompt.RequiresLineOfSight = false
	prompt.Style = Enum.ProximityPromptStyle.Custom
	prompt:SetAttribute("Kind", "DenGate")
	prompt.Parent = barrier
	denLight(barrier, Color3.fromRGB(255, 70, 90), 18, 1.2)

	-- pavimenti: lastre di basalto spesse lungo il tunnel (la sommita' e' la quota del pavimento, il
	-- fondo affonda nel terreno, cosi' sotto non restano vuoti) e un disco per la grotta
	local pts = den.Tunnel
	local FLOOR_DEPTH = 8
	local floorColor = Color3.fromRGB(52, 46, 58)
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local mid = (a + b) / 2
		Build.Part({
			name = "TunnelFloor",
			size = Vector3.new(20, FLOOR_DEPTH, (b - a).Magnitude),
			cframe = CFrame.lookAt(mid, mid + (b - a)) * CFrame.new(0, -FLOOR_DEPTH / 2, 0),
			color = floorColor,
			material = Enum.Material.Basalt,
			parent = folder,
		})
		-- nelle curve un disco inclinato come la media delle due pendenze chiude lo spicchio fra le
		-- lastre, appena sotto il pavimento (cosi' non sporge da nessuna delle due)
		if i > 1 then
			local dirIn = (a - pts[i - 1]).Unit
			local dirOut = (b - a).Unit
			local along = (dirIn + dirOut).Unit
			local right = along:Cross(Vector3.yAxis).Unit
			local up = right:Cross(along).Unit
			local slopeIn = dirIn.Y / Vector2.new(dirIn.X, dirIn.Z).Magnitude
			local slopeOut = dirOut.Y / Vector2.new(dirOut.X, dirOut.Z).Magnitude
			local sink = 0.06 + 10 * math.abs(slopeOut - slopeIn) / 2
			Build.Part({
				name = "TunnelFloorJoint",
				size = Vector3.new(FLOOR_DEPTH, 20, 20),
				cframe = CFrame.fromMatrix(a - up * (FLOOR_DEPTH / 2 + sink), up, along),
				color = floorColor,
				material = Enum.Material.Basalt,
				shape = Enum.PartType.Cylinder,
				parent = folder,
			})
		end
	end
	Build.Part({
		name = "CaveFloor",
		size = Vector3.new(FLOOR_DEPTH, (cave.radius + 4) * 2, (cave.radius + 4) * 2),
		cframe = CFrame.new(cave.center - Vector3.new(0, FLOOR_DEPTH / 2 + 0.04, 0))
			* CFrame.Angles(0, 0, math.rad(90)),
		color = floorColor,
		material = Enum.Material.Basalt,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	Build.Part({
		name = "LavaRing",
		size = Vector3.new(0.2, 48, 48),
		cframe = CFrame.new(cave.center + Vector3.new(0, 0.06, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = Color3.fromRGB(255, 120, 40),
		material = Enum.Material.CrackedLava,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})

	-- tunnel: puntelli di legno con una lanterna ogni 16 stud, crepe di lava lungo i bordi
	local acc = 0
	local nextSupport = den.GateZ - pts[1].Z + 10
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local len = (b - a).Magnitude
		local flat = (b - a) * Vector3.new(1, 0, 1)
		while nextSupport <= acc + len do
			local t = (nextSupport - acc) / len
			local p = a:Lerp(b, t)
			if (p - cave.center).Magnitude > cave.radius + 2 then
				local frame = CFrame.lookAt(p, p + flat)
				for _, sx in { -1, 1 } do
					Build.Part({
						name = "SupportPost",
						size = Vector3.new(1.6, 11.6, 1.6),
						cframe = frame * CFrame.new(sx * 7.4, 5.8, 0),
						color = WOOD_DARK,
						material = Enum.Material.Wood,
						parent = folder,
					})
				end
				Build.Part({
					name = "SupportBeam",
					size = Vector3.new(17, 1.4, 1.8),
					cframe = frame * CFrame.new(0, 11.2, 0),
					color = WOOD,
					material = Enum.Material.Wood,
					parent = folder,
				})
				local lantern = Build.Part({
					name = "Lantern",
					size = Vector3.new(0.9, 1.3, 0.9),
					cframe = frame * CFrame.new(0, 9.7, 0),
					color = Color3.fromRGB(255, 176, 90),
					material = Enum.Material.Neon,
					collide = false,
					castShadow = false,
					parent = folder,
				})
				denLight(lantern, Color3.fromRGB(255, 160, 90), 26, 1.5)
			end
			nextSupport += 16
		end
		if a.Z >= den.GateZ - 1 then
			local frame = CFrame.lookAt((a + b) / 2, (a + b) / 2 + (b - a))
			for _, sx in { -1, 1 } do
				Build.Part({
					name = "LavaCrack",
					size = Vector3.new(0.6, 0.22, len - 3),
					cframe = frame * CFrame.new(sx * 7.6, 0.06, 0),
					color = DEN_LAVA,
					material = Enum.Material.Neon,
					collide = false,
					castShadow = false,
					parent = folder,
				})
			end
		end
		acc += len
	end

	-- grotta: pedana a due gradini, altare con l'uovo Ultra, anello di rune
	Build.Part({
		name = "Dais",
		size = Vector3.new(1.2, 28, 28),
		cframe = CFrame.new(cave.center + Vector3.new(0, 0.6, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = DEN_STONE,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	Build.Part({
		name = "DaisTop",
		size = Vector3.new(1.2, 17, 17),
		cframe = CFrame.new(cave.center + Vector3.new(0, 1.8, 0)) * CFrame.Angles(0, 0, math.rad(90)),
		color = DEN_STONE_LIGHT,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	local altarTop = den.Altar.Y
	Build.Part({
		name = "Altar",
		size = Vector3.new(altarTop - 0.6 - (floorY + 2.4), 4.6, 4.6),
		cframe = CFrame.new(cave.center.X, (altarTop - 0.6 + floorY + 2.4) / 2, cave.center.Z)
			* CFrame.Angles(0, 0, math.rad(90)),
		color = DEN_STONE,
		material = Enum.Material.Slate,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	local altarCap = Build.Part({
		name = "AltarCap",
		size = Vector3.new(0.6, 6.4, 6.4),
		cframe = CFrame.new(cave.center.X, altarTop - 0.3, cave.center.Z) * CFrame.Angles(0, 0, math.rad(90)),
		color = Color3.fromRGB(30, 22, 34),
		material = Enum.Material.Basalt,
		shape = Enum.PartType.Cylinder,
		parent = folder,
	})
	denLight(altarCap, Color3.fromRGB(255, 70, 100), 30, 2)
	for k = 1, 24 do
		local ang = k / 24 * math.pi * 2
		local p = cave.center + Vector3.new(math.cos(ang) * 11.4, 1.24, math.sin(ang) * 11.4)
		Build.Part({
			name = "Rune",
			size = Vector3.new(1.6, 0.1, 0.5),
			cframe = CFrame.lookAt(p, cave.center + Vector3.new(0, 1.24, 0)),
			color = Color3.fromRGB(255, 50, 90),
			material = Enum.Material.Neon,
			collide = false,
			castShadow = false,
			parent = folder,
		})
	end
	-- luce generale della grotta (rosso fuoco dall'alto)
	local lamp = Build.Part({
		name = "CaveLight",
		size = Vector3.new(1, 1, 1),
		cframe = CFrame.new(cave.center + Vector3.new(0, 26, 0)),
		transparency = 1,
		collide = false,
		query = false,
		castShadow = false,
		parent = folder,
	})
	denLight(lamp, Color3.fromRGB(255, 120, 90), 60, 1.4)

	-- statue dei giganti lungo le pareti, rivolte verso l'altare; l'ingresso (nord, -Z) resta libero
	local statues = {
		{ id = "InfernoKomodo", angle = 52, height = 17 },
		{ id = "TitanRex", angle = 116, height = 30 },
		{ id = "PentaDragon", angle = 180, height = 32 },
		{ id = "ThunderGriffin", angle = 244, height = 30 },
		{ id = "VenomWidow", angle = 308, height = 16 },
	}
	for _, st in statues do
		local a = math.rad(st.angle)
		local dir = Vector3.new(math.sin(a), 0, -math.cos(a))
		local base = cave.center + dir * 40
		local plinth = Build.Part({
			name = "Plinth",
			size = Vector3.new(16, 3, 16),
			cframe = CFrame.lookAt(base + Vector3.new(0, 1.5, 0), cave.center + Vector3.new(0, 1.5, 0)),
			color = DEN_STONE,
			material = Enum.Material.Slate,
			parent = folder,
		})
		denStatue(
			folder,
			st.id,
			CFrame.lookAt(base + Vector3.new(0, 3, 0), cave.center + Vector3.new(0, 3, 0)),
			st.height
		)
		-- luce rossa dal basso sulla statua
		local up = Instance.new("SpotLight")
		up.Face = Enum.NormalId.Top
		up.Angle = 70
		up.Range = 40
		up.Brightness = 3
		up.Color = Color3.fromRGB(255, 90, 60)
		up.Shadows = false
		up.Parent = plinth
	end
	for _, angle in { 18, 342 } do
		local a = math.rad(angle)
		denTorch(folder, CFrame.new(cave.center + Vector3.new(math.sin(a), 0, -math.cos(a)) * 30))
	end

	-- cristalli viola fra le statue e ai lati dell'ingresso
	for k, angle in { 20, 84, 148, 212, 276, 340 } do
		local a = math.rad(angle)
		local dir = Vector3.new(math.sin(a), 0, -math.cos(a))
		local crystal = assets.Clone("Props", if k % 2 == 0 then "CrystalCluster1" else "CrystalCluster2")
		if crystal then
			crystal:ScaleTo(2.4)
			crystal:PivotTo(CFrame.new(cave.center + dir * 44 - Vector3.new(0, 0.5, 0)) * CFrame.Angles(0, a, 0))
			crystal.Parent = folder
			local glow = crystal.PrimaryPart or crystal:FindFirstChildWhichIsA("BasePart")
			if glow then
				denLight(glow, Color3.fromRGB(190, 90, 255), 24, 1.3)
			end
		end
	end

	-- fumo e bagliore dalla caldera in cima al vulcano: si vede da tutta la montagna
	local volcano = den.Volcano.center
	local vent = Build.Part({
		name = "VolcanoSmoke",
		size = Vector3.new(30, 2, 30),
		cframe = CFrame.new(volcano.X, volcano.Y - 34, volcano.Z),
		transparency = 1,
		collide = false,
		query = false,
		castShadow = false,
		parent = folder,
	})
	local smoke = Instance.new("ParticleEmitter")
	smoke.Texture = "rbxasset://textures/particles/smoke_main.dds"
	smoke.Color = ColorSequence.new(Color3.fromRGB(90, 80, 90), Color3.fromRGB(170, 160, 170))
	smoke.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 14), NumberSequenceKeypoint.new(1, 46) })
	smoke.Transparency = NumberSequence.new({
		NumberSequenceKeypoint.new(0, 0.6),
		NumberSequenceKeypoint.new(0.6, 0.75),
		NumberSequenceKeypoint.new(1, 1),
	})
	smoke.Lifetime = NumberRange.new(9, 14)
	smoke.Rate = 5
	smoke.Speed = NumberRange.new(8, 12)
	smoke.SpreadAngle = Vector2.new(12, 12)
	smoke.Acceleration = Vector3.new(2, 1, 1)
	smoke.RotSpeed = NumberRange.new(-10, 10)
	smoke.Rotation = NumberRange.new(0, 360)
	smoke.EmissionDirection = Enum.NormalId.Top
	smoke.LightInfluence = 0.6
	smoke.Parent = vent
	denLight(vent, Color3.fromRGB(255, 110, 40), 60, 3)

	-- occhi nel buio sulle pareti: qualcosa guarda chi entra
	local rng = Random.new(66)
	for k = 1, 12 do
		local angle = (k + rng:NextNumber(-0.3, 0.3)) / 12 * 360
		if math.abs(((angle + 180) % 360) - 180) < 18 then
			continue -- li' c'e' l'apertura del tunnel
		end
		local a = math.rad(angle)
		local dir = Vector3.new(math.sin(a), 0, -math.cos(a))
		local y = floorY + rng:NextNumber(9, 22)
		local p = Vector3.new(cave.center.X, y, cave.center.Z) + dir * (cave.radius - 1.5)
		local color = if k % 3 == 0 then Color3.fromRGB(255, 220, 60) else DEN_EYES
		denEyes(folder, CFrame.lookAt(p, Vector3.new(cave.center.X, y, cave.center.Z)), 0.8, color)
	end
	return folder
end

return Scenery
