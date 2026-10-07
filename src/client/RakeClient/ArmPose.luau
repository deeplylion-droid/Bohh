-- Braccia in prima persona (client, sul proprio personaggio R15):
--  - fascio della torcia orientato ogni frame come la visuale e inviato al server;
--  - braccio destro: con torcia o fucile segue la visuale anche in verticale;
--  - braccio sinistro (tasto G): cinematica inversa a due segmenti (spalla, gomito) che porta il polso
--    davanti alla telecamera, avambraccio orizzontale e quadrante dell'orologio rivolto verso di te;
--  - braccia sempre visibili in prima persona.
-- Le pose si ottengono riscrivendo il C0 delle giunture: Part1 = Part0 * C0 * Transform * C1⁻¹,
-- quindi C0 = Part0⁻¹ * Part1(desiderato) * C1 * Transform⁻¹ (annulla anche l'animazione di camminata).
-- Le giunture possono essere Motor6D (avatar classici) o AnimationConstraint (nuove giunture degli
-- avatar Roblox): per queste C0 e C1 sono le CFrame di Attachment0 e Attachment1.
local RunService = game:GetService("RunService")

local ArmPose = {}

function ArmPose.getC0(joint: Instance): CFrame
	if joint:IsA("Motor6D") then
		return joint.C0
	end
	local a = (joint :: AnimationConstraint).Attachment0
	return a and a.CFrame or CFrame.identity
end

function ArmPose.setC0(joint: Instance, cf: CFrame)
	if joint:IsA("Motor6D") then
		joint.C0 = cf
	else
		local a = (joint :: AnimationConstraint).Attachment0
		if a then
			a.CFrame = cf
		end
	end
end

function ArmPose.getC1(joint: Instance): CFrame
	if joint:IsA("Motor6D") then
		return joint.C1
	end
	local a = (joint :: AnimationConstraint).Attachment1
	return a and a.CFrame or CFrame.identity
end

function ArmPose.getTransform(joint: Instance): CFrame
	if joint:IsA("Motor6D") or joint:IsA("AnimationConstraint") then
		return (joint :: any).Transform
	end
	return CFrame.identity
end

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

function ArmPose.solveWatch(torsoCF: CFrame, shoulder: Instance, elbow: Instance, c0s: CFrame, c0e: CFrame, faceRel: CFrame, cam: CFrame)
	local S = (torsoCF * c0s).Position
	local c1s, c1e = ArmPose.getC1(shoulder), ArmPose.getC1(elbow)
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
	local newC0s = torsoCF:Inverse() * upperCF * c1s * ArmPose.getTransform(shoulder):Inverse()
	local newC0e = upperCF:Inverse() * lowerCF * c1e * ArmPose.getTransform(elbow):Inverse()
	return newC0s, newC0e, upperCF, lowerCF, faceCF
end

-- CFrame del quadrante rispetto all'avambraccio: dalla parte "SchermoOrologio" se c'è, altrimenti
-- ricavata dalle misure del braccio (stessa geometria di Team.attachWatch), così il gesto funziona
-- anche se l'orologio non è ancora arrivato dal server o il braccio della skin è stato sostituito.
function ArmPose.faceRel(lower: BasePart): CFrame
	local face = lower:FindFirstChild("SchermoOrologio")
	if face and face:IsA("BasePart") then
		return lower.CFrame:ToObjectSpace(face.CFrame)
	end
	local size = lower.Size
	local r15 = lower.Name == "LeftLowerArm"
	return CFrame.new(-size.X / 2 - 0.07, -size.Y * (r15 and 0.3 or 0.38), 0)
		* CFrame.fromMatrix(Vector3.zero, Vector3.new(0, 1, 0), Vector3.new(0, 0, 1), Vector3.new(1, 0, 0))
		* CFrame.new(0, 0, -0.08)
end

-- Avatar R6 (un solo pezzo per braccio): si cerca (una volta per inclinazione, poi in cache) la
-- direzione del braccio e la rotazione attorno al suo asse che portano il quadrante davanti agli
-- occhi, rivolto verso di te.
function ArmPose.solveWatchR6(torsoCF: CFrame, shoulder: Instance, c0s: CFrame, faceRel: CFrame, cam: CFrame): CFrame
	local S = (torsoCF * c0s).Position
	local c1 = ArmPose.getC1(shoulder)
	local look = cam.LookVector
	local yaw0 = math.atan2(-look.X, -look.Z)
	local pitch = math.clamp(math.asin(math.clamp(look.Y, -1, 1)), -1.1, 0.15)
	local vcam = CFrame.new(cam.Position) * CFrame.Angles(0, yaw0, 0) * CFrame.Angles(pitch, 0, 0)
	local ray = ArmPose.WATCH_RAY

	local function place(az: number, el: number, roll: number): (CFrame, CFrame)
		local d = vcam:VectorToWorldSpace(Vector3.new(math.sin(az) * math.cos(el), math.sin(el), -math.cos(az) * math.cos(el)))
		local R = CFrame.fromAxisAngle(d, roll) * align(Vector3.new(0, -1, 0), d, Vector3.new(-1, 0, 0), cam.Position - S)
		local armCF = CFrame.new(S - R:VectorToWorldSpace(c1.Position)) * R
		return armCF, armCF * faceRel
	end
	local function cost(az: number, el: number, roll: number): number
		local _, faceCF = place(az, el, roll)
		local p = vcam:PointToObjectSpace(faceCF.Position)
		local depth = -p.Z
		if depth < 0.3 then
			return math.huge
		end
		local toCam = (cam.Position - faceCF.Position).Unit
		return math.abs(p.X / depth - ray.X) + math.abs(p.Y / depth - ray.Y) + (1 - faceCF.LookVector:Dot(toCam)) * 8
			+ math.abs(depth - 1) * 0.5 + (1 - faceCF.UpVector:Dot(vcam.UpVector)) * 0.5
	end

	local key = ("r6:%d"):format(math.floor(pitch / 0.05 + 0.5))
	local best = ArmPose._cache[key]
	if not best then
		local bestCost = math.huge
		for az = 0, 1.6, 0.1 do
			for el = -0.6, 1.2, 0.1 do
				for roll = -math.pi, math.pi, math.pi / 8 do
					local c = cost(az, el, roll)
					if c < bestCost then
						best, bestCost = { az, el, roll }, c
					end
				end
			end
		end
		local coarse = best
		for az = coarse[1] - 0.1, coarse[1] + 0.1, 0.025 do
			for el = coarse[2] - 0.1, coarse[2] + 0.1, 0.025 do
				for roll = coarse[3] - 0.2, coarse[3] + 0.2, 0.05 do
					local c = cost(az, el, roll)
					if c < bestCost then
						best, bestCost = { az, el, roll }, c
					end
				end
			end
		end
		ArmPose._cache[key] = best
	end
	local armCF = place(best[1], best[2], best[3])
	return torsoCF:Inverse() * armCF * c1 * ArmPose.getTransform(shoulder):Inverse()
end

-- Un fotogramma della posa del braccio sinistro. blend = 0..1 (0 = posa normale).
function ArmPose.stepWatch(char: Model, cam: CFrame, blend: number, originals: { [Instance]: CFrame }, motor: (Model, string, string, string) -> Instance?, set: (Instance, CFrame) -> ())
	local e = blend * blend * (3 - 2 * blend)
	local upper = char:FindFirstChild("LeftUpperArm")
	if upper then
		local torso = char:FindFirstChild("UpperTorso")
		local lower = char:FindFirstChild("LeftLowerArm")
		local shoulder = motor(char, "LeftUpperArm", "LeftShoulder", "UpperTorso")
		local elbow = motor(char, "LeftLowerArm", "LeftElbow", "LeftUpperArm")
		if not (torso and torso:IsA("BasePart") and lower and lower:IsA("BasePart") and shoulder and elbow) then
			return false
		end
		if e <= 0 then
			set(shoulder, originals[shoulder])
			set(elbow, originals[elbow])
			return true
		end
		local c0s, c0e = ArmPose.solveWatch(torso.CFrame, shoulder, elbow, originals[shoulder], originals[elbow], ArmPose.faceRel(lower), cam)
		set(shoulder, originals[shoulder]:Lerp(c0s, e))
		set(elbow, originals[elbow]:Lerp(c0e, e))
		return true
	end
	local torso = char:FindFirstChild("Torso")
	local arm = char:FindFirstChild("Left Arm")
	local shoulder = motor(char, "Left Arm", "Left Shoulder", "Torso")
	if not (torso and torso:IsA("BasePart") and arm and arm:IsA("BasePart") and shoulder) then
		return false
	end
	if e <= 0 then
		set(shoulder, originals[shoulder])
		return true
	end
	set(shoulder, originals[shoulder]:Lerp(ArmPose.solveWatchR6(torso.CFrame, shoulder, originals[shoulder], ArmPose.faceRel(arm), cam), e))
	return true
end

-- Cerca la giuntura sia nel pezzo mosso sia nel pezzo padre (R15 la mette nel braccio, R6 nel busto)
function ArmPose.findMotor(char: Model, partName: string, jointName: string, parentName: string): Instance?
	for _, holder in { partName, parentName } do
		local part = char:FindFirstChild(holder)
		local joint = part and part:FindFirstChild(jointName)
		if joint and (joint:IsA("Motor6D") or joint:IsA("AnimationConstraint")) then
			return joint
		end
	end
	return nil
end

-- Pose originali delle giunture, aggiornate se qualcun altro (es. il ridimensionamento dell'avatar)
-- cambia la giuntura dopo che l'abbiamo letta.
function ArmPose.newPoser()
	local originals: { [Instance]: CFrame } = {}
	local written: { [Instance]: CFrame } = {}
	local function motor(char: Model, partName: string, jointName: string, parentName: string): Instance?
		local joint = ArmPose.findMotor(char, partName, jointName, parentName)
		if joint then
			local current = ArmPose.getC0(joint)
			local last = written[joint]
			if not originals[joint] or (last and (current.Position - last.Position).Magnitude + (current.LookVector - last.LookVector).Magnitude + (current.UpVector - last.UpVector).Magnitude > 1e-3) then
				originals[joint] = current
				written[joint] = nil
			end
		end
		return joint
	end
	local function set(joint: Instance, cf: CFrame)
		ArmPose.setC0(joint, cf)
		written[joint] = ArmPose.getC0(joint)
	end
	return originals, motor, set, function()
		table.clear(originals)
		table.clear(written)
	end
end

function ArmPose.start(player: Player, watchShown: () -> boolean, remotes: Folder, isBlocked: () -> boolean, hide: () -> ())
	local originals, motor, set, reset = ArmPose.newPoser()
	local watchBlend = 0
	local lastSent, lastLook = 0, Vector3.zero

	player.CharacterAdded:Connect(function()
		reset()
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
		local status = player:GetAttribute("Status")

		-- fascio della torcia
		local tool = char:FindFirstChild("Torcia")
		local lens = tool and tool:FindFirstChild("Lente")
		local beam = lens and lens:FindFirstChild("Fascio")
		if beam and beam:IsA("Attachment") and lens:IsA("BasePart") then
			beam.WorldCFrame = CFrame.lookAt(lens.Position, lens.Position + look)
			local now = os.clock()
			local aim = remotes:FindFirstChild("AimTorch") :: RemoteEvent?
			if aim and now - lastSent > 0.07 and look:Dot(lastLook) < 0.9995 then
				lastSent, lastLook = now, look
				aim:FireServer(look)
			end
		end

		-- braccio destro: segue la visuale con torcia o fucile in mano
		local holding = char:FindFirstChild("Torcia") or char:FindFirstChild("Fucile a dardi")
		local right = motor(char, "RightUpperArm", "RightShoulder", "UpperTorso") or motor(char, "Right Arm", "Right Shoulder", "Torso")
		if right then
			local pitch = 0
			if holding and status == "OK" then
				pitch = math.clamp(math.asin(math.clamp(look.Y, -1, 1)), -1.2, 1.2)
			end
			set(right, originals[right] * CFrame.Angles(pitch, 0, 0))
		end

		-- braccio sinistro: orologio davanti agli occhi (anche nella lobby)
		if watchShown() and ((status ~= "OK" and status ~= "Lobby" and status ~= nil) or isBlocked()) then
			hide()
		end
		local want = watchShown() and 1 or 0
		watchBlend = math.clamp(watchBlend + (want > watchBlend and dt / 0.4 or -dt / 0.3), 0, 1)
		ArmPose.stepWatch(char, cam, watchBlend, originals, motor, set)

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
