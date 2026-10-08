--!strict
-- Segnale leggero (connessioni con Disconnect), sul modello di GoodSignal.

export type Connection = {
	Connected: boolean,
	Disconnect: (self: Connection) -> (),
}

export type Signal<T...> = {
	Connect: (self: Signal<T...>, fn: (T...) -> ()) -> Connection,
	Once: (self: Signal<T...>, fn: (T...) -> ()) -> Connection,
	Fire: (self: Signal<T...>, T...) -> (),
	Wait: (self: Signal<T...>) -> T...,
	DisconnectAll: (self: Signal<T...>) -> (),
}

local Signal = {}
Signal.__index = Signal

local Conn = {}
Conn.__index = Conn

function Conn:Disconnect()
	if not self.Connected then
		return
	end
	self.Connected = false
	local list = self._signal._handlers
	local idx = table.find(list, self)
	if idx then
		table.remove(list, idx)
	end
end

function Signal.new<T...>(): Signal<T...>
	return (setmetatable({ _handlers = {} }, Signal) :: any) :: Signal<T...>
end

function Signal:Connect(fn)
	local c = setmetatable({ Connected = true, _signal = self, _fn = fn }, Conn)
	table.insert(self._handlers, c)
	return c
end

function Signal:Once(fn)
	local c
	c = self:Connect(function(...)
		c:Disconnect()
		fn(...)
	end)
	return c
end

function Signal:Fire(...)
	-- copia: un handler puo' disconnettersi durante il ciclo
	local list = table.clone(self._handlers)
	for _, c in list do
		if c.Connected then
			task.spawn(c._fn, ...)
		end
	end
end

function Signal:Wait()
	local thread = coroutine.running()
	self:Once(function(...)
		task.spawn(thread, ...)
	end)
	return coroutine.yield()
end

function Signal:DisconnectAll()
	for _, c in self._handlers do
		c.Connected = false
	end
	table.clear(self._handlers)
end

return Signal
