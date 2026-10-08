-- Animazione di The Rake (solo client, Bone.Transform sulle 40 ossa): movimenti violenti e a scatti.
-- La posa non viene interpolata: salta da una posa all'altra a intervalli irregolari (stop-motion),
-- con perturbazioni casuali enormi. Andatura sconclusionata, testa che ciondola e si capovolge,
-- convulsioni quando si mostra, braccia che si agitano quando carica, posa da jumpscare quando attacca.
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
	Attacco = Color3.fromRGB(255, 10, 10),
	Fuga = Color3.fromRGB(255, 240, 220),
	Stordita = Color3.fromRGB(40, 40, 40),
	Catturata = Color3.fromRGB(40, 40, 40),
}

local function rot(x: number, y: number, z: number): CFrame
	return CFrame.Angles(-x, y, -z)
end

local function r(amount: number): number
	return (math.random() - 0.5) * 2 * amount
end

local FINGERS = {}
for f = 0, 3 do
	for _, side in { "L", "R" } do
		table.insert(FINGERS, { "Fing" .. f .. side .. "A", "Fing" .. f .. side .. "B" })
	end
end

function RakeAnimator.start(state: Folder)
	local model: Model? = nil
	local bones: { [string]: Bone } = {}
	local eyes: { BasePart } = {}
	local phase = 0
	local nextSnap = 0
	local quirk = { headFlip = 0, armUp = "L", lean = 0 }
	local quirkUntil = 0
	local convulseUntil, nextConvulse = 0, 0
	local lastStatus = ""
	local stateStart = 0
	local nextCrack = 0

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

	local function apply(pose: { [string]: CFrame })
		for name, bone in bones do
			bone.Transform = pose[name] or CFrame.new()
		end
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
		if status ~= lastStatus then
			lastStatus = status
			stateStart = now
			nextSnap = 0
		end
		local vel = root.AssemblyLinearVelocity
		local speed = Vector3.new(vel.X, 0, vel.Z).Magnitude
		local a = math.clamp(speed / 12, 0, 1.4)
		phase += dt * (2 + speed * 0.42)

		-- occhi nelle orbite (sempre fluidi)
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

		if now < nextSnap then
			return -- mantiene la posa: movimento a scatti
		end
		local violent = status == "Aggressiva" or status == "Attacco"
		local interval = violent and (0.025 + math.random() * 0.04) or (0.06 + math.random() * 0.12)
		if math.random() < 0.08 then
			interval += 0.15 + math.random() * 0.25 -- "congelamenti" improvvisi
		end
		nextSnap = now + interval

		-- tic che durano qualche secondo: testa capovolta, braccio alzato, inclinazione
		if now > quirkUntil then
			quirkUntil = now + 1 + math.random() * 3
			quirk.headFlip = math.random() < 0.3 and (math.random() < 0.5 and 2.6 or -2.4) or r(1.1)
			quirk.armUp = math.random() < 0.5 and "L" or "R"
			quirk.lean = r(0.45)
		end
		local s, c = math.sin(phase), math.cos(phase)
		local pose: { [string]: CFrame } = {}
		local function set(name: string, x: number, y: number, z: number)
			pose[name] = rot(x, y, z)
		end

		if hum.PlatformStand or status == "Stordita" or status == "Catturata" then
			for name in bones do
				if math.random() < 0.35 then
					set(name, r(0.5), r(0.5), r(0.5))
				end
			end
			set("Jaw", -0.7 - math.random() * 0.2, 0, 0)
			apply(pose)
			return
		end

		local camPos = workspace.CurrentCamera.CFrame.Position
		local toCam = camPos - headCF.Position
		local local_ = root.CFrame:VectorToObjectSpace(toCam.Unit)
		local yawToCam = math.clamp(math.atan2(-local_.X, -local_.Z), -1.5, 1.5)
		local pitchToCam = math.clamp(math.asin(math.clamp(local_.Y, -1, 1)), -0.6, 0.8)
		local fingersOpen = 0.2

		if status == "Attacco" then
			-- jumpscare: braccia spalancate sopra la testa, fauci al massimo, tremore violento
			set("Spine1", -0.35 + r(0.15), r(0.2), r(0.15))
			set("Spine2", -0.3 + r(0.15), r(0.2), r(0.2))
			set("Spine3", -0.2 + r(0.2), r(0.2), r(0.2))
			set("Neck1", 0.6 + r(0.2), r(0.2), r(0.3))
			set("Neck2", 0.2 + r(0.3), r(0.4), r(0.4))
			set("Head", pitchToCam + r(0.35), yawToCam * 0.5 + r(0.6), r(0.8))
			set("Jaw", -0.95 - math.random() * 0.15, r(0.08), 0)
			set("ShoulderL", 2.5 + r(0.4), r(0.4), -0.9 + r(0.3))
			set("ShoulderR", 2.5 + r(0.4), r(0.4), 0.9 + r(0.3))
			set("ElbowL", 0.6 + r(0.4), 0, 0)
			set("ElbowR", 0.6 + r(0.4), 0, 0)
			set("WristL", r(0.6), r(0.6), 0)
			set("WristR", r(0.6), r(0.6), 0)
			set("KneeL", -0.5 + r(0.2), 0, 0)
			set("KneeR", -0.5 + r(0.2), 0, 0)
			fingersOpen = -0.4
		elseif status == "Aggressiva" or status == "Fuga" then
			-- corsa a quattro arti: busto quasi orizzontale, braccia che si agitano, testa che trema
			local charging = status == "Aggressiva"
			set("Spine1", -0.45 + r(0.15), s * 0.2 + r(0.2), quirk.lean * 0.5 + r(0.2))
			set("Spine2", -0.4 + r(0.15), r(0.25), r(0.2))
			set("Spine3", -0.3 + r(0.2), r(0.25), r(0.2))
			set("Neck1", 0.8 + r(0.2), r(0.2), 0)
			set("Neck2", 0.2 + r(0.2), r(0.3), r(0.3))
			if charging then
				set("Head", pitchToCam * 0.5 + r(0.4), yawToCam * 0.4 + r(0.7), r(0.9))
				set("Jaw", -0.6 - math.random() * 0.35, r(0.1), 0)
				set("ShoulderL", 1.3 + s * 0.9 + r(0.7), r(0.5), -0.3 + r(0.4))
				set("ShoulderR", 1.3 - s * 0.9 + r(0.7), r(0.5), 0.3 + r(0.4))
			else
				set("Head", r(0.3), (math.random() < 0.4 and 2.2 or 0) + r(0.4), r(0.5)) -- si guarda alle spalle
				set("Jaw", -0.15 + r(0.15), 0, 0)
				set("ShoulderL", -0.6 + s * 0.8 + r(0.5), r(0.4), -0.4 + r(0.3))
				set("ShoulderR", -0.6 - s * 0.8 + r(0.5), r(0.4), 0.4 + r(0.3))
			end
			set("ElbowL", 0.3 + math.max(0, s) * 0.9 + r(0.4), 0, 0)
			set("ElbowR", 0.3 + math.max(0, -s) * 0.9 + r(0.4), 0, 0)
			set("WristL", r(0.7), r(0.7), 0)
			set("WristR", r(0.7), r(0.7), 0)
			set("HipL", s * 1.0 * a + r(0.25), r(0.15), r(0.15))
			set("HipR", -s * 1.0 * a + r(0.25), r(0.15), r(0.15))
			set("KneeL", -math.max(0, c) * 1.4 * a - 0.2 + r(0.25), 0, 0)
			set("KneeR", -math.max(0, -c) * 1.4 * a - 0.2 + r(0.25), 0, 0)
			set("AnkleL", math.max(0, c) * 0.6 + r(0.2), 0, 0)
			set("AnkleR", math.max(0, -c) * 0.6 + r(0.2), 0, 0)
			fingersOpen = charging and -0.3 or 0.4
		elseif status == "Territoriale" and speed < 3 then
			-- si mostra: immobile, la testa si piega fino all'estremo, poi convulsioni violente
			local t = now - stateStart
			if now > nextConvulse then
				nextConvulse = now + 0.9 + math.random() * 1.4
				convulseUntil = now + 0.25 + math.random() * 0.3
			end
			local shake = now < convulseUntil and 1 or 0
			local tilt = math.min(t * 0.7, 1.6) * (quirk.headFlip >= 0 and 1 or -1)
			set("Spine1", -0.15 + r(0.5) * shake, r(0.4) * shake, r(0.4) * shake)
			set("Spine2", -0.2 + r(0.5) * shake, r(0.3) * shake, r(0.3) * shake)
			set("Spine3", -0.25 + r(0.4) * shake, 0, r(0.4) * shake)
			set("Neck1", 0.35 + r(0.3) * shake, 0, 0)
			set("Neck2", pitchToCam * 0.4, yawToCam * 0.45, 0)
			set("Head", pitchToCam * 0.5 + r(0.08) + r(0.6) * shake, yawToCam * 0.5 + r(0.08), tilt + r(0.9) * shake)
			set("Jaw", -math.min(t * 0.35, 0.8) - math.abs(r(0.3)) * shake, 0, 0)
			set("ShoulderL", 0.2 + r(0.15) + r(1.2) * shake, r(0.2), -0.35 + r(0.6) * shake)
			set("ShoulderR", 0.2 + r(0.15) + r(1.2) * shake, r(0.2), 0.35 + r(0.6) * shake)
			set("ElbowL", 0.25 + r(0.2) + r(0.8) * shake, 0, 0)
			set("ElbowR", 0.25 + r(0.2) + r(0.8) * shake, 0, 0)
			set("WristL", r(0.4), r(0.4), 0)
			set("WristR", r(0.4), r(0.4), 0)
			set("KneeL", -0.3 + r(0.3) * shake, 0, 0)
			set("KneeR", -0.3 + r(0.3) * shake, 0, 0)
			fingersOpen = 0.1 + r(0.5)
			if shake > 0 and now > nextCrack and toCam.Magnitude < 70 then
				nextCrack = now + 0.6
				Sfx.at("BoneCrack", headCF.Position, { Volume = 1.5, PlaybackSpeed = 0.7 + math.random() * 0.6, RollOffMaxDistance = 70 })
			end
		else
			-- andatura sconclusionata: zoppa, contorta, con un braccio che si agita
			local limp = 1 + 0.5 * math.max(0, math.sin(phase * 0.5))
			set("Spine1", -0.15 + r(0.12), s * 0.3 * a + r(0.15), quirk.lean + s * 0.25 * a + r(0.12))
			set("Spine2", -0.15 + r(0.12), r(0.2), -quirk.lean * 0.5 + r(0.15))
			set("Spine3", -0.2 + r(0.12), r(0.2), r(0.15))
			set("Neck1", 0.3 + r(0.15), r(0.15), 0)
			set("Neck2", pitchToCam * 0.3 + r(0.2), (toCam.Magnitude < 70 and yawToCam * 0.4 or 0) + r(0.3), r(0.3))
			set("Head", r(0.25), (toCam.Magnitude < 70 and yawToCam * 0.5 or r(0.6)), quirk.headFlip + r(0.25))
			set("Jaw", -0.05 - math.abs(r(0.25)), 0, 0)
			local up = quirk.armUp
			local flail = 1.4 + r(0.9)
			set("ShoulderL", up == "L" and flail or (-s * 0.5 * a + r(0.35)), r(0.4), up == "L" and -0.7 + r(0.4) or -0.1 + r(0.2))
			set("ShoulderR", up == "R" and flail or (s * 0.5 * a + r(0.35)), r(0.4), up == "R" and 0.7 + r(0.4) or 0.1 + r(0.2))
			set("ElbowL", 0.2 + math.max(0, s) * 0.5 * a + r(0.45), 0, 0)
			set("ElbowR", 0.2 + math.max(0, -s) * 0.5 * a + r(0.45), 0, 0)
			set("WristL", r(0.6), r(0.5), 0)
			set("WristR", r(0.6), r(0.5), 0)
			set("HipL", s * 0.85 * a * limp + r(0.2), r(0.2), -0.1 + r(0.1))
			set("HipR", -s * 0.55 * a + r(0.2), r(0.2), 0.1 + r(0.1))
			set("KneeL", -math.max(0, c) * 1.3 * a * limp + r(0.2), 0, 0)
			set("KneeR", -math.max(0, -c) * 0.9 * a + r(0.2), 0, 0)
			set("AnkleL", math.max(0, c) * 0.5 * a + r(0.2), 0, 0)
			set("AnkleR", math.max(0, -c) * 0.5 * a + r(0.2), 0, 0)
			fingersOpen = 0.3 + r(0.4)
		end
		for _, f in FINGERS do
			set(f[1], fingersOpen + r(0.5), 0, r(0.25))
			set(f[2], fingersOpen * 1.3 + r(0.6), 0, 0)
		end
		apply(pose)
	end

	RakeAnimator.update = update
	RunService.Stepped:Connect(function(_, dt)
		update(dt)
	end)
end

return RakeAnimator
