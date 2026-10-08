--!strict
-- Definizione centralizzata dei RemoteEvent/RemoteFunction.
-- Il server li crea con Net.Setup(); i client li ottengono con Net.Event()/Net.Function().

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Net = {}

Net.Events = {
	-- server -> client
	"StateInit", -- (data) istantanea completa dei dati del giocatore
	"StateSet", -- (path: {string}, value) aggiornamento puntuale
	"Notify", -- (key, args, style) messaggio a comparsa
	"Announce", -- (key, args, rarity) annuncio grande a tutto il server
	"HatchReveal", -- (info) animazione di schiusa
	"Effect", -- (name, params) effetti visivi/sonori
	"StealAlert", -- (thiefUserId, itemInfo) qualcuno sta rubando
	"Knockback", -- (velocity, ragdollTime) al proprio personaggio
	"Buried", -- () travolto dalla valanga
	-- client -> server
	"BuyUpgrade", -- (upgradeId)
	"BuyBat", -- (batId)
	"EquipBat", -- (batId)
	"BuyTrap", -- (slot, trapId)
	"ToggleBarrier", -- ()
	"SetSetting", -- (key, value)
	"ClaimPlaytime", -- (index)
	"ClaimDaily", -- ()
	"ClaimIndexRow", -- (rarity)
	"ClaimGroup", -- ()
	"TutorialAck", -- (step)
	"AdminAction", -- (action, args)
	"Swing", -- () schiaffo (il server convalida tempi e bersagli)
	"ObstacleHit", -- (obstacleId) il client segnala di essere stato colpito (il server convalida)
}

Net.Functions = {
	"RedeemCode", -- (code) -> (ok, messageKey)
	"GetLeaderboards", -- () -> data
}

local FOLDER = "Remotes"

function Net.Setup()
	assert(RunService:IsServer(), "Net.Setup solo sul server")
	local folder = ReplicatedStorage:FindFirstChild(FOLDER)
	if not folder then
		folder = Instance.new("Folder")
		folder.Name = FOLDER
		folder.Parent = ReplicatedStorage
	end
	for _, name in Net.Events do
		if not folder:FindFirstChild(name) then
			local r = Instance.new("RemoteEvent")
			r.Name = name
			r.Parent = folder
		end
	end
	for _, name in Net.Functions do
		if not folder:FindFirstChild(name) then
			local r = Instance.new("RemoteFunction")
			r.Name = name
			r.Parent = folder
		end
	end
end

local function folder(): Instance
	if RunService:IsServer() then
		local f = ReplicatedStorage:FindFirstChild(FOLDER)
		assert(f, "Net.Setup() non ancora chiamato")
		return f
	end
	return ReplicatedStorage:WaitForChild(FOLDER)
end

function Net.Event(name: string): RemoteEvent
	assert(table.find(Net.Events, name), `RemoteEvent sconosciuto: {name}`)
	return folder():WaitForChild(name) :: RemoteEvent
end

function Net.Function(name: string): RemoteFunction
	assert(table.find(Net.Functions, name), `RemoteFunction sconosciuta: {name}`)
	return folder():WaitForChild(name) :: RemoteFunction
end

return Net
