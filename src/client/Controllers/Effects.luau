-- Effetti visivi e sonori inviati dal server (Effect), scossoni della camera, numeri volanti.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local Debris = game:GetService("Debris")

local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)

local Effects = {}

local C
local handlers: { [string]: { (any) -> () } } = {}
local shake = { amount = 0, untilT = 0 }
local player = Players.LocalPlayer

local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"
local SMOKE = "rbxasset://textures/particles/smoke_main.dds"
local FIRE = "rbxasset://textures/particles/fire_main.dds"

function Effects.Init(controllers)
	C = controllers
end

function Effects.On(name: string, fn: (any) -> ())
	handlers[name] = handlers[name] or {}
	table.insert(handlers[name], fn)
end

function Effects.CameraShake(amount: number, duration: number)
	shake.amount = math.max(shake.amount, amount)
	shake.untilT = math.max(shake.untilT, os.clock() + duration)
end

-- Esplosione di particelle in un punto
function Effects.Burst(position: Vector3, color: ColorSequence | Color3, count: number, texture: string?, speed: number?, size: number?)
	local att = Instance.new("Attachment")
	att.WorldPosition = position
	att.Parent = workspace.Terrain
	local p = Instance.new("ParticleEmitter")
	p.Texture = texture or SPARKLE
	p.Color = if typeof(color) == "Color3" then ColorSequence.new(color) else color
	p.LightEmission = 0.7
	p.Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, size or 0.9), NumberSequenceKeypoint.new(1, 0) })
	p.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0), NumberSequenceKeypoint.new(1, 1) })
	p.Lifetime = NumberRange.new(0.5, 1.1)
	p.Speed = NumberRange.new((speed or 14) * 0.5, speed or 14)
	p.SpreadAngle = Vector2.new(180, 180)
	p.Acceleration = Vector3.new(0, -20, 0)
	p.Rate = 0
	p.Parent = att
	p:Emit(count)
	Debris:AddItem(att, 2.5)
end

-- Numero che sale e svanisce (monete raccolte)
function Effects.FloatText(position: Vector3, text: string, color: Color3?)
	local Kit = C.UI.Kit
	local att = Instance.new("Attachment")
	att.WorldPosition = position
	att.Parent = workspace.Terrain
	local gui = Kit.New("BillboardGui", { Size = UDim2.fromOffset(220, 60), AlwaysOnTop = true, LightInfluence = 0, Adornee = att, Parent = att })
	local label = Kit.Text({ Text = text, TextColor3 = color or Kit.Theme.Gold, Size = UDim2.fromScale(1, 1), Parent = gui })
	Kit.Pop(label)
	Kit.Tween(gui, 1.2, { StudsOffset = Vector3.new(0, 4, 0) })
	task.delay(0.8, function()
		Kit.Tween(label, 0.4, { TextTransparency = 1 })
		local s = label:FindFirstChildOfClass("UIStroke")
		if s then
			Kit.Tween(s, 0.4, { Transparency = 1 })
		end
	end)
	Debris:AddItem(att, 1.4)
end

local function myPosition(): Vector3?
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	return hrp and hrp.Position
end

local function warnCircle(position: Vector3, time: number, color: Color3)
	local p = Instance.new("Part")
	p.Shape = Enum.PartType.Cylinder
	p.Size = Vector3.new(0.3, 2, 2)
	p.CFrame = CFrame.new(position + Vector3.new(0, 0.3, 0)) * CFrame.Angles(0, 0, math.rad(90))
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Material = Enum.Material.Neon
	p.Color = color
	p.Transparency = 0.35
	p.Parent = workspace
	C.UI.Kit.Tween(p, time, { Size = Vector3.new(0.3, 24, 24) }, Enum.EasingStyle.Linear)
	Debris:AddItem(p, time + 0.1)
end

local BUILTIN: { [string]: (any) -> () } = {
	Pickup = function(params)
		C.Audio.Play("Pickup")
		local pos = myPosition()
		if pos then
			local r = Rarities.List[params.rarity or "Common"]
			Effects.Burst(pos + Vector3.new(0, 5, 0), r and r.color or Color3.new(1, 1, 1), 18)
		end
	end,
	Deliver = function(params)
		C.Audio.Play("Deliver")
		local _ = params
	end,
	Collect = function(params)
		C.Audio.Play("Coin")
		local pos = params.position or myPosition()
		if pos then
			Effects.FloatText(pos + Vector3.new(0, 3, 0), "+" .. Format.Money(params.amount))
			Effects.Burst(pos + Vector3.new(0, 1, 0), Color3.fromRGB(255, 214, 60), 14, nil, 10, 0.7)
		end
	end,
	Coins = function(params)
		C.Audio.Play(if params.big then "CoinsBig" else "Coin")
		local pos = myPosition()
		if pos then
			Effects.FloatText(pos + Vector3.new(0, 5, 0), "+" .. Format.Money(params.amount))
		end
	end,
	Purchase = function()
		C.Audio.Play("Purchase")
	end,
	Upgrade = function()
		C.Audio.Play("Upgrade")
		local pos = myPosition()
		if pos then
			Effects.Burst(pos, Color3.fromRGB(110, 220, 255), 30, nil, 18)
		end
	end,
	Slap = function(params)
		C.Audio.Play("Slap", params.position, 1)
		Effects.Burst(params.position + Vector3.new(0, 2, 0), Color3.fromRGB(255, 240, 120), 16, nil, 22, 1.2)
		local pos = myPosition()
		if pos and (pos - params.position).Magnitude < 6 then
			Effects.CameraShake(0.5, 0.4)
		end
	end,
	Hit = function(params)
		C.Audio.Play("Bonk", params.position, 1)
		Effects.Burst(params.position, Color3.fromRGB(255, 255, 255), 14, SMOKE, 10, 2)
	end,
	Poof = function(params)
		Effects.Burst(params.position, Color3.fromRGB(240, 240, 255), 16, SMOKE, 8, 2.5)
	end,
	EggReturn = function(params)
		Effects.Burst(params.position + Vector3.new(0, 2, 0), Color3.fromRGB(255, 255, 200), 12)
	end,
	Alarm = function()
		C.Audio.Play("Alarm")
	end,
	StealSuccess = function()
		C.Audio.Play("Fanfare")
	end,
	Barrier = function(params)
		C.Audio.Play(if params.on then "BarrierOn" else "BarrierOff")
	end,
	Trap = function(params)
		C.Audio.Play("Trap", params.position, 1)
		Effects.Burst(params.position + Vector3.new(0, 1, 0), Color3.fromRGB(255, 220, 80), 20)
	end,
	MeteorWarn = function(params)
		warnCircle(params.position, params.time or 2.5, Color3.fromRGB(170, 110, 255))
		C.Audio.Play("MeteorFall", params.position, 1)
	end,
	MeteorImpact = function(params)
		C.Audio.Play("Explosion", params.position, 1.2)
		Effects.Burst(params.position, ColorSequence.new(Color3.fromRGB(200, 140, 255), Color3.fromRGB(80, 40, 200)), 50, SPARKLE, 40, 2)
		Effects.Burst(params.position, Color3.fromRGB(120, 100, 140), 24, SMOKE, 16, 5)
		local pos = myPosition()
		if pos and (pos - params.position).Magnitude < 60 then
			Effects.CameraShake(0.8, 0.6)
		end
	end,
	LavaBombWarn = function(params)
		warnCircle(params.position, params.time or 2, Color3.fromRGB(255, 90, 30))
	end,
	LavaBombImpact = function(params)
		C.Audio.Play("Explosion", params.position, 1)
		Effects.Burst(params.position, ColorSequence.new(Color3.fromRGB(255, 200, 60), Color3.fromRGB(255, 60, 20)), 40, FIRE, 30, 2)
		local pos = myPosition()
		if pos and (pos - params.position).Magnitude < 40 then
			Effects.CameraShake(0.6, 0.5)
		end
	end,
	Burn = function(params)
		C.Audio.Play("Sizzle", params.position, 1)
		Effects.Burst(params.position, Color3.fromRGB(255, 120, 30), 26, FIRE, 12, 2)
	end,
	GuardianRoar = function(params)
		C.Audio.Play("Roar", params.position, 1.2)
		Effects.CameraShake(0.3, 0.8)
	end,
	GuardianSlam = function(params)
		C.Audio.Play("Explosion", params.position, 0.9)
		Effects.Burst(params.position, Color3.fromRGB(200, 200, 220), 24, SMOKE, 18, 3)
	end,
}

function Effects.Start()
	for name, fn in BUILTIN do
		Effects.On(name, fn)
	end
	Net.Event("Effect").OnClientEvent:Connect(function(name, params)
		for _, fn in handlers[name] or {} do
			task.spawn(fn, params or {})
		end
	end)
	-- scossone della camera
	RunService:BindToRenderStep("CameraShake", Enum.RenderPriority.Camera.Value + 1, function()
		local now = os.clock()
		if now < shake.untilT then
			local a = shake.amount * (shake.untilT - now)
			local cam = workspace.CurrentCamera
			cam.CFrame = cam.CFrame * CFrame.Angles(math.rad((math.random() - 0.5) * a * 2), math.rad((math.random() - 0.5) * a * 2), 0)
		else
			shake.amount = 0
		end
	end)
end

return Effects
