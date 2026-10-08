--!strict
-- Raccoglie connessioni, istanze, thread e funzioni da ripulire insieme (Trove:Clean()).

local Trove = {}
Trove.__index = Trove

export type Trove = typeof(setmetatable({} :: { _items: { any } }, Trove))

function Trove.new(): Trove
	return setmetatable({ _items = {} }, Trove)
end

function Trove.Add<T>(self: Trove, item: T): T
	table.insert(self._items, item)
	return item
end

function Trove.Connect(self: Trove, signal: RBXScriptSignal, fn: (...any) -> ()): RBXScriptConnection
	return self:Add(signal:Connect(fn))
end

local function cleanItem(item: any)
	local t = typeof(item)
	if t == "RBXScriptConnection" then
		item:Disconnect()
	elseif t == "Instance" then
		item:Destroy()
	elseif t == "thread" then
		pcall(task.cancel, item)
	elseif t == "function" then
		item()
	elseif t == "table" then
		if type(item.Destroy) == "function" then
			item:Destroy()
		elseif type(item.Disconnect) == "function" then
			item:Disconnect()
		elseif type(item.Clean) == "function" then
			item:Clean()
		end
	end
end

function Trove.Clean(self: Trove)
	local items = self._items
	self._items = {}
	for i = #items, 1, -1 do
		cleanItem(items[i])
	end
end

function Trove.Destroy(self: Trove)
	self:Clean()
end

return Trove
