-- Schermata di caricamento (ReplicatedFirst): parte subito, prima del resto del gioco.
-- Cielo sfumato, titolo gommoso, uova che saltellano, barra di avanzamento e consigli a rotazione.
-- Si chiude quando server, modelli 3D e personaggio sono pronti (al massimo dopo 45 s).

local LocalizationService = game:GetService("LocalizationService")
local Players = game:GetService("Players")
local ReplicatedFirst = game:GetService("ReplicatedFirst")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local player = Players.LocalPlayer

ReplicatedFirst:RemoveDefaultLoadingScreen()

local OUTLINE = Color3.fromRGB(29, 22, 48)
local TITLE = "CLIMB & STEAL EGGS" -- stesso nome di Config.Game.Name

local italian = false
do
	local ok, locale = pcall(function()
		return LocalizationService.RobloxLocaleId
	end)
	local id = string.lower(if ok and locale then locale else player.LocaleId)
	italian = string.sub(id, 1, 2) == "it"
end

local TEXT = {
	loading = if italian then "Caricamento della montagna..." else "Loading the mountain...",
	server = if italian then "Preparo i sentieri..." else "Preparing the trails...",
	models = if italian then "Covo le uova..." else "Warming up the eggs...",
	spawn = if italian then "Si parte!" else "Here we go!",
}
local TIPS = if italian
	then {
		"Più scendi, più le uova sono rare!",
		"Le uova rare sono pesanti: potenzia la Forza per salire più veloce.",
		"Quando suona la sirena, corri in un rifugio!",
		"Blocca il tuo lotto con la barriera laser quando arrivano i ladri.",
		"Uno schiaffo fa cadere la refurtiva dalle mani del ladro.",
		"Le mamme guardiane proteggono i nidi più preziosi...",
		"Le mutazioni Arcobaleno e Cosmica moltiplicano i guadagni!",
	}
	else {
		"The deeper you go, the rarer the eggs!",
		"Rare eggs are heavy: upgrade Strength to climb faster.",
		"When the siren sounds, run to a shelter!",
		"Lock your base with the laser barrier when thieves show up.",
		"A slap makes thieves drop their loot.",
		"Guardian mothers protect the most precious nests...",
		"Rainbow and Cosmic mutations multiply your income!",
	}

local function new(className: string, props: { [string]: any }, children: { Instance }?): any
	local inst = Instance.new(className)
	for k, v in props do
		if k ~= "Parent" then
			(inst :: any)[k] = v
		end
	end
	if children then
		for _, c in children do
			c.Parent = inst
		end
	end
	inst.Parent = props.Parent
	return inst
end

local function stroke(thickness: number, mode: Enum.ApplyStrokeMode?): UIStroke
	return new("UIStroke", { Thickness = thickness, Color = OUTLINE, LineJoinMode = Enum.LineJoinMode.Round, ApplyStrokeMode = mode or Enum.ApplyStrokeMode.Contextual })
end

local gui = new("ScreenGui", {
	Name = "LoadingScreen",
	IgnoreGuiInset = true,
	ResetOnSpawn = false,
	DisplayOrder = 100,
	ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	Parent = player:WaitForChild("PlayerGui"),
})
local bg = new("Frame", {
	Size = UDim2.fromScale(1, 1),
	BackgroundColor3 = Color3.new(1, 1, 1),
	BorderSizePixel = 0,
	Parent = gui,
}, {
	new("UIGradient", {
		Rotation = 90,
		Color = ColorSequence.new({
			ColorSequenceKeypoint.new(0, Color3.fromRGB(110, 196, 255)),
			ColorSequenceKeypoint.new(0.55, Color3.fromRGB(178, 160, 255)),
			ColorSequenceKeypoint.new(1, Color3.fromRGB(255, 176, 214)),
		}),
	}),
})

-- montagne stilizzate (rombi ruotati) con la vetta innevata
local mountains = new("Frame", { BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = bg })
for i, m in {
	{ x = 0.18, size = 0.62, color = Color3.fromRGB(120, 104, 214) },
	{ x = 0.82, size = 0.58, color = Color3.fromRGB(132, 112, 222) },
	{ x = 0.5, size = 0.86, color = Color3.fromRGB(96, 80, 196) },
} do
	local peak = new("Frame", {
		BackgroundColor3 = m.color,
		BorderSizePixel = 0,
		Size = UDim2.fromScale(m.size, m.size),
		SizeConstraint = Enum.SizeConstraint.RelativeYY,
		Position = UDim2.fromScale(m.x, 1.02),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Rotation = 45,
		ZIndex = i,
		Parent = mountains,
	}, { new("UICorner", { CornerRadius = UDim.new(0.06, 0) }) })
	new("Frame", {
		BackgroundColor3 = Color3.fromRGB(250, 252, 255),
		BorderSizePixel = 0,
		Size = UDim2.fromScale(0.3, 0.3),
		ZIndex = i,
		Parent = peak,
	}, { new("UICorner", { CornerRadius = UDim.new(0.2, 0) }) })
end

local content = new("Frame", {
	BackgroundTransparency = 1,
	Size = UDim2.fromOffset(900, 560),
	Position = UDim2.fromScale(0.5, 0.46),
	AnchorPoint = Vector2.new(0.5, 0.5),
	ZIndex = 10,
	Parent = bg,
})
local scale = new("UIScale", { Parent = content })
local function rescale()
	local cam = workspace.CurrentCamera
	local v = if cam then cam.ViewportSize else Vector2.new(1280, 720)
	scale.Scale = math.clamp(math.min(v.X / 1000, v.Y / 640), 0.45, 1.4)
end
rescale()
if workspace.CurrentCamera then
	workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(rescale)
end

local title = new("TextLabel", {
	BackgroundTransparency = 1,
	Text = TITLE,
	Font = Enum.Font.LuckiestGuy,
	TextScaled = true,
	TextColor3 = Color3.fromRGB(255, 225, 77),
	Size = UDim2.fromOffset(880, 120),
	Position = UDim2.fromOffset(10, 40),
	Rotation = -2,
	ZIndex = 12,
	Parent = content,
}, {
	stroke(8),
	new("UIGradient", { Rotation = 90, Color = ColorSequence.new(Color3.fromRGB(255, 244, 140), Color3.fromRGB(255, 170, 30)) }),
})

-- uova che saltellano
local eggColors = {
	{ Color3.fromRGB(250, 250, 255), Color3.fromRGB(200, 210, 225) },
	{ Color3.fromRGB(110, 190, 255), Color3.fromRGB(40, 110, 230) },
	{ Color3.fromRGB(214, 140, 255), Color3.fromRGB(130, 50, 230) },
	{ Color3.fromRGB(255, 226, 90), Color3.fromRGB(240, 140, 10) },
	{ Color3.fromRGB(110, 255, 230), Color3.fromRGB(150, 60, 255) },
}
local eggs = {}
for i, c in eggColors do
	local egg = new("Frame", {
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(74, 94),
		Position = UDim2.fromOffset(450 + (i - 3) * 110, 290),
		AnchorPoint = Vector2.new(0.5, 1),
		ZIndex = 12,
		Parent = content,
	}, {
		new("UICorner", { CornerRadius = UDim.new(0.5, 0) }),
		stroke(5, Enum.ApplyStrokeMode.Border),
		new("UIGradient", { Rotation = 90, Color = ColorSequence.new(c[1], c[2]) }),
	})
	-- riflesso
	new("Frame", {
		BackgroundColor3 = Color3.new(1, 1, 1),
		BackgroundTransparency = 0.45,
		Size = UDim2.fromScale(0.22, 0.3),
		Position = UDim2.fromScale(0.2, 0.16),
		ZIndex = 13,
		Parent = egg,
	}, { new("UICorner", { CornerRadius = UDim.new(1, 0) }) })
	table.insert(eggs, egg)
end

-- barra di avanzamento
local barBack = new("Frame", {
	BackgroundColor3 = OUTLINE,
	Size = UDim2.fromOffset(620, 44),
	Position = UDim2.fromOffset(140, 360),
	ZIndex = 12,
	Parent = content,
}, { new("UICorner", { CornerRadius = UDim.new(1, 0) }), stroke(5, Enum.ApplyStrokeMode.Border) })
local barFill = new("Frame", {
	BackgroundColor3 = Color3.new(1, 1, 1),
	Size = UDim2.new(0, 0, 1, -10),
	Position = UDim2.fromOffset(5, 5),
	ZIndex = 13,
	Parent = barBack,
}, {
	new("UICorner", { CornerRadius = UDim.new(1, 0) }),
	new("UIGradient", { Rotation = 90, Color = ColorSequence.new(Color3.fromRGB(141, 255, 98), Color3.fromRGB(34, 194, 59)) }),
})
local percent = new("TextLabel", {
	BackgroundTransparency = 1,
	Text = "0%",
	Font = Enum.Font.LuckiestGuy,
	TextScaled = true,
	TextColor3 = Color3.new(1, 1, 1),
	Size = UDim2.new(1, 0, 0.7, 0),
	Position = UDim2.fromScale(0, 0.15),
	ZIndex = 14,
	Parent = barBack,
}, { stroke(3) })
local status = new("TextLabel", {
	BackgroundTransparency = 1,
	Text = TEXT.loading,
	Font = Enum.Font.FredokaOne,
	TextScaled = true,
	TextColor3 = Color3.new(1, 1, 1),
	Size = UDim2.fromOffset(620, 32),
	Position = UDim2.fromOffset(140, 414),
	ZIndex = 12,
	Parent = content,
}, { stroke(3) })
local tip = new("TextLabel", {
	BackgroundTransparency = 1,
	Text = "💡 " .. TIPS[math.random(1, #TIPS)],
	Font = Enum.Font.FredokaOne,
	TextScaled = true,
	TextColor3 = Color3.fromRGB(255, 240, 180),
	Size = UDim2.fromOffset(820, 34),
	Position = UDim2.fromOffset(40, 480),
	ZIndex = 12,
	Parent = content,
}, { stroke(3) })

-- animazioni
local progress, shown = 0.04, 0
local t0 = os.clock()
local anim = RunService.RenderStepped:Connect(function(dt)
	local t = os.clock() - t0
	for i, egg in eggs do
		local hop = math.max(0, math.sin(t * 5 - i * 0.7))
		egg.Position = UDim2.fromOffset(450 + (i - 3) * 110, 290 - hop * 46)
		egg.Rotation = math.sin(t * 5 - i * 0.7 - 0.6) * 8
	end
	title.Rotation = -2 + math.sin(t * 1.6) * 1.2
	shown += (progress - shown) * math.min(1, dt * 4)
	local f = math.clamp(shown, 0, 1)
	barFill.Size = UDim2.new(f, -10 * f, 1, -10)
	percent.Text = `{math.floor(shown * 100 + 0.5)}%`
end)
task.spawn(function()
	while gui.Parent do
		task.wait(4)
		local nextTip = TIPS[math.random(1, #TIPS)]
		local fade = TweenService:Create(tip, TweenInfo.new(0.25), { TextTransparency = 1 })
		fade:Play()
		fade.Completed:Wait()
		tip.Text = "💡 " .. nextTip
		TweenService:Create(tip, TweenInfo.new(0.25), { TextTransparency = 0 }):Play()
	end
end)

-- attesa delle fasi di caricamento (con un limite di tempo complessivo)
local deadline = os.clock() + 45
local function waitFor(check: () -> boolean)
	while not check() and os.clock() < deadline do
		task.wait(0.1)
	end
end

if not game:IsLoaded() then
	game.Loaded:Wait()
end
progress = 0.35
status.Text = TEXT.server
waitFor(function()
	return workspace:GetAttribute("ServerReady") == true
end)
progress = 0.62
status.Text = TEXT.models
waitFor(function()
	local assets = ReplicatedStorage:FindFirstChild("Assets")
	return assets ~= nil and assets:GetAttribute("Ready") == true
end)
progress = 0.85
waitFor(function()
	local char = player.Character
	return char ~= nil and char:FindFirstChild("HumanoidRootPart") ~= nil
end)
progress = 1
status.Text = TEXT.spawn
while os.clock() - t0 < 2.2 do
	task.wait(0.05)
end
task.wait(0.4)

-- dissolvenza
local fadeInfo = TweenInfo.new(0.6, Enum.EasingStyle.Quad)
TweenService:Create(scale, TweenInfo.new(0.5, Enum.EasingStyle.Back, Enum.EasingDirection.In), { Scale = 0 }):Play()
for _, d in bg:GetDescendants() do
	if d:IsA("Frame") then
		TweenService:Create(d, fadeInfo, { BackgroundTransparency = 1 }):Play()
	elseif d:IsA("TextLabel") then
		TweenService:Create(d, fadeInfo, { TextTransparency = 1 }):Play()
	elseif d:IsA("UIStroke") then
		TweenService:Create(d, fadeInfo, { Transparency = 1 }):Play()
	end
end
TweenService:Create(bg, fadeInfo, { BackgroundTransparency = 1 }):Play()
task.wait(0.65)
anim:Disconnect()
gui:Destroy()
