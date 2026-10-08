-- Ambiente minimo per eseguire moduli "Roblox" con Lune (test locali senza Studio).
local roblox = require("@lune/roblox")

local env = {}
for _, name in { "Vector3", "Vector2", "CFrame", "Color3", "ColorSequence", "ColorSequenceKeypoint", "NumberSequence",
	"NumberSequenceKeypoint", "NumberRange", "UDim", "UDim2", "Rect", "BrickColor", "Enum" } do
	env[name] = (roblox :: any)[name]
end

-- Lune 0.10 calcola CFrame.lookAt con l'asse Z invertito: lo sostituiamo con la versione di Roblox
do
	local RealCFrame = (roblox :: any).CFrame
	local V3 = (roblox :: any).Vector3
	local function lookAt(at, target, up)
		up = up or V3.new(0, 1, 0)
		local look = (target - at).Unit
		local right = look:Cross(up)
		if right.Magnitude < 1e-6 then
			right = V3.new(1, 0, 0)
		end
		right = right.Unit
		local up2 = right:Cross(look)
		return RealCFrame.fromMatrix(at, right, up2)
	end
	env.CFrame = setmetatable({ lookAt = lookAt }, { __index = RealCFrame })
end

-- Random deterministico (xorshift) compatibile con l'uso nel progetto
local Random = {}
Random.__index = Random
function Random.new(seed: number?)
	local s = math.floor(seed or os.clock() * 1e6) % 2147483647
	if s == 0 then
		s = 1
	end
	return setmetatable({ state = s }, Random)
end
function Random:_next(): number
	local x = self.state
	x = bit32.bxor(x, bit32.lshift(x, 13))
	x = bit32.bxor(x, bit32.rshift(x, 17))
	x = bit32.bxor(x, bit32.lshift(x, 5))
	self.state = x
	return x / 4294967296
end
function Random:NextNumber(a: number?, b: number?): number
	local r = self:_next()
	if a and b then
		return a + (b - a) * r
	end
	return r
end
function Random:NextInteger(a: number, b: number): number
	return math.floor(a + (b - a + 1) * self:_next())
end
env.Random = Random

-- math.noise (Perlin semplificato, solo per i test)
local function hash(i: number, j: number, k: number): number
	local h = (i * 374761393 + j * 668265263 + k * 1442695040888963407) % 2147483647
	h = bit32.bxor(h, bit32.rshift(h, 13)) * 1274126177 % 2147483647
	return (h % 1000) / 500 - 1
end
local function lerp(a, b, t)
	return a + (b - a) * t
end
local function fade(t)
	return t * t * t * (t * (t * 6 - 15) + 10)
end
local noiseMath = setmetatable({
	noise = function(x: number, y: number?, z: number?)
		y = y or 0
		z = z or 0
		local xi, yi, zi = math.floor(x), math.floor(y :: number), math.floor(z :: number)
		local xf, yf = x - xi, (y :: number) - yi
		local u, v = fade(xf), fade(yf)
		local a = lerp(hash(xi, yi, zi), hash(xi + 1, yi, zi), u)
		local b = lerp(hash(xi, yi + 1, zi), hash(xi + 1, yi + 1, zi), u)
		return lerp(a, b, v) * 0.5
	end,
}, { __index = math })
env.math = noiseMath

function env.install(target)
	for k, v in env do
		if k ~= "install" then
			target[k] = v
		end
	end
end

return env
