-- Test d'integrazione eseguito su un server Roblox vero (Open Cloud Luau Execution).
-- Avvia tutti i servizi in modalita' test, costruisce la montagna e controlla che il mondo sia
-- coerente: remote, lotti, nidi, rifugi, sentiero percorribile (quota e pathfinding).

local LogService = game:GetService("LogService")
local PathfindingService = game:GetService("PathfindingService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local warnings = {}
LogService.MessageOut:Connect(function(msg, kind)
	if kind == Enum.MessageType.MessageWarning or kind == Enum.MessageType.MessageError then
		table.insert(warnings, msg)
	end
end)

local report = {}
local function add(k: string, v: any)
	table.insert(report, k .. "=" .. tostring(v))
end

local t0 = os.clock()
local ok, S = pcall(function()
	return require(ServerScriptService.Server.Boot).Start({ test = true })
end)
add("boot_ok", ok)
if not ok then
	add("boot_error", S)
end
add("boot_s", string.format("%.1f", os.clock() - t0))

local Net = require(ReplicatedStorage.Shared.Net)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)

-- remote
local remotes = ReplicatedStorage:FindFirstChild("Remotes")
local missing = {}
for _, name in Net.Events do
	if not (remotes and remotes:FindFirstChild(name)) then
		table.insert(missing, name)
	end
end
for _, name in Net.Functions do
	if not (remotes and remotes:FindFirstChild(name)) then
		table.insert(missing, name)
	end
end
add("remotes_missing", #missing == 0 and "none" or table.concat(missing, ","))

-- mondo
local map = workspace:FindFirstChild("Map")
local partCount = 0
if map then
	for _, d in map:GetDescendants() do
		if d:IsA("BasePart") then
			partCount += 1
		end
	end
end
add("map_parts", partCount)
local plots = workspace:FindFirstChild("Plots")
add("plots", plots and #plots:GetChildren() or 0)
local plotParts = 0
if plots then
	for _, d in plots:GetDescendants() do
		if d:IsA("BasePart") then
			plotParts += 1
		end
	end
end
add("plot_parts", plotParts)
local function countTagged(tag)
	return #game:GetService("CollectionService"):GetTagged(tag)
end
add("eggs_tagged", countTagged("Egg"))
add("incubators", countTagged("Incubator"))
add("pedestals", countTagged("Pedestal"))
add("guardians", countTagged("Guardian"))
local nests = workspace:FindFirstChild("Nests", true)
add("nests", nests and #nests:GetChildren() or 0)
local shelters = map and map:FindFirstChild("Shelters")
add("shelters", shelters and #shelters:GetChildren() or 0)

-- quota del sentiero: la superficie del terreno deve coincidere con PathPoint su tutta la larghezza
local terrainOnly = RaycastParams.new()
terrainOnly.FilterType = Enum.RaycastFilterType.Include
terrainOnly.FilterDescendantsInstances = { workspace.Terrain }
local anyHit = RaycastParams.new()
anyHit.FilterType = Enum.RaycastFilterType.Exclude
anyHit.FilterDescendantsInstances = {}
local bad, misses, samples, blocked = {}, 0, 0, {}
local s = 0
while s <= MapLayout.PathLength do
	local p, dir = MapLayout.PathPoint(s)
	local flat = Vector3.new(dir.X, 0, dir.Z).Unit
	local right = flat:Cross(Vector3.yAxis)
	for _, lateral in { -20, -12, 0, 12, 20 } do
		local q = p + right * lateral
		local hit = workspace:Raycast(q + Vector3.new(0, 60, 0), Vector3.new(0, -120, 0), terrainOnly)
		samples += 1
		if not hit then
			misses += 1
			table.insert(bad, { s = s, lat = lateral, dy = -999 })
		else
			local dy = hit.Position.Y - p.Y
			if math.abs(dy) > 1.5 then
				table.insert(bad, { s = s, lat = lateral, dy = dy })
			end
		end
		-- parti che sbarrano il passaggio ad altezza d'uomo
		-- (la pavimentazione calpestabile appena sopra il sentiero, come il viale in vetta, non conta)
		local low = workspace:Raycast(q + Vector3.new(0, 7, 0), Vector3.new(0, -9, 0), anyHit)
		if low and low.Instance ~= workspace.Terrain and low.Position.Y > q.Y + 1.5 and #blocked < 10 then
			local name = low.Instance:GetFullName()
			if not string.find(name, "Nest") and not string.find(name, "Egg") and not string.find(name, "Shelter") then
				table.insert(blocked, string.format("%d/%d:%s", s, lateral, name))
			end
		end
	end
	s += 6
end
table.sort(bad, function(a, b)
	return math.abs(a.dy) > math.abs(b.dy)
end)
local worst = {}
for i = 1, math.min(#bad, 8) do
	table.insert(worst, string.format("s%d/l%d:%.1f", bad[i].s, bad[i].lat, bad[i].dy))
end
add("path_samples", samples)
add("path_misses", misses)
add("path_off_count", #bad)
add("path_worst", table.concat(worst, " "))
add("path_blocked", #blocked == 0 and "none" or table.concat(blocked, " | "))

-- pathfinding dalla piazza in vetta fino a ciascuna zona (a tappe di circa 300 stud)
local agent = { AgentRadius = 2, AgentHeight = 5, AgentCanJump = true, AgentCanClimb = false, WaypointSpacing = 6 }
local function reach(a: Vector3, b: Vector3): string
	local path = PathfindingService:CreatePath(agent)
	local okp, err = pcall(function()
		path:ComputeAsync(a, b)
	end)
	if not okp then
		return "err:" .. tostring(err)
	end
	return path.Status.Name .. "/" .. #path:GetWaypoints()
end
local legs = {}
local from = MapLayout.SummitCenter + Vector3.new(0, 3, 60)
local step = 260
local sPos = 0
while sPos < MapLayout.PathLength do
	local nextS = math.min(sPos + step, MapLayout.PathLength - 5)
	local target = MapLayout.PathPoint(nextS) + Vector3.new(0, 3, 0)
	table.insert(legs, string.format("%d:%s", nextS, reach(from, target)))
	from = target
	sPos = nextS
	if nextS >= MapLayout.PathLength - 5 then
		break
	end
end
add("pathfinding_down", table.concat(legs, " "))
-- e al contrario: dal fondo del cratere fino alla vetta (il viaggio con le uova)
local up = {}
from = MapLayout.Crater.Center + Vector3.new(20, 3, 10)
sPos = MapLayout.PathLength
while sPos > 0 do
	local nextS = math.max(sPos - step, 0)
	local target = MapLayout.PathPoint(nextS) + Vector3.new(0, 3, 0)
	table.insert(up, string.format("%d:%s", nextS, reach(from, target)))
	from = target
	sPos = nextS
end
table.insert(up, "plaza:" .. reach(from, MapLayout.SummitCenter + Vector3.new(0, 3, 40)))
add("pathfinding_up", table.concat(up, " "))
add(
	"crater_floor",
	reach(
		MapLayout.PathPoint(MapLayout.PathLength) + Vector3.new(0, 3, 0),
		MapLayout.Crater.Center + Vector3.new(30, 3, 20)
	)
)

-- modelli 3D caricati (InsertService) e segnaposto rimasti
local assets = ReplicatedStorage:FindFirstChild("Assets")
local loaded, placeholders = 0, {}
if assets then
	for _, folder in assets:GetChildren() do
		for _, m in folder:GetChildren() do
			if m:GetAttribute("Placeholder") then
				table.insert(placeholders, m.Name)
			else
				loaded += 1
			end
		end
	end
end
add("assets_loaded", loaded)
add("assets_placeholders", #placeholders == 0 and "none" or table.concat(placeholders, ","))
local decor = workspace:FindFirstChild("Decor", true)
add("decor_models", decor and #decor:GetChildren() or 0)
local edges = workspace:FindFirstChild("TrailEdges", true)
add("trail_edges", edges and #edges:GetChildren() or 0)

-- trono Ultra di ogni lotto: torre, altare con i comandi, pedana, punto del pet in cima
do
	local bad = {}
	local plots = S and S.PlotService and S.PlotService.Plots or {}
	local L = MapLayout.Plot
	for i, plot in plots do
		local th = plot.throne
		if not th then
			table.insert(bad, `{i}:manca`)
			continue
		end
		local point = th.base:FindFirstChild("PetPoint") :: Attachment?
		local floorY = plot.cframe.Position.Y
		if not point or math.abs(point.WorldPosition.Y - (floorY + L.Throne.TowerTop + 0.3)) > 0.05 then
			table.insert(bad, `{i}:punto`)
		end
		if not (th.prompt and th.stealPrompt and th.pad and th.pad:GetAttribute("Slot") == 0) then
			table.insert(bad, `{i}:comandi`)
		end
		if S.PlotService.Stand(plot, 0) ~= th or S.PlotService.Stand(plot, 1) ~= plot.pedestals[1] then
			table.insert(bad, `{i}:stand`)
		end
		-- il piedistallo spostato non deve toccare l'altare ne' gli altri
		local p18 = plot.cframe:PointToObjectSpace(plot.pedestals[18].base.Position)
		if (Vector3.new(p18.X, 0, p18.Z) - L.Pedestals[18]).Magnitude > 0.1 then
			table.insert(bad, `{i}:ped18`)
		end
	end
	add("thrones", #plots)
	add("throne_problems", #bad == 0 and "none" or table.concat(bad, ","))
end

-- giganti Ultra sul trono: altezza in gioco rispetto a quella prevista
do
	local Pets = require(ReplicatedStorage.Shared.Config.Pets)
	local Visuals = require(ReplicatedStorage.Shared.Visuals)
	local sizes = {}
	local k = 0
	for _, def in Pets.List do
		if def.giant and S then
			k += 1
			local plot = S.PlotService.ByIndex(k)
			local m = Visuals.MakePet(def.id, "None", "Normal")
			local point = plot.throne.base:FindFirstChild("PetPoint") :: Attachment
			m:PivotTo(point.WorldCFrame)
			m.Parent = workspace
			local _, size = m:GetBoundingBox()
			local emitters = 0
			for _, d in m:GetDescendants() do
				if d:IsA("ParticleEmitter") then
					emitters += 1
				end
			end
			table.insert(sizes, string.format("%s:%.0fx%.0fx%.0f/fx%d", def.id, size.X, size.Y, size.Z, emitters))
			m:Destroy()
		end
	end
	add("giants", table.concat(sizes, " "))
end

-- uscita dalla vetta: dal viale alla rampa del sentiero la superficie calpestabile non deve avere
-- gradini (prima il viale finiva sospeso 3 stud sopra la rampa)
do
	local solid = RaycastParams.new()
	solid.FilterType = Enum.RaycastFilterType.Exclude
	solid.FilterDescendantsInstances = {}
	solid.RespectCanCollide = true
	local worst, at, gaps = 0, "", 0
	for _, x in { -15, 0, 15 } do
		local prev
		for z = 120, 190 do
			-- da sotto l'arco (trave e cartello sono piu' in alto)
			local hit = workspace:Raycast(Vector3.new(x, 345, z), Vector3.new(0, -40, 0), solid)
			if not hit then
				gaps += 1
			else
				if prev and math.abs(hit.Position.Y - prev) > worst then
					worst = math.abs(hit.Position.Y - prev)
					at = string.format("x=%d,z=%d(%s)", x, z, hit.Instance.Name)
				end
				prev = hit.Position.Y
			end
		end
	end
	add("exit_max_step", string.format("%.2f", worst))
	add("exit_max_step_at", at)
	add("exit_gaps", gaps)
end

-- Tana dei Mostri: pavimento del tunnel continuo, volta chiusa, uovo Ultra sull'altare,
-- percorribile dal cratere fino all'altare (con la barriera aperta)
do
	local den = MapLayout.Den
	local cave = den.Cave
	local solid = RaycastParams.new()
	solid.FilterType = Enum.RaycastFilterType.Exclude
	solid.FilterDescendantsInstances = {}
	solid.RespectCanCollide = true
	local terrainOnly2 = RaycastParams.new()
	terrainOnly2.FilterType = Enum.RaycastFilterType.Include
	terrainOnly2.FilterDescendantsInstances = { workspace.Terrain }
	-- lungo l'asse del tunnel ogni 2 stud: quota del pavimento, spazio sopra la testa, roccia sopra
	local pts = den.Tunnel
	local worstFloor, worstAt, minHead, headAt, holes = 0, "", math.huge, "", {}
	for i = 1, #pts - 1 do
		local a, b = pts[i], pts[i + 1]
		local n = math.ceil((b - a).Magnitude / 2)
		for k = 0, n - 1 do
			local p = a:Lerp(b, k / n)
			local down = workspace:Raycast(p + Vector3.new(0, 6, 0), Vector3.new(0, -14, 0), solid)
			local dy = if down then down.Position.Y - p.Y else -99
			-- (sul piano del cancello il raggio parte dentro la barriera)
			if math.abs(dy) > math.abs(worstFloor) and math.abs(p.Z - den.GateZ) > 1.5 then
				worstFloor, worstAt = dy, string.format("z=%d", p.Z)
			end
			local up = workspace:Raycast(p + Vector3.new(0, 1, 0), Vector3.new(0, 40, 0), terrainOnly2)
			local head = if up then up.Position.Y - p.Y else 99
			if p.Z > den.GateZ + 4 and head < minHead and (p - cave.center).Magnitude > cave.radius then
				minHead, headAt = head, string.format("z=%d", p.Z)
			end
			-- dall'alto: oltre il portale il primo terreno incontrato deve essere la volta, non il pavimento
			if p.Z > den.GateZ + 4 then
				local top = workspace:Raycast(Vector3.new(p.X, 320, p.Z), Vector3.new(0, -300, 0), terrainOnly2)
				if top and top.Position.Y < p.Y + 12 and #holes < 6 then
					table.insert(holes, string.format("z=%d", p.Z))
				end
			end
		end
	end
	add("den_floor_worst", string.format("%.2f@%s", worstFloor, worstAt))
	add("den_headroom_min", string.format("%.1f@%s", minHead, headAt))
	add("den_roof_holes", #holes == 0 and "none" or table.concat(holes, " "))
	-- grotta: pavimento, cupola chiusa sopra il centro
	local caveFloor = workspace:Raycast(cave.center + Vector3.new(30, 8, 0), Vector3.new(0, -20, 0), solid)
	add("den_cave_floor", if caveFloor then string.format("%.2f", caveFloor.Position.Y - cave.center.Y) else "miss")
	local dome = workspace:Raycast(cave.center + Vector3.new(0, 2, 0), Vector3.new(0, 120, 0), terrainOnly2)
	add("den_dome", if dome then string.format("%.1f", dome.Position.Y - cave.center.Y) else "open")
	-- oggetti costruiti
	local map = workspace:FindFirstChild("Map")
	local denModel = map and map:FindFirstChild("Den")
	local statues = 0
	if denModel then
		for _, c in denModel:GetChildren() do
			if string.sub(c.Name, 1, 6) == "Statue" and c:IsA("Model") then
				statues += 1
			end
		end
	end
	add("den_statues", statues)
	add("den_gates", #game:GetService("CollectionService"):GetTagged("DenGate"))
	add("den_zone_cave", MapLayout.ZoneAt(cave.center + Vector3.new(0, 3, 0)))
	add("den_zone_crater", MapLayout.ZoneAt(Vector3.new(70, 98, 715)))
	-- l'uovo Ultra sull'altare, e che ricompaia dopo essere stato tolto
	local altar = S and S.NestService.All().DenAltar
	add("den_egg", if altar and altar.egg and altar.eggInfo then altar.eggInfo.rarity else "none")
	if altar and altar.egg then
		altar.egg:Destroy()
		altar.egg = nil
		altar.away = false
		altar.respawnAt = os.clock() + 1
		task.wait(3)
		add("den_egg_respawn", if altar.egg then altar.eggInfo.rarity else "none")
	end
	-- percorribilita' dal cratere all'altare (il pathfinding di Roblox non regge i pavimenti di pietra
	-- sopra il terreno scavato, quindi si misura con i raggi): ogni 2 stud pavimento al suo posto,
	-- spazio sopra la testa e larghezza libera all'altezza del busto
	local barriers = game:GetService("CollectionService"):GetTagged("DenGate")
	for _, b in barriers do
		(b :: BasePart).CanCollide = false
	end
	local route = table.clone(pts)
	table.insert(route, cave.center + Vector3.new(0, 0, -15))
	local worstDy, minRoom, minWidth, at = 0, math.huge, math.huge, ""
	for i = 1, #route - 1 do
		local a, b = route[i], route[i + 1]
		local flat = ((b - a) * Vector3.new(1, 0, 1)).Unit
		local side = flat:Cross(Vector3.yAxis)
		local n = math.ceil((b - a).Magnitude / 2)
		for k = 0, n - 1 do
			local p = a:Lerp(b, k / n)
			local down = workspace:Raycast(p + Vector3.new(0, 3, 0), Vector3.new(0, -8, 0), solid)
			local dy = if down then down.Position.Y - p.Y else -9
			if math.abs(dy) > math.abs(worstDy) then
				worstDy = dy
			end
			local up = workspace:Raycast(p + Vector3.new(0, 0.5, 0), Vector3.new(0, 30, 0), solid)
			local room = if up then up.Position.Y - p.Y else 30
			local chest = p + Vector3.new(0, 2.5, 0)
			local l = workspace:Raycast(chest, -side * 20, solid)
			local r = workspace:Raycast(chest, side * 20, solid)
			local width = (if l then (l.Position - chest).Magnitude else 20)
				+ (if r then (r.Position - chest).Magnitude else 20)
			if room < minRoom then
				minRoom = room
			end
			if width < minWidth then
				minWidth, at = width, string.format("z=%d", p.Z)
			end
		end
	end
	for _, b in barriers do
		(b :: BasePart).CanCollide = true
	end
	add("den_walk", string.format("floor %.2f, headroom %.1f, width %.1f@%s", worstDy, minRoom, minWidth, at))
	-- dal fondo del cratere fino al portale (fuori dal tunnel il pathfinding funziona)
	local okp, status = pcall(function()
		local path = PathfindingService:CreatePath(agent)
		path:ComputeAsync(Vector3.new(70, 98, 690), MapLayout.DenGateFrame().Position + Vector3.new(0, 3, -6))
		return path.Status.Name .. "/" .. #path:GetWaypoints()
	end)
	add("den_path_gate", if okp then status else "err:" .. tostring(status))
end

-- ragdoll su un personaggio R15 di prova (giunti AnimationConstraint): i giunti si spengono (gli
-- snodi sferici tengono uniti gli arti), l'umanoide resta vivo e alla fine i giunti tornano rigidi.
-- La fisica qui non gira (RunService:IsRunning() e' falso), quindi si controlla solo lo stato dei giunti.
do
	local okRig, rig = pcall(function()
		return game:GetService("Players")
			:CreateHumanoidModelFromDescription(Instance.new("HumanoidDescription"), Enum.HumanoidRigType.R15)
	end)
	if okRig and rig and S then
		rig:PivotTo(CFrame.new(0, MapLayout.SummitY + 5, 60))
		rig.Parent = workspace
		local hum = rig:FindFirstChildOfClass("Humanoid") :: Humanoid
		local function jointsOff(): (number, number)
			local off, sockets = 0, 0
			for _, d in rig:GetDescendants() do
				if d:IsA("AnimationConstraint") and not d.Enabled then
					off += 1
					local socket = d.Parent and d.Parent:FindFirstChild(d.Name .. "BallSocket")
					if socket and (socket :: BallSocketConstraint).Enabled then
						sockets += 1
					end
				end
			end
			return off, sockets
		end
		S.RagdollService.SetRig(rig, true)
		local off, sockets = jointsOff()
		add("ragdoll_joints_off", string.format("%d/sockets%d", off, sockets))
		add("ragdoll_alive", hum.Health > 0 and hum:GetState() ~= Enum.HumanoidStateType.Dead)
		S.RagdollService.SetRig(rig, false)
		add("ragdoll_recovered", (jointsOff()) == 0)
		rig:Destroy()
	else
		add("ragdoll_rig", tostring(rig))
	end
end

-- avvisi raccolti durante l'avvio
add("warnings", #warnings)
for i = 1, math.min(#warnings, 25) do
	add("warn" .. i, warnings[i])
end
return table.concat(report, "\n")
