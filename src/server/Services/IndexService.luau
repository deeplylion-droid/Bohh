-- Album dei pet: registra le scoperte (per variante), premi e bonus permanenti per le righe complete.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Net = require(ReplicatedStorage.Shared.Net)
local Pets = require(ReplicatedStorage.Shared.Config.Pets)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Rewards = require(ReplicatedStorage.Shared.Config.Rewards)

local IndexService = {}

local S

function IndexService.Init(services)
	S = services
end

-- Registra un pet; ritorna true se e' la prima volta che il giocatore lo trova
function IndexService.Record(player: Player, petId: string, mutation: string?): boolean
	local data = S.DataService.Get(player)
	if not data then
		return false
	end
	local entry = data.Index[petId]
	local isNew = entry == nil
	if isNew then
		entry = {}
	end
	local variant = mutation or "None"
	if not entry[variant] then
		entry[variant] = true
		S.StateService.Set(player, { "Index", petId }, entry)
	end
	return isNew
end

function IndexService.RowComplete(player: Player, rarity: string): boolean
	local data = S.DataService.Get(player)
	if not data then
		return false
	end
	for _, p in Pets.ByRarity[rarity] do
		if not data.Index[p.id] then
			return false
		end
	end
	return true
end

-- Bonus permanente sul guadagno: +5% per ogni riga riscattata
function IndexService.Bonus(player: Player): number
	local data = S.DataService.Get(player)
	if not data then
		return 0
	end
	local n = 0
	for _ in data.IndexClaimed do
		n += 1
	end
	return n * GameConfig.IndexRowBonus
end

local function claimRow(player: Player, rarity: any)
	if type(rarity) ~= "string" or not Rarities.List[rarity] then
		return
	end
	local data = S.DataService.Get(player)
	if not data or data.IndexClaimed[rarity] or not IndexService.RowComplete(player, rarity) then
		return
	end
	S.StateService.Set(player, { "IndexClaimed", rarity }, true)
	local coins = Rewards.IndexRow[rarity]
	S.DataService.AddCoins(player, coins, "Index")
	S.PetService.PublishIncome(player)
	S.StateService.Notify(player, "IndexRowDone", { bonus = math.floor(GameConfig.IndexRowBonus * 100) .. "%" }, "Gold")
	S.StateService.Effect(player, "Coins", { amount = coins, big = true })
end

function IndexService.Start()
	Net.Event("ClaimIndexRow").OnServerEvent:Connect(claimRow)
end

return IndexService
