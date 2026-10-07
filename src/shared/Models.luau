-- Modelli 3D generati da tools/meshgen e caricati su Roblox (vedi Assets.luau).
-- Il server li carica una volta in ReplicatedStorage.RakeAssets; server e client li clonano da lì.
-- Se il caricamento fallisce (ad esempio in un luogo di un altro proprietario) si usano blocchi semplici.
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Assets = require(script.Parent:WaitForChild("Assets"))

local Models = {}

local folder: Instance? = nil

function Models.load(): boolean
	if folder then
		return true
	end
	if not RunService:IsServer() then
		folder = ReplicatedStorage:WaitForChild("RakeAssets")
		return true
	end
	local f = Instance.new("Folder")
	f.Name = "RakeAssets"
	local ok, pack = pcall(function()
		return game:GetService("InsertService"):LoadAsset(Assets.ASSET_ID)
	end)
	if ok and pack then
		for _, d in pack:GetDescendants() do
			if d:IsA("MeshPart") then
				d.Anchored = true
				d.CanCollide = false
				d.CanTouch = false
				d.CanQuery = false
				d.Parent = f
			end
		end
		pack:Destroy()
	else
		warn("[Modelli] Impossibile caricare i modelli 3D, uso forme semplici: " .. tostring(pack))
	end
	-- corpo della creatura (mesh con scheletro, asset separato)
	local okBody, bodyPack = pcall(function()
		return game:GetService("InsertService"):LoadAsset(require(script.Parent:WaitForChild("RakeAsset")).ASSET_ID)
	end)
	if okBody and bodyPack then
		local body = bodyPack:FindFirstChildWhichIsA("MeshPart", true)
		if body then
			body.Anchored = true
			body.CanCollide = false
			body.CanTouch = false
			body.Parent = f
		end
		bodyPack:Destroy()
	else
		warn("[Modelli] Impossibile caricare la creatura: " .. tostring(bodyPack))
	end
	f.Parent = ReplicatedStorage
	folder = f
	return ok
end

function Models.template(name: string): Instance?
	return folder and folder:FindFirstChild(name)
end

function Models.info(name: string)
	return Assets.MESHES[name]
end

-- Clona la mesh `name` con l'origine (punto di aggancio) in originCF e la scala indicata.
function Models.mesh(name: string, originCF: CFrame, scale: number?, props: { [string]: any }?, parent: Instance?): BasePart
	local s = scale or 1
	local info = Assets.MESHES[name]
	local template = folder and folder:FindFirstChild(name)
	local part: BasePart
	if template then
		part = (template :: BasePart):Clone()
	else
		part = Instance.new("Part")
		part.Anchored = true
		part.CanCollide = false
		part.CanQuery = false
		part.CanTouch = false
		part.Material = Enum.Material.SmoothPlastic
		part.Color = Color3.fromRGB(60, 60, 60)
	end
	part.Name = name
	if info then
		part.Size = info.size * s
		part.CFrame = originCF * CFrame.new(info.center * s)
	else
		part.CFrame = originCF
	end
	if props then
		for key, value in props do
			(part :: any)[key] = value
		end
	end
	part.Parent = parent
	return part
end

return Models
