-- Incubatrici: inserimento delle uova, conto alla rovescia (anche offline), schiusa con estrazione
-- del pet, della mutazione e della taglia.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Events = require(ReplicatedStorage.Shared.Config.Events)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Net = require(ReplicatedStorage.Shared.Net)
local Pets = require(ReplicatedStorage.Shared.Config.Pets)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Upgrades = require(ReplicatedStorage.Shared.Config.Upgrades)
local Variants = require(ReplicatedStorage.Shared.Config.Variants)
local Visuals = require(ReplicatedStorage.Shared.Visuals)
local Weighted = require(ReplicatedStorage.Shared.Util.Weighted)

local HatchService = {}

local S
local rng = Random.new()
-- uova visibili nelle incubatrici: [player][slot] = model
local visuals: { [Player]: { [string]: Model } } = {}
local revealEvent: RemoteEvent

function HatchService.Init(services)
	S = services
end

local function now(): number
	return os.time()
end

function HatchService.Duration(player: Player, rarity: string): number
	local data = S.DataService.Get(player)
	local level = if data then data.Upgrades.HatchSpeed else 0
	local factor = Upgrades.HatchFactor(level, S.MonetizationService.HasPass(player, "FastHatch"))
	return math.max(5, math.floor(Rarities.Get(rarity).hatch * factor))
end

local function slotPart(player: Player, slot: string)
	local plot = S.PlotService.Get(player)
	if not plot then
		return nil
	end
	local inc = plot.incubators[tonumber(slot) :: number]
	return inc
end

local function refreshPrompts(player: Player, slot: string)
	local inc = slotPart(player, slot)
	local data = S.DataService.Get(player)
	if not inc or not data then
		return
	end
	local entry = data.Incubators[slot]
	local ready = entry ~= nil and now() >= entry.Start + entry.Duration
	inc.prompt.Enabled = ready
	inc.prompt.ActionText = "HATCH"
	inc.stealPrompt.Enabled = entry ~= nil and not inc.base:GetAttribute("BeingStolen")
	inc.base:SetAttribute("EggRarity", if entry then entry.Rarity else nil)
	inc.base:SetAttribute("ReadyAt", if entry then entry.Start + entry.Duration else nil)
	inc.base:SetAttribute("Duration", if entry then entry.Duration else nil)
	inc.base:SetAttribute("Ready", ready)
end

-- Mostra (o toglie) l'uovo sopra l'incubatrice
function HatchService.ShowEgg(player: Player, slot: string)
	visuals[player] = visuals[player] or {}
	local old = visuals[player][slot]
	if old then
		old:Destroy()
		visuals[player][slot] = nil
	end
	local data = S.DataService.Get(player)
	local inc = slotPart(player, slot)
	local entry = data and data.Incubators[slot]
	if inc and entry then
		local egg = Visuals.MakeEgg(entry.Rarity)
		egg.Name = "IncubatingEgg"
		local point = inc.base:FindFirstChild("EggPoint") :: Attachment?
		egg:PivotTo(if point then point.WorldCFrame else inc.base.CFrame)
		egg:SetAttribute("Slot", slot)
		egg:SetAttribute("OwnerUserId", player.UserId)
		egg.Parent = inc.base
		game:GetService("CollectionService"):AddTag(egg, "IncubatingEgg")
		visuals[player][slot] = egg
	end
	refreshPrompts(player, slot)
end

function HatchService.Visual(player: Player, slot: string): Model?
	return visuals[player] and visuals[player][slot]
end

function HatchService.FreeSlot(player: Player): string?
	local data = S.DataService.Get(player)
	if not data then
		return nil
	end
	for i = 1, S.PlotService.IncubatorCount(player) do
		local key = tostring(i)
		if data.Incubators[key] == nil then
			return key
		end
	end
	return nil
end

-- Mette un uovo nella prima incubatrice libera. egg.remaining (uova rubate) conserva il tempo rimasto.
function HatchService.Insert(
	player: Player,
	egg: { rarity: string, remaining: number?, duration: number?, cosmicMin: number? }
): boolean
	local slot = HatchService.FreeSlot(player)
	local data = S.DataService.Get(player)
	if not slot or not data then
		return false
	end
	local duration = egg.duration or HatchService.Duration(player, egg.rarity)
	local start = now()
	if egg.remaining then
		start = now() - (duration - egg.remaining)
	end
	S.StateService.Set(player, { "Incubators", slot }, {
		Rarity = egg.rarity,
		Start = start,
		Duration = duration,
		CosmicMin = egg.cosmicMin,
	})
	HatchService.ShowEgg(player, slot)
	S.StateService.Notify(player, "EggDelivered", { egg = "Egg_" .. egg.rarity }, "Good")
	S.StateService.Effect(player, "Deliver", { rarity = egg.rarity })
	return true
end

-- Toglie l'uovo da un'incubatrice (furto) restituendo i suoi dati
function HatchService.Take(player: Player, slot: string)
	local data = S.DataService.Get(player)
	local entry = data and data.Incubators[slot]
	if not entry then
		return nil
	end
	S.StateService.Set(player, { "Incubators", slot }, nil)
	HatchService.ShowEgg(player, slot)
	HatchService.FillPending(player)
	return entry
end

-- Uova regalo in attesa di un'incubatrice libera
function HatchService.AddPending(player: Player, rarity: string)
	local data = S.DataService.Get(player)
	if not data then
		return
	end
	if not HatchService.Insert(player, { rarity = rarity }) then
		table.insert(data.PendingEggs, { Rarity = rarity })
		S.StateService.Push(player, { "PendingEggs" })
		S.StateService.Notify(player, "EggStored", nil, "Info")
	end
end

function HatchService.FillPending(player: Player)
	local data = S.DataService.Get(player)
	if not data then
		return
	end
	while #data.PendingEggs > 0 and HatchService.FreeSlot(player) do
		local item = table.remove(data.PendingEggs, 1)
		HatchService.Insert(player, { rarity = item.Rarity })
	end
	S.StateService.Push(player, { "PendingEggs" })
end

-- Estrazione del pet: la fortuna sposta i pesi verso i pet piu' rari della fascia
local function rollPet(rarity: string, luck: number): string
	local list = Pets.ByRarity[rarity]
	local entries = {}
	for i, p in list do
		local w = p.chance * (if i > 1 then luck else 1)
		table.insert(entries, { value = p.id, weight = w })
	end
	return Weighted.Pick(entries, rng)
end

function HatchService.Hatch(player: Player, slot: string, skipRequirement: boolean?)
	local data = S.DataService.Get(player)
	local entry = data and data.Incubators[slot]
	if not entry then
		return
	end
	if not skipRequirement and now() < entry.Start + entry.Duration then
		return
	end
	local inc = slotPart(player, slot)
	if inc and inc.base:GetAttribute("BeingStolen") then
		return -- un ladro lo sta portando via
	end
	-- serve un posto libero: un piedistallo, o il trono per i pet Ultra
	if not S.PetService.HasRoomFor(player, entry.Rarity) then
		S.StateService.Notify(player, if entry.Rarity == "Ultra" then "NoThrone" else "NoPedestal", nil, "Bad")
		return
	end
	local luck = S.MonetizationService.LuckMultiplier(player)
	local minChance = {}
	if S.EventService.IsActive("GoldenHour") then
		minChance.Gold = Events.GoldenHourGoldMin
	end
	if entry.CosmicMin then
		minChance.Cosmic = entry.CosmicMin
	end
	local petId = rollPet(entry.Rarity, luck)
	local mutation = Variants.RollMutation(rng, luck, minChance)
	local size = Variants.RollSize(rng, luck)
	S.StateService.Set(player, { "Incubators", slot }, nil)
	HatchService.ShowEgg(player, slot)
	local isNew = S.IndexService.Record(player, petId, mutation)
	local uid = S.PetService.AddPet(player, { Id = petId, Mutation = mutation, Size = size })
	data.Stats.Hatched += 1
	revealEvent:FireClient(player, {
		pet = petId,
		rarity = entry.Rarity,
		mutation = mutation,
		size = size,
		new = isNew,
		uid = uid,
	})
	S.TutorialService.Advance(player, "Hatched")
	S.AnalyticsService.Custom(player, "Hatch", 1, { rarity = entry.Rarity, mutation = mutation })
	if Rarities.Get(entry.Rarity).order >= 6 or mutation == "Cosmic" or mutation == "Rainbow" then
		S.StateService.Announce("AnnounceHatch", { name = player.DisplayName, pet = "Pet_" .. petId }, entry.Rarity)
	end
	HatchService.FillPending(player)
end

-- Salta l'attesa (prodotto Robux): l'uovo con piu' tempo rimasto entro la rarita' massima
function HatchService.Skip(player: Player, maxRarity: string): boolean
	local data = S.DataService.Get(player)
	if not data then
		return false
	end
	local bestSlot, bestLeft = nil, 0
	for slot, entry in data.Incubators do
		local left = entry.Start + entry.Duration - now()
		if left > bestLeft and Rarities.Compare(entry.Rarity, maxRarity) <= 0 then
			bestSlot, bestLeft = slot, left
		end
	end
	if not bestSlot then
		return false
	end
	local entry = data.Incubators[bestSlot]
	entry.Start = now() - entry.Duration
	S.StateService.Set(player, { "Incubators", bestSlot }, entry)
	refreshPrompts(player, bestSlot)
	return true
end

-- Tempo rimasto di un'incubatrice (0 se pronta)
function HatchService.Remaining(player: Player, slot: string): number?
	local data = S.DataService.Get(player)
	local entry = data and data.Incubators[slot]
	if not entry then
		return nil
	end
	return math.max(0, entry.Start + entry.Duration - now())
end

function HatchService.Start()
	revealEvent = Net.Event("HatchReveal")
	for _, plot in S.PlotService.Plots do
		for i, inc in plot.incubators do
			inc.prompt.Triggered:Connect(function(who)
				if plot.owner == who then
					HatchService.Hatch(who, tostring(i))
				end
			end)
		end
	end
	S.PlotService.Assigned:Connect(function(player, plot)
		local data = S.DataService.Get(player)
		if not data then
			return
		end
		-- incubatrici fuori dal numero sbloccato (dati vecchi): sposta le uova nelle libere
		for slot, entry in table.clone(data.Incubators) do
			if tonumber(slot) > S.PlotService.IncubatorCount(player) then
				data.Incubators[slot] = nil
				table.insert(data.PendingEggs, { Rarity = entry.Rarity })
			end
		end
		for i = 1, #plot.incubators do
			HatchService.ShowEgg(player, tostring(i))
		end
		HatchService.FillPending(player)
		-- uovo iniziale per i nuovi giocatori: si schiude in pochi secondi
		if data.Tutorial == 0 and next(data.Incubators) == nil and data.Stats.Hatched == 0 then
			HatchService.Insert(player, { rarity = "Common", duration = GameConfig.StarterEggHatch })
		end
	end)
	S.PlotService.Released:Connect(function(player, plot)
		for i = 1, #plot.incubators do
			local list = visuals[player]
			if list and list[tostring(i)] then
				list[tostring(i)]:Destroy()
			end
			plot.incubators[i].base:SetAttribute("EggRarity", nil)
			plot.incubators[i].base:SetAttribute("ReadyAt", nil)
			plot.incubators[i].base:SetAttribute("Duration", nil)
			plot.incubators[i].base:SetAttribute("Ready", false)
		end
		visuals[player] = nil
	end)
	-- aggiorna lo stato "pronto" delle incubatrici
	task.spawn(function()
		while true do
			task.wait(1)
			for _, player in Players:GetPlayers() do
				local data = S.DataService.Get(player)
				if data and S.PlotService.Get(player) then
					for slot, _ in data.Incubators do
						refreshPrompts(player, slot)
					end
				end
			end
		end
	end)
end

return HatchService
