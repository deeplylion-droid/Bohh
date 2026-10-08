-- Carica i modelli 3D (pet, uova, oggetti) all'avvio e li prepara come modelli pronti da clonare
-- in ReplicatedStorage.Assets/<Categoria>/<Nome>. Se un asset non e' disponibile crea un segnaposto.

local InsertService = game:GetService("InsertService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Assets = require(ReplicatedStorage.Shared.Assets)
local Signal = require(ReplicatedStorage.Shared.Util.Signal)

local AssetService = {}

AssetService.Ready = false
AssetService.Loaded = Signal.new()

local root: Folder
local CATEGORY = { pet = "Pets", egg = "Eggs", prop = "Props", bat = "Bats", fx = "Effects" }

local function folderFor(kind: string): Folder
	local name = CATEGORY[kind] or "Props"
	local f = root:FindFirstChild(name) :: Folder?
	if not f then
		f = Instance.new("Folder")
		f.Name = name
		f.Parent = root
	end
	return f :: Folder
end

local function material(name: string): Enum.Material
	local ok, m = pcall(function()
		return (Enum.Material :: any)[name]
	end)
	return if ok and m then m else Enum.Material.SmoothPlastic
end

local function newRoot(): Part
	local p = Instance.new("Part")
	p.Name = "Root"
	p.Size = Vector3.new(1, 1, 1)
	p.Transparency = 1
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.CFrame = CFrame.new()
	return p
end

-- Applica le proprieta' del manifest alle MeshPart caricate e le raccoglie in un modello pulito
local function build(name: string, info, loaded: Instance): Model
	local model = Instance.new("Model")
	model.Name = name
	local base = newRoot()
	base.Parent = model
	model.PrimaryPart = base
	local byName = {}
	for _, p in info.parts do
		byName[p.name] = p
	end
	for _, d in loaded:GetDescendants() do
		if d:IsA("MeshPart") then
			local pi = byName[d.Name]
			d.Anchored = true
			d.CanCollide = false
			d.CanQuery = false
			d.CanTouch = false
			d.CastShadow = true
			if pi then
				-- posizione e misure dal manifest (coordinate del modello, origine ai piedi):
				-- non dipendono da dove l'importatore ha messo le parti
				if pi.center then
					d.CFrame = CFrame.new(pi.center[1], pi.center[2], pi.center[3]) * d.CFrame.Rotation
				end
				d.Color = Color3.fromRGB(pi.color[1], pi.color[2], pi.color[3])
				d.Material = material(pi.material)
				d.Transparency = pi.transparency or 0
				d.Reflectance = pi.reflectance or 0
				d:SetAttribute("Role", pi.role)
				d:SetAttribute("BaseColor", d.Color)
				d:SetAttribute("BaseMaterial", pi.material)
				if pi.group then
					d:SetAttribute("Group", pi.group)
					if pi.pivot then
						d:SetAttribute("Pivot", Vector3.new(pi.pivot[1], pi.pivot[2], pi.pivot[3]))
					end
				end
				if pi.material == "Neon" then
					d.CastShadow = false
				end
			end
			d.Parent = model
		end
	end
	model.WorldPivot = CFrame.new()
	model:SetAttribute("Height", info.size[2])
	return model
end

-- Segnaposto riconoscibile (forma semplice colorata) se l'asset manca o non si carica
local function placeholder(name: string, info): Model
	local model = Instance.new("Model")
	model.Name = name
	local base = newRoot()
	base.Parent = model
	model.PrimaryPart = base
	local size = Vector3.new(info.size[1], info.size[2], info.size[3])
	local main = info.parts[1]
	local p = Instance.new("Part")
	p.Name = "Body"
	p.Shape = if info.kind == "prop" then Enum.PartType.Block else Enum.PartType.Ball
	p.Size = if info.kind == "prop" then size else Vector3.one * math.max(size.X, size.Y, size.Z) * 0.8
	p.CFrame = CFrame.new(0, size.Y / 2, 0)
	p.Anchored = true
	p.CanCollide = false
	p.CanQuery = false
	p.CanTouch = false
	p.Material = Enum.Material.SmoothPlastic
	p.Color = if main then Color3.fromRGB(main.color[1], main.color[2], main.color[3]) else Color3.fromRGB(255, 200, 80)
	p:SetAttribute("Role", "skin")
	p:SetAttribute("BaseColor", p.Color)
	p:SetAttribute("BaseMaterial", "SmoothPlastic")
	p.Parent = model
	model.WorldPivot = CFrame.new()
	model:SetAttribute("Height", size.Y)
	model:SetAttribute("Placeholder", true)
	return model
end

local function loadOne(name: string, info)
	local folder = folderFor(info.kind)
	local model
	if info.asset and info.asset ~= 0 then
		for attempt = 1, 3 do
			local ok, result = pcall(InsertService.LoadAsset, InsertService, info.asset)
			if ok and result then
				model = build(name, info, result)
				result:Destroy()
				break
			end
			warn(`[AssetService] {name} ({info.asset}) tentativo {attempt}: {result}`)
			task.wait(attempt)
		end
	end
	if not model then
		model = placeholder(name, info)
	end
	model.Parent = folder
end

function AssetService.Init(_S)
	root = ReplicatedStorage:FindFirstChild("Assets") :: Folder
	if not root then
		root = Instance.new("Folder")
		root.Name = "Assets"
		root.Parent = ReplicatedStorage
	end
	for _, kind in { "pet", "egg", "prop", "bat", "fx" } do
		folderFor(kind)
	end
end

function AssetService.Start()
	local pending = 0
	local done = Signal.new()
	for name, info in Assets.Models do
		pending += 1
		task.spawn(function()
			local ok, err = pcall(loadOne, name, info)
			if not ok then
				warn(`[AssetService] errore su {name}: {err}`)
			end
			pending -= 1
			if pending == 0 then
				done:Fire()
			end
		end)
	end
	if pending > 0 then
		-- al massimo 25 s: gli asset ancora in caricamento restano dei segnaposto
		local finished = false
		task.delay(25, function()
			if not finished then
				warn(`[AssetService] {pending} asset ancora in caricamento dopo 25 s`)
				done:Fire()
			end
		end)
		done:Wait()
		finished = true
	end
	AssetService.Ready = true
	root:SetAttribute("Ready", true)
	AssetService.Loaded:Fire()
end

function AssetService.WaitReady()
	if not AssetService.Ready then
		AssetService.Loaded:Wait()
	end
end

-- Clona un modello pronto (nil se non esiste)
function AssetService.Clone(category: string, name: string): Model?
	local f = root:FindFirstChild(category)
	local m = f and f:FindFirstChild(name)
	return if m then (m :: Model):Clone() else nil
end

function AssetService.Has(category: string, name: string): boolean
	local f = root:FindFirstChild(category)
	return f ~= nil and f:FindFirstChild(name) ~= nil
end

return AssetService
