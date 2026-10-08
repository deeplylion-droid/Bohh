-- Zone: rileva dove si trova il giocatore, mostra il nome della zona, cambia la musica, il colore
-- dell'atmosfera e le particelle ambientali (neve, polline, lucciole, polvere, scintille, braci).
-- Altri controller possono imporre una musica con priorita' (valanga, eventi).

local Lighting = game:GetService("Lighting")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local Events = require(ReplicatedStorage.Shared.Config.Events)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local ZoneConfig = require(ReplicatedStorage.Shared.Config.Zones)

local Zones = {}

Zones.Current = "Summit"

local C
local player = Players.LocalPlayer
local overrides: { [string]: { music: string, priority: number } } = {} -- origine -> brano imposto
local playing: string? = nil
local lowGfx = false
local emitterPart: Part
local emitters: { [string]: ParticleEmitter } = {}

local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"
local SMOKE = "rbxasset://textures/particles/smoke_main.dds"

-- Aspetto di ogni zona: atmosfera, viraggio colore e particelle
local LOOK = {
	Summit = { color = Color3.fromRGB(206, 226, 255), decay = Color3.fromRGB(126, 156, 214), density = 0.26, tint = Color3.fromRGB(255, 252, 246), fx = "Snow" },
	Meadow = { color = Color3.fromRGB(198, 230, 255), decay = Color3.fromRGB(122, 164, 214), density = 0.24, tint = Color3.fromRGB(255, 253, 242), fx = "Pollen" },
	Forest = { color = Color3.fromRGB(184, 226, 206), decay = Color3.fromRGB(86, 140, 118), density = 0.3, tint = Color3.fromRGB(246, 255, 244), fx = "Fireflies" },
	Canyon = { color = Color3.fromRGB(255, 218, 182), decay = Color3.fromRGB(196, 124, 80), density = 0.3, tint = Color3.fromRGB(255, 246, 230), fx = "Dust" },
	Crystal = { color = Color3.fromRGB(184, 172, 255), decay = Color3.fromRGB(96, 74, 190), density = 0.34, tint = Color3.fromRGB(246, 240, 255), fx = "Sparkles" },
	Crater = { color = Color3.fromRGB(255, 160, 120), decay = Color3.fromRGB(150, 52, 40), density = 0.36, tint = Color3.fromRGB(255, 238, 224), fx = "Embers" },
}

-- Particelle ambientali (emesse in un volume attorno alla telecamera)
local FX = {
	Snow = {
		Texture = SPARKLE,
		Color = ColorSequence.new(Color3.fromRGB(255, 255, 255)),
		LightEmission = 0.2,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.22), NumberSequenceKeypoint.new(1, 0.16) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.15, 0.1), NumberSequenceKeypoint.new(0.85, 0.2), NumberSequenceKeypoint.new(1, 1) }),
		Lifetime = NumberRange.new(5, 8),
		Speed = NumberRange.new(0.5, 1.5),
		Acceleration = Vector3.new(0.6, -2.2, 0.3),
		Rate = 46,
	},
	Pollen = {
		Texture = SPARKLE,
		Color = ColorSequence.new(Color3.fromRGB(255, 246, 170), Color3.fromRGB(255, 255, 255)),
		LightEmission = 0.6,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.18), NumberSequenceKeypoint.new(1, 0.1) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.3, 0.2), NumberSequenceKeypoint.new(1, 1) }),
		Lifetime = NumberRange.new(4, 7),
		Speed = NumberRange.new(0.3, 1),
		Acceleration = Vector3.new(0.4, 0.15, 0.2),
		Rate = 16,
	},
	Fireflies = {
		Texture = SPARKLE,
		Color = ColorSequence.new(Color3.fromRGB(210, 255, 120), Color3.fromRGB(255, 240, 110)),
		LightEmission = 1,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.3), NumberSequenceKeypoint.new(0.5, 0.42), NumberSequenceKeypoint.new(1, 0.2) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.25, 0), NumberSequenceKeypoint.new(0.6, 0.6), NumberSequenceKeypoint.new(1, 1) }),
		Lifetime = NumberRange.new(3, 5),
		Speed = NumberRange.new(0.4, 1.2),
		Acceleration = Vector3.new(0, 0.2, 0),
		Rate = 12,
	},
	Dust = {
		Texture = SMOKE,
		Color = ColorSequence.new(Color3.fromRGB(240, 196, 150)),
		LightEmission = 0,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 2), NumberSequenceKeypoint.new(1, 5) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.4, 0.86), NumberSequenceKeypoint.new(1, 1) }),
		Lifetime = NumberRange.new(5, 8),
		Speed = NumberRange.new(1, 3),
		Acceleration = Vector3.new(1.2, 0, 0.4),
		Rate = 5,
	},
	Sparkles = {
		Texture = SPARKLE,
		Color = ColorSequence.new(Color3.fromRGB(150, 230, 255), Color3.fromRGB(210, 150, 255)),
		LightEmission = 1,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(0.5, 0.36), NumberSequenceKeypoint.new(1, 0) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.3, 0), NumberSequenceKeypoint.new(1, 1) }),
		Lifetime = NumberRange.new(2, 4),
		Speed = NumberRange.new(0.2, 0.8),
		Acceleration = Vector3.new(0, 0.3, 0),
		Rate = 22,
	},
	Embers = {
		Texture = SPARKLE,
		Color = ColorSequence.new(Color3.fromRGB(255, 200, 80), Color3.fromRGB(255, 70, 20)),
		LightEmission = 1,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.26), NumberSequenceKeypoint.new(1, 0.05) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(0.8, 0.4), NumberSequenceKeypoint.new(1, 1) }),
		Lifetime = NumberRange.new(3, 5),
		Speed = NumberRange.new(1, 2.5),
		Acceleration = Vector3.new(0.5, 2.4, 0),
		Rate = 30,
	},
}

function Zones.Init(controllers)
	C = controllers
end

---------------------------------------------------------------------------------------------
-- Musica con priorita': valanga (2) > evento (1) > zona
---------------------------------------------------------------------------------------------
local function zoneMusic(zone: string): string
	local z = ZoneConfig.List[zone]
	return if z then z.music else "Summit"
end

local function refreshMusic()
	local best, bestPriority = nil, -1
	for _, o in overrides do
		if o.priority > bestPriority then
			best, bestPriority = o.music, o.priority
		end
	end
	local want = best or zoneMusic(Zones.Current)
	if want ~= playing then
		playing = want
		C.Audio.Music(want)
	end
end

-- source identifica chi impone il brano (es. "Avalanche", "Event")
function Zones.SetOverride(source: string, music: string, priority: number)
	overrides[source] = { music = music, priority = priority }
	refreshMusic()
end

function Zones.ClearOverride(source: string)
	if overrides[source] then
		overrides[source] = nil
		refreshMusic()
	end
end

---------------------------------------------------------------------------------------------
-- Atmosfera e particelle
---------------------------------------------------------------------------------------------
local function applyLook(zone: string, instant: boolean?)
	local look = LOOK[zone] or LOOK.Summit
	local info = TweenInfo.new(if instant then 0 else 2.5, Enum.EasingStyle.Sine)
	local atmo = Lighting:FindFirstChildOfClass("Atmosphere")
	if atmo then
		TweenService:Create(atmo, info, { Color = look.color, Decay = look.decay, Density = look.density }):Play()
	end
	local grade = Lighting:FindFirstChild("Grade")
	if grade and grade:IsA("ColorCorrectionEffect") then
		TweenService:Create(grade, info, { TintColor = look.tint }):Play()
	end
	for name, e in emitters do
		e.Enabled = name == look.fx
	end
end

local function buildEmitters()
	emitterPart = Instance.new("Part")
	emitterPart.Name = "AmbientFX"
	emitterPart.Anchored = true
	emitterPart.CanCollide = false
	emitterPart.CanQuery = false
	emitterPart.CanTouch = false
	emitterPart.Transparency = 1
	emitterPart.Size = Vector3.new(110, 40, 110)
	emitterPart.Parent = workspace.CurrentCamera
	for name, props in FX do
		local e = Instance.new("ParticleEmitter")
		e.Name = name
		e.Shape = Enum.ParticleEmitterShape.Box
		e.ShapeStyle = Enum.ParticleEmitterShapeStyle.Volume
		e.ShapeInOut = Enum.ParticleEmitterShapeInOut.Outward
		e.SpreadAngle = Vector2.new(180, 180)
		e.Rotation = NumberRange.new(0, 360)
		e.RotSpeed = NumberRange.new(-40, 40)
		e.LightInfluence = 0
		e.Enabled = false
		for k, v in props do
			(e :: any)[k] = v
		end
		e:SetAttribute("BaseRate", props.Rate)
		e.Parent = emitterPart
		emitters[name] = e
	end
end

local function applyGraphics()
	for _, e in emitters do
		local base = e:GetAttribute("BaseRate") or e.Rate
		e.Rate = if lowGfx then base * 0.3 else base
	end
end

---------------------------------------------------------------------------------------------
-- Rilevamento della zona
---------------------------------------------------------------------------------------------
local function rootPart(): BasePart?
	local char = player.Character
	return char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
end

local function zoneColor(zone: string): Color3
	local z = ZoneConfig.List[zone]
	return if z then z.color else Color3.fromRGB(255, 255, 255)
end

function Zones.Start()
	buildEmitters()
	applyLook("Summit", true)
	C.State.Watch("Settings", function(settings)
		lowGfx = settings ~= nil and settings.LowGfx == true
		applyGraphics()
	end)
	-- musica degli eventi
	local eventMusic: string? = nil
	local function refreshEvent()
		local id = workspace:GetAttribute("EventId")
		local endsAt = workspace:GetAttribute("EventEndsAt") or 0
		local def = id and Events.List[id]
		local want = if def and endsAt > workspace:GetServerTimeNow() then def.music or "Event" else nil
		if want ~= eventMusic then
			eventMusic = want
			if want then
				Zones.SetOverride("Event", want, 1)
			else
				Zones.ClearOverride("Event")
			end
		end
	end
	workspace:GetAttributeChangedSignal("EventId"):Connect(refreshEvent)
	workspace:GetAttributeChangedSignal("EventEndsAt"):Connect(refreshEvent)
	refreshEvent()
	refreshMusic()

	-- le particelle seguono la telecamera
	RunService.RenderStepped:Connect(function()
		local cam = workspace.CurrentCamera
		if emitterPart.Parent ~= cam then
			emitterPart.Parent = cam
		end
		emitterPart.CFrame = CFrame.new(cam.CFrame.Position + Vector3.new(0, 6, 0))
	end)

	-- zona attuale (con un piccolo ritardo per non sfarfallare sui confini)
	local candidate, since = "Summit", 0
	while true do
		local hrp = rootPart()
		if hrp then
			local zone = MapLayout.ZoneAt(hrp.Position)
			if zone ~= candidate then
				candidate, since = zone, os.clock()
			elseif zone ~= Zones.Current and os.clock() - since > 0.4 then
				Zones.Current = zone
				applyLook(zone)
				refreshMusic()
				if C.UI.Hud then
					C.UI.Hud.ShowZone(C.Lang.T("Zone_" .. zone), zoneColor(zone))
				end
			end
		end
		-- l'evento finito toglie la sua musica anche senza cambi di attributo
		refreshEvent()
		task.wait(0.25)
	end
end

return Zones
