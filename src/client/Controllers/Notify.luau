-- Messaggi a comparsa, annunci a tutto il server e avviso di furto con freccia verso il ladro.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Net = require(ReplicatedStorage.Shared.Net)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)

local Notify = {}

local C
local Kit
local stack: Frame
local announceFrame: Frame
local player = Players.LocalPlayer

local STYLE = {
	Good = { Color3.fromRGB(141, 255, 98), Color3.fromRGB(34, 170, 59) },
	Bad = { Color3.fromRGB(255, 120, 110), Color3.fromRGB(200, 30, 45) },
	Info = { Color3.fromRGB(105, 216, 255), Color3.fromRGB(27, 110, 230) },
	Gold = { Color3.fromRGB(255, 236, 120), Color3.fromRGB(240, 150, 10) },
}

function Notify.Init(controllers)
	C = controllers
end

-- Toast in alto a destra dello schermo (piu' recenti in alto)
function Notify.Toast(text: string, style: string?)
	local colors = STYLE[style or "Info"] or STYLE.Info
	local New = Kit.New
	local toast = New("Frame", {
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(420, 58),
		Parent = stack,
	}, { Kit.Corner(UDim.new(0, 18)), Kit.Stroke(4), Kit.Gradient(colors[1], colors[2]), New("UIScale") })
	Kit.Text({
		Text = text,
		Size = UDim2.new(0.92, 0, 0.62, 0),
		Position = UDim2.new(0.04, 0, 0.19, 0),
		RichText = true,
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

-- Annuncio grande al centro (uova rare, schiuse epiche, eventi)
function Notify.Announce(text: string, rarity: string?)
	local New = Kit.New
	for _, ch in announceFrame:GetChildren() do
		ch:Destroy()
	end
	local r = rarity and Rarities.List[rarity]
	local color = if r then r.color else Color3.fromRGB(255, 225, 77)
	local box = New("Frame", {
		BackgroundColor3 = Color3.fromRGB(29, 22, 48),
		BackgroundTransparency = 0.1,
		Size = UDim2.fromOffset(640, 70),
		Position = UDim2.fromScale(0.5, 0),
		AnchorPoint = Vector2.new(0.5, 0),
		Parent = announceFrame,
	}, { Kit.Corner(UDim.new(0, 22)), Kit.Stroke(5, color), New("UIScale") })
	local label = Kit.Text({
		Text = text,
		Size = UDim2.new(0.94, 0, 0.66, 0),
		Position = UDim2.new(0.03, 0, 0.17, 0),
		RichText = true,
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
			box:Destroy()
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
	}, { New("UIStroke", { Thickness = 4, Color = Color3.fromRGB(29, 22, 48) }) })
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
	stack = New("Frame", {
		Name = "Toasts",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(430, 300),
		Position = UDim2.new(1, -16, 1, -150),
		AnchorPoint = Vector2.new(1, 1),
		Parent = C.UI.Gui("Top"),
	}, {
		New("UIListLayout", {
			Padding = UDim.new(0, 8),
			VerticalAlignment = Enum.VerticalAlignment.Bottom,
			HorizontalAlignment = Enum.HorizontalAlignment.Right,
			SortOrder = Enum.SortOrder.LayoutOrder,
		}),
	})
	announceFrame = New("Frame", {
		Name = "Announce",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(660, 80),
		Position = UDim2.new(0.5, 0, 0, 200),
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
