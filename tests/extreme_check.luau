-- Controllo del Percorso Estremo senza Studio: carica src/shared/Extreme.luau con Lune, conta gli
-- elementi e verifica che il percorso si possa finire: grafo dei salti fra gli appoggi (con le
-- piattaforme mobili campionate nel tempo), dalla partenza fino al santuario di ogni sezione.
-- Stampa i salti piu' difficili del percorso migliore.
-- Uso (dalla radice): .tools/bin/lune run tests/extreme_check.luau
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local Vector2 = (roblox :: any).Vector2
local Vector3 = (roblox :: any).Vector3

-- con l'harness (require e script come in Roblox: Extreme usa Shared.Util.Rng)
local E = require("./harness").require("ReplicatedStorage/Shared/Extreme")

local G = 196.2
local V0 = math.sqrt(2 * G * 7.2) -- salto normale (JumpHeight 7.2)
local SPEED = E.WalkSpeed
local SAFETY = 0.88 -- frazione della distanza massima teorica che consideriamo fattibile

local failures = 0
local function fail(msg: string)
	failures += 1
	print("FAIL  " .. msg)
end

-- conteggio per tipo
local counts = {}
for _, p in E.Pieces do
	counts[p.kind] = (counts[p.kind] or 0) + 1
end
local kinds = {}
for k, n in counts do
	table.insert(kinds, `{k}={n}`)
end
table.sort(kinds)
print(`elementi: {#E.Pieces}  ({table.concat(kinds, ", ")})`)

-- id unici
local seen = {}
for _, p in E.Pieces do
	if seen[p.id] then
		fail(`id duplicato: {p.id}`)
	end
	seen[p.id] = true
end

---------------------------------------------------------------------------------------------
-- Nodi: appoggi con forma in pianta (box o cerchio) e posizione nel tempo
---------------------------------------------------------------------------------------------
type Node = { p: any, circle: boolean, hx: number, hz: number, r: number, top0: number }

local nodes: { Node } = {}
for _, list in E.Supports do
	for _, p in list do
		local n: Node = { p = p, circle = false, hx = p.size.X / 2, hz = p.size.Z / 2, r = 0, top0 = 0 }
		if p.shape == "Cylinder" then
			local axis = p.cframe.RightVector
			if math.abs(axis.Y) > 0.7 then
				n.circle = true
				n.r = p.size.Y / 2
				n.top0 = p.cframe.Position.Y + p.size.X / 2
			else
				n.hx, n.hz = p.size.X / 2, p.size.Y / 2
				n.top0 = p.cframe.Position.Y + p.size.Y / 2
			end
		else
			n.top0 = p.cframe.Position.Y + p.size.Y / 2
		end
		table.insert(nodes, n)
	end
end
print(`appoggi: {#nodes}`)

local TIMES = {}
for i = 0, 119 do
	table.insert(TIMES, i * 0.25)
end

local function center(n: Node, t: number): Vector3
	local p = n.p
	if p.kind == "Mover" then
		local cf = E.MoverState(p, t)
		return cf.Position
	end
	return p.cframe.Position
end

local function topAt(n: Node, t: number): number
	return n.top0 + (center(n, t).Y - n.p.cframe.Position.Y)
end

-- distanza orizzontale bordo-bordo fra due forme
local function gap(a: Node, ca: Vector3, b: Node, cb: Vector3): number
	if a.circle and b.circle then
		return math.max(0, Vector2.new(ca.X - cb.X, ca.Z - cb.Z).Magnitude - a.r - b.r)
	end
	if a.circle or b.circle then
		local c, cc, bx, cbx = a, ca, b, cb
		if b.circle then
			c, cc, bx, cbx = b, cb, a, ca
		end
		local dx = math.max(0, math.abs(cc.X - cbx.X) - bx.hx)
		local dz = math.max(0, math.abs(cc.Z - cbx.Z) - bx.hz)
		return math.max(0, math.sqrt(dx * dx + dz * dz) - c.r)
	end
	local dx = math.max(0, math.abs(ca.X - cb.X) - a.hx - b.hx)
	local dz = math.max(0, math.abs(ca.Z - cb.Z) - a.hz - b.hz)
	return math.sqrt(dx * dx + dz * dz)
end

-- distanza massima di un salto che atterra 'rise' stud piu' in alto (negativo = piu' in basso)
local function reach(rise: number, v0: number): number
	local disc = v0 * v0 - 2 * G * rise
	if disc < 0 then
		return -1
	end
	local t = (v0 + math.sqrt(disc)) / G
	return SPEED * t * SAFETY
end

-- difficolta' del salto a -> b (0 = camminata, 1 = al limite) e istante migliore, nil se impossibile
local function jump(a: Node, b: Node): (number?, number)
	local best: number? = nil
	local bestT = 0
	local isBounce = a.p.kind == "Bounce"
	local v0 = if isBounce then (a.p.power or 90) else V0
	local moving = a.p.kind == "Mover" or b.p.kind == "Mover"
	for _, t in (if moving then TIMES else { 0 }) do
		local ca, cb = center(a, t), center(b, t)
		-- un appoggio che in quell'istante e' sotto il pelo del liquido (tronco che affonda) non regge
		local underA = E.InKill(Vector3.new(ca.X, topAt(a, t) + 0.3, ca.Z))
		local underB = E.InKill(Vector3.new(cb.X, topAt(b, t) + 0.3, cb.Z))
		if underA or underB then
			continue
		end
		local g = gap(a, ca, b, cb)
		local rise = topAt(b, t) - topAt(a, t)
		local diff: number?
		if g <= 0.05 and rise <= 1.2 then
			diff = 0
		else
			local r = reach(rise, v0)
			if r > 0 and g <= r then
				diff = g / r
			end
		end
		if diff and (best == nil or diff < best) then
			best = diff
			bestT = t
		end
	end
	return best, bestT
end

-- vicini (solo appoggi a meno di 40 stud)
local function near(a: Node, b: Node): boolean
	local ca, cb = a.p.cframe.Position, b.p.cframe.Position
	local ra = math.max(a.hx, a.hz, a.r) + (if a.p.offset then a.p.offset.Magnitude else 0)
	local rb = math.max(b.hx, b.hz, b.r) + (if b.p.offset then b.p.offset.Magnitude else 0)
	return Vector2.new(ca.X - cb.X, ca.Z - cb.Z).Magnitude <= ra + rb + 14
end

local edges: { [Node]: { { to: Node, diff: number, t: number } } } = {}
for _, a in nodes do
	edges[a] = {}
	for _, b in nodes do
		if a ~= b and near(a, b) then
			local d, t = jump(a, b)
			if d then
				table.insert(edges[a], { to = b, diff = d, t = t })
			end
		end
	end
end

-- Dijkstra con costo = 1 + 4*difficolta'^2 (preferisce salti facili, poi pochi salti)
local function route(from: Node, isGoal: (Node) -> boolean): { { node: Node, diff: number, from: Node, t: number } }?
	local dist: { [Node]: number } = { [from] = 0 }
	local prev: { [Node]: { node: Node, diff: number, t: number } } = {}
	local done: { [Node]: boolean } = {}
	while true do
		local u: Node? = nil
		for n, d in dist do
			if not done[n] and (u == nil or d < dist[u]) then
				u = n
			end
		end
		if u == nil then
			return nil
		end
		local cur = u :: Node
		if isGoal(cur) then
			local path = {}
			local n: Node? = cur
			while n and prev[n] do
				table.insert(path, 1, { node = n, diff = prev[n].diff, from = prev[n].node, t = prev[n].t })
				n = prev[n].node
			end
			return path
		end
		done[cur] = true
		for _, e in edges[cur] do
			local nd = dist[cur] + 1 + 4 * e.diff * e.diff
			if dist[e.to] == nil or nd < dist[e.to] then
				dist[e.to] = nd
				prev[e.to] = { node = cur, diff = e.diff, t = e.t }
			end
		end
	end
end

-- appoggio che contiene il punto (x, z) con la cima piu' vicina a y
local function nodeAt(pos: Vector3): Node?
	local best, bestD = nil, math.huge
	for _, n in nodes do
		local c = n.p.cframe.Position
		local inside
		if n.circle then
			inside = Vector2.new(pos.X - c.X, pos.Z - c.Z).Magnitude <= n.r
		else
			inside = math.abs(pos.X - c.X) <= n.hx and math.abs(pos.Z - c.Z) <= n.hz
		end
		if inside and n.p.kind ~= "Mover" then
			local d = math.abs(n.top0 - pos.Y)
			if d < bestD then
				best, bestD = n, d
			end
		end
	end
	return best
end

local start = nodeAt(E.StartSpawn.Position - Vector3.new(0, 3, 0))
if not start then
	fail("nessun appoggio sotto la partenza")
	process.exit(1)
end

local from = start :: Node
for i, sh in E.Shrines do
	local floorY = E.Sections[i].floor
	local goalX = sh.checkpointX - 6
	local path = route(from, function(n)
		local c = n.p.cframe.Position
		return n.p.section == i and math.abs(n.top0 - floorY) < 0.5 and c.X <= goalX + 30 and n.hx >= 20
	end)
	if not path then
		fail(`sezione {i} ({E.Sections[i].id}): il santuario non si raggiunge`)
	else
		local hard = {}
		for _, step in path do
			table.insert(hard, step)
		end
		table.sort(hard, function(a, b)
			return a.diff > b.diff
		end)
		local tops = {}
		for k = 1, math.min(5, #hard) do
			local p = hard[k].node.p
			table.insert(tops, `{p.id}:{string.format("%.2f", hard[k].diff)}`)
		end
		print(`sezione {i} {E.Sections[i].id}: {#path} salti, piu' difficili {table.concat(tops, " ")}`)
		-- ogni salto del percorso: traiettoria a parabola campionata, come la vedrebbe il server
		local maxAir = 0
		for _, step in path do
			local a, b, t0 = step.from, step.node, step.t
			local ca, cb = center(a, t0), center(b, t0)
			local y0 = topAt(a, t0) + E.BodyDown
			local y1 = topAt(b, t0) + E.BodyDown
			local v0 = if a.p.kind == "Bounce" then (a.p.power or 90) else V0
			local disc = v0 * v0 - 2 * G * (y1 - y0)
			local airT = if disc > 0 then (v0 + math.sqrt(disc)) / G else 0.6
			local flat = Vector3.new(cb.X - ca.X, 0, cb.Z - ca.Z)
			local air = 0
			for k = 0, 20 do
				local tau = airT * k / 20
				local pos = Vector3.new(ca.X, 0, ca.Z)
					+ flat * (k / 20)
					+ Vector3.new(0, y0 + v0 * tau - G * tau * tau / 2, 0)
				if pos.Y > E.CeilingAt(pos.X) then
					fail(
						`{b.p.id}: il salto supera il soffitto ({string.format("%.1f > %.1f", pos.Y, E.CeilingAt(pos.X))})`
					)
					break
				end
				if E.GroundBelow(pos, t0 + tau, 16, 3) then
					air = 0
				else
					air += airT / 20
					maxAir = math.max(maxAir, air)
				end
				if E.InKill(pos - Vector3.new(0, E.BodyDown, 0)) and k > 0 and k < 20 then
					fail(`{b.p.id}: il salto passa dentro un volume mortale`)
					break
				end
			end
		end
		print(`  tempo massimo senza appoggi nei salti: {string.format("%.2f", maxAir)} s`)
		if maxAir > 1.6 then
			fail(`sezione {i}: troppo tempo senza appoggi ({maxAir})`)
		end
		from = path[#path].node
	end
	-- il prossimo tratto parte dal pavimento del santuario
end

-- punti di rinascita: devono stare sopra un appoggio
for i, sh in E.Shrines do
	local spot = sh.spawn.Position
	local g = E.GroundBelow(spot, 0, 8)
	if not g then
		fail(`rinascita del santuario {i} senza pavimento`)
	end
	if E.InKill(spot - Vector3.new(0, E.BodyDown, 0)) then
		fail(`rinascita del santuario {i} dentro un volume mortale`)
	end
	local ceil = E.CeilingAt(spot.X)
	if spot.Y > ceil then
		fail(`rinascita del santuario {i} sopra il soffitto ({spot.Y} > {ceil})`)
	end
end
do
	local spot = E.StartSpawn.Position
	if not E.GroundBelow(spot, 0, 8) then
		fail("partenza senza pavimento")
	end
end

-- chi sta fermo su ogni appoggio statico non deve risultare "in volo" ne' sopra il soffitto
for _, n in nodes do
	local p = n.p
	if p.kind == "Solid" then
		local c = p.cframe.Position
		local pos = Vector3.new(c.X, n.top0 + E.BodyDown, c.Z)
		if not E.GroundBelow(pos, 0, 6) then
			fail(`{p.id}: GroundBelow non trova l'appoggio`)
		end
		if pos.Y > E.CeilingAt(pos.X) then
			fail(`{p.id}: sopra il soffitto`)
		end
	end
end

if failures > 0 then
	print(`{failures} problemi`)
	process.exit(1)
end
print("OK")
