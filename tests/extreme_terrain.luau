-- Quota del terreno lungo l'asse del Percorso Estremo e sotto il ponticello d'ingresso: il percorso
-- deve stare sopra il terreno (le sponde possono affondarci, i pavimenti e l'acqua no).
-- Uso (dalla radice): .tools/bin/lune run tests/extreme_terrain.luau [z] [startX]
local process = require("@lune/process")
local H = require("./harness")
local Terrain = H.require("ServerScriptService/Server/World/Terrain")
Terrain.Prepare()
local Z = tonumber(process.args[1]) or 192
local X0 = tonumber(process.args[2]) or -46
local worst, worstX = -math.huge, 0
for x = X0 + 30, X0 - 700, -4 do
	local maxH = -math.huge
	for dz = -24, 24, 4 do
		local h = Terrain.HeightAt(x, Z + dz)
		maxH = math.max(maxH, h)
	end
	if x % 40 == 0 or maxH > worst then
		print(string.format("x=%5d  terreno max %.1f", x, maxH))
	end
	if x < X0 and maxH > worst then
		worst, worstX = maxH, x
	end
end
print(string.format("massimo dentro il percorso: %.1f a x=%d", worst, worstX))
