-- Navigazione condivisa da bussola e mappa del tablet: destinazione scelta (o automatica in base
-- all'obiettivo) e percorso lungo la rete dei sentieri (Dijkstra sui punti di interesse).
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))

local Nav = {}

local POIS = Config.MAP.POIS
local PATHS = Config.MAP.PATHS
Nav.POIS = POIS
Nav.PATHS = PATHS
Nav.ICONS = { "🏠", "🗼", "⛺", "🌊", "🛖", "⛏" }
Nav.STUD_TO_METERS = 0.28

-- nil = automatica; altrimenti { name, pos } scelta toccando la mappa
Nav.manual = nil :: { name: string, pos: Vector3, poi: number? }?

local function flat(v: Vector3): Vector3
	return Vector3.new(v.X, 0, v.Z)
end

function Nav.meters(studs: number): number
	return math.floor(studs * Nav.STUD_TO_METERS + 0.5)
end

function Nav.setPoi(index: number)
	Nav.manual = { name = POIS[index].name, pos = POIS[index].pos, poi = index }
end

function Nav.clear()
	Nav.manual = nil
end

-- Destinazione corrente: scelta a mano, oppure suggerita dall'obiettivo della notte
function Nav.destination(state: Folder): { name: string, pos: Vector3, poi: number? }?
	if Nav.manual then
		return Nav.manual
	end
	local player = Players.LocalPlayer
	local objective = state:GetAttribute("Objective")
	if objective == "Reperto" then
		if player:GetAttribute("CarryingTape") then
			return { name = "Ranger Station", pos = POIS[1].pos, poi = 1 }
		end
		local world = workspace:FindFirstChild("RakeHunt")
		local tape = world and world:FindFirstChild("NastroAudio")
		local part = tape and tape:FindFirstChild("Nastro") :: BasePart?
		if part then
			return { name = "Nastro audio", pos = part.Position }
		end
	end
	if (state:GetAttribute("HintR") or 0) > 0 then
		return { name = "Area di caccia", pos = Vector3.new(state:GetAttribute("HintX") or 0, 0, state:GetAttribute("HintZ") or 0) }
	end
	local seenAt = state:GetAttribute("LastSeenTime") or 0
	if seenAt > 0 and workspace:GetServerTimeNow() - seenAt < 60 then
		return { name = "Ultimo avvistamento", pos = Vector3.new(state:GetAttribute("LastSeenX") or 0, 0, state:GetAttribute("LastSeenZ") or 0) }
	end
	return nil
end

-- Punto più vicino sulla rete dei sentieri: posizione, indice del segmento, distanza
local function project(p: Vector3)
	local best, bestSeg, bestPoint = math.huge, 1, POIS[1].pos
	for i, pair in PATHS do
		local a, b = flat(POIS[pair[1]].pos), flat(POIS[pair[2]].pos)
		local ab = b - a
		local t = math.clamp((flat(p) - a):Dot(ab) / ab:Dot(ab), 0, 1)
		local q = a + ab * t
		local d = (flat(p) - q).Magnitude
		if d < best then
			best, bestSeg, bestPoint = d, i, q
		end
	end
	return bestPoint, bestSeg, best
end

-- Percorso dal punto `from` alla destinazione: lista di punti (piatti) e lunghezza totale in stud
function Nav.route(from: Vector3, to: Vector3): ({ Vector3 }, number)
	local start = flat(from)
	local goal = flat(to)
	if (goal - start).Magnitude < 45 then
		return { start, goal }, (goal - start).Magnitude
	end
	local entry, entrySeg = project(start)
	local exit, exitSeg = project(goal)
	-- nodi: 1..#POIS, poi S (ingresso) e T (uscita)
	local n = #POIS
	local S, Tn = n + 1, n + 2
	local pos = {}
	for i, poi in POIS do
		pos[i] = flat(poi.pos)
	end
	pos[S], pos[Tn] = entry, exit
	local edges: { [number]: { { number } } } = {}
	local function link(a: number, b: number)
		local w = (pos[a] - pos[b]).Magnitude
		edges[a] = edges[a] or {}
		edges[b] = edges[b] or {}
		table.insert(edges[a], { b, w })
		table.insert(edges[b], { a, w })
	end
	for i, pair in PATHS do
		if i ~= entrySeg and i ~= exitSeg then
			link(pair[1], pair[2])
		end
	end
	local function splitSegment(segIndex: number, node: number)
		local pair = PATHS[segIndex]
		link(node, pair[1])
		link(node, pair[2])
	end
	splitSegment(entrySeg, S)
	splitSegment(exitSeg, Tn)
	if entrySeg == exitSeg then
		link(S, Tn)
		-- il segmento originale serve ancora per gli altri percorsi
		link(PATHS[entrySeg][1], PATHS[entrySeg][2])
	else
		-- gli estremi dei due segmenti divisi restano collegati tra loro attraverso S e T
	end
	local dist, prev, done = { [S] = 0 }, {}, {}
	while true do
		local u, best = nil, math.huge
		for node, d in dist do
			if not done[node] and d < best then
				u, best = node, d
			end
		end
		if not u or u == Tn then
			break
		end
		done[u] = true
		for _, e in edges[u] or {} do
			local v, w = e[1], e[2]
			if not dist[v] or best + w < dist[v] then
				dist[v] = best + w
				prev[v] = u
			end
		end
	end
	local points = { goal }
	local node = Tn
	while node do
		table.insert(points, 1, pos[node])
		node = prev[node]
	end
	table.insert(points, 1, start)
	local total = 0
	for i = 2, #points do
		total += (points[i] - points[i - 1]).Magnitude
	end
	return points, total
end

-- Prossimo punto del percorso a più di 12 stud dal giocatore (dove "puntare")
function Nav.nextWaypoint(points: { Vector3 }, from: Vector3): Vector3
	for i = 2, #points do
		if (points[i] - flat(from)).Magnitude > 12 then
			return points[i]
		end
	end
	return points[#points]
end

return Nav
