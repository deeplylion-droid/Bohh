-- Ruota della fortuna: un giro gratis ogni qualche ora, giri extra dalle missioni e con i Robux.
-- Il server estrae lo spicchio; qui la ruota gira fino a fermarsi li' e poi arriva il premio.

local MarketplaceService = game:GetService("MarketplaceService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Assets = require(ReplicatedStorage.Shared.Assets)
local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)
local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)
local Products = require(ReplicatedStorage.Shared.Config.Products)
local Kit = require(script.Parent.Parent.Kit)
local RewardInfo = require(script.Parent.Parent.RewardInfo)
local WheelFace = require(script.Parent.Parent.WheelFace)

local Theme = Kit.Theme
local New = Kit.New
local player = Players.LocalPlayer

local Panel = {}

-- giri disponibili adesso: quello gratis (se pronto) + quelli extra
function Panel.Available(data): (boolean, number)
	local wheel = data and data.Wheel
	if not wheel then
		return false, 0
	end
	local free = workspace:GetServerTimeNow() >= (wheel.NextFree or 0)
	return free, (wheel.Spins or 0)
end

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("WheelTitle"), UDim2.fromOffset(860, 540), "Orange", parent)

	-- ruota (a sinistra) con la freccia fissa in alto
	local holder = New("Frame", {
		Name = "Wheel",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(452, 452),
		Position = UDim2.fromOffset(8, 22),
		ZIndex = 22,
		Parent = p.Body,
	})
	local disc = New("ImageLabel", {
		Name = "Disc",
		BackgroundTransparency = 1,
		Image = Assets.Images.WheelFace or "",
		Size = UDim2.fromScale(1, 1),
		ZIndex = 22,
		Parent = holder,
	})
	if disc.Image == "" then
		-- immagine non ancora caricata: un disco semplice
		disc.BackgroundTransparency = 0
		disc.BackgroundColor3 = Theme.CardLight
		Kit.Corner(UDim.new(1, 0)).Parent = disc
		Kit.Stroke(6).Parent = disc
	end
	local refreshFace = WheelFace.Build(disc, C, 22)
	local pointer = New("Frame", {
		Name = "Pointer",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(44, 44),
		Position = UDim2.new(0.5, 0, 0, 6),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Rotation = 45,
		ZIndex = 30,
		Parent = holder,
	}, { Kit.Corner(UDim.new(0, 8)), Kit.Stroke(4), Kit.Gradient(Theme.Buttons.Red[1], Theme.Buttons.Red[2], 45) })
	New("Frame", {
		BackgroundColor3 = Theme.Gold,
		Size = UDim2.fromOffset(26, 26),
		Position = UDim2.new(0.5, 0, 0, -18),
		AnchorPoint = Vector2.new(0.5, 0.5),
		ZIndex = 31,
		Parent = holder,
	}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(4) })
	local _ = pointer

	-- informazioni e pulsanti (a destra)
	local right = New("Frame", {
		BackgroundTransparency = 1,
		Size = UDim2.new(1, -488, 1, -10),
		Position = UDim2.fromOffset(484, 10),
		ZIndex = 22,
		Parent = p.Body,
	})
	local freeTitle = Kit.Text({ Size = UDim2.new(1, 0, 0, 36), Position = UDim2.fromOffset(0, 4), Parent = right })
	local freeClock = Kit.Text({
		Size = UDim2.new(1, 0, 0, 44),
		Position = UDim2.fromOffset(0, 42),
		TextColor3 = Theme.Green,
		Parent = right,
	})
	local spinsText = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, 0, 0, 30),
		Position = UDim2.fromOffset(0, 92),
		Stroke = 2,
		Parent = right,
	})
	local spinning = false
	local spinBtn
	local angle = 0
	local function spin()
		if spinning then
			return
		end
		local free, extra = Panel.Available(C.State.Data)
		if not free and extra <= 0 then
			C.Audio.Play("Error")
			Kit.Bounce(spinBtn.Frame, 0.1)
			return
		end
		spinning = true
		spinBtn.SetColor("Grey")
		local called, ok, res = pcall(function()
			return Net.Function("SpinWheel"):InvokeServer()
		end)
		if not called or not ok or type(res) ~= "number" then
			spinning = false
			if type(res) == "string" then
				C.Notify.Toast(T(res), "Bad")
			end
			return
		end
		local from = angle
		local target = WheelFace.Target(from, res, 5, math.random() - 0.5)
		local duration = Plaza.Wheel.SpinTime - 0.25
		local t0 = os.clock()
		local lastTick = math.floor(from / WheelFace.Step)
		local conn
		conn = RunService.RenderStepped:Connect(function()
			local u = (os.clock() - t0) / duration
			angle = from + (target - from) * WheelFace.Ease(u)
			disc.Rotation = angle
			local tick = math.floor((angle + WheelFace.Step / 2) / WheelFace.Step)
			if tick ~= lastTick then
				lastTick = tick
				C.Audio.Play("Click", nil, 0.35)
				Kit.Bounce(pointer, 0.15)
			end
			if u >= 1 then
				conn:Disconnect()
				angle = target % 360
				disc.Rotation = angle
				spinning = false
				local seg = Plaza.Wheel.Segments[res]
				C.Audio.Play(if seg.kind == "Primal" then "Fanfare" else "Success")
				Kit.Bounce(holder, 0.08)
			end
		end)
	end
	spinBtn = Kit.Button({
		Text = "",
		Color = "Green",
		Size = UDim2.new(1, -20, 0, 82),
		Position = UDim2.fromOffset(10, 132),
		TextSize = 40,
		Parent = right,
		OnClick = spin,
	})
	local buyTitle = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, 0, 0, 26),
		Position = UDim2.fromOffset(0, 236),
		TextColor3 = Theme.Muted,
		Stroke = 2,
		Parent = right,
	})
	local buys = {}
	for i, key in { "WheelSpin1", "WheelSpins5" } do
		local prod = Products.Products[key]
		local b = Kit.Button({
			Text = "",
			Color = "Yellow",
			Size = UDim2.new(0.5, -16, 0, 64),
			Position = UDim2.new((i - 1) * 0.5, 8, 0, 268),
			TextSize = 26,
			Parent = right,
			OnClick = function()
				if prod and prod.id ~= 0 then
					MarketplaceService:PromptProductPurchase(player, prod.id)
				end
			end,
		})
		b.Frame.Visible = prod ~= nil and prod.id ~= 0
		buys[i] = { btn = b, key = key, prod = prod }
	end
	local hint = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -10, 0, 52),
		Position = UDim2.fromOffset(5, 352),
		TextWrapped = true,
		Stroke = 2,
		MaxTextSize = 22,
		Parent = right,
	})
	local jackpot = Kit.Text({
		Size = UDim2.new(1, -10, 0, 34),
		Position = UDim2.fromOffset(5, 412),
		TextColor3 = Color3.fromRGB(255, 120, 110),
		MaxTextSize = 28,
		Parent = right,
	})

	local function refresh()
		local data = C.State.Data
		if not data then
			return
		end
		p.Title.Text = T("WheelTitle")
		refreshFace()
		local free, extra = Panel.Available(data)
		freeTitle.Text = T("WheelFree")
		if free then
			freeClock.Text = T("WheelReady")
			freeClock.TextColor3 = Theme.Green
		else
			freeClock.Text = Format.Clock((data.Wheel.NextFree or 0) - workspace:GetServerTimeNow())
			freeClock.TextColor3 = Theme.Text
		end
		spinsText.Text = T("WheelExtra", { n = extra })
		if spinning then
			spinBtn.SetColor("Grey")
		else
			spinBtn.SetText(if free then T("WheelSpinFree") elseif extra > 0 then T("WheelSpin") else T("WheelNoSpin"))
			spinBtn.SetColor(if free or extra > 0 then "Green" else "Grey")
		end
		buyTitle.Text = T("WheelBuy")
		for _, b in buys do
			if b.prod then
				b.btn.SetText(`{RewardInfo.Spins(T, Products.WheelSpins[b.key])} · R$ {b.prod.price}`)
			end
		end
		hint.Text = T("WheelHint")
		jackpot.Text = T("WheelJackpot")
	end

	-- badge sul pulsante del menu (giri disponibili) e orologio del giro gratis a pannello aperto
	task.spawn(function()
		C.State.WaitReady()
		while true do
			local hud = C.UI.Hud
			if hud and hud.Badges and hud.Badges.Wheel then
				local free, extra = Panel.Available(C.State.Data)
				local n = (if free then 1 else 0) + extra
				hud.Badges.Wheel.Parent.Visible = n > 0
				hud.Badges.Wheel.Text = tostring(n)
			end
			if p.Frame.Visible then
				refresh()
			end
			task.wait(0.5)
		end
	end)
	C.Lang.Changed:Connect(refresh)
	return { Frame = p.Frame, Close = p.Close, OnOpen = refresh }
end

return Panel
