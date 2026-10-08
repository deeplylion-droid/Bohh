-- Atmosfera locale: nebbia bassa, lucciole, pioggia e lampi, luci che tremano (e muoiono quando la
-- creatura è vicina), suoni d'ambiente, battito cardiaco, respiro affannato e rumori improvvisi.
local Lighting = game:GetService("Lighting")
local CollectionService = game:GetService("CollectionService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Audio = require(Shared:WaitForChild("Audio"))
local Sfx = require(Shared:WaitForChild("Sfx"))

local Ambience = {}

local SMOKE = "rbxasset://textures/particles/smoke_main.dds"
local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"

local function rakeRoot(): BasePart?
	local folder = workspace:FindFirstChild("RakeHunt")
	local rake = folder and folder:FindFirstChild("TheRake")
	return rake and rake:FindFirstChild("HumanoidRootPart") :: BasePart?
end
Ambience.rakeRoot = rakeRoot

local function emitterPart(parent: Instance, size: Vector3): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Transparency = 1
	p.Size = size
	p.Parent = parent
	return p
end

local function seq(points: { { number } }): NumberSequence
	local kps = {}
	for _, p in points do
		table.insert(kps, NumberSequenceKeypoint.new(p[1], p[2]))
	end
	return NumberSequence.new(kps)
end

local function groundBelow(pos: Vector3): number
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Include
	params.FilterDescendantsInstances = { workspace.Terrain }
	local hit = workspace:Raycast(pos + Vector3.new(0, 20, 0), Vector3.new(0, -200, 0), params)
	return hit and hit.Position.Y or pos.Y - 3
end

-- Ritorna una funzione che va chiamata a ogni frame con lo stato corrente
function Ambience.start(player: Player, state: Folder, onHallucination: () -> ())
	local folder = Instance.new("Folder")
	folder.Name = "EffettiLocali"
	folder.Parent = workspace

	-- Nebbia che striscia a terra intorno al giocatore
	local fogPart = emitterPart(folder, Vector3.new(170, 2, 170))
	local fog = Instance.new("ParticleEmitter")
	fog.Texture = SMOKE
	fog.Color = ColorSequence.new(Color3.fromRGB(150, 160, 176))
	fog.LightInfluence = 1
	fog.LightEmission = 0
	fog.Size = seq({ { 0, 9 }, { 1, 18 } })
	fog.Transparency = seq({ { 0, 1 }, { 0.3, 0.84 }, { 0.7, 0.87 }, { 1, 1 } })
	fog.Lifetime = NumberRange.new(10, 16)
	fog.Rate = 16
	fog.Speed = NumberRange.new(0.3, 1.2)
	fog.SpreadAngle = Vector2.new(180, 180)
	fog.Rotation = NumberRange.new(0, 360)
	fog.RotSpeed = NumberRange.new(-6, 6)
	fog.Acceleration = Vector3.new(0.3, 0, 0.15)
	fog.Parent = fogPart

	-- Lucciole nella palude e al campeggio
	local fliesPart = emitterPart(folder, Vector3.new(90, 8, 90))
	local flies = Instance.new("ParticleEmitter")
	flies.Texture = SPARKLE
	flies.Color = ColorSequence.new(Color3.fromRGB(200, 255, 120))
	flies.LightEmission = 1
	flies.LightInfluence = 0
	flies.Size = seq({ { 0, 0.1 }, { 0.5, 0.25 }, { 1, 0.08 } })
	flies.Transparency = seq({ { 0, 1 }, { 0.2, 0.1 }, { 0.4, 0.8 }, { 0.6, 0.1 }, { 0.8, 0.7 }, { 1, 1 } })
	flies.Lifetime = NumberRange.new(3, 6)
	flies.Rate = 7
	flies.Speed = NumberRange.new(0.3, 1)
	flies.SpreadAngle = Vector2.new(180, 180)
	flies.Enabled = false
	flies.Parent = fliesPart

	-- Pioggia
	local rainPart = emitterPart(folder, Vector3.new(120, 1, 120))
	local rain = Instance.new("ParticleEmitter")
	rain.Color = ColorSequence.new(Color3.fromRGB(170, 182, 200))
	rain.LightInfluence = 1
	rain.Size = NumberSequence.new(0.08)
	rain.Squash = NumberSequence.new(-2.5)
	rain.Transparency = NumberSequence.new(0.45)
	rain.Orientation = Enum.ParticleOrientation.VelocityParallel
	rain.EmissionDirection = Enum.NormalId.Bottom
	rain.Lifetime = NumberRange.new(0.9, 1.1)
	rain.Speed = NumberRange.new(75, 85)
	rain.Rate = 900
	rain.Enabled = false
	rain.Parent = rainPart

	local lightning = Instance.new("ColorCorrectionEffect")
	lightning.Name = "Fulmine"
	lightning.Parent = Lighting

	-- Suoni
	local ambience = Instance.new("Sound")
	ambience.Name = "Ambiente"
	ambience.SoundId = Audio.AMBIENCE
	ambience.Looped = true
	ambience.Volume = 0.55
	ambience.Parent = SoundService
	ambience:Play()
	local rainSound = Sfx.new("Rain", SoundService, { Volume = 0 })
	-- temporale
	local stormRain = Sfx.new("HeavyRain", SoundService, { Volume = 0 })
	local stormWind = Sfx.new("Wind", SoundService, { Volume = 0 })
	stormRain:Play()
	stormWind:Play()
	local stormLevel = 0
	local nextStormBolt = 0
	local flash = Instance.new("PointLight") -- lampo che illumina davvero il bosco attorno a te
	flash.Range = 60
	flash.Brightness = 0
	flash.Shadows = true
	flash.Color = Color3.fromRGB(200, 215, 255)
	flash.Parent = rainPart
	local heartbeat = Sfx.new("Heartbeat", SoundService, { Volume = 0 })
	local breathing = Sfx.new("Breathing", SoundService, { Volume = 0 })
	rainSound:Play()
	heartbeat:Play()
	breathing:Play()

	-- Luci tremolanti
	local lights: { [Light]: number } = {}
	local function track(light: Instance)
		if light:IsA("Light") then
			lights[light] = math.random() * 100
		end
	end
	for _, l in CollectionService:GetTagged("Flicker") do
		track(l)
	end
	CollectionService:GetInstanceAddedSignal("Flicker"):Connect(track)
	CollectionService:GetInstanceRemovedSignal("Flicker"):Connect(function(l)
		lights[l :: Light] = nil
	end)

	local nextFollow, nextSnap, nextBolt = 0, os.clock() + 25, os.clock() + 20
	local nextFlicker = 0

	return function(dt: number, info: { exhausted: boolean, panic: boolean })
		local now = os.clock()
		local camera = workspace.CurrentCamera
		local camPos = camera.CFrame.Position
		local phase = state:GetAttribute("Phase")
		local night = Lighting.ClockTime >= 19.5 or Lighting.ClockTime < 6
		local storm = state:GetAttribute("Storm") == true and phase == "Notte"
		stormLevel = math.clamp(stormLevel + (storm and dt / 3 or -dt / 5), 0, 1)
		local raining = (state:GetAttribute("Weather") == "Pioggia" or stormLevel > 0.05) and phase == "Notte"

		if now >= nextFollow then
			nextFollow = now + 0.3
			local ground = groundBelow(camPos)
			fogPart.CFrame = CFrame.new(camPos.X, ground + 1.5, camPos.Z)
			fliesPart.CFrame = CFrame.new(camPos.X, ground + 4, camPos.Z)
			local swampOrCamp = camPos.X < 0
			flies.Enabled = night and swampOrCamp and not raining
			fog.Rate = (state:GetAttribute("Weather") == "Nebbia" and 26 or 14) * (night and 1 or 0.4)
		end
		rainPart.CFrame = CFrame.new(camPos + Vector3.new(0, 35, 0))
		rain.Enabled = raining
		-- temporale: pioggia fitta inclinata dal vento, scroscio e raffiche
		rain.Rate = 900 + 2600 * stormLevel
		rain.Speed = NumberRange.new(75 + 30 * stormLevel, 85 + 35 * stormLevel)
		rain.Acceleration = Vector3.new(28, 0, 10) * stormLevel
		rainSound.Volume = raining and 0.6 * (1 - stormLevel * 0.5) or 0
		stormRain.Volume = 1.1 * stormLevel
		stormWind.Volume = 0.7 * stormLevel

		if storm and now >= nextStormBolt then
			nextStormBolt = now + 2.5 + math.random() * 5
			local close = math.random() < 0.35
			task.spawn(function()
				-- lampo: scatti di luce bianco-azzurra, poi il tuono arriva dopo un po' (più è lontano, più tarda)
				for _ = 1, math.random(2, 4) do
					lightning.Brightness = close and 0.7 or 0.35
					lightning.Contrast = close and 0.35 or 0.15
					flash.Brightness = close and 6 or 2.5
					TweenService:Create(lightning, TweenInfo.new(0.15), { Brightness = 0, Contrast = 0 }):Play()
					TweenService:Create(flash, TweenInfo.new(0.2), { Brightness = 0 }):Play()
					task.wait(0.06 + math.random() * 0.12)
				end
				task.wait(close and 0.2 + math.random() * 0.4 or 1.2 + math.random() * 2)
				Sfx.new(close and "Thunder" or "ThunderFar", SoundService, {
					Volume = close and 2.4 or 1.6,
					PlaybackSpeed = 0.85 + math.random() * 0.3,
					PlayOnRemove = true,
				}):Destroy()
			end)
		end

		if raining and now >= nextBolt then
			nextBolt = now + math.random(15, 40)
			task.spawn(function()
				for _ = 1, math.random(1, 3) do
					lightning.Brightness = 0.45
					lightning.Contrast = 0.3
					TweenService:Create(lightning, TweenInfo.new(0.18), { Brightness = 0, Contrast = 0 }):Play()
					task.wait(0.12 + math.random() * 0.15)
				end
			end)
		end

		-- Creatura vicina: battito, luci che muoiono
		local root = rakeRoot()
		local rakePos = root and root.Position
		local dist = rakePos and (rakePos - camPos).Magnitude or math.huge
		local closeness = math.clamp(1 - dist / 55, 0, 1)
		heartbeat.Volume = closeness * 1.3
		heartbeat.PlaybackSpeed = 1 + closeness * 0.5
		breathing.Volume = (info.exhausted or info.panic) and 0.7 or 0
		ambience.Volume = 0.55 * (1 - closeness * 0.6)

		if now >= nextFlicker then
			nextFlicker = now + 1 / 20
			for light, seed in lights do
				if not light.Parent then
					lights[light] = nil
					continue
				end
				local base = light:GetAttribute("BaseBrightness") or light.Brightness
				local f = 0.9 + math.noise(now * 3, seed) * 0.25
				local holder = light.Parent
				local holderPos = holder and (holder:IsA("BasePart") and holder.Position or (holder:IsA("Attachment") and holder.WorldPosition or nil))
				if rakePos and holderPos then
					local d = (holderPos - rakePos).Magnitude
					if d < 45 then
						local k = 1 - d / 45
						if math.random() < 0.15 + k * 0.4 then
							f = math.random() * (1 - k) * 0.6
						end
					end
				end
				light.Brightness = base * math.max(f, 0)
			end
		end

		-- Rumori improvvisi alle spalle
		if phase == "Notte" and now >= nextSnap then
			nextSnap = now + math.random(22, 55)
			local back = -camera.CFrame.LookVector * Vector3.new(1, 0, 1)
			if back.Magnitude > 0.1 then
				local dir = CFrame.Angles(0, math.rad(math.random(-60, 60)), 0) * back.Unit
				local p = camPos + dir * math.random(14, 30)
				Sfx.at("Snap", Vector3.new(p.X, groundBelow(p) + 1, p.Z), { Volume = 1.3, PlaybackSpeed = 0.85 + math.random() * 0.3 })
			end
		end
	end, function(position: Vector3)
		-- suono sussurrato per le allucinazioni
		Sfx.at("Whisper", position, { Volume = 1.6, RollOffMinDistance = 10 })
		onHallucination()
	end
end

return Ambience
