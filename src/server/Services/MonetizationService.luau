-- Game pass e prodotti sviluppatore (Robux). Le ricevute sono idempotenti: un acquisto viene
-- accreditato una sola volta e confermato a Roblox solo dopo il salvataggio dei dati.

local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Products = require(ReplicatedStorage.Shared.Config.Products)

local MonetizationService = {}

local S
local owned: { [Player]: { [string]: boolean } } = {}

function MonetizationService.Init(services)
	S = services
end

function MonetizationService.HasPass(player: Player, key: string): boolean
	local list = owned[player]
	return list ~= nil and list[key] == true
end

-- Fortuna: x2 durante il boost acquistato o vinto
function MonetizationService.LuckMultiplier(player: Player): number
	local data = S.DataService.Get(player)
	local mult = 1
	if data and (data.LuckUntil or 0) > os.time() then
		mult *= 2
	end
	return mult
end

function MonetizationService.AddLuck(player: Player, minutes: number)
	local data = S.DataService.Get(player)
	if not data then
		return
	end
	local base = math.max(data.LuckUntil or 0, os.time())
	S.StateService.Set(player, { "LuckUntil" }, base + minutes * 60)
	player:SetAttribute("LuckUntil", base + minutes * 60)
end

local function refreshPasses(player: Player)
	owned[player] = owned[player] or {}
	for key, pass in Products.Passes do
		if pass.id ~= 0 then
			local ok, has = pcall(MarketplaceService.UserOwnsGamePassAsync, MarketplaceService, player.UserId, pass.id)
			if ok and has then
				owned[player][key] = true
				player:SetAttribute("Pass_" .. key, true)
			end
		end
	end
end

local function onPassGranted(player: Player, key: string)
	owned[player] = owned[player] or {}
	owned[player][key] = true
	player:SetAttribute("Pass_" .. key, true)
	if key == "ExtraIncubator" then
		S.PlotService.RefreshLocks(player)
		S.HatchService.FillPending(player)
	elseif key == "BigBackpack" then
		S.CharacterService.UpdateSpeed(player)
	elseif key == "VIP" then
		S.CombatService.GiveBat(player)
		S.ChatService.Refresh(player)
	end
	S.PetService.PublishIncome(player)
	S.StateService.Notify(player, "PurchaseThanks", nil, "Gold")
	S.StateService.Effect(player, "Purchase", { big = true })
end

-- Accredito dei prodotti: ritorna true se l'acquisto e' stato applicato
local function grant(player: Player, key: string): boolean
	if key == "Luck15" then
		MonetizationService.AddLuck(player, Products.LuckMinutes)
		return true
	elseif Products.SkipHatchTier[key] then
		-- se non c'e' nessun uovo l'acquisto resta comunque valido come fortuna breve
		if not S.HatchService.Skip(player, Products.SkipHatchTier[key]) then
			MonetizationService.AddLuck(player, 5)
		end
		return true
	elseif Products.CoinPacks[key] then
		local pack = Products.CoinPacks[key]
		local amount = math.max(pack.min, math.floor(S.PetService.TotalIncome(player) * 60 * pack.minutes))
		S.DataService.AddCoins(player, amount, "Purchase")
		S.StateService.Effect(player, "Coins", { amount = amount, big = true })
		return true
	end
	return false
end

local function processReceipt(receipt)
	local player = Players:GetPlayerByUserId(receipt.PlayerId)
	if not player then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	local data = S.DataService.Wait(player, 20)
	local profile = S.DataService.Profile(player)
	if not data or not profile then
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	local product = Products.ProductById(receipt.ProductId)
	if not product then
		warn(`[Monetization] prodotto sconosciuto {receipt.ProductId}`)
		return Enum.ProductPurchaseDecision.NotProcessedYet
	end
	local pid = tostring(receipt.PurchaseId)
	if not data.Purchases[pid] then
		if not grant(player, product.key) then
			return Enum.ProductPurchaseDecision.NotProcessedYet
		end
		data.Purchases[pid] = os.time()
		table.insert(data.PurchaseOrder, pid)
		-- conserva solo le ultime 60 ricevute
		while #data.PurchaseOrder > 60 do
			local old = table.remove(data.PurchaseOrder, 1)
			data.Purchases[old] = nil
		end
		S.StateService.Notify(player, "PurchaseThanks", nil, "Gold")
		S.AnalyticsService.Custom(player, "Product", product.price, { key = product.key })
	end
	-- conferma solo dopo che la ricevuta e' stata salvata
	if profile.LastSavedData and profile.LastSavedData.Purchases and profile.LastSavedData.Purchases[pid] then
		return Enum.ProductPurchaseDecision.PurchaseGranted
	end
	profile:Save()
	local deadline = os.clock() + 15
	while os.clock() < deadline do
		task.wait(0.5)
		if not profile:IsActive() then
			return Enum.ProductPurchaseDecision.NotProcessedYet
		end
		if profile.LastSavedData and profile.LastSavedData.Purchases and profile.LastSavedData.Purchases[pid] then
			return Enum.ProductPurchaseDecision.PurchaseGranted
		end
	end
	return Enum.ProductPurchaseDecision.NotProcessedYet
end

function MonetizationService.Start()
	MarketplaceService.ProcessReceipt = processReceipt
	MarketplaceService.PromptGamePassPurchaseFinished:Connect(function(player, passId, purchased)
		if not purchased then
			return
		end
		local pass = Products.PassById(passId)
		if pass then
			onPassGranted(player, pass.key)
		end
	end)
	S.DataService.Loaded:Connect(function(player, data)
		refreshPasses(player)
		player:SetAttribute("LuckUntil", data.LuckUntil or 0)
		S.PetService.PublishIncome(player)
	end)
	Players.PlayerRemoving:Connect(function(player)
		owned[player] = nil
	end)
end

return MonetizationService
