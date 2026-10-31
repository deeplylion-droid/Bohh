-- Percorso Estremo lato client: anima gli elementi del percorso col tempo del server (le stesse
-- funzioni di Shared.Extreme usate dal server per i controlli), fa funzionare molle e nastri,
-- segnala al server colpi e cadute e mostra il cronometro della corsa sotto le monete.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")
local TweenService = game:GetService("TweenService")

local Extreme = require(ReplicatedStorage.Shared.Extreme)
local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)

local ExtremeController = {}

type Entry = {
	def: Extreme.Piece,
	part: BasePart?,
	rope: BasePart?,
	stripes: { BasePart },
	emitter: ParticleEmitter?,
	solid: boolean?,
}

local C
local player = Players.LocalPlayer
local entries: { [string]: Entry } = {}
local bySection: { [number]: { Entry } } = {}
local hitEvent: RemoteEvent
local lastReport: { [string]: number } = {}
local lastAnyReport = 0
local lastBounce = 0
local lastWarn = 0
local run: { [string]: any }? = nil
local card: Frame? = nil
local cardTitle: TextLabel? = nil
local cardLine: TextLabel? = nil
local cardBest: TextLabel? = nil
local flash: Frame? = nil

local HAZARD_YELLOW = Color3.fromRGB(255, 210, 0)
local BODY_UP = 2 -- dal centro del HumanoidRootPart alla testa
local RANGE = 520 -- elementi animati solo se la telecamera e' entro questa distanza (in x)

local RESPAWN_STYLE = {
	Water = { color = Color3.fromRGB(80, 190, 255), sound = "GeyserBurst" },
	Sand = { color = Color3.fromRGB(230, 190, 120), sound = "Whoosh" },
	Lava = { color = Color3.fromRGB(255, 90, 30), sound = "Sizzle" },
	Fire = { color = Color3.fromRGB(255, 110, 40), sound = "FireBurst" },
	Zap = { color = Color3.fromRGB(120, 255, 230), sound = "BarrierOff" },
	Laser = { color = Color3.fromRGB(255, 50, 90), sound = "BarrierOff" },
	Crusher = { color = Color3.fromRGB(200, 170, 120), sound = "Bonk" },
	Cheat = { color = Color3.fromRGB(255, 255, 255), sound = "Error" },
}

function ExtremeController.Init(controllers)
	C = controllers
end

---------------------------------------------------------------------------------------------
-- Elementi
---------------------------------------------------------------------------------------------
local function register(inst: Instance)
	if not inst:IsA("BasePart") then
		return
	end
	local id = inst:GetAttribute("Piece")
	local def = if type(id) == "string" then Extreme.Get(id) else nil
	if not def then
		return
	end
	local entry = entries[id]
	if not entry then
		entry = { def = def, part = nil, rope = nil, stripes = {}, emitter = nil, solid = nil }
		entries[id] = entry
		bySection[def.section] = bySection[def.section] or {}
		table.insert(bySection[def.section], entry)
	end
	local part = inst :: BasePart
	if part:GetAttribute("Rope") then
		entry.rope = part
	elseif part:GetAttribute("Stripe") ~= nil then
		table.insert(entry.stripes, part)
	else
		entry.part = part
		entry.emitter = part:FindFirstChildWhichIsA("ParticleEmitter")
	end
end

local function report(id: string)
	local t = os.clock()
	if t - (lastReport[id] or 0) < 0.8 or t - lastAnyReport < 0.25 then
		return
	end
	lastReport[id] = t
	lastAnyReport = t
	hitEvent:FireServer(id)
end

-- Il corpo (da piedi a testa, raggio ~1) tocca il box (cf, size)?
local function bodyInBox(cf: CFrame, size: Vector3, hrpPos: Vector3, margin: number): boolean
	local rel = cf:PointToObjectSpace(hrpPos)
	local h = size / 2
	local feet = rel.Y - Extreme.BodyDown
	local head = rel.Y + BODY_UP
	return math.abs(rel.X) <= h.X + margin and math.abs(rel.Z) <= h.Z + margin and feet < h.Y and head > -h.Y
end

local function updateEntry(e: Entry, t: number, hrp: BasePart?, hrpPos: Vector3?)
	local def = e.def
	local part = e.part
	if not part then
		return
	end
	local kind = def.kind
	if kind == "Mover" then
		local cf, vel = Extreme.MoverState(def, t)
		part.CFrame = cf
		part.AssemblyLinearVelocity = vel
	elseif kind == "Spinner" then
		local cf, w = Extreme.SpinnerState(def, t)
		part.CFrame = cf
		part.AssemblyAngularVelocity = Vector3.new(0, w, 0)
	elseif kind == "Swing" then
		local ang = Extreme.SwingAngle(def, t)
		local cf = def.cframe * CFrame.Angles(ang, 0, 0) * CFrame.new(0, -(def.length or 10), 0)
		part.CFrame = cf
		if e.rope then
			e.rope.CFrame = def.cframe * CFrame.Angles(ang, 0, 0) * CFrame.new(0, -(def.length or 10) / 2, 0)
		end
		if hrpPos and bodyInBox(cf, def.size, hrpPos, 0.9) then
			report(def.id)
		end
	elseif kind == "Sweeper" then
		local cf = Extreme.SweeperState(def, t)
		part.CFrame = cf
		if hrpPos and bodyInBox(cf, def.size, hrpPos, 0.8) then
			report(def.id)
		end
	elseif kind == "Pulse" then
		local phase = Extreme.PulsePhase(def, t)
		local style = def.style
		if style == "Crusher" then
			part.CFrame = Extreme.CrusherCFrame(def, t)
			if phase == "warn" then
				part.CFrame *= CFrame.new((math.random() - 0.5) * 0.3, 0, (math.random() - 0.5) * 0.3)
			end
		elseif style == "Laser" then
			part.Transparency = if phase == "active"
				then 0.1
				elseif phase == "warn" then (if math.sin(t * 40) > 0 then 0.55 else 0.9)
				else 1
		elseif style == "Fire" then
			part.Transparency = if phase == "active" then 0.35 elseif phase == "warn" then 0.86 else 1
			if e.emitter then
				e.emitter.Enabled = phase == "active"
			end
		else
			part.Transparency = if phase == "active" then 0.45 else 1
			if e.emitter then
				e.emitter.Enabled = phase ~= "idle"
				e.emitter.Rate = if phase == "active" then 40 else 8
			end
		end
		if phase == "active" and hrpPos then
			local cf, size = Extreme.PulseBox(def)
			if bodyInBox(cf, size, hrpPos, 0.1) then
				report(def.id)
			end
		end
	elseif kind == "Faller" then
		local solid = Extreme.FallerSolid(def, t)
		local soon = solid and not Extreme.FallerSolid(def, t + 0.6)
		if solid ~= e.solid then
			e.solid = solid
			part.CanCollide = solid
			part.Transparency = if solid then (def.transparency or 0) else 0.8
		end
		if not solid then
			part.CFrame = def.cframe - Vector3.new(0, 1.6, 0)
		elseif soon then
			part.CFrame = def.cframe * CFrame.new((math.random() - 0.5) * 0.24, 0, (math.random() - 0.5) * 0.24)
		else
			part.CFrame = def.cframe
		end
	elseif kind == "Conveyor" then
		local v = def.velocity or Vector3.zero
		part.AssemblyLinearVelocity = v
		local length = def.size.X
		for _, stripe in e.stripes do
			local k = stripe:GetAttribute("Stripe") or 0
			local x = ((k + 0.5) / #e.stripes * length + t * v.X) % length - length / 2
			stripe.CFrame = def.cframe * CFrame.new(x, def.size.Y / 2 + 0.06, 0)
		end
	elseif kind == "Bounce" then
		if hrp and hrpPos and os.clock() - lastBounce > 0.4 then
			local rel = def.cframe:PointToObjectSpace(hrpPos)
			local h = def.size / 2
			local feet = rel.Y - Extreme.BodyDown - h.Y
			if math.abs(rel.X) <= h.X + 0.6 and math.abs(rel.Z) <= h.Z + 0.6 and feet > -0.8 and feet < 1.2 then
				local vel = hrp.AssemblyLinearVelocity
				if vel.Y < 4 then
					lastBounce = os.clock()
					hrp.AssemblyLinearVelocity = Vector3.new(vel.X, def.power or 90, vel.Z)
					C.Audio.Play("Whoosh", hrpPos, 1)
				end
			end
		end
	end
end

local function update()
	local t = workspace:GetServerTimeNow()
	local cam = workspace.CurrentCamera
	local camPos = cam and cam.CFrame.Position or Vector3.zero
	if camPos.X > Extreme.StartX + RANGE or math.abs(camPos.Z - Extreme.Z) > 400 then
		return
	end
	local char = player.Character
	local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
	local hrpPos = hrp and hrp.Position
	local inRun = run ~= nil and hrpPos ~= nil and Extreme.InCourse(hrpPos)
	local sec = Extreme.SectionAt(math.min(camPos.X, Extreme.StartX))
	for s = sec - 1, sec + 1 do
		local list = bySection[s]
		if list then
			for _, e in list do
				updateEntry(e, t, if inRun then hrp else nil, if inRun then hrpPos else nil)
			end
		end
	end
	if inRun and hrpPos and Extreme.InKill(hrpPos - Vector3.new(0, Extreme.BodyDown, 0)) then
		report("Fall")
	end
end

---------------------------------------------------------------------------------------------
-- Cronometro della corsa e lampo quando si rinasce
---------------------------------------------------------------------------------------------
local function buildCard()
	local hud = C.UI.Hud
	if not hud or not hud.TopStack then
		return
	end
	local Kit = C.UI.Kit
	local New = Kit.New
	local frame = New("Frame", {
		Name = "ExtremeRun",
		BackgroundColor3 = Color3.fromRGB(40, 36, 44),
		Size = UDim2.fromOffset(380, 70),
		Visible = false,
		LayoutOrder = 4,
		Parent = hud.TopStack,
	}, {
		Kit.Corner(UDim.new(0, 16)),
		Kit.Stroke(4),
	})
	Kit.Felt(frame)
	Kit.Stitch(frame, 16)
	cardTitle = Kit.Text({
		Size = UDim2.new(1, -24, 0, 30),
		Position = UDim2.fromOffset(14, 6),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = HAZARD_YELLOW,
		ZIndex = 2,
		Parent = frame,
	})
	cardLine = Kit.Text({
		Font = C.UI.Kit.Theme.BodyFont,
		Size = UDim2.new(0.6, -14, 0, 26),
		Position = UDim2.fromOffset(14, 38),
		TextXAlignment = Enum.TextXAlignment.Left,
		TextColor3 = Color3.new(1, 1, 1),
		Stroke = 2,
		ZIndex = 2,
		Parent = frame,
	})
	cardBest = Kit.Text({
		Font = C.UI.Kit.Theme.BodyFont,
		Size = UDim2.new(0.4, -14, 0, 26),
		Position = UDim2.new(0.6, 0, 0, 38),
		TextXAlignment = Enum.TextXAlignment.Right,
		TextColor3 = Color3.fromRGB(200, 255, 120),
		Stroke = 2,
		ZIndex = 2,
		Parent = frame,
	})
	card = frame
	local overlay = C.UI.Gui("Overlay")
	if overlay then
		flash = New("Frame", {
			Name = "ExtremeFlash",
			BackgroundColor3 = Color3.new(1, 1, 1),
			BackgroundTransparency = 1,
			Size = UDim2.fromScale(1, 1),
			ZIndex = 50,
			Parent = overlay,
		})
	end
end

local function refreshCard()
	if not card then
		return
	end
	card.Visible = run ~= nil
	local r = run
	if not r or not cardTitle or not cardLine or not cardBest then
		return
	end
	local T = C.Lang.T
	cardTitle.Text = T("ExtremeHudTitle")
	local elapsed = workspace:GetServerTimeNow() - (r.started or 0)
	local total = #Extreme.Sections
	local section = math.min(total, (r.checkpoint or 0) + 1)
	cardLine.Text = T("ExtremeHudSection", { n = section, total = total }) .. "  ·  " .. Format.Clock(elapsed)
	cardBest.Text = if (r.best or 0) > 0 then T("ExtremeHudBest", { time = Format.Clock(r.best) }) else ""
end

local function flashScreen(color: Color3)
	if not flash then
		return
	end
	flash.BackgroundColor3 = color
	flash.BackgroundTransparency = 0.15
	TweenService:Create(flash, TweenInfo.new(0.6, Enum.EasingStyle.Quad), { BackgroundTransparency = 1 }):Play()
end

---------------------------------------------------------------------------------------------
function ExtremeController.Start()
	hitEvent = Net.Event("ExtremeHit")
	for _, inst in CollectionService:GetTagged("ExtremePiece") do
		register(inst)
	end
	CollectionService:GetInstanceAddedSignal("ExtremePiece"):Connect(register)
	Net.Event("ExtremeRun").OnClientEvent:Connect(function(state)
		local was = run ~= nil
		run = state
		if card and run and not was then
			C.UI.Kit.Pop(card)
		end
		refreshCard()
	end)
	C.Effects.On("ExtremeRespawn", function(params)
		local style = RESPAWN_STYLE[params.kind] or RESPAWN_STYLE.Water
		flashScreen(style.color)
		C.Audio.Play(style.sound)
		C.Effects.CameraShake(0.25, 0.4)
	end)
	C.Effects.On("ExtremeSplash", function(params)
		local style = RESPAWN_STYLE[params.kind] or RESPAWN_STYLE.Water
		if params.position then
			C.Effects.Burst(params.position, style.color, 20, nil, 16, 2.4)
		end
	end)
	C.Effects.On("ExtremeCheckpoint", function(params)
		C.Audio.Play("Success")
		flashScreen(Color3.fromRGB(200, 255, 120))
		for _, beam in CollectionService:GetTagged("ExtremeCheckpoint") do
			if beam:IsA("BasePart") and beam:GetAttribute("Checkpoint") == params.n then
				local base = beam.Size
				beam.Size = base * Vector3.new(1, 3, 1)
				TweenService:Create(beam, TweenInfo.new(0.8, Enum.EasingStyle.Back), { Size = base }):Play()
			end
		end
	end)
	C.Effects.On("ExtremeComplete", function(params)
		if params.userId == player.UserId then
			C.Audio.Play("Fanfare")
		end
	end)
	C.Effects.On("ExtremePortal", function()
		C.Audio.Play("Whoosh")
		flashScreen(Color3.fromRGB(160, 120, 255))
	end)
	task.spawn(function()
		C.State.WaitReady()
		while not (C.UI.Hud and C.UI.Hud.TopStack) do
			task.wait(0.5)
		end
		buildCard()
		while true do
			if run then
				refreshCard()
			end
			task.wait(0.25)
		end
	end)
	RunService.PreSimulation:Connect(function()
		local ok, err = pcall(update)
		if not ok and os.clock() - lastWarn > 5 then
			lastWarn = os.clock()
			warn("[Extreme] " .. tostring(err))
		end
	end)
end

return ExtremeController
