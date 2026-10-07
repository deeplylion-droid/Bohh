-- Animazione procedurale di The Rake (solo client, tramite Bone.Transform sulle 40 ossa della mesh):
-- andatura zoppa e asimmetrica, movimento "a scatti" come in stop-motion, spasmi improvvisi con
-- schiocchi d'ossa, testa che ti segue e si piega di lato, mascella che batte, dita che si contraggono.
-- Le ossa importate sono ruotate di 180 gradi attorno a Y: gli angoli di progetto (x, y, z) diventano
-- CFrame.Angles(-x, y, -z) nello spazio dell'osso.
local RunService = game:GetService("RunService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Sfx = require(Shared:WaitForChild("Sfx"))

local RakeAnimator = {}

local EYE_COLORS = {
	Inattiva = Color3.fromRGB(255, 240, 220),
	Curiosa = Color3.fromRGB(255, 240, 220),
	Territoriale = Color3.fromRGB(255, 170, 70),
	Aggressiva = Color3.fromRGB(255, 30, 20),
	Fuga = Color3.fromRGB(255, 240, 220),
	Stordita = Color3.fromRGB(40, 40, 40),
	Catturata = Color3.fromRGB(40, 40, 40),
}

local function rot(x: number, y: number, z: number): CFrame
	return CFrame.Angles(-x, y, -z)
end

local SPASM_BONES = { "Neck1", "Neck2", "Head", "Spine2", "Spine3", "ShoulderL", "ShoulderR", "ElbowL", "ElbowR", "WristL", "WristR", "Jaw" }
local FINGERS = {}
for f = 0, 3 do
	for _, side in { "L", "R" } do
		table.insert(FINGERS, { "Fing" .. f .. side .. "A", "Fing" .. f .. side .. "B", f * 1.7 + (side == "L" and 0 or 9) })
	end
end

function RakeAnimator.start(state: Folder)
	local model: Model? = nil
	local bones: { [string]: Bone } = {}
	local eyes: { BasePart } = {}
	local pose: { [string]: CFrame } = {}
	local phase = 0
	local nextApply, stutterUntil, nextStutter = 0, 0, os.clock() + 3
	local nextTwitch, twitchUntil, twitch = 0, 0, CFrame.new()
	local spasm: { [string]: { cf: CFrame, t0: number } } = {}
	local nextSpasm = os.clock() + 2
	local chatterUntil, nextChatter = 0, os.clock() + 4

	local function clearEyes()
		for _, e in eyes do
			e:Destroy()
		end
		table.clear(eyes)
	end

	local function attach(rake: Model)
		model = rake
		table.clear(bones)
		clearEyes()
		for _, d in rake:GetDescendants() do
			if d:IsA("Bone") then
				bones[d.Name] = d
			end
		end
		for i = 1, 2 do
			local eye = Instance.new("Part")
			eye.Name = "OcchioLocale"
			eye.Shape = Enum.PartType.Ball
			eye.Size = Vector3.new(0.12, 0.12, 0.12)
			eye.Material = Enum.Material.Neon
			eye.Anchored = true
			eye.CanCollide = false
			eye.CanQuery = false
			eye.CanTouch = false
			eye.CastShadow = false
			eye.Parent = workspace
			if i == 1 then
				local glow = Instance.new("PointLight")
				glow.Range = 7
				glow.Brightness = 1.4
				glow.Parent = eye
			end
			table.insert(eyes, eye)
		end
	end

	local function set(name: string, cf: CFrame)
		pose[name] = cf
	end

	local function update(dt: number)
		local folder = workspace:FindFirstChild("RakeHunt")
		local rake = folder and folder:FindFirstChild("TheRake") :: Model?
		if rake ~= model then
			if rake then
				attach(rake)
			else
				model = nil
				clearEyes()
			end
		end
		if not rake then
			return
		end
		local root = rake:FindFirstChild("HumanoidRootPart") :: BasePart?
		local hum = rake:FindFirstChildOfClass("Humanoid")
		local head = bones.Head
		if not root or not hum or not head then
			return
		end
		local now = os.clock()
		local status = state:GetAttribute("RakeState") or "Inattiva"
		local knocked = hum.PlatformStand or status == "Stordita" or status == "Catturata"
		local aggressive = status == "Aggressiva"
		table.clear(pose)

		local vel = root.AssemblyLinearVelocity
		local speed = Vector3.new(vel.X, 0, vel.Z).Magnitude
		local a = math.clamp(speed / 12, 0, 1.3)
		phase += dt * (1.6 + speed * 0.4) * (0.75 + 0.5 * math.noise(now * 0.7, 3.1) + 0.25)
		local s, c = math.sin(phase), math.cos(phase)
		local function n(seed: number, freq: number): number
			return math.noise(now * freq, seed, 0.5)
		end

		if knocked then
			-- a terra: convulsioni
			for name in bones do
				if math.random() < 0.3 then
					set(name, rot((math.random() - 0.5) * 0.5, (math.random() - 0.5) * 0.5, (math.random() - 0.5) * 0.5))
				end
			end
			set("Jaw", rot(-0.6 - math.random() * 0.2, 0, 0))
		else
			-- postura di base: gobba, collo proteso
			local hunch = aggressive and 0.33 or 0.12
			set("Spine1", rot(-hunch + n(1, 0.4) * 0.05, s * 0.06 * a, math.sin(phase) * 0.05 * a))
			set("Spine2", rot(-hunch - 0.05 + n(2, 0.5) * 0.05, 0, 0))
			set("Spine3", rot(-hunch * 0.8 + math.sin(now * 1.7) * 0.03, 0, 0))
			set("Neck1", rot(hunch * 1.4 + 0.1, 0, 0))
			-- gambe zoppe e asimmetriche
			local limp = 1 + 0.35 * math.max(0, math.sin(phase * 0.5))
			set("HipL", rot(s * 0.6 * a * limp, 0, -0.05))
			set("HipR", rot(-s * 0.45 * a, 0, 0.05))
			set("KneeL", rot(-math.max(0, c) * 0.95 * a * limp, 0, 0))
			set("KneeR", rot(-math.max(0, -c) * 0.8 * a, 0, 0))
			set("AnkleL", rot(math.max(0, c) * 0.4 * a, 0, 0))
			set("AnkleR", rot(math.max(0, -c) * 0.4 * a, 0, 0))
			-- braccia: penzolano e strisciano, o si protendono quando carica
			if aggressive then
				set("ShoulderL", rot(1.0 + s * 0.6, 0, -0.2))
				set("ShoulderR", rot(1.0 - s * 0.6, 0, 0.2))
				set("ElbowL", rot(0.5 + math.max(0, s) * 0.5, 0, 0))
				set("ElbowR", rot(0.5 + math.max(0, -s) * 0.5, 0, 0))
			else
				set("ShoulderL", rot(-s * 0.4 * a + n(4, 0.6) * 0.15, 0, -0.05 + n(5, 0.4) * 0.1))
				set("ShoulderR", rot(s * 0.4 * a + n(6, 0.6) * 0.15, 0, 0.05 + n(7, 0.4) * 0.1))
				set("ElbowL", rot(0.15 + math.max(0, s) * 0.3 * a + n(8, 1.2) * 0.1, 0, 0))
				set("ElbowR", rot(0.15 + math.max(0, -s) * 0.3 * a + n(9, 1.2) * 0.1, 0, 0))
			end
			set("WristL", rot(n(10, 1.5) * 0.4, n(11, 1) * 0.3, 0))
			set("WristR", rot(n(12, 1.5) * 0.4, n(13, 1) * 0.3, 0))
			for _, f in FINGERS do
				local curl = 0.25 + n(f[3], 2.5) * 0.6 + (aggressive and -0.3 or 0)
				set(f[1], rot(curl, 0, n(f[3] + 1, 2) * 0.2))
				set(f[2], rot(curl * 1.2 + n(f[3] + 2, 4) * 0.3, 0, 0))
			end

			-- testa: ti segue quando sei vicino, si piega di lato quando ti studia
			local camPos = workspace.CurrentCamera.CFrame.Position
			local toCam = camPos - head.TransformedWorldCFrame.Position
			local yaw, pitch = n(14, 0.3) * 0.8, n(15, 0.25) * 0.3
			if toCam.Magnitude < 75 then
				local d = root.CFrame:VectorToObjectSpace(toCam.Unit)
				yaw = math.clamp(math.atan2(-d.X, -d.Z), -1.4, 1.4)
				pitch = math.clamp(math.asin(math.clamp(d.Y, -1, 1)), -0.6, 0.7)
			end
			local tilt = (status == "Curiosa" or status == "Territoriale") and (0.55 + n(16, 0.2) * 0.4) or n(17, 0.3) * 0.25
			set("Neck2", rot(pitch * 0.4, yaw * 0.45, 0))
			local headCF = rot(pitch * 0.6, yaw * 0.55, tilt)
			if now > nextTwitch then
				nextTwitch = now + math.random() * (aggressive and 0.8 or 2.2) + 0.3
				twitchUntil = now + 0.08 + math.random() * 0.25
				twitch = rot((math.random() - 0.5) * 0.9, (math.random() - 0.5) * 1.4, (math.random() - 0.5) * 1.6)
			end
			if now < twitchUntil then
				headCF *= twitch
			end
			set("Head", headCF)

			-- mascella: spalancata quando carica, batte a raffiche
			local jaw = aggressive and (-0.45 - math.abs(math.sin(now * 14)) * 0.25) or -0.04
			if now > nextChatter then
				nextChatter = now + 3 + math.random() * 6
				chatterUntil = now + 0.6 + math.random() * 0.9
			end
			if now < chatterUntil then
				jaw = -0.12 - math.abs(math.sin(now * 38)) * 0.22
			end
			set("Jaw", rot(jaw, 0, 0))

			-- spasmi: alcune ossa scattano di colpo e tornano a posto
			if now > nextSpasm then
				nextSpasm = now + (aggressive and 0.6 or 1.5) + math.random() * 2.5
				for _ = 1, math.random(2, 4) do
					local name = SPASM_BONES[math.random(1, #SPASM_BONES)]
					spasm[name] = {
						cf = rot((math.random() - 0.5) * 1.4, (math.random() - 0.5) * 1.6, (math.random() - 0.5) * 1.8),
						t0 = now,
					}
				end
				if toCam.Magnitude < 60 then
					Sfx.at("BoneCrack", head.TransformedWorldCFrame.Position, { Volume = 1.4, PlaybackSpeed = 0.8 + math.random() * 0.5, RollOffMaxDistance = 60 })
				end
			end
			for name, sp in spasm do
				local k = 1 - (now - sp.t0) / 0.35
				if k <= 0 then
					spasm[name] = nil
				else
					local base = pose[name] or CFrame.new()
					set(name, base * CFrame.new():Lerp(sp.cf, math.min(1, k * 1.6)))
				end
			end
		end

		-- movimento a scatti: la posa viene applicata a intervalli irregolari
		if now > nextStutter then
			nextStutter = now + (aggressive and 1.5 or 3) + math.random() * 4
			stutterUntil = now + 0.3 + math.random() * 0.6
		end
		if now >= nextApply then
			local interval = now < stutterUntil and (0.07 + math.random() * 0.12) or 0
			nextApply = now + interval
			for name, bone in bones do
				bone.Transform = pose[name] or CFrame.new()
			end
		end

		-- occhi nelle orbite
		local color = EYE_COLORS[status] or EYE_COLORS.Inattiva
		local headCF = head.TransformedWorldCFrame
		for i, eye in eyes do
			local side = i == 1 and -1 or 1
			eye.CFrame = headCF * CFrame.new(-side * 0.15, 0.34, 0.66)
			eye.Color = color
			local glow = eye:FindFirstChildOfClass("PointLight")
			if glow then
				glow.Color = color
			end
		end
	end
	RakeAnimator.update = update
	RunService.Stepped:Connect(function(_, dt)
		update(dt)
	end)
end

return RakeAnimator
