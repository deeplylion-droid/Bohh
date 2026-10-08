-- Etichette in chat: [VIP] dorato per chi ha il pass, [ADMIN] rosso per gli amministratori.
-- Il server imposta gli attributi VIP e IsAdmin sul giocatore.

local Players = game:GetService("Players")
local TextChatService = game:GetService("TextChatService")

local ChatTags = {}

function ChatTags.Init(_C) end

function ChatTags.Start()
	if TextChatService.ChatVersion ~= Enum.ChatVersion.TextChatService then
		return
	end
	TextChatService.OnIncomingMessage = function(message: TextChatMessage)
		local props = Instance.new("TextChatMessageProperties")
		local source = message.TextSource
		local p = source and Players:GetPlayerByUserId(source.UserId)
		if p then
			local prefix = ""
			if p:GetAttribute("IsAdmin") then
				prefix ..= '<font color="#FF5A4E">[ADMIN]</font> '
			end
			if p:GetAttribute("VIP") then
				prefix ..= '<font color="#FFD54D">[VIP]</font> '
			end
			if prefix ~= "" then
				props.PrefixText = prefix .. message.PrefixText
			end
		end
		return props
	end
end

return ChatTags
