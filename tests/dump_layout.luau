-- Esporta la geometria della mappa in JSON per controllarla con un disegno dall'alto.
local fs = require("@lune/fs")
local serde = require("@lune/serde")
local luau = require("@lune/luau")
local env = require("./roblox_env")

local function load(path: string)
	local src = fs.readFile(path)
	local g = setmetatable({}, { __index = _G })
	env.install(g)
	g.typeof = typeof
	local fn = luau.load(src, { debugName = path, environment = g })
	return fn()
end

local L = load("src/shared/MapLayout.luau")
local out = { path = {}, shelters = {}, nests = {}, lairs = {}, legs = L.Legs, length = L.PathLength }
for _, smp in L.SamplePath(4) do
	table.insert(out.path, { smp.pos.X, smp.pos.Y, smp.pos.Z, smp.zone })
end
for i = 1, #L.Shelters do
	local cf = L.ShelterFrame(i)
	table.insert(out.shelters, { cf.Position.X, cf.Position.Y, cf.Position.Z, cf.LookVector.X, cf.LookVector.Z })
end
for _, n in L.Nests do
	table.insert(out.nests, { n.cframe.Position.X, n.cframe.Position.Y, n.cframe.Position.Z, n.zone })
end
for _, l in L.Lairs do
	table.insert(out.lairs, { l.center.X, l.center.Y, l.center.Z, l.radius, l.leash })
end
for i = 1, 8 do
	local cf = L.PlotFrame(i)
	out["plot" .. i] = { cf.Position.X, cf.Position.Z, cf.LookVector.X, cf.LookVector.Z }
end
fs.writeFile("art/out/layout.json", serde.encode("json", out))
print("path length", L.PathLength, "nests", #L.Nests, "shelters", #L.Shelters)
