-- Replica i dati salvati del giocatore verso il suo client (istantanea + aggiornamenti puntuali).

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)

local StateService = {}

local S
local initEvent: RemoteEvent
local setEvent: RemoteEvent
local ready: { [Player]: boolean } = {}

-- Campi interni che il client non deve ricevere
local HIDDEN = { Purchases = true, PurchaseOrder = true, Codes = true }

local function snapshot(data)
	local out = {}
	for k, v in data do
		if not HIDDEN[k] then
			out[k] = v
		end
	end
	return out
end

function StateService.Init(services)
	S = services
end

function StateService.Start()
	initEvent = Net.Event("StateInit")
	setEvent = Net.Event("StateSet")
	S.DataService.Loaded:Connect(function(player, data)
		ready[player] = true
		initEvent:FireClient(player, snapshot(data))
	end)
	game:GetService("Players").PlayerRemoving:Connect(function(player)
		ready[player] = nil
	end)
	-- impostazioni scelte dal giocatore (convalidate)
	Net.Event("SetSetting").OnServerEvent:Connect(function(player, key, value)
		local ok = (key == "Music" or key == "Sfx" or key == "LowGfx") and type(value) == "boolean"
			or key == "Lang" and (value == "en" or value == "it" or value == "")
		if ok then
			StateService.Set(player, { "Settings", key }, value)
		end
	end)
end

-- Scrive il valore nei dati (path relativo a Profile.Data) e lo invia al client.
function StateService.Set(player: Player, path: { string }, value: any)
	local data = S.DataService.Get(player)
	if not data then
		return
	end
	local node = data
	for i = 1, #path - 1 do
		local k = path[i]
		if node[k] == nil then
			node[k] = {}
		end
		node = node[k]
	end
	node[path[#path]] = value
	if ready[player] and not HIDDEN[path[1]] then
		setEvent:FireClient(player, path, value)
	end
end

-- Invia di nuovo il valore attuale di un ramo (dopo modifiche dirette ai dati).
function StateService.Push(player: Player, path: { string })
	local data = S.DataService.Get(player)
	if not data or not ready[player] then
		return
	end
	local node = data
	for _, k in path do
		if type(node) ~= "table" then
			node = nil
			break
		end
		node = node[k]
	end
	setEvent:FireClient(player, path, node)
end

-- Stato volatile (non salvato) comunicato come attributo del giocatore, visibile a tutti i client.
function StateService.SetAttr(player: Player, name: string, value: any)
	player:SetAttribute(name, value)
end

-- Messaggi a comparsa (chiave di Strings + argomenti; il client traduce). style: Good/Bad/Info/Gold
function StateService.Notify(player: Player, key: string, args: { [string]: any }?, style: string?)
	Net.Event("Notify"):FireClient(player, key, args, style or "Info")
end

function StateService.NotifyAll(key: string, args: { [string]: any }?, style: string?)
	Net.Event("Notify"):FireAllClients(key, args, style or "Info")
end

-- Annuncio grande a tutto il server (uova rare, schiuse speciali, eventi)
function StateService.Announce(key: string, args: { [string]: any }?, rarity: string?)
	Net.Event("Announce"):FireAllClients(key, args, rarity)
end

-- Effetto visivo/sonoro: a un giocatore o a tutti (player = nil)
function StateService.Effect(player: Player?, name: string, params: { [string]: any }?)
	if player then
		Net.Event("Effect"):FireClient(player, name, params)
	else
		Net.Event("Effect"):FireAllClients(name, params)
	end
end

return StateService
