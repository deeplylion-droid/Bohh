-- Braccia in prima persona (client, sul proprio personaggio R15):
--  - fascio della torcia orientato ogni frame come la visuale e inviato al server;
--  - braccio destro: con torcia o fucile segue la visuale anche in verticale;
--  - braccio sinistro (tasto G): cinematica inversa a due segmenti (spalla, gomito) che porta il polso
--    davanti alla telecamera, avambraccio orizzontale e quadrante dell'orologio rivolto verso di te;
--  - braccia sempre visibili in prima persona.
-- Le pose si ottengono riscrivendo il C0 delle giunture: Part1 = Part0 * C0 * Transform * C1⁻¹,
-- quindi C0 = Part0⁻¹ * Part1(desiderato) * C1 * Transform⁻¹ (annulla anche l'animazione di camminata).
local RunService = game:GetService("RunService")

local ArmPose = {}

local VISIBLE = { "LeftUpperArm", "LeftLowerArm", "LeftHand", "RightUpperArm", "RightLowerArm", "RightHand", "Left Arm", "Right Arm" }

-- Direzione (sullo schermo) in cui compare il quadrante: x e y per ogni stud di profondità
ArmPose.WATCH_RAY = Vector3.new(0.04, -0.34, 1)

local function ortho(v: Vector3, axis: Vector3): Vector3
	local o = v - axis * v:Dot(axis)
	if o.Magnitude < 1e-4 then
		o = Vector3.new(axis.Y, axis.Z, axis.X)
		o = o - axis * o:Dot(axis)
	end
	return o.Unit
end

-- Rotazione che porta il vettore locale `la` sulla direzione mondo `wa`, e `lb` il più vicino a `wb`
local function align(la: Vector3, wa: Vector3, lb: Vector3, wb: Vector3): CFrame
	local a1 = la.Unit
	local a2 = ortho(lb, a1)
	local b1 = wa.Unit
	local b2 = ortho(wb, b1)
	local A = CFrame.fromMatrix(Vector3.zero, a1, a2, a1:Cross(a2))
	local B = CFrame.fromMatrix(Vector3.zero, b1, b2, b1:Cross(b2))
	return B * A:Inverse()
end

-- Calcola i C0 di spalla e gomito che mettono il quadrante davanti agli occhi, rivolto verso di te.
-- Si usa una "telecamera virtuale" con la stessa direzione orizzontale dello sguardo ma inclinazione
-- limitata: se guardi in alto il polso resta all'altezza del viso, come nella realtà.
-- Per ogni inclinazione si cercano (una volta, poi in cache) spostamento laterale, profondità,
-- inclinazione e rotazione dell'avambraccio che tengono il gomito attaccato e il quadrante frontale.
-- faceRel = CFrame del quadrante rispetto all'avambraccio. Restituisce anche le CFrame risultanti.
ArmPose._cache = {}

function ArmPose.solveWatch(torsoCF: CFrame, shoulder: Motor6D, elbow: Motor6D, c0s: CFrame, c0e: CFrame, faceRel: CFrame, cam: CFrame)
	local S = (torsoCF * c0s).Position
	local c1s, c1e = shoulder.C1, elbow.C1
	local u = c0e.Position - c1s.Position -- spalla → gomito, nel braccio
	local l1 = u.Magnitude
	local look = cam.LookVector
	local yaw0 = math.atan2(-look.X, -look.Z)
	local pitch = math.clamp(math.asin(math.clamp(look.Y, -1, 1)), -1.1, 0.15)
	local vcam = CFrame.new(cam.Position) * CFrame.Angles(0, yaw0, 0) * CFrame.Angles(pitch, 0, 0)
	local ray = ArmPose.WATCH_RAY

	local function place(x: number, depth: number, roll: number, yaw: number)
		local p = (vcam * CFrame.new((ray.X + x) * depth, ray.Y * depth, -depth)).Position
		local faceCF = CFrame.lookAt(p, cam.Position, vcam.UpVector) * CFrame.Angles(0, yaw, 0) * CFrame.Angles(0, 0, roll)
		local lowerCF = faceCF * faceRel:Inverse()
		return lowerCF, (lowerCF * c1e).Position, faceCF
	end
	local function cost(x: number, depth: number, roll: number, yaw: number): number
		local _, Ej = place(x, depth, roll, yaw)
		return math.abs((Ej - S).Magnitude - l1) * 12 + math.abs(roll) * 0.3 + math.abs(yaw) * 0.4 + math.abs(x) * 0.3 + math.abs(depth - 1) * 0.1
	end

	local bucket = math.floor(pitch / 0.05 + 0.5)
	local key = ("%d:%.3f"):format(bucket, l1)
	local best = ArmPose._cache[key]
	if not best then
		local bestCost = math.huge
		for x = -0.5, 0.1, 0.1 do
			for depth = 0.6, 1.8, 0.1 do
				for roll = -1.0, 0.3, 0.2 do
					for yaw = -0.4, 0.4, 0.2 do
						local c = cost(x, depth, roll, yaw)
						if c < bestCost then
							best, bestCost = { x, depth, roll, yaw }, c
						end
					end
				end
			end
		end
		local coarse = best
		for x = coarse[1] - 0.1, coarse[1] + 0.1, 0.025 do
			for depth = coarse[2] - 0.1, coarse[2] + 0.1, 0.025 do
				for roll = coarse[3] - 0.2, coarse[3] + 0.2, 0.05 do
					for yaw = coarse[4] - 0.2, coarse[4] + 0.2, 0.1 do
						local c = cost(x, depth, roll, yaw)
						if c < bestCost then
							best, bestCost = { x, depth, roll, yaw }, c
						end
					end
				end
			end
		end
		ArmPose._cache[key] = best
	end
	local lowerCF, Ej, faceCF = place(best[1], best[2], best[3], best[4])
	local Ru = align(u, Ej - S, Vector3.xAxis, cam.RightVector)
	local upperCF = CFrame.new(S - Ru:VectorToWorldSpace(c1s.Position)) * Ru
	local newC0s = torsoCF:Inverse() * upperCF * c1s * shoulder.Transform:Inverse()
	local newC0e = upperCF:Inverse() * lowerCF * c1e * elbow.Transform:Inverse()
	return newC0s, newC0e, upperCF, lowerCF, faceCF
end

function ArmPose.start(player: Player, watchShown: () -> boolean, remotes: Folder, isBlocked: () -> boolean, hide: () -> ())
	local originals: { [Motor6D]: CFrame } = {}
	local watchBlend = 0
	local lastSent, lastLook = 0, Vector3.zero

	local function motor(char: Model, partName: string, jointName: string): Motor6D?
		local part = char:FindFirstChild(partName)
		local joint = part and part:FindFirstChild(jointName)
		if joint and joint:IsA("Motor6D") then
			if not originals[joint] then
				originals[joint] = joint.C0
			end
			return joint
		end
		return nil
	end

	player.CharacterAdded:Connect(function()
		table.clear(originals)
		watchBlend = 0
	end)

	RunService:BindToRenderStep("BracciaPrimaPersona", Enum.RenderPriority.Camera.Value + 5, function(dt)
		local char = player.Character
		if not char then
			return
		end
		local camera = workspace.CurrentCamera
		local cam = camera.CFrame
		local look = cam.LookVector

		-- fascio della torcia
		local tool = char:FindFirstChild("Torcia")
		local lens = tool and tool:FindFirstChild("Lente")
		local beam = lens and lens:FindFirstChild("Fascio")
		if beam and beam:IsA("Attachment") and lens:IsA("BasePart") then
			beam.WorldCFrame = CFrame.lookAt(lens.Position, lens.Position + look)
			local now = os.clock()
			if now - lastSent > 0.07 and look:Dot(lastLook) < 0.9995 then
				lastSent, lastLook = now, look
				remotes.AimTorch:FireServer(look)
			end
		end

		-- braccio destro: segue la visuale con torcia o fucile in mano
		local holding = char:FindFirstChild("Torcia") or char:FindFirstChild("Fucile a dardi")
		local right = motor(char, "RightUpperArm", "RightShoulder")
		if right then
			local pitch = 0
			if holding and player:GetAttribute("Status") == "OK" then
				pitch = math.clamp(math.asin(math.clamp(look.Y, -1, 1)), -1.2, 1.2)
			end
			right.C0 = originals[right] * CFrame.Angles(pitch, 0, 0)
		end

		-- braccio sinistro: orologio davanti agli occhi
		if watchShown() and (player:GetAttribute("Status") ~= "OK" or isBlocked()) then
			hide()
		end
		local want = watchShown() and 1 or 0
		watchBlend = math.clamp(watchBlend + (want > watchBlend and dt / 0.4 or -dt / 0.3), 0, 1)
		local torso = char:FindFirstChild("UpperTorso") :: BasePart?
		local upper = char:FindFirstChild("LeftUpperArm") :: BasePart?
		local lower = char:FindFirstChild("LeftLowerArm") :: BasePart?
		local shoulder = motor(char, "LeftUpperArm", "LeftShoulder")
		local elbow = motor(char, "LeftLowerArm", "LeftElbow")
		local face = lower and lower:FindFirstChild("SchermoOrologio") :: BasePart?
		if torso and upper and lower and shoulder and elbow then
			if watchBlend <= 0 or not face then
				shoulder.C0 = originals[shoulder]
				elbow.C0 = originals[elbow]
			else
				local faceRel = lower.CFrame:ToObjectSpace(face.CFrame)
				local c0s, c0e = ArmPose.solveWatch(torso.CFrame, shoulder, elbow, originals[shoulder], originals[elbow], faceRel, cam)
				local e = watchBlend * watchBlend * (3 - 2 * watchBlend)
				shoulder.C0 = originals[shoulder]:Lerp(c0s, e)
				elbow.C0 = originals[elbow]:Lerp(c0e, e)
			end
		end

		-- braccia (e orologio) visibili in prima persona
		for _, name in VISIBLE do
			local p = char:FindFirstChild(name)
			if p and p:IsA("BasePart") then
				p.LocalTransparencyModifier = 0
				for _, d in p:GetChildren() do
					if d:IsA("BasePart") then
						d.LocalTransparencyModifier = 0
					end
				end
			end
		end
	end)
end

return ArmPose
