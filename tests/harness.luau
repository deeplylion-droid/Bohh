-- Mini "Rojo" per Lune: carica i moduli del progetto risolvendo game/script/require come in Roblox.
-- Uso: local H = require("./harness"); local M = H.require("ReplicatedStorage/Shared/MapLayout")
local fs = require("@lune/fs")
local luau = require("@lune/luau")
local serde = require("@lune/serde")
local env = require("./roblox_env")

local H = {}

local project = serde.decode("json", fs.readFile("default.project.json"))

-- percorso DataModel ("ReplicatedStorage/Shared") -> percorso su disco
local mounts: { [string]: string } = {}
local function walk(node, prefix: string)
	for k, v in node do
		if type(v) == "table" and string.sub(k, 1, 1) ~= "$" then
			local p = if prefix == "" then k else prefix .. "/" .. k
			if v["$path"] then
				mounts[p] = v["$path"]
			end
			walk(v, p)
		end
	end
end
walk(project.tree, "")

local function resolveFs(dmPath: string): string?
	-- trova il mount piu' lungo che e' prefisso del percorso
	local best, bestLen = nil, -1
	for m, fsPath in mounts do
		if (dmPath == m or string.sub(dmPath, 1, #m + 1) == m .. "/") and #m > bestLen then
			best, bestLen = fsPath, #m
		end
	end
	if not best then
		return nil
	end
	local rest = string.sub(dmPath, bestLen + 2)
	local base = if rest == "" then best else best .. "/" .. rest
	for _, cand in { base .. ".luau", base .. ".server.luau", base .. ".client.luau", base .. "/init.luau", base } do
		if fs.isFile(cand) or fs.isDir(cand) then
			return cand
		end
	end
	return nil
end

local cache: { [string]: any } = {}
local Proxy = {}

local function proxy(dmPath: string)
	return setmetatable({ __dm = dmPath }, Proxy)
end

Proxy.__index = function(self, key)
	if key == "Parent" then
		local p = string.match(self.__dm, "^(.*)/[^/]+$")
		return proxy(p or "")
	elseif key == "Name" then
		return string.match(self.__dm, "([^/]+)$")
	elseif key == "FindFirstChild" or key == "WaitForChild" then
		return function(s, name)
			local child = s.__dm .. "/" .. name
			if resolveFs(child) then
				return proxy(child)
			end
			return nil
		end
	elseif key == "IsA" then
		return function()
			return false
		end
	end
	return proxy(self.__dm .. "/" .. key)
end

local stubServices = {
	RunService = { IsServer = function() return true end, IsClient = function() return false end, IsStudio = function() return true end },
}

local game = {
	GetService = function(_, name: string)
		if stubServices[name] then
			return stubServices[name]
		end
		return proxy(name)
	end,
}

local loadModule

local function requireProxy(p)
	if type(p) == "string" then
		return require(p)
	end
	return loadModule(p.__dm)
end

loadModule = function(dmPath: string)
	if cache[dmPath] ~= nil then
		return cache[dmPath]
	end
	local file = resolveFs(dmPath)
	assert(file, "modulo non trovato: " .. dmPath)
	if fs.isDir(file) then
		file = file .. "/init.luau"
	end
	local g = setmetatable({}, { __index = _G })
	env.install(g)
	g.game = game
	g.workspace = { Terrain = {} }
	g.script = proxy(dmPath)
	g.require = requireProxy
	g.typeof = typeof
	g.warn = print
	g.task = { wait = function() end, spawn = function(f, ...) f(...) end, defer = function(f, ...) f(...) end, delay = function() end }
	local fn = luau.load(fs.readFile(file), { debugName = file, environment = g })
	local result = fn()
	cache[dmPath] = result
	return result
end

H.require = loadModule
H.game = game
return H
