-- Pet sui piedistalli: posizionamento, guadagno al secondo, raccolta sulla pedana, vendita.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Pets = require(ReplicatedStorage.Shared.Config.Pets)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Variants = require(ReplicatedStorage.Shared.Config.Variants)
local Visuals = require(ReplicatedStorage.Shared.Visuals)

local PetService = {}

local S
local models: { [Player]: { [string]: Model } } = {} -- [player][uid]

function PetService.Init(services)
	S = services
end

-- Guadagno al secondo di base di un pet (senza bonus del giocatore)
function PetService.BaseIncome(pet: { Id: string, Mutation: string, Size: string }): number
	local def = Pets.Get(pet.Id)
	return def.income * Variants.Mutations[pet.Mutation or "None"].mult * Variants.Sizes[pet.Size or "Normal"].mult
end

-- Moltiplicatore del giocatore: pass Monete x2, VIP, bonus amici, righe complete dell'album
function PetService.Multiplier(player: Player): number
	local m = 1
	if S.MonetizationService.HasPass(player, "DoubleCoins") then
		m *= 2
	end
	local bonus = 0
	if S.MonetizationService.HasPass(player, "VIP") then
		bonus += GameConfig.VIPIncomeBonus
	end
	bonus += (player:GetAttribute("FriendBonus") or 0)
	bonus += S.IndexService.Bonus(player)
	return m * (1 + bonus)
end

function PetService.IncomeOf(player: Player, pet): number
	return PetService.BaseIncome(pet) * PetService.Multiplier(player)
end

function PetService.TotalIncome(player: Player): number
	local data = S.DataService.Get(player)
	if not data then
		return 0
	end
	local total = 0
	for _, pet in data.Pets do
		total += PetService.BaseIncome(pet)
	end
	return total * PetService.Multiplier(player)
end

function PetService.SellValue(pet): number
	return math.floor(PetService.BaseIncome(pet) * Rarities.Get(Pets.Get(pet.Id).rarity).sell)
end

-- Posto libero per un pet: i pet Ultra (giganti) vanno solo sul trono (slot 0), gli altri sui
-- piedistalli sbloccati. Senza petId si cerca un piedistallo normale.
function PetService.FreeSlot(player: Player, petId: string?): number?
	local data = S.DataService.Get(player)
	if not data then
		return nil
	end
	local used = {}
	for _, pet in data.Pets do
		used[pet.Slot] = true
	end
	if petId and Pets.Get(petId).giant then
		return if used[0] then nil else 0
	end
	for i = 1, S.PlotService.PedestalCount(player) do
		if not used[i] then
			return i
		end
	end
	return nil
end

-- C'e' posto per un pet di questa rarita'? (prima di sapere quale pet uscira' dall'uovo)
function PetService.HasRoomFor(player: Player, rarity: string): boolean
	local list = Pets.ByRarity[rarity]
	local sample = list and list[1]
	return PetService.FreeSlot(player, if sample then sample.id else nil) ~= nil
end

local function pedestal(player: Player, slot: number)
	local plot = S.PlotService.Get(player)
	return plot and S.PlotService.Stand(plot, slot)
end

local function petAt(player: Player, slot: number): (string?, any)
	local data = S.DataService.Get(player)
	if not data then
		return nil, nil
	end
	for uid, pet in data.Pets do
		if pet.Slot == slot then
			return uid, pet
		end
	end
	return nil, nil
end

local function updatePedestal(player: Player, slot: number)
	local ped = pedestal(player, slot)
	if not ped then
		return
	end
	local uid, pet = petAt(player, slot)
	ped.prompt.Enabled = uid ~= nil
	ped.stealPrompt.Enabled = uid ~= nil and not ped.base:GetAttribute("BeingStolen")
	ped.base:SetAttribute("PetUid", uid)
	ped.base:SetAttribute("PetId", if pet then pet.Id else nil)
	ped.pad:SetAttribute("Bank", if pet then math.floor(pet.Bank or 0) else 0)
	if pet then
		ped.prompt.ActionText = "SELL"
		ped.prompt.ObjectText = tostring(PetService.SellValue(pet))
		ped.base:SetAttribute("Income", PetService.IncomeOf(player, pet))
	else
		ped.base:SetAttribute("Income", 0)
	end
end

-- Crea il modello del pet sul suo piedistallo
local function showPet(player: Player, uid: string)
	local data = S.DataService.Get(player)
	local pet = data and data.Pets[uid]
	models[player] = models[player] or {}
	if models[player][uid] then
		models[player][uid]:Destroy()
		models[player][uid] = nil
	end
	if not pet then
		return
	end
	local ped = pedestal(player, pet.Slot)
	if not ped then
		return
	end
	local model = Visuals.MakePet(pet.Id, pet.Mutation, pet.Size)
	model.Name = "Pet_" .. uid
	local point = ped.base:FindFirstChild("PetPoint") :: Attachment?
	model:PivotTo(if point then point.WorldCFrame else ped.base.CFrame)
	model:SetAttribute("Uid", uid)
	model:SetAttribute("OwnerUserId", player.UserId)
	model:SetAttribute("Slot", pet.Slot)
	model:SetAttribute("Flying", Pets.Get(pet.Id).flying == true)
	model.Parent = ped.base
	CollectionService:AddTag(model, "PetDisplay")
	models[player][uid] = model
	updatePedestal(player, pet.Slot)
end

function PetService.Model(player: Player, uid: string): Model?
	return models[player] and models[player][uid]
end

-- Aggiunge un pet nuovo (schiusa) o rubato. Ritorna l'uid o nil se non c'e' posto.
function PetService.AddPet(player: Player, pet: { Id: string, Mutation: string?, Size: string? }): string?
	local data = S.DataService.Get(player)
	local slot = PetService.FreeSlot(player, pet.Id)
	if not data or not slot then
		return nil
	end
	local uid = S.DataService.NewUid(player)
	S.StateService.Set(player, { "Pets", uid }, {
		Id = pet.Id,
		Mutation = pet.Mutation or "None",
		Size = pet.Size or "Normal",
		Slot = slot,
		Bank = 0,
		Got = os.time(),
	})
	showPet(player, uid)
	PetService.PublishIncome(player)
	return uid
end

-- Toglie un pet (vendita o furto) e ne restituisce i dati
function PetService.RemovePet(player: Player, uid: string)
	local data = S.DataService.Get(player)
	local pet = data and data.Pets[uid]
	if not pet then
		return nil
	end
	-- le monete accumulate sulla pedana restano al proprietario
	if (pet.Bank or 0) >= 1 then
		S.DataService.AddCoins(player, math.floor(pet.Bank), "PetBank")
	end
	S.StateService.Set(player, { "Pets", uid }, nil)
	if models[player] and models[player][uid] then
		models[player][uid]:Destroy()
		models[player][uid] = nil
	end
	updatePedestal(player, pet.Slot)
	PetService.PublishIncome(player)
	return pet
end

function PetService.PublishIncome(player: Player)
	local income = PetService.TotalIncome(player)
	player:SetAttribute("Income", income)
	local data = S.DataService.Get(player)
	if data and income > (data.Stats.BestIncome or 0) then
		data.Stats.BestIncome = income
	end
end

local function sell(player: Player, slot: number)
	local uid, pet = petAt(player, slot)
	if not uid or not pet then
		return
	end
	local ped = pedestal(player, slot)
	if ped and ped.base:GetAttribute("BeingStolen") then
		return
	end
	local value = PetService.SellValue(pet)
	PetService.RemovePet(player, uid)
	S.DataService.AddCoins(player, value, "Sell")
	S.StateService.Notify(player, "PetSold", { pet = "Pet_" .. pet.Id, price = value }, "Gold")
	S.StateService.Effect(player, "Coins", { amount = value })
end

local function collect(player: Player, slot: number)
	local uid, pet = petAt(player, slot)
	if not uid or not pet or (pet.Bank or 0) < 1 then
		return
	end
	local amount = math.floor(pet.Bank)
	pet.Bank -= amount
	S.DataService.AddCoins(player, amount, "Collect")
	S.StateService.Set(player, { "Pets", uid, "Bank" }, pet.Bank)
	updatePedestal(player, slot)
	local ped = pedestal(player, slot)
	S.StateService.Effect(player, "Collect", { amount = amount, position = if ped then ped.pad.Position else nil })
	S.TutorialService.Advance(player, "Collected")
end

-- Quando i piedistalli sbloccati cambiano, i pet fuori posto vengono riassegnati
function PetService.Reflow(player: Player)
	local data = S.DataService.Get(player)
	if not data then
		return
	end
	local count = S.PlotService.PedestalCount(player)
	for uid, pet in data.Pets do
		if pet.Slot > count then
			local free = PetService.FreeSlot(player, pet.Id)
			if free then
				pet.Slot = free
				S.StateService.Set(player, { "Pets", uid }, pet)
				showPet(player, uid)
			end
		end
	end
	for i = 1, count do
		updatePedestal(player, i)
	end
end

function PetService.Start()
	S.PlotService.Assigned:Connect(function(player, plot)
		local data = S.DataService.Get(player)
		if not data then
			return
		end
		-- slot doppi, oltre il limite o sbagliati per il tipo di pet (dati vecchi): ricolloca
		local seen = {}
		for _, pet in data.Pets do
			local giant = Pets.Get(pet.Id).giant == true
			if seen[pet.Slot] or pet.Slot > S.PlotService.PedestalCount(player) or (pet.Slot == 0) ~= giant then
				pet.Slot = 999
			else
				seen[pet.Slot] = true
			end
		end
		for uid, pet in data.Pets do
			if pet.Slot == 999 then
				local free = PetService.FreeSlot(player, pet.Id)
				pet.Slot = free or 999
			end
			if pet.Slot ~= 999 then
				showPet(player, uid)
			end
		end
		for _, ped in S.PlotService.Stands(plot) do
			updatePedestal(player, ped.slot)
		end
		S.StateService.Push(player, { "Pets" })
		PetService.PublishIncome(player)
	end)
	-- pulsanti collegati una sola volta: il proprietario si legge al momento dell'uso
	for _, plot in S.PlotService.Plots do
		for _, ped in S.PlotService.Stands(plot) do
			local i = ped.slot
			ped.prompt.Triggered:Connect(function(who)
				if plot.owner == who then
					sell(who, i)
				end
			end)
			local lastTouch = 0
			-- le parti costruite da Build hanno CanTouch spento: la pedana deve sentire i passi
			ped.pad.CanTouch = true
			ped.pad.Touched:Connect(function(hit)
				local owner = plot.owner
				if owner and hit.Parent == owner.Character and os.clock() - lastTouch > 0.3 then
					lastTouch = os.clock()
					collect(owner, i)
				end
			end)
		end
	end
	S.PlotService.Released:Connect(function(player)
		if models[player] then
			for _, m in models[player] do
				m:Destroy()
			end
		end
		models[player] = nil
	end)
	-- guadagno: ogni secondo le monete maturano sulle pedane
	task.spawn(function()
		while true do
			task.wait(GameConfig.IncomeTick)
			for _, player in Players:GetPlayers() do
				local data = S.DataService.Get(player)
				local plot = data and S.PlotService.Get(player)
				if data and plot then
					local mult = PetService.Multiplier(player)
					for _, pet in data.Pets do
						local ped = S.PlotService.Stand(plot, pet.Slot)
						if ped then
							pet.Bank = (pet.Bank or 0) + PetService.BaseIncome(pet) * mult * GameConfig.IncomeTick
							ped.pad:SetAttribute("Bank", math.floor(pet.Bank))
						end
					end
				end
			end
		end
	end)
end

return PetService
