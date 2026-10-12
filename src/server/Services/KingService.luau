-- Re della collina: chi resta da solo in cima al monumento della piazza diventa il re e guadagna
-- monete extra ogni secondo (una quota del proprio guadagno, con un minimo). Se in cima ci sono due
-- o piu' giocatori la cima e' contesa e nessuno guadagna: bisogna buttare giu' gli altri a schiaffi.
-- Stato per i client: workspace KingUserId / HillContested, giocatore OnHill / King / KingRate / KingIdle.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)

local KingService = {}

local S
local cfg = Plaza.King
local TICK = 0.5

local king: Player? = nil
local kingSince = 0
local owed: { [Player]: number } = {}
local still: { [Player]: { pos: Vector3, t: number } } = {}
local lastAnnounce = -math.huge
local announced = 0

function KingService.Init(services)
	S = services
end

-- Quota della cima del monumento
function KingService.TopY(): number
	return MapLayout.SummitCenter.Y + 0.8 + cfg.Height
end

function KingService.Rate(player: Player): number
	return math.max(cfg.MinPerSecond, math.floor(S.PetService.TotalIncome(player) * cfg.IncomeShare))
end

function KingService.OnHill(player: Player): boolean
	local char = player.Character
	local hrp = S.CharacterService.Root(player)
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if not hrp or not hum or hum.Health <= 0 or S.RagdollService.IsRagdolled(player) then
		return false
	end
	local d = hrp.Position - MapLayout.SummitCenter
	local top = KingService.TopY()
	return Vector2.new(d.X, d.Z).Magnitude <= cfg.Radius and hrp.Position.Y > top + 1 and hrp.Position.Y < top + 30
end

function KingService.Current(): Player?
	return king
end

-- Accredita le monete maturate (ogni pochi secondi: una transazione al secondo sarebbe troppo)
local function pay(p: Player)
	local whole = math.floor(owed[p] or 0)
	if whole >= 1 then
		owed[p] -= whole
		S.DataService.AddCoins(p, whole, "King")
	end
end

local function setKing(p: Player?)
	if king and king ~= p then
		king:SetAttribute("King", nil)
		king:SetAttribute("KingIdle", nil)
		pay(king)
	end
	king = p
	kingSince = os.clock()
	workspace:SetAttribute("KingUserId", if p then p.UserId else 0)
	if p then
		p:SetAttribute("King", true)
		p:SetAttribute("KingRate", KingService.Rate(p))
		still[p] = nil
	end
end

local secondAt, paidAt = 0, 0
local function tick()
	local onTop = {}
	for _, p in Players:GetPlayers() do
		local on = KingService.OnHill(p)
		if (p:GetAttribute("OnHill") == true) ~= on then
			p:SetAttribute("OnHill", if on then true else nil)
		end
		if on then
			table.insert(onTop, p)
		end
	end
	local contested = #onTop > 1
	if (workspace:GetAttribute("HillContested") == true) ~= contested then
		workspace:SetAttribute("HillContested", contested)
	end
	local newKing = if #onTop == 1 then onTop[1] else nil
	if newKing ~= king then
		setKing(newKing)
	end
	local k = king
	if not k then
		return
	end
	-- un re fermo troppo a lungo non guadagna piu' (niente monete da fermi)
	local hrp = S.CharacterService.Root(k)
	local mark = still[k]
	if hrp and (not mark or (hrp.Position - mark.pos).Magnitude > 3) then
		still[k] = { pos = hrp.Position, t = os.clock() }
		mark = still[k]
	end
	local idle = mark ~= nil and os.clock() - mark.t > cfg.IdleAfter
	if (k:GetAttribute("KingIdle") == true) ~= idle then
		k:SetAttribute("KingIdle", if idle then true else nil)
	end
	if not idle then
		owed[k] = (owed[k] or 0) + KingService.Rate(k) * TICK
	end
	-- una volta al secondo: missioni e annuncio del nuovo re; ogni 3 secondi l'accredito
	if os.clock() - secondAt >= 1 then
		secondAt = os.clock()
		local rate = KingService.Rate(k)
		if k:GetAttribute("KingRate") ~= rate then
			k:SetAttribute("KingRate", rate)
		end
		if os.clock() - paidAt >= 3 then
			paidAt = os.clock()
			pay(k)
		end
		if not idle then
			S.QuestService.Add(k, "King", 1)
		end
		if k.UserId ~= announced and os.clock() - kingSince >= 3 and os.clock() - lastAnnounce >= cfg.AnnounceGap then
			announced = k.UserId
			lastAnnounce = os.clock()
			S.StateService.NotifyAll("KingNew", { name = k.DisplayName }, "Gold")
		end
	end
end

function KingService.Start()
	workspace:SetAttribute("KingUserId", 0)
	Players.PlayerRemoving:Connect(function(player)
		if king == player then
			setKing(nil) -- accredita anche le ultime monete
		end
		owed[player] = nil
		still[player] = nil
	end)
	task.spawn(function()
		while true do
			task.wait(TICK)
			local ok, err = pcall(tick)
			if not ok then
				warn(`[KingService] {err}`)
			end
		end
	end)
end

return KingService
