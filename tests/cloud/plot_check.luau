-- Controllo di funzionamento dei lotti su un server vero, da rifare dopo ogni modifica estetica a
-- lotti e piazza (recinzione, pavimento, arredo):
-- - pedane di raccolta (piedistalli e troni): solide, CanTouch acceso (PetService raccoglie le monete
--   con Touched), niente di solido sopra fino all'altezza di un corpo, non piu' basse del pavimento
--   intorno, e sotto l'impronta dei piedi la superficie piu' alta e' la pedana;
-- - incubatrici, piedistalli e troni: prompt e attachment al loro posto;
-- - cancello: apertura libera all'altezza del corpo e senza gradini fra piazza e lotto;
-- - dalla piazza si arriva a piedi su ogni pedana (pathfinding) e ogni pedana e' dentro il suo lotto.
-- Uso: .tools/venv/bin/python tools/cloud_test.py tests/cloud/plot_check.luau [--no-build --version N]

local PathfindingService = game:GetService("PathfindingService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local S = require(ServerScriptService.Server.Boot).Start({ test = true })
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local L = MapLayout.Plot

local lines = {}
local function add(key: string, value: any)
	table.insert(lines, `{key}={tostring(value)}`)
end

-- elenco dei problemi per controllo: conta e primi esempi
local problems: { [string]: { string } } = {}
local function fail(check: string, detail: string)
	problems[check] = problems[check] or {}
	table.insert(problems[check], detail)
end

local solid = RaycastParams.new()
solid.FilterType = Enum.RaycastFilterType.Exclude
solid.FilterDescendantsInstances = {}

local function topY(part: BasePart): number
	-- disco steso (cilindro ruotato): lo spessore e' lungo l'asse X della parte
	return part.Position.Y + part.Size.X / 2
end

local pads: { { plot: any, pad: BasePart, name: string } } = {}
for _, plot in S.PlotService.Plots do
	for i, ped in plot.pedestals do
		table.insert(pads, { plot = plot, pad = ped.pad, name = `P{plot.index}.ped{i}` })
	end
	for k, t in plot.thrones or {} do
		if t.pad then
			table.insert(pads, { plot = plot, pad = t.pad, name = `P{plot.index}.throne{k}` })
		end
	end
end
add("pads", #pads)

-- 1) proprieta' e niente sopra
for _, e in pads do
	local pad = e.pad
	if not (pad.Anchored and pad.CanCollide) then
		fail("pad_props", `{e.name} anchored={pad.Anchored} collide={pad.CanCollide}`)
	end
	if not pad.CanTouch then
		fail("pad_cantouch", e.name)
	end
	-- fino all'altezza di un personaggio (6 stud): piu' su (cappelli dei pilastri, travi) non tocca nessuno
	local hit =
		workspace:Raycast(Vector3.new(pad.Position.X, topY(pad) + 6, pad.Position.Z), Vector3.new(0, -8, 0), solid)
	if not hit or hit.Instance ~= pad then
		fail("pad_covered", `{e.name}<-{if hit then hit.Instance:GetFullName() else "nothing"}`)
	end
end

-- 2) la pedana non e' piu' bassa del pavimento intorno (altrimenti i piedi non la toccano): il pavimento
-- e' il campione piu' basso dell'anello attorno (gli altri possono cadere sul piedistallo accanto)
for _, e in pads do
	local pad = e.pad
	local r = pad.Size.Y / 2 + 0.9
	local floor = math.huge
	for k = 0, 7 do
		local a = k * math.pi / 4
		local p = Vector3.new(pad.Position.X + math.cos(a) * r, topY(pad) + 6, pad.Position.Z + math.sin(a) * r)
		local hit = workspace:Raycast(p, Vector3.new(0, -12, 0), solid)
		if hit then
			floor = math.min(floor, hit.Position.Y)
		end
	end
	local margin = topY(pad) - floor
	if floor < math.huge and margin < -0.02 then
		fail("pad_buried", string.format("%s %.2f", e.name, margin))
	end
end

-- 3) chi ci sale sopra la tocca: sotto l'impronta dei piedi (2 x 1 stud, in ogni verso) la superficie
-- solida piu' alta e' la pedana stessa, alla sua quota (sul server dei test la fisica non gira, quindi
-- niente prova con un oggetto che cade: con CanTouch acceso e il corpo appoggiato, Touched arriva)
for _, e in pads do
	local pad = e.pad
	local top = topY(pad)
	for _, off in
		{ { 0, 0 }, { 0.9, 0.45 }, { -0.9, 0.45 }, { 0.9, -0.45 }, { -0.9, -0.45 }, { 0.45, 0.9 }, { -0.45, -0.9 } }
	do
		local p = Vector3.new(pad.Position.X + off[1], top + 6, pad.Position.Z + off[2])
		local hit = workspace:Raycast(p, Vector3.new(0, -8, 0), solid)
		if not hit or hit.Instance ~= pad or math.abs(hit.Position.Y - top) > 0.05 then
			fail(
				"pad_standing",
				string.format(
					"%s (%.1f,%.1f)<-%s",
					e.name,
					off[1],
					off[2],
					if hit then hit.Instance.Name else "nothing"
				)
			)
			break
		end
	end
end

-- 4) incubatrici, piedistalli e troni: prompt e attachment
for _, plot in S.PlotService.Plots do
	if #plot.incubators ~= #L.Incubators then
		fail("incubators", `P{plot.index} {#plot.incubators}/{#L.Incubators}`)
	end
	for i, inc in plot.incubators do
		local b = inc.base
		if
			not (b:FindFirstChild("EggPoint") and b:FindFirstChild("HatchPrompt") and b:FindFirstChild("StealPrompt"))
		then
			fail("incubator_parts", `P{plot.index}.inc{i}`)
		end
	end
	for i, ped in plot.pedestals do
		local b = ped.base
		if
			not (b:FindFirstChild("PetPoint") and b:FindFirstChild("SellPrompt") and b:FindFirstChild("StealPrompt"))
		then
			fail("pedestal_parts", `P{plot.index}.ped{i}`)
		end
	end
	for k, t in plot.thrones or {} do
		if not (t.base and t.base:FindFirstChild("PetPoint") and t.prompt) then
			fail("throne_parts", `P{plot.index}.throne{k}`)
		end
	end
	if not (plot.sign and plot.sign:FindFirstChild("SignGui")) then
		fail("owner_sign", `P{plot.index}`)
	end
end

-- 5) cancello: niente di solido nell'apertura all'altezza del corpo, niente gradini piazza-lotto
for _, plot in S.PlotService.Plots do
	local base: CFrame = plot.cframe
	local D = MapLayout.PlotSize.Z
	local half = L.GateWidth / 2 - 1.2
	local x = -half
	while x <= half do
		for _, y in { 1.2, 3, 5 } do
			local from = (base * CFrame.new(x, y, -D / 2 - 3)).Position
			local to = (base * CFrame.new(x, y, -D / 2 + 3)).Position
			local hit = workspace:Raycast(from, to - from, solid)
			if hit then
				fail("gate_blocked", string.format("P%d x=%.1f y=%.1f %s", plot.index, x, y, hit.Instance.Name))
			end
		end
		x += 1.5
	end
	local worstStep = 0
	local prev: number? = nil
	for z = -D / 2 - 8, -D / 2 + 8, 0.5 do
		local p = (base * CFrame.new(0, 6, z)).Position
		local hit = workspace:Raycast(p, Vector3.new(0, -14, 0), solid)
		if hit then
			if prev then
				worstStep = math.max(worstStep, math.abs(hit.Position.Y - prev))
			end
			prev = hit.Position.Y
		end
	end
	if worstStep > 0.6 then
		fail("gate_step", string.format("P%d %.2f", plot.index, worstStep))
	end
end

-- 6) dalla piazza a piedi fino a ogni pedana dei piedistalli; ogni pedana dentro il suo lotto
local agent = { AgentRadius = 1.6, AgentHeight = 5, AgentCanJump = true, WaypointSpacing = 4 }
for _, e in pads do
	if not S.PlotService.Contains(e.plot, e.pad.Position) then
		fail("pad_outside_plot", e.name)
	end
end
for _, plot in S.PlotService.Plots do
	local D = MapLayout.PlotSize.Z
	local start = (plot.cframe * CFrame.new(0, 3, -D / 2 - 12)).Position
	for i, ped in plot.pedestals do
		local path = PathfindingService:CreatePath(agent)
		local ok = pcall(function()
			path:ComputeAsync(start, ped.pad.Position + Vector3.new(0, 3, 0))
		end)
		if not ok or path.Status ~= Enum.PathStatus.Success then
			fail("pad_path", `P{plot.index}.ped{i}:{if ok then path.Status.Name else "error"}`)
		end
	end
end

local order = {
	"pad_props",
	"pad_cantouch",
	"pad_covered",
	"pad_buried",
	"pad_standing",
	"incubators",
	"incubator_parts",
	"pedestal_parts",
	"throne_parts",
	"owner_sign",
	"gate_blocked",
	"gate_step",
	"pad_outside_plot",
	"pad_path",
}
local bad = 0
for _, k in order do
	local list = problems[k]
	if list then
		bad += #list
		local shown = {}
		for i = 1, math.min(6, #list) do
			table.insert(shown, list[i])
		end
		add(k, `{#list} FAIL {table.concat(shown, " ")}`)
	else
		add(k, "ok")
	end
end
add("plot_check", if bad == 0 then "PASS" else `FAIL ({bad})`)
return table.concat(lines, "\n")
