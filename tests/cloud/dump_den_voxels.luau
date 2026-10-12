-- Esporta i voxel del terreno attorno alla Tana dei Mostri (tunnel e grotta scavati) per il render di
-- controllo: occupazione 0-255 e materiale, a fette lungo x. Uscita: art/out/den_voxels.json
local HttpService = game:GetService("HttpService")
local ServerScriptService = game:GetService("ServerScriptService")

require(ServerScriptService.Server.Boot).Start({ test = true })

local RES = 4
local lo = Vector3.new(-32, 64, 680)
local hi = Vector3.new(172, 168, 952)
local region = Region3.new(lo, hi):ExpandToGrid(RES)
local mats, occ = workspace.Terrain:ReadVoxels(region, RES)
local names = {}
local index = {}
local slices = {}
for ix = 1, #occ do
	local rows = {}
	for iy = 1, #occ[ix] do
		local row = table.create(#occ[ix][iy])
		for iz = 1, #occ[ix][iy] do
			local m = mats[ix][iy][iz].Name
			if not index[m] then
				table.insert(names, m)
				index[m] = #names
			end
			row[iz] = string.format("%d.%d", math.floor(occ[ix][iy][iz] * 255 + 0.5), index[m])
		end
		table.insert(rows, table.concat(row, ","))
	end
	table.insert(slices, rows)
end
local min = region.CFrame.Position - region.Size / 2
return HttpService:JSONEncode({
	x0 = min.X,
	y0 = min.Y,
	z0 = min.Z,
	res = RES,
	materials = names,
	slices = slices,
})
