-- Generatore pseudo-casuale deterministico (xorshift a 32 bit), identico in Roblox e nei test offline
-- con Lune. Il Random di Roblox fuori da Roblox non c'e' (tests/roblox_env.luau usa questo stesso
-- algoritmo), quindi tutto cio' che deve venire uguale nel gioco e nei controlli offline (sponde del
-- Percorso Estremo, arredo) usa Rng: stessa interfaccia di Random (NextNumber, NextInteger).
local Rng = {}
Rng.__index = Rng

export type Rng = typeof(setmetatable({} :: { state: number }, Rng))

function Rng.new(seed: number): Rng
	local s = math.floor(seed) % 2147483647
	if s == 0 then
		s = 1
	end
	return setmetatable({ state = s }, Rng)
end

-- numero in [0, 1)
function Rng.Next(self: Rng): number
	local x = self.state
	x = bit32.bxor(x, bit32.lshift(x, 13))
	x = bit32.bxor(x, bit32.rshift(x, 17))
	x = bit32.bxor(x, bit32.lshift(x, 5))
	self.state = x
	return x / 4294967296
end

function Rng.NextNumber(self: Rng, a: number?, b: number?): number
	local r = self:Next()
	if a and b then
		return a + (b - a) * r
	end
	return r
end

function Rng.NextInteger(self: Rng, a: number, b: number): number
	return math.floor(a + (b - a + 1) * self:Next())
end

return Rng
