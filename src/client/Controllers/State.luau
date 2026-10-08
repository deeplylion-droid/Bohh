-- Copia locale dei dati del giocatore, aggiornata dal server (StateInit / StateSet).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)
local Signal = require(ReplicatedStorage.Shared.Util.Signal)

local State = {}

State.Data = nil :: any
State.Ready = false
State.Loaded = Signal.new()
State.Changed = Signal.new() -- (path: {string}, value)

local listeners: { [string]: { (any) -> () } } = {}

function State.Init(_C) end

-- Valore a un percorso, es. State.Get("Upgrades", "Speed")
function State.Get(...: string): any
	local node = State.Data
	for _, k in { ... } do
		if type(node) ~= "table" then
			return nil
		end
		node = node[k]
	end
	return node
end

-- Chiama fn(valore) ora (se pronto) e ogni volta che la chiave principale cambia
function State.Watch(key: string, fn: (any) -> ()): () -> ()
	listeners[key] = listeners[key] or {}
	table.insert(listeners[key], fn)
	if State.Ready then
		task.spawn(fn, State.Data[key])
	end
	return function()
		local list = listeners[key]
		local i = list and table.find(list, fn)
		if i then
			table.remove(list, i)
		end
	end
end

local function notify(key: string)
	for _, fn in listeners[key] or {} do
		task.spawn(fn, State.Data[key])
	end
end

function State.WaitReady()
	if not State.Ready then
		State.Loaded:Wait()
	end
end

function State.Start()
	Net.Event("StateInit").OnClientEvent:Connect(function(data)
		State.Data = data
		State.Ready = true
		State.Loaded:Fire(data)
		for key in listeners do
			notify(key)
		end
	end)
	Net.Event("StateSet").OnClientEvent:Connect(function(path, value)
		if not State.Data then
			return
		end
		local node = State.Data
		for i = 1, #path - 1 do
			local k = path[i]
			if type(node[k]) ~= "table" then
				node[k] = {}
			end
			node = node[k]
		end
		node[path[#path]] = value
		State.Changed:Fire(path, value)
		notify(path[1])
	end)
end

return State
