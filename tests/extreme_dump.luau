-- Costruisce offline (Lune) il Percorso Estremo con ExtremeBuild ed esporta le parti nel formato di
-- tests/cloud/dump_world.luau, piu' CanCollide (cc), tag (tg) e cartella (f). Serve al controllo delle
-- compenetrazioni e ai render senza caricare il luogo sul server:
--   .tools/bin/lune run tests/extreme_dump.luau [--all] [--out file.json]  -> art/out/extreme_world.json
--   WORLD=art/out/world.json,art/out/extreme_world.json .tools/venv/bin/python tests/render_world.py xfork
-- Gli elementi mobili sono nella posa del server (fermi): le pose nel tempo le calcola Shared.Extreme.
local fs = require("@lune/fs")
local process = require("@lune/process")
local roblox = require("@lune/roblox")
local serde = require("@lune/serde")
local H = require("./harness")

local ExtremeBuild = H.require("ServerScriptService/Server/World/ExtremeBuild")

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
local parts = {}
for _, d in folder:GetDescendants() do
	if d:IsA("BasePart") and (d.Transparency < 1 or includeInvisible) then
		local cf = d.CFrame
		local entry = {
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
			end
		elseif d:IsA("WedgePart") then
			entry.sh = "Wedge"
		elseif d:IsA("CornerWedgePart") then
			entry.sh = "CornerWedge"
		end
		table.insert(parts, entry)
	end
end
-- --out percorso.json: file d'uscita diverso (piu' agenti al lavoro insieme non si sovrascrivono)
local outPath = "art/out/extreme_world.json"
local at = table.find(process.args, "--out")
if at and process.args[at + 1] then
	outPath = process.args[at + 1]
end
fs.writeDir("art/out")
fs.writeFile(outPath, serde.encode("json", { count = #parts, parts = parts }))
print(`[extreme_dump] {#parts} parti -> {outPath}`)
