-- Nidi lungo il sentiero: generano uova della rarita' della zona, annunciano quelle rare,
-- e gestiscono il ritorno delle uova perse. Anche le uova "libere" (meteoriti) passano da qui.

local CollectionService = game:GetService("CollectionService")
local HttpService = game:GetService("HttpService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Events = require(ReplicatedStorage.Shared.Config.Events)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Visuals = require(ReplicatedStorage.Shared.Visuals)
local Weighted = require(ReplicatedStorage.Shared.Util.Weighted)
local Zones = require(ReplicatedStorage.Shared.Config.Zones)

local NestService = {}

type Nest = {
	id: string,
	zone: string,
	cframe: CFrame,
	model: Model?,
	egg: Model?, -- uovo presente nel nido
	eggInfo: any?,
	away: boolean, -- l'uovo e' stato preso e non ancora consegnato/restituito
	respawnAt: number,
	lair: string?,
	weights: { [string]: number }?,
}

local S
local nests: { [string]: Nest } = {}
local folder: Folder
local rng = Random.new()

function NestService.Init(services)
	S = services
	folder = Instance.new("Folder")
	folder.Name = "Nests"
	folder.Parent = workspace
end

local function zoneWeights(nest: Nest): { [string]: number }
	local base = nest.weights or Zones.Get(nest.zone).eggs
	local w = table.clone(base)
	if S.EventService.IsActive("SuperAvalanche") then
		-- le due rarita' piu' alte della zona diventano molto piu' frequenti
		local present = {}
		for _, id in Rarities.Order do
			if w[id] then
				table.insert(present, id)
			end
		end
		for k = math.max(1, #present - 1), #present do
			local id = present[k]
			w[id] *= Events.SuperAvalancheRareBoost
		end
	end
	return w
end

local function attachPrompt(egg: Model, info)
	local root = egg.PrimaryPart or egg:FindFirstChildWhichIsA("BasePart")
	local prompt = Instance.new("ProximityPrompt")
	prompt.Name = "PickupPrompt"
	prompt.ActionText = "PICK UP"
	prompt.ObjectText = info.rarity
	prompt.HoldDuration = GameConfig.PickupHold
	prompt.MaxActivationDistance = 10
	prompt.RequiresLineOfSight = false
	prompt.Style = Enum.ProximityPromptStyle.Custom
	prompt:SetAttribute("Kind", "Egg")
	prompt:SetAttribute("Rarity", info.rarity)
	prompt.UIOffset = Vector2.new(0, 40)
	prompt.Parent = root
	return prompt
end

local function placeEgg(nest: Nest, info)
	local egg = Visuals.MakeEgg(info.rarity)
	egg.Name = "Egg"
	egg:PivotTo(
		nest.cframe
			* CFrame.new(0, 0.55, 0)
			* CFrame.Angles(0, rng:NextNumber(0, math.pi * 2), math.rad(rng:NextNumber(-6, 6)))
	)
	egg:SetAttribute("EggId", info.id)
	egg.Parent = nest.model or folder
	CollectionService:AddTag(egg, "Egg")
	nest.egg = egg
	nest.eggInfo = info
	nest.away = false
	local prompt = attachPrompt(egg, info)
	prompt.Triggered:Connect(function(player)
		if nest.egg ~= egg then
			return
		end
		if not S.CarryService.CanCarry(player) then
			S.StateService.Notify(player, "BackpackFull", nil, "Bad")
			return
		end
		prompt:Destroy()
		nest.egg = nil
		nest.away = true
		egg.Parent = nil
		if not S.CarryService.AddEgg(player, info, egg) then
			-- non dovrebbe succedere (controllato sopra): rimette l'uovo nel nido
			placeEgg(nest, info)
			return
		end
		if nest.lair then
			S.GuardianService.EggTaken(nest.lair, player)
		end
	end)
end

local function spawnEgg(nest: Nest, forced: string?)
	local rarity = forced or Weighted.Pick(Weighted.FromMap(zoneWeights(nest), Rarities.Order), rng)
	local info = { id = HttpService:GenerateGUID(false), rarity = rarity, nestId = nest.id, zone = nest.zone }
	placeEgg(nest, info)
	local zone = Zones.Get(nest.zone)
	if Rarities.Compare(rarity, zone.announceFrom) >= 0 and Rarities.Get(rarity).announce or forced then
		S.StateService.Announce("AnnounceEgg", { rarity = "Rarity_" .. rarity, zone = "Zone_" .. nest.zone }, rarity)
	end
end

local function buildNest(id: string, zone: string, cframe: CFrame, lair: string?, weights): Nest
	local model = S.AssetService.Clone("Props", "Nest")
	if model then
		model.Name = id
		model:PivotTo(cframe)
		model.Parent = folder
	else
		model = Instance.new("Model")
		model.Name = id
		model.Parent = folder
	end
	model:SetAttribute("Zone", zone)
	local nest: Nest = {
		id = id,
		zone = zone,
		cframe = cframe,
		model = model,
		egg = nil,
		eggInfo = nil,
		away = false,
		respawnAt = 0,
		lair = lair,
		weights = weights,
	}
	nests[id] = nest
	return nest
end

function NestService.Start()
	S.MapService.WaitReady()
	for _, n in MapLayout.Nests do
		-- appoggia il nido sul terreno reale (il sentiero e' terreno)
		local pos = n.cframe.Position
		local y = S.MapService.HeightAt(pos.X, pos.Z)
		local cf = CFrame.new(pos.X, y, pos.Z) * (n.cframe - n.cframe.Position)
		buildNest(n.id, n.zone, cf, nil, nil)
	end
	for _, lair in MapLayout.Lairs do
		for k = 1, lair.nests do
			local a = (k / lair.nests) * math.pi * 2
			local p = lair.center + Vector3.new(math.cos(a) * lair.radius * 0.5, 0, math.sin(a) * lair.radius * 0.5)
			local y = S.MapService.HeightAt(p.X, p.Z)
			buildNest(`{lair.id}Lair{k}`, lair.zone, CFrame.new(p.X, y, p.Z), lair.id, lair.eggs)
		end
	end
	for _, nest in nests do
		spawnEgg(nest)
	end
	-- ciclo di ricomparsa
	task.spawn(function()
		while true do
			task.wait(1)
			local now = os.clock()
			for _, nest in nests do
				if not nest.egg and not nest.away and now >= nest.respawnAt then
					spawnEgg(nest)
				end
			end
		end
	end)
	-- uovo segreto: raro, nel cratere, annunciato a tutti
	task.spawn(function()
		while true do
			task.wait(rng:NextNumber(Zones.SecretSpawn.minInterval, Zones.SecretSpawn.maxInterval))
			NestService.SpawnSpecial(Zones.SecretSpawn.zone, "Secret")
		end
	end)
	-- uovo Ultra: rarissimo, una colonna di luce lo rende visibile da tutta la montagna
	task.spawn(function()
		while true do
			task.wait(rng:NextNumber(Zones.UltraSpawn.minInterval, Zones.UltraSpawn.maxInterval))
			-- se un altro uovo Ultra e' ancora in giro se ne aspetta un altro giro
			if not NestService.UltraAround() then
				NestService.SpawnSpecial(Zones.UltraSpawn.zone, "Ultra")
			end
		end
	end)
end

-- L'uovo e' stato messo in un'incubatrice: il nido ricomincia a contare
function NestService.Delivered(info)
	local nest = info.nestId and nests[info.nestId]
	if nest then
		nest.away = false
		nest.respawnAt = os.clock() + Zones.Get(nest.zone).respawn
	end
end

-- L'uovo torna al suo nido (caduta nel vuoto, valanga, tempo scaduto a terra)
function NestService.ReturnEgg(info)
	local nest = info.nestId and nests[info.nestId]
	if not nest then
		return
	end
	if nest.egg then
		nest.away = false
		return
	end
	placeEgg(nest, info)
	S.StateService.Effect(nil, "EggReturn", { position = nest.cframe.Position })
end

-- Uovo speciale in un nido a caso della zona (sostituisce l'uovo presente)
function NestService.SpawnSpecial(zone: string, rarity: string)
	-- preferisce i nidi che non hanno gia' un uovo raro quanto quello speciale (un uovo Segreto
	-- appena annunciato non deve sparire per far posto all'uovo Ultra)
	local candidates, fallback = {}, {}
	for _, nest in nests do
		if nest.zone == zone and not nest.away and not nest.lair then
			table.insert(fallback, nest)
			local held = nest.egg and nest.eggInfo and nest.eggInfo.rarity
			if not held or Rarities.Compare(held, rarity) < 0 then
				table.insert(candidates, nest)
			end
		end
	end
	if #candidates == 0 then
		candidates = fallback
	end
	if #candidates == 0 then
		return
	end
	local nest = candidates[rng:NextInteger(1, #candidates)]
	if nest.egg then
		nest.egg:Destroy()
		nest.egg = nil
	end
	spawnEgg(nest, rarity)
end

-- Uovo "libero" in un punto qualsiasi (meteoriti, regali dell'admin): non torna a nessun nido
function NestService.SpawnLoose(position: Vector3, rarity: string, extra: { [string]: any }?)
	local nest: Nest = {
		id = "Loose" .. HttpService:GenerateGUID(false),
		zone = MapLayout.ZoneAt(position),
		cframe = CFrame.new(position),
		model = nil,
		egg = nil,
		eggInfo = nil,
		away = false,
		respawnAt = math.huge,
		lair = nil,
		weights = nil,
	}
	local info = { id = HttpService:GenerateGUID(false), rarity = rarity, nestId = nil, zone = nest.zone }
	if extra then
		for k, v in extra do
			(info :: any)[k] = v
		end
	end
	placeEgg(nest, info)
	-- dopo 3 minuti sparisce se nessuno lo prende
	task.delay(180, function()
		if nest.egg and nest.egg.Parent then
			S.StateService.Effect(nil, "Poof", { position = position })
			nest.egg:Destroy()
			nest.egg = nil
		end
	end)
	return nest
end

function NestService.All()
	return nests
end

-- C'e' gia' un uovo Ultra in un nido o portato in giro da qualcuno?
function NestService.UltraAround(): boolean
	for _, nest in nests do
		if nest.eggInfo and nest.eggInfo.rarity == "Ultra" and (nest.egg or nest.away) then
			return true
		end
	end
	return false
end

return NestService
