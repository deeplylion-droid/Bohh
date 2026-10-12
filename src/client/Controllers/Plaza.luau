-- Piazza della vetta lato client: la ruota della fortuna (premi del giocatore sugli spicchi, giro
-- quando qualcuno la fa girare), la bacheca con le proprie missioni, il re della collina (anello del
-- monumento, cartello con il nome del re, corona sopra la sua testa).

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Assets = require(ReplicatedStorage.Shared.Assets)
local Plaza = require(ReplicatedStorage.Shared.Config.Plaza)

local PlazaController = {}

local C
local Kit
local player = Players.LocalPlayer

function PlazaController.Init(controllers)
	C = controllers
end

---------------------------------------------------------------------------------------------
-- Ruota della fortuna
---------------------------------------------------------------------------------------------
local function setupWheel(wheel: Instance)
	local WheelFace = require(script.Parent.Parent.UI.WheelFace)
	local face = wheel:WaitForChild("WheelFace", 10) :: BasePart?
	local disc = wheel:WaitForChild("WheelDisc", 10) :: BasePart?
	local axle = wheel:GetAttribute("Axle")
	if not face or not disc or typeof(axle) ~= "CFrame" then
		return
	end
	local gui = face:WaitForChild("WheelGui", 10)
	local image = gui and gui:WaitForChild("Face", 10) :: ImageLabel?
	if image then
		local refresh = WheelFace.Build(image, C, 1)
		C.Lang.Changed:Connect(refresh)
		C.State.Watch("Stats", refresh)
		task.spawn(function()
			-- gli importi in monete seguono il guadagno del giocatore
			while wheel.Parent do
				task.wait(5)
				refresh()
			end
		end)
	end
	local faceOffset = axle:ToObjectSpace(face.CFrame)
	local discOffset = axle:ToObjectSpace(disc.CFrame)
	local angle = 0
	local function place(deg: number)
		local rot = axle * CFrame.Angles(0, 0, math.rad(deg))
		face.CFrame = rot * faceOffset
		disc.CFrame = rot * discOffset
	end
	local spinConn: RBXScriptConnection? = nil
	local function onSpin()
		local index = wheel:GetAttribute("SpinIndex")
		local start = wheel:GetAttribute("SpinStart")
		if type(index) ~= "number" or type(start) ~= "number" then
			return
		end
		if spinConn then
			spinConn:Disconnect()
		end
		-- stesso arrivo per tutti i client (lo spostamento dentro lo spicchio dipende dall'ora)
		local jitter = ((start * 7.31) % 1) - 0.5
		local from = angle
		local target = WheelFace.Target(from, index, 4, jitter)
		local duration = Plaza.Wheel.SpinTime - 0.25
		local lastTick = math.floor(from / WheelFace.Step)
		local conn
		conn = RunService.Heartbeat:Connect(function()
			local u = (workspace:GetServerTimeNow() - start) / duration
			angle = from + (target - from) * WheelFace.Ease(u)
			place(angle)
			local tick = math.floor((angle + WheelFace.Step / 2) / WheelFace.Step)
			if tick ~= lastTick then
				lastTick = tick
				C.Audio.Play("Click", face.Position, 0.3)
			end
			if u >= 1 then
				conn:Disconnect()
				angle = target % 360
				place(angle)
				spinConn = nil
			end
		end)
		spinConn = conn
	end
	wheel:GetAttributeChangedSignal("SpinStart"):Connect(onSpin)
	-- la freccia della piazza indica l'ultimo premio estratto (anche per chi entra dopo)
	local last = wheel:GetAttribute("SpinIndex")
	if type(last) == "number" then
		angle = WheelFace.Target(0, last, 0, 0)
		place(angle)
	end
	local promptPart = wheel:FindFirstChild("WheelPromptAnchor")
	local prompt = promptPart and promptPart:FindFirstChildOfClass("ProximityPrompt")
	if prompt then
		prompt.Triggered:Connect(function()
			C.UI.Open("Wheel")
		end)
	end
end

---------------------------------------------------------------------------------------------
-- Bacheca delle missioni: le missioni giornaliere del giocatore con l'avanzamento
---------------------------------------------------------------------------------------------
local function setupBoard(board: Instance)
	local Quests = require(script.Parent.Parent.UI.Panels.Quests)
	local gui = board:WaitForChild("BoardGui", 10)
	if not gui then
		return
	end
	local T = C.Lang.T
	local New = Kit.New
	local Theme = Kit.Theme
	local root = New("Frame", {
		BackgroundTransparency = 1,
		Size = UDim2.fromScale(1, 1),
		Parent = gui,
	}, { Kit.Padding(14) })
	local title = Kit.Text({
		Size = UDim2.new(1, 0, 0, 52),
		TextColor3 = Theme.Gold,
		Stroke = 4,
		Parent = root,
	})
	local rows = {}
	for i = 1, 3 do
		local row = New("Frame", {
			BackgroundColor3 = Theme.Card,
			Size = UDim2.new(1, 0, 0, 52),
			Position = UDim2.fromOffset(0, 58 + (i - 1) * 60),
			Parent = root,
		}, { Kit.Corner(UDim.new(0, 12)), Kit.Stroke(3) })
		local text = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.new(1, -120, 0.7, 0),
			Position = UDim2.new(0, 12, 0.15, 0),
			TextXAlignment = Enum.TextXAlignment.Left,
			Stroke = 2,
			Parent = row,
		})
		local prog = Kit.Text({
			Size = UDim2.new(0, 100, 0.7, 0),
			Position = UDim2.new(1, -110, 0.15, 0),
			TextXAlignment = Enum.TextXAlignment.Right,
			Parent = row,
		})
		rows[i] = { row = row, text = text, prog = prog }
	end
	local footer = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, 0, 0, 30),
		Position = UDim2.new(0, 0, 1, -30),
		TextColor3 = Theme.Muted,
		Stroke = 2,
		Parent = root,
	})
	local function refresh()
		local data = C.State.Data
		local q = data and data.Quests
		title.Text = T("QuestsBoard")
		local claim = Quests.Claimable(data)
		footer.Text = if claim > 0 then T("QuestsBoardClaim", { n = claim }) else T("QuestsBoardHint")
		footer.TextColor3 = if claim > 0 then Theme.Green else Theme.Muted
		for i, r in rows do
			local e = q and q.Daily and q.Daily[i]
			local def = e and Quests.ById[e.Id]
			r.row.Visible = def ~= nil
			if def then
				r.text.Text = T("Quest_" .. def.stat, { n = def.target })
				local done = e.P >= def.target
				r.prog.Text = if e.C then "✔" else `{math.min(e.P, def.target)}/{def.target}`
				r.prog.TextColor3 = if done then Theme.Green else Theme.Text
				r.row.BackgroundColor3 = if e.C then Theme.CardLight else Theme.Card
			end
		end
	end
	C.State.Watch("Quests", refresh)
	C.Lang.Changed:Connect(refresh)
	local anchor = board.Parent and board.Parent:FindFirstChild("QuestPromptAnchor")
	local prompt = anchor and anchor:FindFirstChildOfClass("ProximityPrompt")
	if prompt then
		prompt.Triggered:Connect(function()
			C.UI.Open("Quests")
		end)
	end
end

---------------------------------------------------------------------------------------------
-- Re della collina
---------------------------------------------------------------------------------------------
local crown: BillboardGui? = nil
local crownFx: Instance? = nil

local function crownFor(king: Player?)
	if crown then
		crown:Destroy()
		crown = nil
	end
	if crownFx then
		crownFx:Destroy()
		crownFx = nil
	end
	local char = king and king.Character
	local head = char and (char:FindFirstChild("Head") :: BasePart?)
	if not head then
		return
	end
	local New = Kit.New
	local gui = New("BillboardGui", {
		Name = "KingCrown",
		Size = UDim2.fromScale(4.2, 4.2),
		StudsOffsetWorldSpace = Vector3.new(0, 3.4, 0),
		LightInfluence = 0,
		MaxDistance = 300,
		Adornee = head,
		Parent = player:WaitForChild("PlayerGui"),
	})
	local icon = Kit.Icon("VIP", { Size = UDim2.fromScale(1, 1), Parent = gui })
	local _ = icon
	crown = gui
	local sparkles = Instance.new("Sparkles")
	sparkles.SparkleColor = Color3.fromRGB(255, 215, 80)
	sparkles.Parent = head
	crownFx = sparkles
end

local function setupHill()
	local T = C.Lang.T
	local Theme = Kit.Theme
	local New = Kit.New
	-- cartello sopra il monumento
	local sign: BillboardGui? = nil
	local title, sub
	local anchors = CollectionService:GetTagged("HillSign")
	if anchors[1] then
		sign = New("BillboardGui", {
			Name = "HillSign",
			Size = UDim2.fromScale(20, 6.5),
			LightInfluence = 0,
			MaxDistance = 260,
			Adornee = anchors[1],
			Parent = player:WaitForChild("PlayerGui"),
		})
		New("ImageLabel", {
			BackgroundTransparency = 1,
			Image = Assets.Images.IconKing or "",
			Size = UDim2.fromScale(0.3, 0.92),
			Position = UDim2.fromScale(0.5, 0),
			AnchorPoint = Vector2.new(0.5, 0.62),
			ScaleType = Enum.ScaleType.Fit,
			Parent = sign,
		})
		title = Kit.Text({
			Size = UDim2.fromScale(1, 0.46),
			Position = UDim2.fromScale(0, 0.3),
			TextColor3 = Theme.Gold,
			Stroke = 4,
			Parent = sign,
		})
		sub = Kit.Text({
			Font = Theme.BodyFont,
			Size = UDim2.fromScale(1, 0.3),
			Position = UDim2.fromScale(0, 0.74),
			Stroke = 3,
			Parent = sign,
		})
	end
	local GOLD = Color3.fromRGB(255, 196, 40)
	local RED = Color3.fromRGB(255, 70, 80)
	local IDLE = Color3.fromRGB(150, 128, 96)
	local lastKing = -1
	local function refresh()
		local kingId = workspace:GetAttribute("KingUserId") or 0
		local contested = workspace:GetAttribute("HillContested") == true
		local king = if kingId ~= 0 then Players:GetPlayerByUserId(kingId) else nil
		for _, band in CollectionService:GetTagged("HillBand") do
			if band:IsA("BasePart") then
				band.Color = if contested then RED elseif king then GOLD else IDLE
				band.Material = if king or contested then Enum.Material.Neon else Enum.Material.SmoothPlastic
			end
		end
		if title and sub then
			title.Text = T("KingTitle")
			if contested then
				sub.Text = T("KingContested")
				sub.TextColor3 = RED
			elseif king then
				sub.Text = T("KingIs", { name = king.DisplayName })
				sub.TextColor3 = Theme.Text
			else
				sub.Text = T("KingClimb")
				sub.TextColor3 = Theme.Green
			end
		end
		if kingId ~= lastKing then
			lastKing = kingId
			crownFor(king)
		end
	end
	workspace:GetAttributeChangedSignal("KingUserId"):Connect(refresh)
	workspace:GetAttributeChangedSignal("HillContested"):Connect(refresh)
	C.Lang.Changed:Connect(refresh)
	refresh()
	-- se il re rinasce la corona torna sulla nuova testa
	task.spawn(function()
		while true do
			task.wait(1)
			local kingId = workspace:GetAttribute("KingUserId") or 0
			local king = if kingId ~= 0 then Players:GetPlayerByUserId(kingId) else nil
			local head = king and king.Character and king.Character:FindFirstChild("Head")
			if king and (not crown or crown.Adornee ~= head) then
				crownFor(king)
			end
		end
	end)
	local _ = sign
end

function PlazaController.Start()
	Kit = C.UI.Kit
	C.State.WaitReady()
	local function onWheel(w)
		task.spawn(setupWheel, w)
	end
	for _, w in CollectionService:GetTagged("FortuneWheel") do
		onWheel(w)
	end
	CollectionService:GetInstanceAddedSignal("FortuneWheel"):Connect(onWheel)
	local function onBoard(b)
		task.spawn(setupBoard, b)
	end
	for _, b in CollectionService:GetTagged("QuestBoard") do
		onBoard(b)
	end
	CollectionService:GetInstanceAddedSignal("QuestBoard"):Connect(onBoard)
	-- il cartello del monumento arriva con la mappa
	task.spawn(function()
		local t0 = os.clock()
		while #CollectionService:GetTagged("HillSign") == 0 and os.clock() - t0 < 60 do
			task.wait(1)
		end
		setupHill()
	end)
end

return PlazaController
