-- Furti di uova (dalle incubatrici) e pet (dai piedistalli) degli altri giocatori.
-- La refurtiva resta nei dati del proprietario finche' il ladro non la porta nel suo lotto:
-- se il ladro la perde torna a casa, se il proprietario esce sparisce. Nessuna duplicazione possibile.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Net = require(ReplicatedStorage.Shared.Net)
local Pets = require(ReplicatedStorage.Shared.Config.Pets)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Visuals = require(ReplicatedStorage.Shared.Visuals)

local StealService = {}

type Steal = {
	victim: Player,
	kind: "Egg" | "Pet",
	slot: string?, -- incubatrice (uova)
	uid: string?, -- pet
	petId: string?,
	rarity: string,
	base: BasePart, -- incubatrice o piedistallo del proprietario
	hidden: Model?, -- modello originale nascosto durante il furto
}

local S
local alertEvent: RemoteEvent
local joinedAt: { [Player]: number } = {}

function StealService.Init(services)
	S = services
end

local function setHidden(model: Model?, hidden: boolean)
	if not model then
		return
	end
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") and d.Name ~= "Root" then
			if hidden then
				d:SetAttribute("PreStealT", d.Transparency)
				d.Transparency = 1
			else
				d.Transparency = (d:GetAttribute("PreStealT") :: number?) or 0
			end
		elseif d:IsA("ParticleEmitter") or d:IsA("PointLight") then
			d.Enabled = not hidden
		end
	end
end

local function countStolen(thief: Player, kind: string): number
	local n = 0
	for _, c in S.CarryService.Items(thief) do
		if c.stolen and c.stolen.kind == kind then
			n += 1
		end
	end
	return n
end

local function freeCount(thief: Player, kind: string): number
	local data = S.DataService.Get(thief)
	if not data then
		return 0
	end
	if kind == "Egg" then
		local free = 0
		for i = 1, S.PlotService.IncubatorCount(thief) do
			if data.Incubators[tostring(i)] == nil then
				free += 1
			end
		end
		return free
	end
	local used = 0
	for _ in data.Pets do
		used += 1
	end
	return S.PlotService.PedestalCount(thief) - used
end

local function canStart(thief: Player, victim: Player?, base: BasePart, kind: string): boolean
	if not victim or victim == thief or not S.DataService.Get(thief) or not S.PlotService.Get(thief) then
		return false
	end
	if base:GetAttribute("BeingStolen") or base:GetAttribute("Locked") then
		return false
	end
	if S.RagdollService.IsRagdolled(thief) then
		return false
	end
	if not S.CarryService.CanCarry(thief) then
		S.StateService.Notify(thief, "BackpackFull", nil, "Bad")
		return false
	end
	if os.clock() - (joinedAt[victim] or 0) < GameConfig.StealProtectAfterJoin then
		S.StateService.Notify(thief, "CantStealProtected", nil, "Bad")
		return false
	end
	if freeCount(thief, kind) - countStolen(thief, kind) < 1 then
		S.StateService.Notify(thief, "CantStealNoRoom", nil, "Bad")
		return false
	end
	-- il ladro deve essere davvero vicino (anti-exploit)
	local hrp = S.CharacterService.Root(thief)
	if not hrp or (hrp.Position - base.Position).Magnitude > 14 then
		return false
	end
	return true
end

local function itemKey(st: Steal): string
	return if st.kind == "Pet" then "Pet_" .. (st.petId :: string) else "Egg_" .. st.rarity
end

local function startSteal(thief: Player, plot, base: BasePart, kind: "Egg" | "Pet", slotOrUid: string)
	local victim = plot.owner
	local data = S.DataService.Get(victim)
	if not data then
		return
	end
	local st: Steal
	local carryModel: Model
	if kind == "Egg" then
		local entry = data.Incubators[slotOrUid]
		if not entry then
			return
		end
		st = { victim = victim, kind = "Egg", slot = slotOrUid, rarity = entry.Rarity, base = base, hidden = S.HatchService.Visual(victim, slotOrUid) }
		carryModel = Visuals.MakeEgg(entry.Rarity)
	else
		local pet = data.Pets[slotOrUid]
		if not pet then
			return
		end
		local rarity = Pets.Get(pet.Id).rarity
		st = { victim = victim, kind = "Pet", uid = slotOrUid, petId = pet.Id, rarity = rarity, base = base, hidden = S.PetService.Model(victim, slotOrUid) }
		carryModel = Visuals.MakePet(pet.Id, pet.Mutation, "Mini")
	end
	base:SetAttribute("BeingStolen", true)
	local prompt = base:FindFirstChild("StealPrompt") :: ProximityPrompt?
	if prompt then
		prompt.Enabled = false
	end
	setHidden(st.hidden, true)
	S.CarryService.AddStolen(thief, carryModel, st, st.rarity, kind)
	alertEvent:FireClient(victim, thief.UserId, itemKey(st))
	S.StateService.Effect(victim, "Alarm", {})
	S.AnalyticsService.Custom(thief, "StealStart", 1, { kind = kind, rarity = st.rarity })
end

local function restore(st: Steal)
	st.base:SetAttribute("BeingStolen", nil)
	setHidden(st.hidden, false)
	local prompt = st.base:FindFirstChild("StealPrompt") :: ProximityPrompt?
	if prompt and st.victim.Parent == Players then
		prompt.Enabled = true
	end
end

-- Il ladro ha perso la refurtiva: torna al proprietario
function StealService.Cancel(thief: Player, item, reason: string)
	local st: Steal = item.stolen
	if not st then
		return
	end
	restore(st)
	if st.victim.Parent == Players then
		S.StateService.Notify(st.victim, "StealStopped", { item = itemKey(st) }, "Good")
	end
	if reason ~= "Left" then
		S.StateService.Notify(thief, "StealStopped", { item = itemKey(st) }, "Bad")
	end
end

-- Il ladro e' arrivato nel suo lotto: trasferimento definitivo
function StealService.Complete(thief: Player, item): boolean
	local st: Steal = item.stolen
	local victim = st.victim
	if victim.Parent ~= Players or not S.DataService.Get(victim) then
		return true -- il proprietario e' uscito: gestito da onVictimLeft
	end
	if st.kind == "Egg" then
		if not S.HatchService.FreeSlot(thief) then
			return false
		end
		local remaining = S.HatchService.Remaining(victim, st.slot :: string)
		local entry = S.HatchService.Take(victim, st.slot :: string)
		if not entry then
			restore(st)
			return true
		end
		S.HatchService.Insert(thief, { rarity = entry.Rarity, remaining = remaining, duration = entry.Duration, cosmicMin = entry.CosmicMin })
	else
		if not S.PetService.FreeSlot(thief) then
			return false
		end
		local pet = S.PetService.RemovePet(victim, st.uid :: string)
		if not pet then
			restore(st)
			return true
		end
		S.PetService.AddPet(thief, { Id = pet.Id, Mutation = pet.Mutation, Size = pet.Size })
		S.IndexService.Record(thief, pet.Id, pet.Mutation)
	end
	st.base:SetAttribute("BeingStolen", nil)
	local tData, vData = S.DataService.Get(thief), S.DataService.Get(victim)
	tData.Stats.Steals += 1
	vData.Stats.Stolen += 1
	S.StateService.Push(thief, { "Stats" })
	S.StateService.Push(victim, { "Stats" })
	S.StateService.Notify(thief, "StealSuccessThief", { item = itemKey(st), name = victim.DisplayName }, "Gold")
	S.StateService.Notify(victim, "StealSuccessVictim", { item = itemKey(st), name = thief.DisplayName }, "Bad")
	S.StateService.Effect(thief, "StealSuccess", { rarity = st.rarity })
	if st.kind == "Pet" and Rarities.Get(st.rarity).order >= 5 then
		S.StateService.Announce("AnnounceSteal", { thief = thief.DisplayName, victim = victim.DisplayName, pet = "Pet_" .. (st.petId :: string) }, st.rarity)
	end
	S.AnalyticsService.Custom(thief, "StealDone", 1, { kind = st.kind, rarity = st.rarity })
	return true
end

-- Il proprietario esce: la refurtiva in viaggio sparisce (resta salvata nei suoi dati)
local function onVictimLeft(victim: Player)
	for _, thief in Players:GetPlayers() do
		for _, item in table.clone(S.CarryService.Items(thief)) do
			if item.stolen and item.stolen.victim == victim then
				S.CarryService.Remove(thief, item)
				item.model:Destroy()
				S.StateService.Notify(thief, "StealOwnerLeft", nil, "Bad")
			end
		end
	end
end

function StealService.Start()
	alertEvent = Net.Event("StealAlert")
	for _, plot in S.PlotService.Plots do
		for i, inc in plot.incubators do
			inc.stealPrompt.Triggered:Connect(function(thief)
				local slot = tostring(i)
				if canStart(thief, plot.owner, inc.base, "Egg") then
					startSteal(thief, plot, inc.base, "Egg", slot)
				end
			end)
		end
		for _, ped in plot.pedestals do
			ped.stealPrompt.Triggered:Connect(function(thief)
				local uid = ped.base:GetAttribute("PetUid")
				if uid and canStart(thief, plot.owner, ped.base, "Pet") then
					startSteal(thief, plot, ped.base, "Pet", uid)
				end
			end)
		end
	end
	S.DataService.Loaded:Connect(function(player)
		joinedAt[player] = os.clock()
	end)
	Players.PlayerRemoving:Connect(function(player)
		onVictimLeft(player)
		joinedAt[player] = nil
	end)
end

function StealService.IsBeingStolen(base: BasePart): boolean
	return base:GetAttribute("BeingStolen") == true
end

return StealService
