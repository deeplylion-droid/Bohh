-- Tutorial guidato per i nuovi giocatori: un riquadro con l'istruzione del passo attuale, una
-- freccia che rimbalza sopra il bersaglio e una scia luminosa dal personaggio al bersaglio.
-- Passi (data.Tutorial): 1 schiudi, 2 raccogli, 3 potenzia, 4 raccogli un uovo, 5 riportalo, 6 fatto.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)

local Tutorial = {}

local C
local Kit
local player = Players.LocalPlayer
local step = 0
local card: Frame
local cardText: TextLabel
local cardStep: TextLabel
local targetAtt: Attachment
local arrow: BillboardGui
local beams: { Beam } = {}
local hand: TextLabel?

local KEYS = { "Tut_Hatch", "Tut_Collect", "Tut_Upgrade", "Tut_Pickup", "Tut_Deliver" }
local ICONS = { "Egg", "Coin", "Upgrades", "Egg", "Incubator" }
local DONE = 6

function Tutorial.Init(controllers)
	C = controllers
end

local function rootPart(): BasePart?
	local char = player.Character
	return char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
end

local function myPlot(): Model?
	local index = player:GetAttribute("PlotIndex")
	local plots = workspace:FindFirstChild("Plots")
	return if index and plots then plots:FindFirstChild("Plot" .. index) :: Model? else nil
end

---------------------------------------------------------------------------------------------
-- Bersagli dei passi
---------------------------------------------------------------------------------------------
local function incubatorTarget(plot: Model): Vector3?
	local best, bestScore = nil, -1
	for _, inc in CollectionService:GetTagged("Incubator") do
		if inc:IsDescendantOf(plot) and inc:IsA("BasePart") and inc:GetAttribute("EggRarity") then
			local score = if inc:GetAttribute("Ready") then 2 else 1
			if score > bestScore then
				best, bestScore = inc.Position + Vector3.new(0, 4, 0), score
			end
		end
	end
	return best
end

local function padTarget(plot: Model): Vector3?
	for _, ped in CollectionService:GetTagged("Pedestal") do
		if ped:IsDescendantOf(plot) and ped:GetAttribute("PetUid") then
			local pad = ped:FindFirstChild("CollectPad")
			if pad and pad:IsA("BasePart") then
				return pad.Position + Vector3.new(0, 1, 0)
			end
		end
	end
	return nil
end

local function nearestEgg(from: Vector3): Vector3?
	-- solo le uova nei nidi (non quelle in mano ad altri giocatori)
	local nests = workspace:FindFirstChild("Nests", true)
	if not nests then
		return nil
	end
	local best, bestD = nil, math.huge
	for _, egg in CollectionService:GetTagged("Egg") do
		if egg:IsA("Model") and egg:IsDescendantOf(nests) then
			local p = egg:GetPivot().Position
			local d = (p - from).Magnitude
			if d < bestD then
				best, bestD = p + Vector3.new(0, 2, 0), d
			end
		end
	end
	return best
end

local function targetFor(s: number, pos: Vector3): Vector3?
	local plot = myPlot()
	if s == 1 then
		return plot and incubatorTarget(plot)
	elseif s == 2 then
		return plot and padTarget(plot)
	elseif s == 4 then
		-- dalla vetta: prima verso l'inizio del sentiero, poi verso l'uovo piu' vicino
		if MapLayout.ZoneAt(pos) == "Summit" then
			return MapLayout.PathPoint(30) + Vector3.new(0, 3, 0)
		end
		return nearestEgg(pos)
	elseif s == 5 then
		if not plot then
			return nil
		end
		if MapLayout.ZoneAt(pos) ~= "Summit" and pos.Y < 326 then
			return MapLayout.PathPoint(0) + Vector3.new(0, 3, 0)
		end
		return plot:GetPivot().Position + Vector3.new(0, 4, 0)
	end
	return nil
end

---------------------------------------------------------------------------------------------
-- Grafica
---------------------------------------------------------------------------------------------
local function buildCard()
	local New = Kit.New
	card = New("Frame", {
		Name = "Tutorial",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(600, 76),
		Position = UDim2.new(0.5, 0, 1, -124),
		AnchorPoint = Vector2.new(0.5, 1),
		Visible = false,
		Parent = C.UI.Gui("HUD"),
	}, { Kit.Corner(UDim.new(0, 24)), Kit.Stroke(5), Kit.Gradient(Color3.fromRGB(255, 236, 120), Color3.fromRGB(255, 168, 30)), New("UIScale") })
	local badge = New("Frame", {
		BackgroundColor3 = Kit.Theme.Outline,
		Size = UDim2.fromOffset(62, 62),
		Position = UDim2.fromOffset(8, 7),
		Parent = card,
	}, { Kit.Corner(UDim.new(1, 0)) })
	cardStep = Kit.Text({ Text = "1/5", Size = UDim2.fromScale(0.8, 0.5), Position = UDim2.fromScale(0.1, 0.25), TextColor3 = Kit.Theme.Gold, Parent = badge })
	cardText = Kit.Text({
		Text = "",
		Font = Kit.Theme.BodyFont,
		Size = UDim2.new(1, -150, 0, 56),
		Position = UDim2.fromOffset(80, 10),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextWrapped = true,
		Stroke = 3,
		Parent = card,
	})
end

local function setIcon(name: string)
	local old = card:FindFirstChild("StepIcon")
	if old then
		old:Destroy()
	end
	Kit.Icon(name, { Name = "StepIcon", Size = UDim2.fromOffset(50, 50), Position = UDim2.new(1, -62, 0, 13), Parent = card })
end

local function buildPointer()
	targetAtt = Instance.new("Attachment")
	targetAtt.Name = "TutorialTarget"
	targetAtt.Parent = workspace.Terrain
	arrow = Kit.New("BillboardGui", {
		Name = "TutorialArrow",
		Size = UDim2.fromOffset(90, 90),
		AlwaysOnTop = true,
		LightInfluence = 0,
		Enabled = false,
		Adornee = targetAtt,
		Parent = targetAtt,
	})
	Kit.Text({ Text = "▼", TextColor3 = Kit.Theme.Gold, Stroke = 5, Parent = arrow })
	-- due scie: un filo continuo e un flusso di scintille che scorre verso il bersaglio
	local core = Instance.new("Beam")
	core.Name = "TutorialBeam"
	core.Color = ColorSequence.new(Color3.fromRGB(255, 240, 120))
	core.LightEmission = 1
	core.LightInfluence = 0
	core.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.7), NumberSequenceKeypoint.new(0.15, 0.35), NumberSequenceKeypoint.new(1, 0.25) })
	core.Width0 = 0.35
	core.Width1 = 0.35
	core.FaceCamera = true
	core.Segments = 24
	core.Enabled = false
	local sparkle = core:Clone()
	sparkle.Name = "TutorialSparkle"
	sparkle.Texture = "rbxasset://textures/particles/sparkles_main.dds"
	sparkle.TextureMode = Enum.TextureMode.Wrap
	sparkle.TextureLength = 3
	sparkle.TextureSpeed = 1.4
	sparkle.Width0 = 1.8
	sparkle.Width1 = 1.8
	sparkle.Color = ColorSequence.new(Color3.fromRGB(255, 255, 200), Color3.fromRGB(255, 200, 60))
	sparkle.Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1), NumberSequenceKeypoint.new(0.15, 0.2), NumberSequenceKeypoint.new(1, 0) })
	beams = { core, sparkle }
	for _, b in beams do
		b.Attachment1 = targetAtt
		b.Parent = workspace.Terrain
	end
end

local function attachBeams()
	local hrp = rootPart()
	if not hrp then
		return
	end
	local att = hrp:FindFirstChild("TutorialAtt") :: Attachment?
	if not att then
		att = Instance.new("Attachment")
		att.Name = "TutorialAtt"
		att.Position = Vector3.new(0, -1.5, 0)
		att.Parent = hrp
	end
	for _, b in beams do
		b.Attachment0 = att
	end
end

-- Manina che indica il pulsante dei potenziamenti nel menu
local function showHand(on: boolean)
	if on and not hand then
		local hud = C.UI.Gui("HUD")
		local menu = hud and hud:FindFirstChild("Menu")
		local button = menu and menu:FindFirstChild("Upgrades") :: Frame?
		if not button then
			return
		end
		local label = Kit.Text({
			Name = "TutorialHand",
			Text = "👈",
			Font = Enum.Font.SourceSans,
			Stroke = false,
			Size = UDim2.fromOffset(64, 64),
			Position = UDim2.fromOffset(button.Position.X.Offset + 104, button.Position.Y.Offset + 14),
			ZIndex = 20,
			Parent = menu,
		})
		hand = label
		task.spawn(function()
			local x0 = label.Position.X.Offset
			while label.Parent do
				Kit.Tween(label, 0.35, { Position = UDim2.fromOffset(x0 + 14, label.Position.Y.Offset) }, Enum.EasingStyle.Sine)
				task.wait(0.35)
				Kit.Tween(label, 0.35, { Position = UDim2.fromOffset(x0, label.Position.Y.Offset) }, Enum.EasingStyle.Sine)
				task.wait(0.35)
				Kit.Bounce(button, 0.06)
			end
		end)
	elseif not on and hand then
		hand:Destroy()
		hand = nil
	end
end

local function setStep(s: number)
	local previous = step
	step = s
	local active = s >= 1 and s < DONE
	card.Visible = active
	showHand(s == 3)
	if not active then
		arrow.Enabled = false
		for _, b in beams do
			b.Enabled = false
		end
		return
	end
	cardText.Text = C.Lang.T(KEYS[s])
	cardStep.Text = `{s}/5`
	setIcon(ICONS[s])
	Kit.Pop(card)
	if previous > 0 and s > previous then
		C.Audio.Play("Success")
		local hrp = rootPart()
		if hrp then
			C.Effects.Burst(hrp.Position + Vector3.new(0, 3, 0), Color3.fromRGB(255, 225, 77), 24)
		end
	end
end

function Tutorial.Start()
	Kit = C.UI.Kit
	C.State.WaitReady()
	buildCard()
	buildPointer()
	C.State.Watch("Tutorial", function(v)
		setStep(tonumber(v) or 0)
	end)
	C.Lang.Changed:Connect(function()
		if step >= 1 and step < DONE then
			cardText.Text = C.Lang.T(KEYS[step])
		end
	end)
	player.CharacterAdded:Connect(function()
		task.wait(0.5)
		attachBeams()
	end)
	attachBeams()
	-- aggiorna il bersaglio (l'uovo piu' vicino cambia mentre si scende)
	local bounce = 0
	RunService.RenderStepped:Connect(function(dt)
		if arrow.Enabled then
			bounce += dt
			arrow.StudsOffset = Vector3.new(0, 1.5 + math.abs(math.sin(bounce * 4)) * 1.5, 0)
		end
	end)
	while true do
		local hrp = rootPart()
		if step >= 1 and step < DONE and step ~= 3 and hrp then
			local target = targetFor(step, hrp.Position)
			if target then
				targetAtt.WorldPosition = target
				local far = (target - hrp.Position).Magnitude > 9
				arrow.Enabled = true
				for _, b in beams do
					b.Enabled = far
				end
				local a0 = beams[1].Attachment0
				if not a0 or not a0:IsDescendantOf(workspace) then
					attachBeams()
				end
			else
				arrow.Enabled = false
				for _, b in beams do
					b.Enabled = false
				end
			end
		elseif arrow.Enabled then
			arrow.Enabled = false
			for _, b in beams do
				b.Enabled = false
			end
		end
		task.wait(0.2)
	end
end

return Tutorial
