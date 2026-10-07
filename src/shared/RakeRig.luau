-- Corpo di The Rake: radice invisibile (HumanoidRootPart) più la mesh con scheletro (40 ossa),
-- animata dai client tramite Bone.Transform. Usato dal server per la creatura vera e dai client
-- per le allucinazioni (sagoma nera ancorata).
local Models = require(script.Parent:WaitForChild("Models"))
local RakeAsset = require(script.Parent:WaitForChild("RakeAsset"))

local RakeRig = {}

-- Il centro della HumanoidRootPart sta 3.7 stud sopra il suolo
RakeRig.HIP_HEIGHT = 2.7
RakeRig.ROOT_HEIGHT = 3.7

-- rootCF: CFrame del centro della radice. opts.ghost = sagoma nera ancorata (allucinazione).
function RakeRig.build(model: Model, rootCF: CFrame, opts: { ghost: boolean? }?)
	local ghost = opts and opts.ghost or false
	local root = Instance.new("Part")
	root.Name = "HumanoidRootPart"
	root.Size = Vector3.new(2, 2, 1)
	root.Transparency = 1
	root.CFrame = rootCF
	root.Anchored = ghost
	root.CanCollide = not ghost
	root.CanQuery = not ghost
	root.Parent = model

	local template = Models.template("Rake_Body")
	local body: BasePart
	if template then
		body = (template :: BasePart):Clone()
	else
		body = Instance.new("Part")
		body.Color = Color3.fromRGB(190, 184, 172)
		body.Material = Enum.Material.SmoothPlastic
	end
	body.Name = "Body"
	body.Size = RakeAsset.size
	body.CFrame = rootCF * CFrame.new(RakeAsset.center - Vector3.new(0, RakeRig.ROOT_HEIGHT, 0))
	body.Anchored = ghost
	body.CanCollide = false
	body.CanTouch = false
	body.CanQuery = not ghost
	body.Massless = true
	body.CastShadow = true
	if ghost then
		(body :: any).TextureID = ""
		body.Color = Color3.fromRGB(6, 6, 6)
	end
	body.Parent = model
	if not ghost then
		local weld = Instance.new("WeldConstraint")
		weld.Part0 = root
		weld.Part1 = body
		weld.Parent = body
	end
	model.PrimaryPart = root
	return { root = root, body = body, head = body }
end

return RakeRig
