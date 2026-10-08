-- Regali: premio giornaliero (serie di 7 giorni), regali a tempo di gioco, premio del gruppo.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Format = require(ReplicatedStorage.Shared.Util.Format)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local Net = require(ReplicatedStorage.Shared.Net)
local Rewards = require(ReplicatedStorage.Shared.Config.Rewards)
local Kit = require(script.Parent.Parent.Kit)

local Theme = Kit.Theme
local player = Players.LocalPlayer

local Panel = {}

local DAY = 86400

local function rewardIcon(r): string
	return if r.kind == "Coins" then "CoinsSmall" elseif r.kind == "Luck" then "Luck" else "Egg"
end

local function rewardText(T, r): string
	if r.kind == "Coins" then
		return Format.Money(r.amount)
	elseif r.kind == "Luck" then
		return `x2 {r.amount}m`
	end
	return T("Rarity_" .. r.rarity)
end

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("GiftsTitle"), UDim2.fromOffset(860, 580), "Pink", parent)

	-- giornaliero
	local dailyTitle = Kit.Text({ Size = UDim2.new(0.6, 0, 0, 34), Position = UDim2.fromOffset(6, 16), TextXAlignment = Enum.TextXAlignment.Left, Parent = p.Body })
	local dailyClaim = Kit.Button({ Text = "", Color = "Green", Size = UDim2.fromOffset(220, 50), Position = UDim2.new(1, -226, 0, 10), TextSize = 24, Parent = p.Body, OnClick = function()
		Net.Event("ClaimDaily"):FireServer()
	end })
	local days = {}
	for i, r in Rewards.Daily do
		local d = Kit.Card({ Size = UDim2.new(1 / 7, -10, 0, 128), Position = UDim2.new((i - 1) / 7, 5, 0, 66), Parent = p.Body })
		local dayLabel = Kit.Text({ Font = Theme.BodyFont, Size = UDim2.new(0.9, 0, 0, 22), Position = UDim2.new(0.05, 0, 0, 6), Stroke = 2, Parent = d })
		Kit.Icon(rewardIcon(r), { Size = UDim2.fromOffset(48, 48), Position = UDim2.new(0.5, 0, 0, 32), AnchorPoint = Vector2.new(0.5, 0), Parent = d })
		local amount = Kit.Text({ Size = UDim2.new(0.92, 0, 0, 26), Position = UDim2.new(0.04, 0, 1, -32), TextColor3 = Theme.Gold, Parent = d })
		days[i] = { card = d, day = dayLabel, amount = amount, reward = r }
	end

	-- regali a tempo
	local playTitle = Kit.Text({ Size = UDim2.new(0.6, 0, 0, 34), Position = UDim2.fromOffset(6, 212), TextXAlignment = Enum.TextXAlignment.Left, Parent = p.Body })
	local gifts = {}
	for i, g in Rewards.Playtime do
		local d = Kit.Card({ Size = UDim2.new(1 / 7, -10, 0, 170), Position = UDim2.new((i - 1) / 7, 5, 0, 254), Parent = p.Body })
		Kit.Icon(rewardIcon(g.reward), { Size = UDim2.fromOffset(52, 52), Position = UDim2.new(0.5, 0, 0, 10), AnchorPoint = Vector2.new(0.5, 0), Parent = d })
		local amount = Kit.Text({ Size = UDim2.new(0.92, 0, 0, 24), Position = UDim2.new(0.04, 0, 0, 68), TextColor3 = Theme.Gold, Parent = d })
		local btn = Kit.Button({ Text = "", Color = "Grey", Size = UDim2.new(0.86, 0, 0, 46), Position = UDim2.new(0.07, 0, 1, -58), TextSize = 20, Parent = d, OnClick = function()
			Net.Event("ClaimPlaytime"):FireServer(i)
		end })
		gifts[i] = { amount = amount, btn = btn, gift = g }
	end

	-- gruppo
	local groupBtn = Kit.Button({ Text = "", Color = "Blue", Size = UDim2.fromOffset(420, 52), Position = UDim2.new(0.5, 0, 1, -58), AnchorPoint = Vector2.new(0.5, 0), TextSize = 22, Parent = p.Body, OnClick = function()
		Net.Event("ClaimGroup"):FireServer()
	end })
	groupBtn.Frame.Visible = GameConfig.GroupId ~= 0

	local function refresh()
		local data = C.State.Data
		if not data then
			return
		end
		p.Title.Text = T("GiftsTitle")
		dailyTitle.Text = T("DailyTitle")
		playTitle.Text = T("PlaytimeTitle")
		local now = workspace:GetServerTimeNow()
		local last = data.Daily and data.Daily.Last or 0
		local streak = data.Daily and data.Daily.Streak or 0
		local ready = now - last >= DAY
		local nextIndex = if now - last < DAY * 2 then streak + 1 else 1
		if nextIndex > #Rewards.Daily then
			nextIndex = 1
		end
		for i, d in days do
			d.day.Text = T("DailyDay", { n = i })
			d.amount.Text = rewardText(T, d.reward)
			local stroke = d.card:FindFirstChildOfClass("UIStroke")
			if stroke then
				stroke.Color = if i == nextIndex and ready then Theme.Gold else Theme.Outline
				stroke.Thickness = if i == nextIndex and ready then 5 else 3
			end
			d.card.BackgroundColor3 = if i < nextIndex and not ready or (i <= streak and not ready) then Theme.CardLight else Theme.Card
		end
		if ready then
			dailyClaim.SetText(T("Claim"))
			dailyClaim.SetColor("Green")
		else
			dailyClaim.SetText(T("DailyNext", { t = Format.Clock(last + DAY - now) }))
			dailyClaim.SetColor("Grey")
		end
		local start = player:GetAttribute("SessionStart") or now
		for i, g in gifts do
			g.amount.Text = rewardText(T, g.gift.reward)
			local left = start + g.gift.minutes * 60 - now
			if player:GetAttribute("PlaytimeClaimed_" .. i) then
				g.btn.SetText("✔")
				g.btn.SetColor("Purple")
			elseif left <= 0 then
				g.btn.SetText(T("Claim"))
				g.btn.SetColor("Green")
			else
				g.btn.SetText(Format.Clock(left))
				g.btn.SetColor("Grey")
			end
		end
		groupBtn.SetText(if data.GroupClaimed then T("Claimed") else T("GroupTitle", { coins = Format.Money(GameConfig.GroupReward) }))
	end

	-- badge sul pulsante del menu quando c'e' qualcosa da riscattare
	task.spawn(function()
		C.State.WaitReady()
		while true do
			local data = C.State.Data
			local now = workspace:GetServerTimeNow()
			local count = 0
			if data and now - (data.Daily and data.Daily.Last or 0) >= DAY then
				count += 1
			end
			local start = player:GetAttribute("SessionStart") or now
			for i, g in Rewards.Playtime do
				if not player:GetAttribute("PlaytimeClaimed_" .. i) and start + g.minutes * 60 <= now then
					count += 1
				end
			end
			local hud = C.UI.Hud
			if hud and hud.Badges and hud.Badges.Gifts then
				hud.Badges.Gifts.Parent.Visible = count > 0
				hud.Badges.Gifts.Text = tostring(count)
			end
			if p.Frame.Visible then
				refresh()
			end
			task.wait(1)
		end
	end)
	C.Lang.Changed:Connect(refresh)
	return { Frame = p.Frame, Close = p.Close, OnOpen = refresh }
end

return Panel
