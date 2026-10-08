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
		local low = workspace:Raycast(q + Vector3.new(0, 7, 0), Vector3.new(0, -9, 0), anyHit)
		if low and low.Instance ~= workspace.Terrain and #blocked < 10 then
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
add("crater_floor", reach(MapLayout.PathPoint(MapLayout.PathLength) + Vector3.new(0, 3, 0), MapLayout.Crater.Center + Vector3.new(30, 3, 20)))

-- avvisi raccolti durante l'avvio
add("warnings", #warnings)
for i = 1, math.min(#warnings, 25) do
	add("warn" .. i, warnings[i])
end
return table.concat(report, "\n")
