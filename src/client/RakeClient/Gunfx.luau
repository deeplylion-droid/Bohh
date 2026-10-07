-- Effetti del fucile a dardi (client): fiammata con luce che illumina il bosco, fumo, rinculo
-- (la canna sale e torna giù a metà), sobbalzo dell'arma, lampo e colpo di zoom, sparo con eco e
-- otturatore, dardo visibile in volo che resta conficcato dove colpisce, conferma del colpo.
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")
local Debris = game:GetService("Debris")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local Sfx = require(Shared:WaitForChild("Sfx"))

local Gunfx = {}

local SMOKE = "rbxasset://textures/particles/smoke_main.dds"
local SPARK = "rbxasset://textures/particles/sparkles_main.dds"
local EQ = Config.EQUIPMENT

local player = Players.LocalPlayer
local lastShot = 0
local overlay: ScreenGui? = nil
local flashFrame: Frame? = nil
local hitMarker: TextLabel? = nil

local function part(props: { [string]: any }): Part
	local p = Instance.new("Part")
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CastShadow = false
	for k, v in props do
		(p :: any)[k] = v
	end
	return p
end

local function burst(position: Vector3, props: { [string]: any }, count: number, life: number)
	local holder = part({ Transparency = 1, Size = Vector3.new(0.2, 0.2, 0.2), CFrame = CFrame.new(position) })
	local emitter = Instance.new("ParticleEmitter")
	emitter.Rate = 0
	for k, v in props do
		(emitter :: any)[k] = v
	end
	emitter.Parent = holder
	holder.Parent = workspace
	emitter:Emit(count)
	Debris:AddItem(holder, life)
end

local function muzzleFlash(from: Vector3, dir: Vector3)
	local flash = part({
		Shape = Enum.PartType.Ball,
		Size = Vector3.new(0.9, 0.9, 0.9),
		Material = Enum.Material.Neon,
		Color = Color3.fromRGB(255, 200, 120),
		CFrame = CFrame.new(from + dir * 0.3),
	})
	local cone = part({
		Size = Vector3.new(0.35, 0.35, 1.6),
		Material = Enum.Material.Neon,
		Color = Color3.fromRGB(255, 170, 80),
		CFrame = CFrame.lookAt(from + dir * 0.8, from + dir * 2),
		Transparency = 0.2,
	})
	local light = Instance.new("PointLight")
	light.Range = 38
	light.Brightness = 9
	light.Color = Color3.fromRGB(255, 190, 120)
	light.Shadows = true
	light.Parent = flash
	flash.Parent = workspace
	cone.Parent = workspace
	Debris:AddItem(flash, 0.06)
	Debris:AddItem(cone, 0.04)
	burst(from + dir * 0.4, {
		Texture = SMOKE,
		Color = ColorSequence.new(Color3.fromRGB(170, 170, 165)),
		LightInfluence = 1,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.4), NumberSequenceKeypoint.new(1, 2.6) }),
		Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.55), NumberSequenceKeypoint.new(1, 1) }),
		Lifetime = NumberRange.new(1.2, 2.4),
		Speed = NumberRange.new(1.5, 4),
		SpreadAngle = Vector2.new(25, 25),
		Acceleration = Vector3.new(0, 1.2, 0),
		Drag = 2,
		EmissionDirection = Enum.NormalId.Top,
	}, 14, 3)
	burst(from + dir * 0.4, {
		Texture = SPARK,
		Color = ColorSequence.new(Color3.fromRGB(255, 200, 120)),
		LightEmission = 1,
		Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.25), NumberSequenceKeypoint.new(1, 0) }),
		Lifetime = NumberRange.new(0.08, 0.2),
		Speed = NumberRange.new(10, 25),
		SpreadAngle = Vector2.new(20, 20),
	}, 10, 1)
end

local function ensureOverlay()
	if overlay then
		return
	end
	overlay = Instance.new("ScreenGui")
	overlay.Name = "Sparo"
	overlay.IgnoreGuiInset = true
	overlay.ResetOnSpawn = false
	overlay.DisplayOrder = 6
	overlay.Parent = player:WaitForChild("PlayerGui")
	flashFrame = Instance.new("Frame")
	flashFrame.Size = UDim2.fromScale(1, 1)
	flashFrame.BackgroundColor3 = Color3.fromRGB(255, 220, 170)
	flashFrame.BackgroundTransparency = 1
	flashFrame.BorderSizePixel = 0
	flashFrame.Parent = overlay
	hitMarker = Instance.new("TextLabel")
	hitMarker.AnchorPoint = Vector2.new(0.5, 0.5)
	hitMarker.Position = UDim2.fromScale(0.5, 0.5)
	hitMarker.Size = UDim2.fromOffset(40, 40)
	hitMarker.BackgroundTransparency = 1
	hitMarker.Text = "✕"
	hitMarker.Font = Enum.Font.GothamBlack
	hitMarker.TextSize = 30
	hitMarker.TextColor3 = Color3.fromRGB(255, 50, 40)
	hitMarker.TextTransparency = 1
	hitMarker.Parent = overlay
end

local function recoil(scoped: boolean)
	local camera = workspace.CurrentCamera
	local kick = math.rad(scoped and 2.4 or 4.2)
	local yaw = (math.random() - 0.5) * kick * 0.5
	task.spawn(function()
		for _ = 1, 3 do
			camera.CFrame *= CFrame.Angles(kick / 3, yaw / 3, 0)
			RunService.RenderStepped:Wait()
		end
		for _ = 1, 16 do
			camera.CFrame *= CFrame.Angles(-kick * 0.55 / 16, -yaw * 0.5 / 16, 0)
			RunService.RenderStepped:Wait()
		end
	end)
	if not scoped then
		local fov = camera.FieldOfView
		camera.FieldOfView = fov + 4
		TweenService:Create(camera, TweenInfo.new(0.25, Enum.EasingStyle.Quad, Enum.EasingDirection.Out), { FieldOfView = fov }):Play()
	end
	ensureOverlay()
	local frame = flashFrame :: Frame
	frame.BackgroundTransparency = scoped and 0.9 or 0.8
	TweenService:Create(frame, TweenInfo.new(0.12), { BackgroundTransparency = 1 }):Play()
end

local function gripKick(tool: Tool)
	local original = tool:GetAttribute("GripOriginale")
	if typeof(original) ~= "CFrame" then
		original = tool.Grip
		tool:SetAttribute("GripOriginale", original)
	end
	tool.Grip = (original :: CFrame) * CFrame.new(0, -0.05, -0.45) * CFrame.Angles(-0.25, 0, 0)
	TweenService:Create(tool, TweenInfo.new(0.3, Enum.EasingStyle.Back, Enum.EasingDirection.Out), { Grip = original }):Play()
end

-- Il dardo vola fino al punto colpito e resta conficcato
local function projectile(from: Vector3, to: Vector3, kind: string, normal: Vector3, hitInst: Instance?, isMine: boolean)
	local dir = to - from
	local dist = dir.Magnitude
	if dist < 0.5 then
		return
	end
	local unit = dir.Unit
	local dart = Instance.new("Model")
	dart.Name = "Dardo"
	local shaft = part({ Size = Vector3.new(0.07, 0.07, 1), Color = Color3.fromRGB(150, 150, 155), Material = Enum.Material.Metal })
	local needle = part({ Size = Vector3.new(0.03, 0.03, 0.5), Color = Color3.fromRGB(200, 200, 205), Material = Enum.Material.Metal })
	local fletch = part({ Size = Vector3.new(0.22, 0.22, 0.3), Color = Color3.fromRGB(255, 120, 30), Material = Enum.Material.Neon })
	shaft.Parent, needle.Parent, fletch.Parent = dart, dart, dart
	dart.PrimaryPart = shaft
	local whoosh = Sfx.new("DartWhoosh", shaft, { Volume = 0.8, RollOffMaxDistance = 35 })
	dart.Parent = workspace
	if not isMine then
		whoosh:Play()
	end
	local function place(pos: Vector3)
		local cf = CFrame.lookAt(pos, pos + unit)
		shaft.CFrame = cf
		needle.CFrame = cf * CFrame.new(0, 0, -0.7)
		fletch.CFrame = cf * CFrame.new(0, 0, 0.45) * CFrame.Angles(0, 0, math.pi / 4)
	end
	local duration = dist / EQ.DART_SPEED
	local start = os.clock()
	local conn
	conn = RunService.RenderStepped:Connect(function()
		local a = math.clamp((os.clock() - start) / duration, 0, 1)
		place(from:Lerp(to, a) - Vector3.new(0, math.sin(a * math.pi) * 0.25, 0))
		if a >= 1 then
			conn:Disconnect()
			-- impatto: il dardo resta conficcato
			place(to - unit * 0.35)
			if kind == "rake" and hitInst and hitInst:IsA("BasePart") then
				for _, p in dart:GetChildren() do
					if p:IsA("BasePart") then
						p.Anchored = false
						p.Massless = true
						local weld = Instance.new("WeldConstraint")
						weld.Part0 = hitInst
						weld.Part1 = p
						weld.Parent = p
					end
				end
				burst(to, {
					Texture = SMOKE,
					Color = ColorSequence.new(Color3.fromRGB(70, 8, 8)),
					LightInfluence = 1,
					Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.3), NumberSequenceKeypoint.new(1, 0.9) }),
					Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(1, 1) }),
					Lifetime = NumberRange.new(0.3, 0.7),
					Speed = NumberRange.new(4, 9),
					SpreadAngle = Vector2.new(40, 40),
					Acceleration = Vector3.new(0, -30, 0),
				}, 22, 2)
				if isMine and hitMarker then
					hitMarker.TextTransparency = 0
					hitMarker.TextSize = 40
					TweenService:Create(hitMarker, TweenInfo.new(0.4), { TextTransparency = 1, TextSize = 28 }):Play()
				end
			elseif kind == "terrain" or kind == "wood" then
				burst(to, {
					Texture = SMOKE,
					Color = ColorSequence.new(kind == "terrain" and Color3.fromRGB(90, 75, 55) or Color3.fromRGB(120, 95, 70)),
					LightInfluence = 1,
					Size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.2), NumberSequenceKeypoint.new(1, 1.2) }),
					Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.3), NumberSequenceKeypoint.new(1, 1) }),
					Lifetime = NumberRange.new(0.4, 0.9),
					Speed = NumberRange.new(2, 6),
					SpreadAngle = Vector2.new(50, 50),
					EmissionDirection = Enum.NormalId.Top,
				}, 10, 2)
				Sfx.at("HitWood", to, { Volume = 1.1, RollOffMaxDistance = 70, PlaybackSpeed = kind == "terrain" and 0.75 or 1 })
			else
				dart:Destroy()
				return
			end
			Debris:AddItem(dart, 25)
		end
	end)
	local _ = normal
end

-- Chiamato quando premi il grilletto: rinculo e fiammata immediati, poi il server conferma
function Gunfx.fireLocal(tool: Tool, scoped: boolean): boolean
	local now = os.clock()
	if now - lastShot < EQ.DART_COOLDOWN or (player:GetAttribute("Darts") or 0) <= 0 or player:GetAttribute("Status") ~= "OK" then
		return now - lastShot >= EQ.DART_COOLDOWN -- senza dardi il server avvisa
	end
	lastShot = now
	local muzzle = tool:FindFirstChild("Volata") :: BasePart?
	if muzzle then
		muzzleFlash(muzzle.Position, workspace.CurrentCamera.CFrame.LookVector)
	end
	Sfx.new("RifleShot", SoundService, { Volume = 1.6, PlayOnRemove = true }):Destroy()
	task.delay(0.55, function()
		Sfx.new("BoltCycle", SoundService, { Volume = 0.9, PlayOnRemove = true }):Destroy()
	end)
	recoil(scoped)
	gripKick(tool)
	return true
end

function Gunfx.start(remotes: Folder)
	ensureOverlay()
	remotes:WaitForChild("DartFx").OnClientEvent:Connect(function(shooter: Player, from: Vector3, to: Vector3, kind: string, normal: Vector3, hitInst: Instance?)
		local isMine = shooter == player
		if not isMine then
			muzzleFlash(from, (to - from).Unit)
			Sfx.at("RifleShot", from, { Volume = 2.4, RollOffMinDistance = 20, RollOffMaxDistance = 600 })
			task.delay(0.55, function()
				Sfx.at("BoltCycle", from, { Volume = 1.2, RollOffMaxDistance = 60 })
			end)
		end
		projectile(from, to, kind, normal, hitInst, isMine)
	end)
end

return Gunfx
