-- Esporta le parti del mondo costruito su un server vero (per il render di controllo in Blender).
-- Ogni parte: classe, forma, misure, posizione, assi, colore, materiale, trasparenza e, per le
-- MeshPart dei nostri modelli, il nome del modello e della parte (la mesh si prende dai file FBX).

local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local ServerScriptService = game:GetService("ServerScriptService")

local S = require(ServerScriptService.Server.Boot).Start({ test = true })
S.AssetService.WaitReady()

-- un lotto "abitato" per vedere pet e uova nel render
do
	local Visuals = require(ReplicatedStorage.Shared.Visuals)
	local plot = S.PlotService.ByIndex(1)
	local ids = { "Chick", "LavaDragon", "PinguinoPanettone", "Chick", "LavaDragon", "PinguinoPanettone" }
	for i, id in ids do
		local ped = plot.pedestals[i]
		local pet = Visuals.MakePet(id, if i == 2 then "Gold" else "None", if i == 3 then "Giant" else "Normal")
		local point = ped.base:FindFirstChild("PetPoint") :: Attachment
		pet:PivotTo(point.WorldCFrame)
		pet.Parent = plot.model
	end
	for i, rarity in { "Common", "Epic", "Legendary" } do
		local inc = plot.incubators[i]
		local egg = Visuals.MakeEgg(rarity)
		local point = inc.base:FindFirstChild("EggPoint") :: Attachment
		egg:PivotTo(point.WorldCFrame)
		egg.Parent = plot.model
	end
end

local function r3(v: number): number
	return math.floor(v * 1000 + 0.5) / 1000
end

local function modelName(part: BasePart): string?
	local node = part.Parent
	while node and node ~= workspace do
		if node:IsA("Model") then
			local pet = node:GetAttribute("PetId")
			if pet then
				return pet
			end
			local rarity = node:GetAttribute("Rarity")
			if rarity and (node.Name == "Egg" or node.Name == "IncubatingEgg" or string.sub(node.Name, 1, 3) == "Egg") then
				return "Egg" .. rarity
			end
			if ReplicatedStorage.Assets:FindFirstChild(node.Name, true) then
				return node.Name
			end
		end
		node = node.Parent
	end
	return nil
end

local parts = {}
for _, d in workspace:GetDescendants() do
	if d:IsA("BasePart") and d ~= workspace.Terrain and d.Transparency < 1 then
		local cf = d.CFrame
		local entry = {
			c = d.ClassName,
			n = d.Name,
			s = { r3(d.Size.X), r3(d.Size.Y), r3(d.Size.Z) },
			p = { r3(cf.X), r3(cf.Y), r3(cf.Z) },
			r = { r3(cf.RightVector.X), r3(cf.RightVector.Y), r3(cf.RightVector.Z), r3(cf.UpVector.X), r3(cf.UpVector.Y), r3(cf.UpVector.Z) },
			k = { math.floor(d.Color.R * 255 + 0.5), math.floor(d.Color.G * 255 + 0.5), math.floor(d.Color.B * 255 + 0.5) },
			m = d.Material.Name,
			t = r3(d.Transparency),
		}
		if d:IsA("Part") then
			entry.sh = d.Shape.Name
			local mesh = d:FindFirstChildOfClass("SpecialMesh")
			if mesh then
				entry.sm = mesh.MeshType.Name
			end
		elseif d:IsA("WedgePart") then
			entry.sh = "Wedge"
		elseif d:IsA("CornerWedgePart") then
			entry.sh = "CornerWedge"
		elseif d:IsA("MeshPart") then
			entry.mo = modelName(d)
		end
		table.insert(parts, entry)
	end
end
return HttpService:JSONEncode({ count = #parts, parts = parts })
