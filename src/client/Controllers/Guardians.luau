-- Mamme guardiane lato client: il server pubblica posizione e direzione (attributi Pos e Look),
-- qui il modello viene spostato con fluidita' e animato (passo ondeggiante, scatto quando e'
-- arrabbiata), con nome, "!" e contorno rosso mentre insegue qualcuno.

local CollectionService = game:GetService("CollectionService")
local Players = game:GetService("Players")
local RunService = game:GetService("RunService")

local Guardians = {}

type Entry = {
	model: Model,
	parts: { BasePart },
	offsets: { CFrame },
	pos: Vector3,
	look: Vector3,
	height: number,
	seed: number,
	highlight: Highlight,
	gui: BillboardGui,
	angry: boolean,
	lastStomp: number,
}

local C
local player = Players.LocalPlayer
local entries: { [Model]: Entry } = {}

function Guardians.Init(controllers)
	C = controllers
end

local function attrVector(model: Model, name: string, default: Vector3): Vector3
	local v = model:GetAttribute(name)
	return if typeof(v) == "Vector3" then v else default
end

local function add(model: Instance)
	if not model:IsA("Model") or entries[model] then
		return
	end
	-- aspetta che le parti siano arrivate dal server
	local deadline = os.clock() + 10
	while #model:GetDescendants() == 0 and os.clock() < deadline do
		task.wait(0.2)
	end
	local pivot = model:GetPivot()
	local parts, offsets = {}, {}
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			table.insert(parts, d)
			table.insert(offsets, pivot:ToObjectSpace(d.CFrame))
		end
	end
	local _, size = model:GetBoundingBox()
	local Kit = C.UI.Kit
	local highlight = Instance.new("Highlight")
	highlight.FillTransparency = 1
	highlight.OutlineColor = Color3.fromRGB(255, 50, 40)
	highlight.OutlineTransparency = 0
	highlight.DepthMode = Enum.HighlightDepthMode.Occluded
	highlight.Enabled = false
	highlight.Adornee = model
	highlight.Parent = model
	local nameKey = "Guardian_" .. tostring(model:GetAttribute("Guardian") or model.Name)
	local gui = Kit.New("BillboardGui", {
		Name = "GuardianInfo",
		Size = UDim2.fromOffset(260, 80),
		StudsOffsetWorldSpace = Vector3.new(0, size.Y + 2, 0),
		MaxDistance = 140,
		LightInfluence = 0,
		Adornee = model.PrimaryPart or parts[1],
		Parent = model,
	})
	local alert = Kit.Text({ Text = "!", TextColor3 = Color3.fromRGB(255, 70, 60), Size = UDim2.new(1, 0, 0.55, 0), Visible = false, Parent = gui })
	local label = Kit.Text({ Text = C.Lang.T(nameKey), TextColor3 = Color3.fromRGB(255, 220, 120), Size = UDim2.new(1, 0, 0.42, 0), Position = UDim2.fromScale(0, 0.58), Parent = gui })
	C.Lang.Changed:Connect(function()
		label.Text = C.Lang.T(nameKey)
	end)
	entries[model] = {
		model = model,
		parts = parts,
		offsets = offsets,
		pos = attrVector(model, "Pos", pivot.Position),
		look = attrVector(model, "Look", Vector3.zAxis),
		height = size.Y,
		seed = math.random() * 10,
		highlight = highlight,
		gui = gui,
		angry = false,
		lastStomp = 0,
	}
	local e = entries[model]
	local function refreshAngry()
		local angry = model:GetAttribute("Angry") == true
		e.angry = angry
		highlight.Enabled = angry
		alert.Visible = angry
	end
	model:GetAttributeChangedSignal("Angry"):Connect(refreshAngry)
	refreshAngry()
end

local function update(dt: number)
	local t = os.clock()
	local hrp = player.Character and player.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
	local cam = workspace.CurrentCamera.CFrame.Position
	local allParts, allCfs = {}, {}
	for model, e in entries do
		if not model.Parent then
			entries[model] = nil
			continue
		end
		local target = attrVector(model, "Pos", e.pos)
		local look = attrVector(model, "Look", e.look)
		local k = 1 - math.exp(-dt * 9)
		local moved = (target - e.pos).Magnitude
		e.pos = e.pos:Lerp(target, k)
		e.look = e.look:Lerp(look, k)
		if (e.pos - cam).Magnitude > 450 then
			continue
		end
		local flatLook = Vector3.new(e.look.X, 0, e.look.Z)
		flatLook = if flatLook.Magnitude > 0.01 then flatLook.Unit else Vector3.zAxis
		-- passo: piu' veloce e ampio quando insegue
		local speed = if e.angry then 13 else 6
		local s = t * speed + e.seed
		local walking = moved > 0.05 or e.angry
		local amp = if walking then 1 else 0.3
		local bob = math.abs(math.sin(s)) * e.height * 0.05 * amp
		local roll = math.sin(s) * math.rad(if e.angry then 7 else 4) * amp
		local breathe = 1 + math.sin(t * 2 + e.seed) * 0.015
		local base = CFrame.lookAt(e.pos, e.pos + flatLook) * CFrame.new(0, bob, 0) * CFrame.Angles(if e.angry then math.rad(-6) else 0, 0, roll)
		for i, part in e.parts do
			local off = e.offsets[i]
			table.insert(allParts, part)
			table.insert(allCfs, base * (off - off.Position) + base:VectorToWorldSpace(off.Position * Vector3.new(1, breathe, 1)))
		end
		-- passi pesanti che fanno tremare la telecamera da vicino
		if e.angry and hrp and math.abs(math.sin(s)) < 0.12 and t - e.lastStomp > 0.25 then
			e.lastStomp = t
			local d = (hrp.Position - e.pos).Magnitude
			if d < 45 then
				C.Effects.CameraShake(0.25 * (1 - d / 45) + 0.05, 0.2)
			end
		end
	end
	if #allParts > 0 then
		workspace:BulkMoveTo(allParts, allCfs, Enum.BulkMoveMode.FireCFrameChanged)
	end
end

function Guardians.Start()
	for _, m in CollectionService:GetTagged("Guardian") do
		task.spawn(add, m)
	end
	CollectionService:GetInstanceAddedSignal("Guardian"):Connect(function(m)
		task.spawn(add, m)
	end)
	RunService.RenderStepped:Connect(update)
end

return Guardians
