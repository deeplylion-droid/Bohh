-- Etichette in chat (VIP): il server segna gli attributi, il client aggiunge il prefisso ai messaggi.

local ChatService = {}

local S

function ChatService.Init(services)
	S = services
end

function ChatService.Refresh(player: Player)
	player:SetAttribute("VIP", S.MonetizationService.HasPass(player, "VIP"))
	player:SetAttribute("IsAdmin", S.AdminService.IsAdmin(player))
end

function ChatService.Start()
	S.DataService.Loaded:Connect(function(player)
		task.wait(1)
		ChatService.Refresh(player)
	end)
end

return ChatService
