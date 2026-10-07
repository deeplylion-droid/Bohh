-- Braccia in prima persona (client, sul proprio personaggio):
--  - fascio della torcia orientato ogni frame come la visuale e inviato al server;
--  - braccio destro: con torcia o fucile segue la visuale anche in verticale;
--  - braccio sinistro (tasto G): una copia del braccio della skin agganciata alla telecamera, messa in
--    posa con cinematica inversa (spalla, gomito) dal fianco fino a davanti agli occhi, con il quadrante
--    dell'orologio rivolto verso di te;
--  - in prima persona si vede solo il braccio che regge torcia o fucile.
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

local RIGHT_ARM = { "RightUpperArm", "RightLowerArm", "RightHand", "Right Arm" }
local LEFT_ARM = { "LeftUpperArm", "LeftLowerArm", "LeftHand", "Left Arm" }

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
function ArmPose.solveWatchR6(torsoCF: CFrame, shoulder: Instance, c0s: CFrame, faceRel: CFrame, cam: CFrame): (CFrame, CFrame)
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
	return torsoCF:Inverse() * armCF * c1 * ArmPose.getTransform(shoulder):Inverse(), armCF
end

-- Braccio sinistro "da prima persona": una copia locale del braccio della tua skin (stesse mesh,
-- colori, texture e maglietta, con l'orologio al polso) agganciata alla telecamera. Non dipende dalle
-- giunture del personaggio, che il motore di animazione può sovrascrivere.
local ARM_R15 = { "LeftUpperArm", "LeftLowerArm", "LeftHand" }
local ARM_R6 = { "Left Arm" }
local KEEP = { "SurfaceAppearance", "SpecialMesh", "Decal", "Texture" }

function ArmPose.buildViewmodel(char: Model, parent: Instance): { model: Model, parts: { [string]: BasePart }, extras: { { part: BasePart, root: string, rel: CFrame } }, source: Instance, screen: BasePart? }?
	local names = char:FindFirstChild("LeftUpperArm") and ARM_R15 or ARM_R6
	local model = Instance.new("Model")
	model.Name = "BraccioPrimaPersona"
	local hum = Instance.new("Humanoid") -- serve per disegnare maglietta e colori sui pezzi del braccio
	hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	hum.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
	hum.RigType = names == ARM_R15 and Enum.HumanoidRigType.R15 or Enum.HumanoidRigType.R6
	hum.Parent = model
	for _, item in char:GetChildren() do
		if item:IsA("Shirt") or item:IsA("BodyColors") then
			item:Clone().Parent = model
		end
	end
	local parts, extras = {}, {}
	local screen: BasePart? = nil
	for _, name in names do
		local src = char:FindFirstChild(name)
		if not src or not src:IsA("BasePart") then
			model:Destroy()
			return nil
		end
		local copy = src:Clone()
		for _, d in copy:GetDescendants() do
			if d:IsA("BasePart") then
				-- pezzi dell'orologio: diventano pezzi indipendenti posizionati rispetto al braccio
				local rel = copy.CFrame:ToObjectSpace(d.CFrame)
				d.Parent = model
				table.insert(extras, { part = d, root = name, rel = rel })
				if d.Name == "SchermoOrologio" then
					screen = d
				end
			end
		end
		for _, d in copy:GetDescendants() do
			if not d:IsA("BasePart") and not table.find(KEEP, d.ClassName) then
				d:Destroy()
			end
		end
		copy.Parent = model
		parts[name] = copy
	end
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			for _, c in d:GetChildren() do
				if not table.find(KEEP, c.ClassName) then
					c:Destroy()
				end
			end
			d.Anchored = true
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
			d.CastShadow = false
			d.Massless = true
			d.LocalTransparencyModifier = 0
		end
	end
	model.Parent = parent
	return { model = model, parts = parts, extras = extras, source = char:FindFirstChild(names[#names == 3 and 2 or 1]) :: Instance, screen = screen }
end

-- CFrame finali dei pezzi del braccio (nome → CFrame), oppure nil se il personaggio è incompleto
function ArmPose.solveViewmodel(char: Model, cam: CFrame): { [string]: CFrame }?
	local upper = char:FindFirstChild("LeftUpperArm")
	if upper then
		local torso = char:FindFirstChild("UpperTorso")
		local lower = char:FindFirstChild("LeftLowerArm")
		local shoulder = ArmPose.findMotor(char, "LeftUpperArm", "LeftShoulder", "UpperTorso")
		local elbow = ArmPose.findMotor(char, "LeftLowerArm", "LeftElbow", "LeftUpperArm")
		local wrist = ArmPose.findMotor(char, "LeftHand", "LeftWrist", "LeftLowerArm")
		if not (torso and torso:IsA("BasePart") and lower and lower:IsA("BasePart") and shoulder and elbow) then
			return nil
		end
		local _, _, upperCF, lowerCF = ArmPose.solveWatch(torso.CFrame, shoulder, elbow, ArmPose.getC0(shoulder), ArmPose.getC0(elbow), ArmPose.faceRel(lower), cam)
		local handCF = wrist and lowerCF * ArmPose.getC0(wrist) * ArmPose.getC1(wrist):Inverse() or lowerCF * CFrame.new(0, -lower.Size.Y / 2 - 0.3, 0)
		return { LeftUpperArm = upperCF, LeftLowerArm = lowerCF, LeftHand = handCF }
	end
	local torso = char:FindFirstChild("Torso")
	local arm = char:FindFirstChild("Left Arm")
	local shoulder = ArmPose.findMotor(char, "Left Arm", "Left Shoulder", "Torso")
	if not (torso and torso:IsA("BasePart") and arm and arm:IsA("BasePart") and shoulder) then
		return nil
	end
	-- R6: il braccio è un pezzo unico, quindi lo si stacca dalla spalla e lo si fissa alla telecamera
	-- con il quadrante davanti agli occhi, dritto, e il resto del braccio che scende fuori schermo
	local faceRel = ArmPose.faceRel(arm)
	local key = ("r6:%.2f:%.2f"):format(arm.Size.Y, faceRel.Y)
	local rel = ArmPose._cache[key]
	if not rel then
		local ray = ArmPose.WATCH_RAY
		local p = Vector3.new(ray.X * 1.1, ray.Y * 1.1, -1.1)
		local bestCost = math.huge
		for roll = -math.pi, math.pi, math.pi / 36 do
			local faceCam = CFrame.lookAt(p, Vector3.zero, Vector3.yAxis) * CFrame.Angles(0, 0, roll)
			local armCam = faceCam * faceRel:Inverse()
			local top = armCam * Vector3.new(0, arm.Size.Y / 2, 0)
			local c = (1 - faceCam.UpVector.Y) + 2 * math.max(0, top.Y - p.Y + 0.5)
			if c < bestCost then
				rel, bestCost = armCam, c
			end
		end
		ArmPose._cache[key] = rel
	end
	return { ["Left Arm"] = cam * rel }
end

-- Posa del braccio rispetto alla telecamera, calcolata una volta quando alzi il polso (sguardo
-- orizzontale): da lì in poi il braccio è rigidamente agganciato alla visuale e non trema con i
-- movimenti del busto o dell'animazione di camminata.
function ArmPose.relativeGoal(char: Model, cam: CFrame): { [string]: CFrame }?
	local look = cam.LookVector
	local camH = CFrame.new(cam.Position) * CFrame.Angles(0, math.atan2(-look.X, -look.Z), 0)
	local goal = ArmPose.solveViewmodel(char, camH)
	if not goal then
		return nil
	end
	local rel = {}
	for name, cf in goal do
		rel[name] = camH:ToObjectSpace(cf)
	end
	return rel
end

-- Mette il braccio in posa: e = 0 parte dalla posizione del braccio vero (che pende lungo il fianco),
-- e = 1 è il braccio alzato davanti agli occhi. L'interpolazione è gerarchica (spalla → avambraccio →
-- mano) così il gomito resta attaccato durante il movimento.
function ArmPose.poseViewmodel(vm: any, char: Model, goal: { [string]: CFrame }, e: number)
	local names = vm.parts.LeftUpperArm and ARM_R15 or ARM_R6
	local prevReal, prevGoal, prevOut = nil, nil, nil
	local out: { [string]: CFrame } = {}
	for _, name in names do
		local real = char:FindFirstChild(name)
		local realCF = (real and real:IsA("BasePart")) and real.CFrame or goal[name]
		local cf
		if prevReal then
			cf = prevOut * (prevReal:ToObjectSpace(realCF)):Lerp(prevGoal:ToObjectSpace(goal[name]), e)
		else
			cf = realCF:Lerp(goal[name], e)
		end
		vm.parts[name].CFrame = cf
		out[name] = cf
		prevReal, prevGoal, prevOut = realCF, goal[name], cf
	end
	for _, x in vm.extras do
		x.part.CFrame = out[x.root] * x.rel
	end
	return out
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

function ArmPose.start(player: Player, watchShown: () -> boolean, remotes: Folder, isBlocked: () -> boolean, hide: () -> (), onScreen: (BasePart?) -> ())
	local originals, motor, set, reset = ArmPose.newPoser()
	local watchBlend = 0
	local lastSent, lastLook = 0, Vector3.zero
	local vm: any = nil

	player.CharacterAdded:Connect(function()
		reset()
		watchBlend = 0
		if vm then
			vm.model:Destroy()
			vm = nil
		end
	end)

	-- dopo tutti gli aggiornamenti della visuale, così il braccio usa la posizione definitiva della telecamera
	RunService:BindToRenderStep("BracciaPrimaPersona", Enum.RenderPriority.Camera.Value + 20, function(dt)
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
		watchBlend = math.clamp(watchBlend + (want > watchBlend and dt / 0.45 or -dt / 0.3), 0, 1)
		local shown = false
		if watchBlend > 0 then
			local lowerName = char:FindFirstChild("LeftLowerArm") and "LeftLowerArm" or "Left Arm"
			local src = char:FindFirstChild(lowerName)
			local hasWatch = src ~= nil and src:FindFirstChild("SchermoOrologio") ~= nil
			if vm and (vm.source ~= src or vm.model.Parent ~= camera or (hasWatch and not vm.screen)) then
				vm.model:Destroy()
				vm = nil
			end
			if not vm then
				vm = ArmPose.buildViewmodel(char, camera)
				if vm then
					vm.rel = ArmPose.relativeGoal(char, cam)
				end
			end
			local goal = nil
			if vm and vm.rel then
				goal = {}
				for name, rel in vm.rel do
					goal[name] = cam * rel
				end
			end
			if vm and goal then
				ArmPose.poseViewmodel(vm, char, goal, watchBlend * watchBlend * (3 - 2 * watchBlend))
				shown = true
			end
		end
		if vm and not shown then
			vm.model:Destroy()
			vm = nil
		end
		onScreen(shown and vm and vm.screen or nil)

		-- braccio destro visibile in prima persona solo con torcia o fucile in mano; il sinistro resta
		-- nascosto (lo si vede solo come copia quando guardi l'orologio)
		for _, name in RIGHT_ARM do
			local p = char:FindFirstChild(name)
			if p and p:IsA("BasePart") then
				local show = holding ~= nil and status == "OK"
				p.LocalTransparencyModifier = show and 0 or 1
			end
		end
		if shown then
			for _, name in LEFT_ARM do
				local p = char:FindFirstChild(name)
				if p and p:IsA("BasePart") then
					p.LocalTransparencyModifier = 1
					for _, d in p:GetChildren() do
						if d:IsA("BasePart") then
							d.LocalTransparencyModifier = 1
						end
					end
				end
			end
		end
	end)
end

return ArmPose
