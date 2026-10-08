-- Calcola la mappa delle altezze del terreno (passo 4 stud) per il render di controllo.
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local H = require("./harness")
local Terrain = H.require("ServerScriptService/Server/World/Terrain")
Terrain.Prepare()
local ok = true
local X0, X1, Z0, Z1, STEP = -324, 324, -332, 832, 4
local rows, kinds, zones = {}, {}, {}
local t0 = os.clock()
for z = Z0, Z1, STEP do
	local row, krow, zrow = {}, {}, {}
	for x = X0, X1, STEP do
		local h, k, zn = Terrain.HeightAt(x, z)
		table.insert(row, h)
		table.insert(krow, k)
		table.insert(zrow, zn)
	end
	table.insert(rows, row)
	table.insert(kinds, krow)
	table.insert(zones, zrow)
end
-- materiali calcolati con la stessa funzione del gioco (pendenza dalle differenze finite)
local mats = {}
for j = 1, #rows do
	local mrow = {}
	for i = 1, #rows[j] do
		local hl = rows[j][math.max(i - 1, 1)]
		local hr = rows[j][math.min(i + 1, #rows[j])]
		local hd = rows[math.max(j - 1, 1)][i]
		local hu = rows[math.min(j + 1, #rows)][i]
		local slope = math.sqrt(((hr - hl) / (2 * STEP)) ^ 2 + ((hu - hd) / (2 * STEP)) ^ 2)
		local m = Terrain.SurfaceMaterial(rows[j][i], kinds[j][i], zones[j][i], slope)
		table.insert(mrow, m.Name)
	end
	table.insert(mats, mrow)
end
local colors = {}
for m, c in Terrain.Colors do
	colors[m.Name] = { c.R, c.G, c.B }
end
print("heights in", os.clock() - t0, "s", ok)
fs.writeFile("art/out/terrain.json", serde.encode("json", { x0 = X0, z0 = Z0, step = STEP, rows = rows, mats = mats, colors = colors }))
