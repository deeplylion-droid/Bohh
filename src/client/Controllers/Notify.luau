-- Messaggi a comparsa, annunci a tutto il server e avviso di furto con freccia verso il ladro.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local UserInputService = game:GetService("UserInputService")

local Net = require(ReplicatedStorage.Shared.Net)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)

local Notify = {}

local C
local Kit
local stack: Frame
local announceFrame: Frame
local player = Players.LocalPlayer

-- colore della scritta sul cartellino quasi bianco, per tipo di messaggio
local STYLE = {
	Good = Color3.fromRGB(18, 150, 62),
	Bad = Color3.fromRGB(214, 26, 56),
	Info = Color3.fromRGB(58, 34, 22),
	Gold = Color3.fromRGB(206, 112, 0),
}

function Notify.Init(controllers)
	C = controllers
end

-- Messaggio su un cartellino quasi bianco (con il foro), in basso a destra (in alto a destra sui
-- telefoni), lontano dal centro dello schermo
function Notify.Toast(text: string, style: string?)
	local color = STYLE[style or "Info"] or STYLE.Info
	local New = Kit.New
	local Theme = Kit.Theme
	local toast = New("Frame", {
		BackgroundColor3 = Theme.Card,
		Size = UDim2.fromOffset(420, 56),
		Rotation = -1,
		Parent = stack,
	}, { Kit.Corner(UDim.new(0, 8)), Kit.Stroke(3), New("UIScale") })
	Kit.Stitch(toast, 8, Theme.StitchCard)
	New("Frame", {
		Name = "Hole",
		BackgroundColor3 = Theme.Outline,
		Size = UDim2.fromOffset(10, 10),
		Position = UDim2.new(0, 12, 0.5, 0),
		AnchorPoint = Vector2.new(0, 0.5),
		ZIndex = 2,
		Parent = toast,
	}, { Kit.Corner(UDim.new(1, 0)) })
	Kit.Text({
		Text = text,
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -46, 0.7, 0),
		Position = UDim2.new(0, 32, 0.15, 0),
		TextColor3 = color,
		Stroke = false,
		RichText = true,
		ZIndex = 2,
		Parent = toast,
	})
	Kit.Pop(toast)
	task.delay(3.6, function()
		local sc = toast:FindFirstChildOfClass("UIScale")
		if sc then
			Kit.Tween(sc, 0.25, { Scale = 0 })
		end
		task.wait(0.26)
		toast:Destroy()
	end)
	-- al massimo 4 messaggi contemporanei
	local children = {}
	for _, ch in stack:GetChildren() do
		if ch:IsA("Frame") then
			table.insert(children, ch)
		end
	end
	if #children > 4 then
		children[1]:Destroy()
	end
end

-- Annuncio a tutto il server (uova rare, schiuse epiche, eventi): striscia di feltro scuro nella
-- colonna in alto sotto le monete, con il bordo del colore della rarita'
local function announceParent(): Frame
	local hud = C.UI.Hud
	local slot = hud and hud.AnnounceSlot
	if slot then
		return slot
	end
	return announceFrame
end

function Notify.Announce(text: string, rarity: string?)
	local New = Kit.New
	local Theme = Kit.Theme
	local parent = announceParent()
	for _, ch in parent:GetChildren() do
		if ch:IsA("GuiObject") then
			ch:Destroy()
		end
	end
	local r = rarity and Rarities.List[rarity]
	local color = if r then r.color else Theme.Gold
	local box = New("Frame", {
		BackgroundColor3 = Theme.Outline,
		Size = UDim2.fromOffset(600, 44),
		Position = UDim2.fromScale(0.5, 0),
		AnchorPoint = Vector2.new(0.5, 0),
		Parent = parent,
	}, { Kit.Corner(UDim.new(0, 12)), Kit.Stroke(3, color), New("UIScale") })
	Kit.Stitch(box, 12, color)
	if parent:IsA("Frame") and parent.Name == "AnnounceSlot" then
		parent.Visible = true
	end
	local label = Kit.Text({
		Text = text,
		Font = Theme.BodyFont,
		Size = UDim2.new(0.94, 0, 0.7, 0),
		Position = UDim2.new(0.03, 0, 0.15, 0),
		RichText = true,
		Stroke = 2,
		ZIndex = 2,
		Parent = box,
	})
	if rarity and Rarities.Gradients[rarity] then
		local g = New("UIGradient", { Color = Rarities.Gradients[rarity], Parent = label })
		task.spawn(function()
			while g.Parent do
				g.Offset = Vector2.new(math.sin(os.clock() * 2) * 0.5, 0)
				task.wait()
			end
		end)
	else
		label.TextColor3 = color
	end
	Kit.Pop(box)
	C.Audio.Play(if rarity and Rarities.Get(rarity).order >= 6 then "Fanfare" else "Announce")
	task.delay(5, function()
		if box.Parent then
			Kit.Tween(box, 0.4, { BackgroundTransparency = 1 })
			Kit.Tween(label, 0.4, { TextTransparency = 1 })
			task.wait(0.45)
			local slot = box.Parent
			box:Destroy()
			if slot and slot.Name == "AnnounceSlot" and #slot:GetChildren() == 0 then
				(slot :: Frame).Visible = false
			end
		end
	end)
end

-- Freccia ai bordi dello schermo che punta verso il ladro per qualche secondo
local function arrowTo(thief: Player, duration: number)
	local New = Kit.New
	local gui = C.UI.Gui("Overlay")
	local arrow = New("TextLabel", {
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(70, 70),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Text = "➤",
		TextScaled = true,
		Font = Enum.Font.SourceSansBold,
		TextColor3 = Color3.fromRGB(255, 70, 70),
		Parent = gui,
	}, { New("UIStroke", { Thickness = 4, Color = Kit.Theme.Outline }) })
	local stop = os.clock() + duration
	local conn
	conn = RunService.RenderStepped:Connect(function()
		local char = thief.Character
		local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
		if os.clock() > stop or not hrp or not thief:GetAttribute("Thief") then
			conn:Disconnect()
			arrow:Destroy()
			return
		end
		local cam = workspace.CurrentCamera
		local vp = cam.ViewportSize
		local pos, onScreen = cam:WorldToViewportPoint(hrp.Position + Vector3.new(0, 4, 0))
		local center = vp / 2
		local dir = Vector2.new(pos.X, pos.Y) - center
		if pos.Z < 0 then
			dir = -dir
		end
		if onScreen and pos.Z > 0 then
			arrow.Position = UDim2.fromOffset(pos.X, pos.Y - 50)
			arrow.Rotation = 90
		else
			local m = math.max(math.abs(dir.X) / (center.X - 60), math.abs(dir.Y) / (center.Y - 60), 0.001)
			local p = center + dir / m
			arrow.Position = UDim2.fromOffset(p.X, p.Y)
			arrow.Rotation = math.deg(math.atan2(dir.Y, dir.X))
		end
	end)
end

function Notify.Start()
	Kit = C.UI.Kit
	local New = Kit.New
	local touch = UserInputService.TouchEnabled
	stack = New("Frame", {
		Name = "Toasts",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(430, 300),
		Position = if touch then UDim2.new(1, -16, 0, 96) else UDim2.new(1, -16, 1, -24),
		AnchorPoint = if touch then Vector2.new(1, 0) else Vector2.new(1, 1),
		Parent = C.UI.Gui("Top"),
	}, {
		New("UIListLayout", {
			Padding = UDim.new(0, 8),
			VerticalAlignment = if touch then Enum.VerticalAlignment.Top else Enum.VerticalAlignment.Bottom,
			HorizontalAlignment = Enum.HorizontalAlignment.Right,
			SortOrder = Enum.SortOrder.LayoutOrder,
		}),
	})
	-- annunci sotto le monete e la riga di stato dell'HUD
	announceFrame = New("Frame", {
		Name = "Announce",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(660, 80),
		Position = UDim2.new(0.5, 0, 0, 300),
		AnchorPoint = Vector2.new(0.5, 0),
		Parent = C.UI.Gui("Top"),
	})
	local T = C.Lang.T
	Net.Event("Notify").OnClientEvent:Connect(function(key, args, style)
		Notify.Toast(T(key, args), style)
		if style == "Bad" then
			C.Audio.Play("Error")
		elseif style == "Gold" or style == "Good" then
			C.Audio.Play("Success")
		end
	end)
	Net.Event("Announce").OnClientEvent:Connect(function(key, args, rarity)
		Notify.Announce(T(key, args), rarity)
	end)
	Net.Event("StealAlert").OnClientEvent:Connect(function(thiefId, itemKey)
		local thief = Players:GetPlayerByUserId(thiefId)
		local name = if thief then thief.DisplayName else "?"
		C.UI.Hud.ShowBanner(
			"🚨 " .. T("StealYourEgg", { name = name, item = itemKey }),
			T("StealCatchHint"),
			{ Color3.fromRGB(255, 90, 78), Color3.fromRGB(216, 27, 43) },
			3
		)
		task.delay(4, function()
			C.UI.Hud.ShowBanner(nil, nil, nil, 3)
		end)
		C.Audio.Play("Alarm")
		if thief then
			arrowTo(thief, 12)
		end
	end)
	-- bentornato: monete guadagnate dai pet mentre si era via (attributo impostato all'ingresso)
	local welcomed = false
	local function welcome()
		local amount = player:GetAttribute("OfflineEarned")
		if welcomed or type(amount) ~= "number" or amount <= 0 then
			return
		end
		welcomed = true
		task.wait(3) -- dopo la schermata di caricamento
		Notify.Announce(T("WelcomeBack") .. "  " .. T("OfflineEarned", { amount = amount }))
		C.Audio.Play("CoinsBig")
	end
	player:GetAttributeChangedSignal("OfflineEarned"):Connect(welcome)
	task.spawn(welcome)
end

return Notify
