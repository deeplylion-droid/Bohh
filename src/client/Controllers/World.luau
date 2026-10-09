-- Animazioni ed etichette lato client: pet sui piedistalli, uova in incubazione, soldi sulle pedane,
-- monumento, tabelloni delle classifiche, indicatore del proprio lotto.

local CollectionService = game:GetService("CollectionService")
local HttpService = game:GetService("HttpService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Format = require(ReplicatedStorage.Shared.Util.Format)
local Pets = require(ReplicatedStorage.Shared.Config.Pets)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Variants = require(ReplicatedStorage.Shared.Config.Variants)

local World = {}

local C
local Kit
local player = Players.LocalPlayer

type PetAnim = {
	model: Model,
	base: CFrame,
	parts: { { part: BasePart, offset: CFrame, group: string?, pivot: CFrame? } },
	seed: number,
	flying: boolean,
	giant: boolean,
	billboard: BillboardGui?,
}

local pets: { [Model]: PetAnim } = {}
local eggs: { [Model]: { base: CFrame, parts: { { part: BasePart, offset: CFrame } }, seed: number } } = {}
local lowGfx = false
local applySmallDecor: () -> ()

function World.Init(controllers)
	C = controllers
end

-- Grafica leggera: i dettagli piccoli dello scenario (erba, fiori, felci...) vengono tolti dal mondo
local hiddenDecor: { [Instance]: Instance } = {}
applySmallDecor = function()
	if lowGfx then
		for _, m in CollectionService:GetTagged("SmallDecor") do
			if m.Parent then
				hiddenDecor[m] = m.Parent
				m.Parent = nil
			end
		end
	else
		for m, parent in hiddenDecor do
			m.Parent = parent
		end
		table.clear(hiddenDecor)
	end
end

---------------------------------------------------------------------------------------------
-- Pet
---------------------------------------------------------------------------------------------
local function petBillboard(model: Model): BillboardGui
	local T = C.Lang.T
	local petId = model:GetAttribute("PetId")
	local def = Pets.ById[petId]
	local r = def and Rarities.List[def.rarity]
	local mutation = model:GetAttribute("Mutation") or "None"
	local size = model:GetAttribute("Size") or "Normal"
	local _, bbSize = model:GetBoundingBox()
	-- i giganti Ultra hanno la targhetta piu' grande, visibile da tutta la vetta
	local giant = model:GetAttribute("Giant") == true
	local gui = Kit.New("BillboardGui", {
		Name = "PetInfo",
		Size = if giant then UDim2.fromOffset(330, 138) else UDim2.fromOffset(220, 92),
		StudsOffsetWorldSpace = Vector3.new(0, bbSize.Y + (if giant then 4 else 1.6), 0),
		MaxDistance = if giant then 320 else 60,
		LightInfluence = 0,
		AlwaysOnTop = false,
		Adornee = model.PrimaryPart,
		Parent = model,
	})
	local tagText = ""
	if mutation ~= "None" then
		tagText ..= T("Mutation_" .. mutation) .. " "
	end
	if size ~= "Normal" then
		tagText ..= T("Size_" .. size)
	end
	if tagText ~= "" then
		local tag = Kit.Text({
			Text = tagText,
			Size = UDim2.new(1, 0, 0, 22),
			Position = UDim2.fromOffset(0, 0),
			TextColor3 = Variants.Mutations[mutation] and Variants.Mutations[mutation].color or Color3.new(1, 1, 1),
			Parent = gui,
		})
		if mutation == "Rainbow" then
			Kit.New("UIGradient", { Color = Rarities.Gradients.Divine, Parent = tag })
			tag.TextColor3 = Color3.new(1, 1, 1)
		end
	end
	local name = Kit.Text({
		Text = T("Pet_" .. petId),
		Size = UDim2.new(1, 0, 0, 28),
		Position = UDim2.fromOffset(0, 22),
		TextColor3 = r and r.color or Color3.new(1, 1, 1),
		Parent = gui,
	})
	if def and Rarities.Gradients[def.rarity] then
		Kit.New("UIGradient", { Color = Rarities.Gradients[def.rarity], Parent = name })
		name.TextColor3 = Color3.new(1, 1, 1)
	end
	Kit.Text({
		Text = def and T("Rarity_" .. def.rarity) or "",
		Font = Kit.Theme.BodyFont,
		Size = UDim2.new(1, 0, 0, 18),
		Position = UDim2.fromOffset(0, 50),
		Stroke = 2,
		Parent = gui,
	})
	local income = Kit.Text({
		Name = "Income",
		Text = "",
		Size = UDim2.new(1, 0, 0, 22),
		Position = UDim2.fromOffset(0, 68),
		TextColor3 = Kit.Theme.Green,
		Parent = gui,
	})
	local base = model.Parent
	local function refreshIncome()
		local v = base and base:GetAttribute("Income")
		income.Text = if v then Format.Rate(v) else ""
	end
	if base then
		-- il collegamento muore con l'etichetta (nuovo pet o cambio lingua): niente accumuli
		local conn = base:GetAttributeChangedSignal("Income"):Connect(refreshIncome)
		gui.Destroying:Connect(function()
			conn:Disconnect()
		end)
	end
	refreshIncome()
	return gui
end

local function addPet(model: Model)
	if not model:IsA("Model") then
		return
	end
	local pivot = model:GetPivot()
	-- il perno delle ali/pinne e' salvato in coordinate del modello non scalato
	local scale = model:GetScale()
	local parts = {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			local group = d:GetAttribute("Group")
			local pv = d:GetAttribute("Pivot")
			table.insert(parts, {
				part = d,
				offset = pivot:ToObjectSpace(d.CFrame),
				group = group,
				pivot = if typeof(pv) == "Vector3" then CFrame.new(pv * scale) else nil,
			})
		end
	end
	local anim: PetAnim = {
		model = model,
		base = pivot,
		parts = parts,
		seed = math.random() * 10,
		flying = model:GetAttribute("Flying") == true,
		giant = model:GetAttribute("Giant") == true,
		billboard = nil,
	}
	pets[model] = anim
	anim.billboard = petBillboard(model)
end

local function animatePet(a: PetAnim, t: number)
	-- i giganti Ultra si muovono lenti e maestosi
	local s = (if a.giant then t * 0.4 else t) + a.seed
	local bob = if a.flying then 1.2 + math.sin(s * 2.2) * 0.45 else math.abs(math.sin(s * 3.1)) * 0.22
	local sway = math.sin(s * 1.3) * math.rad(if a.giant then 3 else 7)
	if a.giant then
		bob = math.sin(s * 2) * 0.35
	end
	local squash = 1 + math.sin(s * 6.2) * 0.02
	local root = a.base * CFrame.new(0, bob, 0) * CFrame.Angles(0, sway, math.sin(s * 2.6) * math.rad(2))
	for _, p in a.parts do
		local cf = root * p.offset
		if p.group and p.pivot then
			local amp = if a.flying then 28 elseif a.giant then 10 else 16
			local flap = math.sin(s * (if a.flying then 14 else 9)) * math.rad(amp)
			local dir = if string.find(p.group, "L") == #p.group then -1 else 1
			cf = root * p.pivot * CFrame.Angles(0, 0, flap * dir) * p.pivot:Inverse() * p.offset
		end
		p.part.CFrame = cf
	end
	local _ = squash
end

---------------------------------------------------------------------------------------------
-- Uova in incubazione: tremano sempre di piu' avvicinandosi alla schiusa
---------------------------------------------------------------------------------------------
local function addEgg(model: Model)
	if not model:IsA("Model") then
		return
	end
	local pivot = model:GetPivot()
	local parts = {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			table.insert(parts, { part = d, offset = pivot:ToObjectSpace(d.CFrame) })
		end
	end
	eggs[model] = { base = pivot, parts = parts, seed = math.random() * 10 }
end

local incubatorGuis: { [BasePart]: { gui: BillboardGui, label: TextLabel, bar: Frame, fill: Frame } } = {}

local function incubatorBillboard(base: BasePart)
	local gui = Kit.New("BillboardGui", {
		Name = "IncubatorInfo",
		Size = UDim2.fromOffset(150, 56),
		StudsOffsetWorldSpace = Vector3.new(0, 6.2, 0),
		MaxDistance = 70,
		LightInfluence = 0,
		Adornee = base,
		Enabled = false,
		Parent = base,
	})
	local label = Kit.Text({ Text = "", Size = UDim2.new(1, 0, 0, 30), Parent = gui })
	local bar = Kit.New("Frame", {
		BackgroundColor3 = Color3.fromRGB(29, 22, 48),
		Size = UDim2.new(0.86, 0, 0, 14),
		Position = UDim2.new(0.07, 0, 0, 34),
		Parent = gui,
	}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(3) })
	local fill = Kit.New(
		"Frame",
		{ BackgroundColor3 = Kit.Theme.Green, Size = UDim2.fromScale(0, 1), Parent = bar },
		{ Kit.Corner(UDim.new(1, 0)) }
	)
	incubatorGuis[base] = { gui = gui, label = label, bar = bar, fill = fill }
end

local RING_IDLE = Color3.fromRGB(150, 140, 170)
local RING_BUSY = Color3.fromRGB(255, 160, 60)
local RING_READY = Color3.fromRGB(255, 230, 80)

local function refreshIncubators()
	local now = workspace:GetServerTimeNow()
	local T = C.Lang.T
	for base, g in incubatorGuis do
		local rarity = base:GetAttribute("EggRarity")
		local readyAt = base:GetAttribute("ReadyAt")
		-- anello luminoso: spento se vuota, arancione mentre cova, giallo pulsante quando e' pronta
		local ring = base:FindFirstChild("Ring")
		if ring and ring:IsA("BasePart") then
			if not rarity then
				ring.Color = RING_IDLE
			elseif readyAt and readyAt <= now then
				ring.Color = RING_BUSY:Lerp(RING_READY, 0.5 + math.sin(now * 6) * 0.5)
			else
				ring.Color = RING_BUSY
			end
		end
		if rarity and readyAt and base.Parent then
			g.gui.Enabled = true
			local r = Rarities.List[rarity]
			local total = base:GetAttribute("Duration") or (r and r.hatch) or 60
			local left = readyAt - now
			if left <= 0 then
				g.label.Text = T("Ready")
				g.label.TextColor3 = Kit.Theme.Gold
				g.fill.Size = UDim2.fromScale(1, 1)
				g.fill.BackgroundColor3 = Kit.Theme.Gold
			else
				g.label.Text = Format.Clock(left)
				g.label.TextColor3 = Color3.new(1, 1, 1)
				g.fill.Size = UDim2.fromScale(math.clamp(1 - left / total, 0.03, 1), 1)
				g.fill.BackgroundColor3 = Kit.Theme.Green
			end
		else
			g.gui.Enabled = false
		end
	end
end

---------------------------------------------------------------------------------------------
-- Pedane con le monete accumulate
---------------------------------------------------------------------------------------------
local padGuis: { [BasePart]: TextLabel } = {}
local function addPad(pad: BasePart)
	local gui = Kit.New("BillboardGui", {
		Name = "Bank",
		Size = UDim2.fromOffset(130, 34),
		StudsOffsetWorldSpace = Vector3.new(0, 2.2, 0),
		MaxDistance = 45,
		LightInfluence = 0,
		Adornee = pad,
		Parent = pad,
	})
	local label = Kit.Text({ Text = "", TextColor3 = Kit.Theme.Gold, Size = UDim2.fromScale(1, 1), Parent = gui })
	padGuis[pad] = label
	local function refresh()
		local v = pad:GetAttribute("Bank") or 0
		label.Text = if v >= 1 then Format.Money(v) else ""
	end
	pad:GetAttributeChangedSignal("Bank"):Connect(refresh)
	refresh()
end

---------------------------------------------------------------------------------------------
-- Tabelloni delle classifiche
---------------------------------------------------------------------------------------------
local function drawBoard(board: BasePart)
	local gui = board:FindFirstChild("BoardGui")
	if not gui then
		return
	end
	gui:ClearAllChildren()
	local T = C.Lang.T
	local New = Kit.New
	New("Frame", { BackgroundColor3 = Color3.fromRGB(40, 30, 72), Size = UDim2.fromScale(1, 1), Parent = gui })
	Kit.Text({
		Text = T(board:GetAttribute("TitleKey") or "LbMoney"),
		TextColor3 = Kit.Theme.Gold,
		Size = UDim2.new(0.9, 0, 0.12, 0),
		Position = UDim2.new(0.05, 0, 0.02, 0),
		Parent = gui,
	})
	local ok, list = pcall(HttpService.JSONDecode, HttpService, board:GetAttribute("Data") or "[]")
	if not ok or type(list) ~= "table" or #list == 0 then
		Kit.Text({
			Text = T("LbEmpty"),
			Font = Kit.Theme.BodyFont,
			Size = UDim2.new(0.9, 0, 0.08, 0),
			Position = UDim2.new(0.05, 0, 0.45, 0),
			Parent = gui,
		})
		return
	end
	local key = board:GetAttribute("BoardKey")
	for i, e in list do
		local y = 0.15 + (i - 1) * 0.084
		local color = if i == 1
			then Kit.Theme.Gold
			elseif i == 2 then Color3.fromRGB(210, 220, 235)
			elseif i == 3 then Color3.fromRGB(230, 150, 80)
			else Color3.new(1, 1, 1)
		Kit.Text({
			Text = `#{e.rank}`,
			TextColor3 = color,
			Size = UDim2.new(0.14, 0, 0.07, 0),
			Position = UDim2.new(0.04, 0, y, 0),
			TextXAlignment = Enum.TextXAlignment.Left,
			Parent = gui,
		})
		Kit.Text({
			Text = e.name,
			Font = Kit.Theme.BodyFont,
			Size = UDim2.new(0.5, 0, 0.065, 0),
			Position = UDim2.new(0.18, 0, y, 0),
			TextXAlignment = Enum.TextXAlignment.Left,
			Stroke = 2,
			Parent = gui,
		})
		local value = if key == "Steals"
			then tostring(math.floor(e.value + 0.5))
			elseif key == "Income" then Format.Rate(e.value)
			else Format.Money(e.value)
		Kit.Text({
			Text = value,
			TextColor3 = Kit.Theme.Green,
			Size = UDim2.new(0.3, 0, 0.065, 0),
			Position = UDim2.new(0.66, 0, y, 0),
			TextXAlignment = Enum.TextXAlignment.Right,
			Parent = gui,
		})
	end
end

---------------------------------------------------------------------------------------------
-- Freccia/indicatore del proprio lotto (utile appena entrati o dopo una caduta)
---------------------------------------------------------------------------------------------
local function homeMarker()
	local plotIndex = player:GetAttribute("PlotIndex")
	local plots = workspace:FindFirstChild("Plots")
	local plot = plotIndex and plots and plots:FindFirstChild("Plot" .. plotIndex)
	local old = workspace:FindFirstChild("HomeMarker")
	if old then
		old:Destroy()
	end
	if not plot then
		return
	end
	local floor = plot:FindFirstChild("Floor") :: BasePart?
	if not floor then
		return
	end
	local gui = Kit.New("BillboardGui", {
		Name = "HomeMarker",
		Size = UDim2.fromOffset(220, 90),
		StudsOffsetWorldSpace = Vector3.new(0, 26, 0),
		AlwaysOnTop = true,
		LightInfluence = 0,
		Adornee = floor,
		Parent = workspace,
	})
	local label = Kit.Text({
		Text = C.Lang.T("YourBase"),
		TextColor3 = Kit.Theme.Gold,
		Size = UDim2.new(1, 0, 0.5, 0),
		Parent = gui,
	})
	Kit.Text({
		Text = "▼",
		TextColor3 = Kit.Theme.Gold,
		Size = UDim2.new(1, 0, 0.5, 0),
		Position = UDim2.fromScale(0, 0.5),
		Parent = gui,
	})
	C.Lang.Changed:Connect(function()
		label.Text = C.Lang.T("YourBase")
	end)
	-- visibile solo da lontano (vicino al lotto non serve)
	task.spawn(function()
		while gui.Parent do
			local char = player.Character
			local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
			gui.Enabled = hrp ~= nil and (hrp.Position - floor.Position).Magnitude > 70
			task.wait(0.5)
		end
	end)
end

---------------------------------------------------------------------------------------------

local function watchTag(tag: string, fn: (Instance) -> ())
	for _, inst in CollectionService:GetTagged(tag) do
		task.spawn(fn, inst)
	end
	CollectionService:GetInstanceAddedSignal(tag):Connect(fn)
end

function World.Start()
	Kit = C.UI.Kit
	watchTag("PetDisplay", function(m)
		task.wait()
		addPet(m :: Model)
	end)
	CollectionService:GetInstanceRemovedSignal("PetDisplay"):Connect(function(m)
		pets[m :: Model] = nil
	end)
	watchTag("IncubatingEgg", function(m)
		task.wait()
		addEgg(m :: Model)
	end)
	CollectionService:GetInstanceRemovedSignal("IncubatingEgg"):Connect(function(m)
		eggs[m :: Model] = nil
	end)
	watchTag("Incubator", function(b)
		incubatorBillboard(b :: BasePart)
	end)
	watchTag("CollectPad", function(p)
		addPad(p :: BasePart)
	end)
	watchTag("LeaderboardBoard", function(b)
		drawBoard(b :: BasePart)
		b:GetAttributeChangedSignal("Data"):Connect(function()
			drawBoard(b :: BasePart)
		end)
	end)
	C.Lang.Changed:Connect(function()
		for _, b in CollectionService:GetTagged("LeaderboardBoard") do
			drawBoard(b)
		end
		for m, a in pets do
			if a.billboard then
				a.billboard:Destroy()
			end
			a.billboard = petBillboard(m)
		end
	end)
	player:GetAttributeChangedSignal("PlotIndex"):Connect(homeMarker)
	task.delay(2, homeMarker)
	C.State.Watch("Settings", function(settings)
		lowGfx = settings and settings.LowGfx == true
		applySmallDecor()
	end)

	local acc = 0
	RunService.RenderStepped:Connect(function(dt)
		acc += dt
		local t = os.clock()
		local cam = workspace.CurrentCamera
		local camPos = cam.CFrame.Position
		local range = if lowGfx then 45 else 90
		-- pet vicini: animazione a ogni fotogramma
		for m, a in pets do
			if not m.Parent then
				pets[m] = nil
			elseif (a.base.Position - camPos).Magnitude < (if a.giant then range * 3.5 else range) then
				animatePet(a, t)
			end
		end
		-- uova in incubazione: tremolio
		for m, e in eggs do
			if not m.Parent then
				eggs[m] = nil
			elseif (e.base.Position - camPos).Magnitude < range then
				local base = m.Parent :: BasePart?
				local readyAt = base and base:GetAttribute("ReadyAt") or 0
				local left = readyAt - workspace:GetServerTimeNow()
				local intensity = if left <= 0 then 1 elseif left < 10 then 0.6 else 0.15
				local s = t * 6 + e.seed
				local wobble =
					CFrame.Angles(math.sin(s * 2.3) * 0.08 * intensity, 0, math.sin(s * 3.1) * 0.12 * intensity)
				local hop = if left <= 0 then math.abs(math.sin(s * 1.5)) * 0.5 else 0
				local root = e.base * CFrame.new(0, hop, 0) * wobble
				for _, p in e.parts do
					p.part.CFrame = root * p.offset
				end
			end
		end
		-- monumento: rotazione lenta
		for _, m in CollectionService:GetTagged("Spinner") do
			if m:IsA("Model") then
				local base = m:GetAttribute("BaseCF")
				if not base then
					m:SetAttribute("BaseCF", m:GetPivot())
					base = m:GetPivot()
				end
				m:PivotTo((base :: CFrame) * CFrame.new(0, math.sin(t) * 0.8, 0) * CFrame.Angles(0, t * 0.4, 0))
			end
		end
		if acc > 0.25 then
			acc = 0
			refreshIncubators()
		end
	end)
	-- pet arcobaleno: colore che scorre
	RunService.Heartbeat:Connect(function()
		local hue = (os.clock() * 0.18) % 1
		for _, m in CollectionService:GetTagged("RainbowPet") do
			local i = 0
			for _, d in (m :: Model):GetDescendants() do
				if d:IsA("BasePart") then
					local role = d:GetAttribute("Role")
					if role == "skin" or role == "detail" or role == "glow" then
						i += 1
						d.Color = Color3.fromHSV((hue + i * 0.07) % 1, 0.65, 1)
					end
				end
			end
		end
	end)
end

return World
