-- Missioni: tre giornaliere (nuove a mezzanotte UTC) e tre settimanali (nuove il lunedi'), con la
-- barra di avanzamento, il premio e il pulsante per riscattarlo; completarle tutte da' un premio extra.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Assets = require(ReplicatedStorage.Shared.Assets)
local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)
local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)
local Kit = require(script.Parent.Parent.Kit)
local RewardInfo = require(script.Parent.Parent.RewardInfo)

local Theme = Kit.Theme
local New = Kit.New

local Panel = {}

local DAY = 86400
local WEEK = 7 * DAY
local MONDAY = 4 * DAY

local byId = {}
for _, q in Plaza.Quests.Daily do
	byId[q.id] = q
end
for _, q in Plaza.Quests.Weekly do
	byId[q.id] = q
end
Panel.ById = byId

-- Missioni e premi extra pronti da riscattare (per il badge del menu e la bacheca)
function Panel.Claimable(data): number
	local q = data and data.Quests
	if not q then
		return 0
	end
	local count = 0
	for _, kind in { "Daily", "Weekly" } do
		local list = q[kind] or {}
		local all = #list > 0
		for _, e in list do
			local def = byId[e.Id]
			if def and not e.C and e.P >= def.target then
				count += 1
			end
			if not e.C then
				all = false
			end
		end
		if all and not q[kind .. "Bonus"] then
			count += 1
		end
	end
	return count
end

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("QuestsTitle"), UDim2.fromOffset(920, 560), "Blue", parent)
	local columns = {}
	for col, kind in { "Daily", "Weekly" } do
		local x = (col - 1) * 0.5
		local frame = New("Frame", {
			BackgroundTransparency = 1,
			Size = UDim2.new(0.5, -12, 1, 0),
			Position = UDim2.new(x, if col == 1 then 0 else 12, 0, 0),
			ZIndex = 22,
			Parent = p.Body,
		})
		local title = Kit.Text({
			Size = UDim2.new(0.62, 0, 0, 36),
			Position = UDim2.fromOffset(6, 14),
			TextXAlignment = Enum.TextXAlignment.Left,
			Parent = frame,
		})
		local clock = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(0.38, -6, 0, 26),
			Position = UDim2.new(0.62, 0, 0, 20),
			TextXAlignment = Enum.TextXAlignment.Right,
			TextColor3 = Theme.Muted,
			Stroke = 2,
			Parent = frame,
		})
		local cards = {}
		local ready = {} -- [i] = true se la missione e' pronta da riscattare
		for i = 1, 3 do
			local card = Kit.Card({
				Size = UDim2.new(1, 0, 0, 104),
				Position = UDim2.fromOffset(0, 58 + (i - 1) * 114),
				Parent = frame,
			})
			local icon = Kit.Icon("Egg", {
				Size = UDim2.fromOffset(62, 62),
				Position = UDim2.fromOffset(10, 21),
				ZIndex = 23,
				Parent = card,
			})
			local text = Kit.Text({
				Font = Theme.BodyFont,
				Size = UDim2.new(1, -206, 0, 46),
				Position = UDim2.fromOffset(82, 6),
				TextXAlignment = Enum.TextXAlignment.Left,
				TextWrapped = true,
				Stroke = 2,
				MaxTextSize = 22,
				ZIndex = 23,
				Parent = card,
			})
			local bar = New("Frame", {
				BackgroundColor3 = Theme.Outline,
				Size = UDim2.new(1, -212, 0, 26),
				Position = UDim2.fromOffset(84, 62),
				ZIndex = 23,
				Parent = card,
			}, { Kit.Corner(UDim.new(1, 0)) })
			local fill = New("Frame", {
				BackgroundColor3 = Color3.new(1, 1, 1),
				Size = UDim2.fromScale(0, 1),
				ZIndex = 24,
				Parent = bar,
			}, { Kit.Corner(UDim.new(1, 0)), Kit.Gradient(Theme.Buttons.Green[1], Theme.Buttons.Green[2]) })
			local barText = Kit.Text({
				Size = UDim2.fromScale(1, 0.84),
				Position = UDim2.fromScale(0, 0.08),
				ZIndex = 25,
				Stroke = 2,
				Parent = bar,
			})
			local rIcon = Kit.Icon("Coin", {
				Size = UDim2.fromOffset(34, 34),
				Position = UDim2.new(1, -118, 0, 8),
				ZIndex = 23,
				Parent = card,
			})
			local rText = Kit.Text({
				Size = UDim2.fromOffset(78, 28),
				Position = UDim2.new(1, -84, 0, 12),
				TextXAlignment = Enum.TextXAlignment.Left,
				TextColor3 = Theme.Gold,
				ZIndex = 23,
				Parent = card,
			})
			local btn = Kit.Button({
				Text = "",
				Color = "Grey",
				Size = UDim2.fromOffset(108, 46),
				Position = UDim2.new(1, -118, 0, 50),
				TextSize = 20,
				Parent = card,
				OnClick = function()
					if ready[i] then
						Net.Event("ClaimQuest"):FireServer(kind, i)
					else
						-- "VAI!": si chiude il pannello per andare a completarla
						C.UI.Close()
					end
				end,
			})
			Kit.RaiseZ(btn.Frame, 23)
			cards[i] = {
				card = card,
				icon = icon,
				text = text,
				fill = fill,
				barText = barText,
				rIcon = rIcon,
				rText = rText,
				btn = btn,
			}
		end
		-- premio per averle completate tutte
		local bonus = Kit.Card({
			Size = UDim2.new(1, 0, 0, 66),
			Position = UDim2.fromOffset(0, 58 + 3 * 114),
			Color = Color3.fromRGB(70, 46, 120),
			Parent = frame,
		})
		local bonusReward = if kind == "Daily" then Plaza.Quests.DailyBonus else Plaza.Quests.WeeklyBonus
		Kit.Icon(RewardInfo.Icon(bonusReward), {
			Size = UDim2.fromOffset(46, 46),
			Position = UDim2.fromOffset(10, 10),
			ZIndex = 23,
			Parent = bonus,
		})
		local bonusText = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(1, -196, 0, 44),
			Position = UDim2.fromOffset(64, 11),
			TextXAlignment = Enum.TextXAlignment.Left,
			TextWrapped = true,
			Stroke = 2,
			MaxTextSize = 21,
			ZIndex = 23,
			Parent = bonus,
		})
		local bonusBtn = Kit.Button({
			Text = "",
			Color = "Grey",
			Size = UDim2.fromOffset(118, 46),
			Position = UDim2.new(1, -128, 0, 10),
			TextSize = 20,
			Parent = bonus,
			OnClick = function()
				Net.Event("ClaimQuest"):FireServer(kind .. "Bonus")
			end,
		})
		Kit.RaiseZ(bonusBtn.Frame, 23)
		columns[kind] = {
			ready = ready,
			title = title,
			clock = clock,
			cards = cards,
			bonusText = bonusText,
			bonusBtn = bonusBtn,
			bonusReward = bonusReward,
		}
	end

	local function refresh()
		local data = C.State.Data
		local q = data and data.Quests
		if not q then
			return
		end
		p.Title.Text = T("QuestsTitle")
		local now = workspace:GetServerTimeNow()
		for kind, col in columns do
			col.title.Text = T(if kind == "Daily" then "QuestsDaily" else "QuestsWeekly")
			local nextReset = if kind == "Daily"
				then (now // DAY + 1) * DAY
				else ((now - MONDAY) // WEEK + 1) * WEEK + MONDAY
			local left = nextReset - now
			col.clock.Text = T("QuestsNew", {
				t = if left >= DAY
					then T("DaysHours", { d = left // DAY, h = (left % DAY) // 3600 })
					else Format.Clock(left),
			})
			local list = q[kind] or {}
			local all = #list > 0
			for i, c in col.cards do
				local e = list[i]
				local def = e and byId[e.Id]
				c.card.Visible = def ~= nil
				if def then
					if c.icon:IsA("ImageLabel") then
						c.icon.Image = Assets.Images["Icon" .. def.icon] or c.icon.Image
					elseif c.icon:IsA("TextLabel") then
						c.icon.Text = Theme.Emoji[def.icon] or "⭐"
					end
					c.text.Text = T("Quest_" .. def.stat, { n = def.target })
					local prog = math.min(e.P, def.target)
					c.fill.Size = UDim2.fromScale(prog / def.target, 1)
					c.fill.Visible = prog > 0
					c.barText.Text = `{prog}/{def.target}`
					local rIconName = RewardInfo.Icon(def.reward)
					if c.rIcon:IsA("ImageLabel") then
						c.rIcon.Image = Assets.Images["Icon" .. rIconName] or c.rIcon.Image
					end
					c.rText.Text = RewardInfo.Text(T, def.reward, data)
					c.rText.TextColor3 = RewardInfo.Color(def.reward, data)
					col.ready[i] = not e.C and prog >= def.target
					if e.C then
						c.btn.SetText("✔")
						c.btn.SetColor("Purple")
					elseif prog >= def.target then
						c.btn.SetText(T("Claim"))
						c.btn.SetColor("Green")
					else
						c.btn.SetText(T("QuestGo"))
						c.btn.SetColor("Grey")
					end
					if not e.C then
						all = false
					end
				end
			end
			col.bonusText.Text = T(if kind == "Daily" then "QuestsBonusDaily" else "QuestsBonusWeekly", {
				reward = RewardInfo.Text(T, col.bonusReward, data),
			})
			if q[kind .. "Bonus"] then
				col.bonusBtn.SetText("✔")
				col.bonusBtn.SetColor("Purple")
			elseif all then
				col.bonusBtn.SetText(T("Claim"))
				col.bonusBtn.SetColor("Green")
			else
				col.bonusBtn.SetText("🔒")
				col.bonusBtn.SetColor("Grey")
			end
		end
	end

	C.State.Watch("Quests", function()
		if p.Frame.Visible then
			refresh()
		end
	end)
	-- badge sul pulsante del menu + orologi mentre il pannello e' aperto
	task.spawn(function()
		C.State.WaitReady()
		while true do
			local hud = C.UI.Hud
			if hud and hud.Badges and hud.Badges.Quests then
				local n = Panel.Claimable(C.State.Data)
				hud.Badges.Quests.Parent.Visible = n > 0
				hud.Badges.Quests.Text = tostring(n)
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
