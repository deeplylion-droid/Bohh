-- Pulsanti di interazione nel mondo (ProximityPrompt con stile personalizzato e anello di
-- caricamento), tradotti e filtrati: il proprietario vede "Schiudi/Vendi", gli altri "Ruba".

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ProximityPromptService = game:GetService("ProximityPromptService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local TweenService = game:GetService("TweenService")
local UserInputService = game:GetService("UserInputService")

local Format = require(ReplicatedStorage.Shared.Util.Format)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)

local Prompts = {}

local C
local Kit
local player = Players.LocalPlayer

local STYLE = {
	PickupPrompt = { key = "Prompt_Pickup", color = "Green" },
	HatchPrompt = { key = "Prompt_Hatch", color = "Yellow" },
	StealPrompt = { key = "Prompt_Steal", color = "Red" },
	SellPrompt = { key = "Prompt_Sell", color = "Orange" },
	BarrierPrompt = { key = "Prompt_Barrier", color = "Red" },
}

function Prompts.Init(controllers)
	C = controllers
end

-- Il lotto a cui appartiene un prompt (nil se fuori dai lotti)
local function plotOwner(prompt: ProximityPrompt): number?
	local node: Instance? = prompt
	while node do
		if node:IsA("Model") and node:GetAttribute("PlotIndex") then
			return node:GetAttribute("OwnerUserId") :: number?
		end
		node = node.Parent
	end
	return nil
end

-- Vero se questo prompt deve essere visibile al giocatore locale
local function visibleToMe(prompt: ProximityPrompt): boolean
	local forWhom = prompt:GetAttribute("For")
	if not forWhom then
		return true
	end
	local owner = plotOwner(prompt)
	if forWhom == "Owner" then
		return owner == player.UserId
	end
	return owner ~= nil and owner ~= 0 and owner ~= player.UserId
end

-- Stato voluto di un prompt dei lotti, ricavato dagli attributi della base (incubatrice/piedistallo):
-- cosi' non dipende dall'ordine in cui arrivano gli aggiornamenti dal server.
local function intended(prompt: ProximityPrompt): boolean
	local base = prompt.Parent
	if not base then
		return false
	end
	if base:GetAttribute("Locked") then
		return false
	end
	local name = prompt.Name
	if name == "HatchPrompt" then
		return base:GetAttribute("Ready") == true
	elseif name == "SellPrompt" then
		return base:GetAttribute("PetUid") ~= nil
	elseif name == "StealPrompt" then
		return (base:GetAttribute("PetUid") ~= nil or base:GetAttribute("EggRarity") ~= nil) and not base:GetAttribute("BeingStolen")
	elseif name == "BarrierPrompt" then
		return true
	end
	return prompt.Enabled
end

local function enforce(prompt: ProximityPrompt)
	local want = intended(prompt) and visibleToMe(prompt)
	if prompt.Enabled ~= want then
		prompt.Enabled = want
	end
end

local function watch(prompt: Instance)
	if not prompt:IsA("ProximityPrompt") or not prompt:GetAttribute("For") then
		return
	end
	enforce(prompt)
	prompt:GetPropertyChangedSignal("Enabled"):Connect(function()
		enforce(prompt)
	end)
	local base = prompt.Parent
	if base then
		for _, attr in { "Ready", "PetUid", "EggRarity", "BeingStolen", "Locked" } do
			base:GetAttributeChangedSignal(attr):Connect(function()
				enforce(prompt)
			end)
		end
	end
end

local function promptTexts(prompt: ProximityPrompt): (string, string)
	local T = C.Lang.T
	local style = STYLE[prompt.Name]
	local action = if style then T(style.key, { price = Format.Money(tonumber(prompt.ObjectText) or 0) }) else prompt.ActionText
	local object = ""
	local rarity = prompt:GetAttribute("Rarity")
	if prompt.Name == "PickupPrompt" and rarity then
		object = T("Egg_" .. rarity)
	elseif prompt.Name == "StealPrompt" or prompt.Name == "HatchPrompt" then
		local base = prompt.Parent
		local petId = base and base:GetAttribute("PetId")
		local eggRarity = base and base:GetAttribute("EggRarity")
		if petId then
			object = T("Pet_" .. petId)
		elseif eggRarity then
			object = T("Egg_" .. eggRarity)
		end
	end
	return action, object
end

local function build(prompt: ProximityPrompt, inputType: Enum.ProximityPromptInputType)
	local New = Kit.New
	local style = STYLE[prompt.Name] or { color = "Green" }
	local colors = Kit.Theme.Buttons[style.color]
	local gui = New("BillboardGui", {
		Name = "PromptUI",
		AlwaysOnTop = true,
		Active = true,
		Size = UDim2.fromOffset(300, 96),
		StudsOffsetWorldSpace = Vector3.new(0, 4.5, 0),
		LightInfluence = 0,
		ResetOnSpawn = false,
		Adornee = prompt.Parent,
		Parent = player:WaitForChild("PlayerGui"),
	})
	local holder = New("Frame", { BackgroundTransparency = 1, Size = UDim2.fromScale(1, 1), Parent = gui }, { New("UIScale", { Scale = math.max(0.75, C.UI.Scale or 1) }) })
	-- tasto rotondo con anello di caricamento
	local key = New("TextButton", {
		Text = "",
		AutoButtonColor = false,
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(72, 72),
		Position = UDim2.fromOffset(8, 12),
		Parent = holder,
	}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(5), Kit.Gradient(colors[1], colors[2]) })
	local keyText = if inputType == Enum.ProximityPromptInputType.Touch then "👆" elseif inputType == Enum.ProximityPromptInputType.Gamepad then "X" else prompt.KeyboardKeyCode.Name
	Kit.Text({ Text = keyText, Size = UDim2.fromScale(0.6, 0.6), Position = UDim2.fromScale(0.2, 0.2), Parent = key })
	local ring = New("UIStroke", { Thickness = 7, Color = Color3.new(1, 1, 1), Transparency = 1, Parent = New("Frame", {
		BackgroundTransparency = 1,
		Size = UDim2.fromScale(1.2, 1.2),
		Position = UDim2.fromScale(-0.1, -0.1),
		Parent = key,
	}, { Kit.Corner(UDim.new(1, 0)) }) })
	local box = New("Frame", {
		BackgroundColor3 = Color3.fromRGB(29, 22, 48),
		BackgroundTransparency = 0.12,
		Size = UDim2.fromOffset(200, 64),
		Position = UDim2.fromOffset(88, 16),
		Parent = holder,
	}, { Kit.Corner(UDim.new(0, 16)), Kit.Stroke(4) })
	local action, object = promptTexts(prompt)
	Kit.Text({ Text = action, Size = UDim2.new(0.9, 0, 0, 32), Position = UDim2.new(0.05, 0, 0, 4), TextXAlignment = Enum.TextXAlignment.Left, Parent = box })
	local objLabel = Kit.Text({ Text = object, Font = Kit.Theme.BodyFont, Size = UDim2.new(0.9, 0, 0, 22), Position = UDim2.new(0.05, 0, 0, 36), TextXAlignment = Enum.TextXAlignment.Left, Stroke = 2, Parent = box })
	local rarity = prompt:GetAttribute("Rarity") or (prompt.Parent and prompt.Parent:GetAttribute("EggRarity"))
	if rarity and Rarities.List[rarity] then
		objLabel.TextColor3 = Rarities.List[rarity].color
	end
	Kit.Pop(holder)

	-- tocco / clic sul tasto: inizio e fine della pressione
	key.InputBegan:Connect(function(input)
		if input.UserInputType == Enum.UserInputType.Touch or input.UserInputType == Enum.UserInputType.MouseButton1 then
			prompt:InputHoldBegin()
		end
	end)
	key.InputEnded:Connect(function(input)
		if input.UserInputType == Enum.UserInputType.Touch or input.UserInputType == Enum.UserInputType.MouseButton1 then
			prompt:InputHoldEnd()
		end
	end)
	local holdTween: Tween? = nil
	local c1 = prompt.PromptButtonHoldBegan:Connect(function()
		if prompt.HoldDuration > 0 then
			ring.Transparency = 0
			ring.Color = Color3.new(1, 1, 1)
			local tween = TweenService:Create(ring, TweenInfo.new(prompt.HoldDuration, Enum.EasingStyle.Linear), { Color = colors[1] })
			holdTween = tween
			tween:Play()
		end
		Kit.Tween(key, 0.1, { Size = UDim2.fromOffset(64, 64), Position = UDim2.fromOffset(12, 16) })
	end)
	local c2 = prompt.PromptButtonHoldEnded:Connect(function()
		if holdTween then
			holdTween:Cancel()
		end
		ring.Transparency = 1
		Kit.Tween(key, 0.15, { Size = UDim2.fromOffset(72, 72), Position = UDim2.fromOffset(8, 12) }, Enum.EasingStyle.Back)
	end)
	local c3 = prompt.Triggered:Connect(function()
		Kit.Bounce(holder, 0.18)
		C.Audio.Play("Click")
	end)
	return function()
		c1:Disconnect()
		c2:Disconnect()
		c3:Disconnect()
		gui:Destroy()
	end
end

function Prompts.Start()
	Kit = C.UI.Kit
	local active: { [ProximityPrompt]: () -> () } = {}
	ProximityPromptService.PromptShown:Connect(function(prompt, inputType)
		if prompt.Style ~= Enum.ProximityPromptStyle.Custom then
			return
		end
		if not visibleToMe(prompt) then
			prompt.Enabled = false
			return
		end
		if active[prompt] then
			active[prompt]()
		end
		active[prompt] = build(prompt, inputType)
	end)
	ProximityPromptService.PromptHidden:Connect(function(prompt)
		if active[prompt] then
			active[prompt]()
			active[prompt] = nil
		end
	end)
	-- filtro proprietario/altri su tutti i prompt dei lotti
	local plots = workspace:WaitForChild("Plots", 60)
	if plots then
		for _, d in plots:GetDescendants() do
			watch(d)
		end
		plots.DescendantAdded:Connect(watch)
		for _, plot in plots:GetChildren() do
			plot:GetAttributeChangedSignal("OwnerUserId"):Connect(function()
				for _, d in plot:GetDescendants() do
					if d:IsA("ProximityPrompt") and d:GetAttribute("For") then
						enforce(d)
					end
				end
			end)
		end
	end
	local _ = { CollectionService, UserInputService }
end

return Prompts
