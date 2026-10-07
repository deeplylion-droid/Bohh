-- Scheletro di The Rake costruito con le mesh degli arti e giunture Motor6D (animate dai client).
-- Usato dal server per la creatura vera e dai client per le allucinazioni.
local Models = require(script.Parent:WaitForChild("Models"))

local RakeRig = {}

-- Il centro della HumanoidRootPart sta 3.7 stud sopra il suolo
RakeRig.HIP_HEIGHT = 2.7
RakeRig.ROOT_HEIGHT = 3.7

RakeRig.MOTORS = { "Waist", "Neck", "LShoulder", "RShoulder", "LElbow", "RElbow", "LHip", "RHip", "LKnee", "RKnee" }

local function rad(d: number): number
	return math.rad(d)
end

-- rootCF: CFrame del centro della radice. opts.ghost = sagoma nera ancorata (allucinazione).
function RakeRig.build(model: Model, rootCF: CFrame, opts: { ghost: boolean? }?)
	local ghost = opts and opts.ghost
	local root = Instance.new("Part")
	root.Name = "HumanoidRootPart"
	root.Size = Vector3.new(2, 2, 1)
	root.Transparency = 1
	root.CFrame = rootCF
	root.Anchored = ghost or false
	root.CanCollide = not ghost
	root.CanQuery = not ghost
	root.Parent = model

	local parts = {}
	local function attach(meshName: string, partName: string, parent: BasePart, jointCF: CFrame, motorName: string): BasePart
		local part = Models.mesh(meshName, jointCF, 1, {
			Name = partName,
			Anchored = false,
			Massless = true,
			CanCollide = false,
			CanTouch = false,
			CanQuery = not ghost,
			CastShadow = true,
		}, model)
		if ghost then
			(part :: any).TextureID = ""
			part.Color = Color3.fromRGB(8, 8, 8)
		end
		local motor = Instance.new("Motor6D")
		motor.Name = motorName
		motor.Part0 = parent
		motor.Part1 = part
		motor.C0 = parent.CFrame:ToObjectSpace(jointCF)
		motor.C1 = part.CFrame:ToObjectSpace(jointCF)
		motor.Parent = part
		parts[partName] = part
		return part
	end

	local torso = attach("Rake_Torso", "Torso", root, rootCF, "Waist")
	local neck = rootCF * CFrame.new(0, 2.85, -1.15) * CFrame.Angles(rad(-8), 0, 0)
	local head = attach("Rake_Head", "Head", torso, neck, "Neck")
	for _, side in { -1, 1 } do
		local prefix = side < 0 and "L" or "R"
		local shoulder = rootCF * CFrame.new(side * 0.85, 2.7, -1.05) * CFrame.Angles(rad(18), 0, rad(side * 5))
		local upper = attach("Rake_UpperArm", prefix .. "UpperArm", torso, shoulder, prefix .. "Shoulder")
		local elbow = shoulder * CFrame.new(0, -2.35, 0) * CFrame.Angles(rad(28), 0, 0)
		attach("Rake_Forearm", prefix .. "Forearm", upper, elbow, prefix .. "Elbow")
		local hip = rootCF * CFrame.new(side * 0.45, -0.15, 0.1) * CFrame.Angles(rad(30), 0, rad(side * 3))
		local thigh = attach("Rake_Thigh", prefix .. "Thigh", root, hip, prefix .. "Hip")
		local knee = hip * CFrame.new(0, -1.95, 0) * CFrame.Angles(rad(-63), 0, 0)
		attach("Rake_Shin", prefix .. "Shin", thigh, knee, prefix .. "Knee")
	end

	-- Occhi luminosi (colore cambiato in base allo stato)
	local eyes = {}
	for _, side in { -1, 1 } do
		local eye = Instance.new("Part")
		eye.Name = "Occhio"
		eye.Shape = Enum.PartType.Ball
		eye.Size = Vector3.new(0.17, 0.17, 0.17)
		eye.Material = Enum.Material.Neon
		eye.Color = Color3.fromRGB(255, 240, 220)
		eye.CanCollide = false
		eye.CanQuery = false
		eye.CanTouch = false
		eye.Massless = true
		eye.CFrame = neck * CFrame.new(side * 0.17, 0.92, -1.0)
		local weld = Instance.new("WeldConstraint")
		weld.Part0 = head
		weld.Part1 = eye
		weld.Parent = eye
		eye.Parent = model
		table.insert(eyes, eye)
	end
	local glow = Instance.new("PointLight")
	glow.Name = "Bagliore"
	glow.Range = 7
	glow.Brightness = 1.2
	glow.Color = Color3.fromRGB(255, 230, 210)
	glow.Parent = eyes[1]

	model.PrimaryPart = root
	return { root = root, head = head, torso = torso, eyes = eyes, glow = glow, parts = parts }
end

return RakeRig
