-- Costruisce offline (Lune) il Percorso Estremo con ExtremeBuild ed esporta le parti nel formato di
-- tests/cloud/dump_world.luau, piu' CanCollide (cc), tag (tg) e cartella (f). Serve al controllo delle
-- compenetrazioni e ai render senza caricare il luogo sul server:
--   .tools/bin/lune run tests/extreme_dump.luau [--all] [--poses] [--terrain] [--out file.json]
--     (senza --out -> art/out/extreme_world.json)
--   WORLD=art/out/world.json,art/out/extreme_world.json .tools/venv/bin/python tests/render_world.py xfork
-- Gli elementi mobili sono nella posa del server (fermi): le pose nel tempo le calcola Shared.Extreme.
--   --poses: per gli elementi del percorso aggiunge pc (id dell'elemento), kd (tipo), dc/wl/st/sc (deco,
--     sponda, stile, sezione) e, per le parti animate dal client (tag ExtremePiece), sw = pose campionate
--     su un periodo {x, y, z, destra xyz, su xyz, trasparenza} calcolate come updateEntry in
--     src/client/Controllers/Extreme.luau (se cambia il client, va aggiornato clientPoses qui sotto) e
--     pv = posizione del cframe dell'elemento (perno dei tronchi appesi, mozzo delle lame...)
--   --terrain: aggiunge "terrain" = quote delle colonne di voxel (4 stud, come Terrain.Build) sotto il
--     tratto del percorso dove c'e' il terreno
-- Lo usa tests/extreme_overlap.py (controllo delle compenetrazioni).
local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local serde = require("@lune/serde")
local H = require("./harness")

local CFrame = (roblox :: any).CFrame
local Vector3 = (roblox :: any).Vector3

local ExtremeBuild = H.require("ServerScriptService/Server/World/ExtremeBuild")
local Extreme = H.require("ReplicatedStorage/Shared/Extreme")

local root = roblox.Instance.new("Model")
root.Name = "World"
local folder = ExtremeBuild.Build(root)

local function r3(v: number): number
	return math.floor(v * 1000 + 0.5) / 1000
end

-- primo livello sotto la cartella del percorso (Pieces, o il nome della parte stessa)
local function topFolder(d: Instance): string
	local node = d
	while node.Parent and node.Parent ~= folder do
		node = node.Parent
	end
	return node.Name
end

local includeInvisible = table.find(process.args, "--all") ~= nil
local withPoses = table.find(process.args, "--poses") ~= nil
local withTerrain = table.find(process.args, "--terrain") ~= nil

local function pose(cf: any, transparency: number): { number }
	return {
		r3(cf.X),
		r3(cf.Y),
		r3(cf.Z),
		r3(cf.RightVector.X),
		r3(cf.RightVector.Y),
		r3(cf.RightVector.Z),
		r3(cf.UpVector.X),
		r3(cf.UpVector.Y),
		r3(cf.UpVector.Z),
		r3(transparency),
	}
end

-- strisce di ogni nastro (il client le distribuisce sulla lunghezza in base a quante sono)
local stripeCount: { [string]: number } = {}
for _, d in folder:GetDescendants() do
	if d:IsA("BasePart") and d:GetAttribute("Stripe") ~= nil then
		local id = d:GetAttribute("Piece")
		stripeCount[id] = (stripeCount[id] or 0) + 1
	end
end

-- Pose di una parte animata nel corso di un periodo, come le mette il client (updateEntry in
-- src/client/Controllers/Extreme.luau); i tremolii casuali del client sono i quattro casi estremi
local SAMPLES = 48
local function clientPoses(d: any, def: any): { { number } }
	local out = {}
	local function add(cf: any, transparency: number)
		table.insert(out, pose(cf, transparency))
	end
	local function shaken(cf: any, amount: number, transparency: number)
		for _, j in { { -1, -1 }, { -1, 1 }, { 1, -1 }, { 1, 1 } } do
			add(cf * CFrame.new(j[1] * amount, 0, j[2] * amount), transparency)
		end
	end
	local kind = def.kind
	local base = def.transparency or 0
	local per = math.abs(def.period or 1)
	if kind == "Conveyor" and d:GetAttribute("Stripe") ~= nil then
		-- strisce che scorrono: il motivo si ripete ogni lunghezza / velocita'
		local v = def.velocity or Vector3.zero
		per = if math.abs(v.X) > 0 then def.size.X / math.abs(v.X) else 1
	end
	local styleTr = { Laser = 1, Fire = 1, Jet = 1 }
	for k = 0, SAMPLES - 1 do
		local t = per * k / SAMPLES
		if kind == "Mover" then
			add((Extreme.MoverState(def, t)), base)
		elseif kind == "Spinner" then
			add((Extreme.SpinnerState(def, t)), base)
		elseif kind == "Swing" then
			local ang = Extreme.SwingAngle(def, t)
			local length = def.length or 10
			if d:GetAttribute("Rope") then
				add(def.cframe * CFrame.Angles(ang, 0, 0) * CFrame.new(0, -length / 2, 0), d.Transparency)
			else
				add(def.cframe * CFrame.Angles(ang, 0, 0) * CFrame.new(0, -length, 0), base)
			end
		elseif kind == "Sweeper" then
			add((Extreme.SweeperState(def, t)), base)
		elseif kind == "Pulse" then
			local phase = Extreme.PulsePhase(def, t)
			if def.style == "Crusher" then
				local cf = Extreme.CrusherCFrame(def, t)
				if phase == "warn" then
					shaken(cf, 0.15, 0)
				else
					add(cf, 0)
				end
			elseif def.style == "Laser" then
				local wall = def.size.Y > 2
				local tr = if phase == "active" then (if wall then 0.45 else 0.1) elseif phase == "warn" then 0.55 else 1
				styleTr.Laser = math.min(styleTr.Laser, tr)
			elseif def.style == "Fire" then
				local tr = if phase == "active" then 0.35 elseif phase == "warn" then 0.86 else 1
				styleTr.Fire = math.min(styleTr.Fire, tr)
			else
				styleTr.Jet = math.min(styleTr.Jet, if phase == "active" then 0.45 else 1)
			end
		elseif kind == "Faller" then
			local solid = Extreme.FallerSolid(def, t)
			if not solid then
				add(def.cframe - Vector3.new(0, 1.6, 0), 0.8)
			elseif not Extreme.FallerSolid(def, t + 0.6) then
				shaken(def.cframe, 0.12, base)
			else
				add(def.cframe, base)
			end
		elseif kind == "Conveyor" then
			local stripe = d:GetAttribute("Stripe")
			if stripe ~= nil then
				local v = def.velocity or Vector3.zero
				local length = def.size.X
				local n = stripeCount[def.id] or 1
				local x = ((stripe + 0.5) / n * length + t * v.X) % length - length / 2
				add(def.cframe * CFrame.new(x, def.size.Y / 2 + 0.06, 0), d.Transparency)
			else
				add(def.cframe, base)
			end
		else
			add(def.cframe, base)
		end
	end
	if kind == "Pulse" and def.style ~= "Crusher" then
		-- fermi: cambia solo quanto si vedono (la parte e' accesa solo quando e' attiva)
		local tr = styleTr[def.style or "Jet"] or styleTr.Jet
		add(def.cframe, tr)
	end
	if kind == "Conveyor" and d:GetAttribute("Stripe") ~= nil then
		-- in fondo al nastro, un attimo prima di ricominciare
		add(def.cframe * CFrame.new(def.size.X / 2 - 0.001, def.size.Y / 2 + 0.06, 0), d.Transparency)
	end
	return out
end

local parts = {}
for _, d in folder:GetDescendants() do
	local def = nil
	if withPoses and d:IsA("BasePart") then
		local id = d:GetAttribute("Piece")
		if type(id) ~= "string" and topFolder(d) == "Pieces" then
			id = d.Name
		end
		def = if type(id) == "string" then Extreme.Get(id) else nil
	end
	local poses = if def and d:HasTag("ExtremePiece") then clientPoses(d, def) else nil
	local visibleLater = false
	if poses then
		for _, ps in poses do
			visibleLater = visibleLater or ps[10] < 1
		end
	end
	if d:IsA("BasePart") and (d.Transparency < 1 or includeInvisible or visibleLater) then
		local cf = d.CFrame
		local entry: { [string]: any } = {
			c = d.ClassName,
			n = d.Name,
			s = { r3(d.Size.X), r3(d.Size.Y), r3(d.Size.Z) },
			p = { r3(cf.X), r3(cf.Y), r3(cf.Z) },
			r = {
				r3(cf.RightVector.X),
				r3(cf.RightVector.Y),
				r3(cf.RightVector.Z),
				r3(cf.UpVector.X),
				r3(cf.UpVector.Y),
				r3(cf.UpVector.Z),
			},
			k = {
				math.floor(d.Color.R * 255 + 0.5),
				math.floor(d.Color.G * 255 + 0.5),
				math.floor(d.Color.B * 255 + 0.5),
			},
			m = d.Material.Name,
			t = r3(d.Transparency),
			cc = d.CanCollide,
			tg = d:GetTags(),
			f = topFolder(d),
		}
		if d:IsA("Part") then
			entry.sh = d.Shape.Name
			local mesh = d:FindFirstChildOfClass("SpecialMesh")
			if mesh then
				entry.sm = mesh.MeshType.Name
				entry.ms = { r3(mesh.Scale.X), r3(mesh.Scale.Y), r3(mesh.Scale.Z) }
			end
		elseif d:IsA("WedgePart") then
			entry.sh = "Wedge"
		elseif d:IsA("CornerWedgePart") then
			entry.sh = "CornerWedge"
		end
		if def then
			entry.pc = def.id
			entry.kd = def.kind
			entry.dc = def.deco == true
			entry.wl = def.wall == true
			entry.st = def.style
			entry.sc = def.section
			if d:GetAttribute("Rope") then
				entry.ro = "Rope"
			elseif d:GetAttribute("Stripe") ~= nil then
				entry.ro = "Stripe"
			end
		end
		if poses then
			entry.sw = poses
			-- perno / mozzo / centro della posa di riferimento (cframe dell'elemento)
			local pv = def.cframe.Position
			entry.pv = { r3(pv.X), r3(pv.Y), r3(pv.Z) }
		end
		table.insert(parts, entry)
	end
end

local out: { [string]: any } = { count = #parts, parts = parts }
if withTerrain then
	-- colonne di voxel di Terrain.Build (RES 4 a partire da X0 = -324, Z0 = -332; niente terreno a
	-- ovest di x = -324) sotto il primo tratto del percorso e il bivio
	local Terrain = H.require("ServerScriptService/Server/World/Terrain")
	Terrain.Prepare()
	local RES, X0, Z0 = 4, -324, -332
	local ix0, ix1 = 1, math.floor((0 - X0) / RES)
	local iz0 = math.floor((Extreme.Z - 70 - Z0) / RES)
	local iz1 = math.floor((Extreme.Z + 70 - Z0) / RES)
	local rows = {}
	for iz = iz0, iz1 do
		local row = {}
		for ix = ix0, ix1 do
			local h = Terrain.HeightAt(X0 + (ix - 0.5) * RES, Z0 + (iz - 0.5) * RES)
			table.insert(row, r3(h))
		end
		table.insert(rows, row)
	end
	out.terrain = {
		x0 = X0 + (ix0 - 0.5) * RES,
		z0 = Z0 + (iz0 - 0.5) * RES,
		step = RES,
		rows = rows,
	}
end

-- --out percorso.json: file d'uscita diverso (piu' agenti al lavoro insieme non si sovrascrivono)
local outPath = "art/out/extreme_world.json"
local at = table.find(process.args, "--out")
if at and process.args[at + 1] then
	outPath = process.args[at + 1]
end
local dir = string.match(outPath, "^(.*)/[^/]*$")
fs.writeDir(dir or "art/out")
fs.writeFile(outPath, serde.encode("json", out))
print(`[extreme_dump] {#parts} parti -> {outPath}`)
