-- Mamme guardiane delle tane (Grotte di cristallo e Cratere): girano attorno ai nidi preziosi e
-- inseguono chi porta via le loro uova finche' resta nel loro territorio. Se ti prendono, ti
-- sbalzano e l'uovo cade a terra.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Visuals = require(ReplicatedStorage.Shared.Visuals)

local GuardianService = {}

type Guardian = {
	lair: any,
	model: Model,
	pos: Vector3,
	facing: Vector3,
	target: Player?,
	chaseUntil: number,
	cooldown: number,
	wanderTo: Vector3,
	sent: number,
}

local S
local guardians: { [string]: Guardian } = {}
local rng = Random.new()

local IDLE_SPEED = 7
local CHASE_SPEED = 21
local HIT_RANGE = 7.5

function GuardianService.Init(services)
	S = services
end

local function groundY(p: Vector3): number
	return S.MapService.HeightAt(p.X, p.Z)
end

local function spawnGuardian(lair)
	-- modello dedicato se esiste, altrimenti il pet della zona in versione gigante
	local model = S.AssetService.Clone("Props", lair.guardian)
	if not model then
		model = Visuals.MakePet(if lair.id == "Crater" then "LavaDragon" else "CrystalTurtle", "None", "Normal")
		model:ScaleTo(model:GetScale() * 3.2)
	end
	model.Name = lair.guardian
	for _, d in model:GetDescendants() do
		if d:IsA("BasePart") then
			d.Anchored = true
			d.CanCollide = false
			d.CanQuery = false
		end
	end
	local pos = Vector3.new(lair.center.X, groundY(lair.center), lair.center.Z)
	model:PivotTo(CFrame.new(pos))
	model:SetAttribute("Lair", lair.id)
	model:SetAttribute("Guardian", lair.guardian)
	model:SetAttribute("Pos", pos)
	model:SetAttribute("Look", Vector3.zAxis)
	model.Parent = workspace:FindFirstChild("Map")
	game:GetService("CollectionService"):AddTag(model, "Guardian")
	guardians[lair.id] = { lair = lair, model = model, pos = pos, facing = Vector3.zAxis, target = nil, chaseUntil = 0, cooldown = 0, wanderTo = pos, sent = 0 }
end

-- Chiamata quando qualcuno prende un uovo da una tana
function GuardianService.EggTaken(lairId: string, player: Player)
	local g = guardians[lairId]
	if g then
		g.target = player
		g.chaseUntil = os.clock() + 14
		g.model:SetAttribute("Angry", true)
		S.StateService.Effect(nil, "GuardianRoar", { position = g.pos, lair = lairId })
	end
end

local function carriesLairEgg(player: Player, lairId: string): boolean
	for _, item in S.CarryService.Items(player) do
		if item.egg and item.egg.nestId and string.sub(item.egg.nestId, 1, #lairId + 4) == lairId .. "Lair" then
			return true
		end
	end
	return false
end

local function step(g: Guardian, dt: number)
	local now = os.clock()
	local lair = g.lair
	local center = Vector3.new(lair.center.X, g.pos.Y, lair.center.Z)
	local goal: Vector3
	local speed = IDLE_SPEED
	-- chi porta un uovo della tana dentro il territorio diventa il bersaglio
	if not g.target then
		for _, p in Players:GetPlayers() do
			local hrp = S.CharacterService.Root(p)
			if hrp and (hrp.Position - center).Magnitude < lair.leash and carriesLairEgg(p, lair.id) then
				g.target = p
				g.chaseUntil = now + 14
				g.model:SetAttribute("Angry", true)
			end
		end
	end
	local target = g.target
	local thrp = target and S.CharacterService.Root(target)
	if target and thrp and now < g.chaseUntil and (thrp.Position - center).Magnitude < lair.leash and S.CarryService.Count(target) > 0 then
		goal = thrp.Position
		speed = CHASE_SPEED
		if now > g.cooldown and (Vector3.new(thrp.Position.X - g.pos.X, 0, thrp.Position.Z - g.pos.Z)).Magnitude < HIT_RANGE then
			g.cooldown = now + 2
			local dir = (thrp.Position - g.pos) * Vector3.new(1, 0, 1)
			dir = if dir.Magnitude > 0.1 then dir.Unit else Vector3.xAxis
			S.CarryService.DropAll(target, "Guardian")
			S.RagdollService.Ragdoll(target, 1.6, dir * 70 + Vector3.new(0, 55, 0))
			S.StateService.Notify(target, "GuardianHit", nil, "Bad")
			S.StateService.Effect(nil, "GuardianSlam", { position = g.pos + dir * 4 })
			g.target = nil
			g.model:SetAttribute("Angry", false)
		end
	else
		if g.target then
			g.target = nil
			g.model:SetAttribute("Angry", false)
		end
		if (g.wanderTo - g.pos).Magnitude < 3 or (g.wanderTo - center).Magnitude > lair.radius then
			local a, r = rng:NextNumber(0, math.pi * 2), rng:NextNumber(0, lair.radius * 0.8)
			g.wanderTo = center + Vector3.new(math.cos(a) * r, 0, math.sin(a) * r)
		end
		goal = g.wanderTo
	end
	local delta = Vector3.new(goal.X - g.pos.X, 0, goal.Z - g.pos.Z)
	if delta.Magnitude > 0.5 then
		local move = delta.Unit * math.min(delta.Magnitude, speed * dt)
		local nextPos = g.pos + move
		-- non esce troppo dal territorio
		if (Vector3.new(nextPos.X, 0, nextPos.Z) - Vector3.new(center.X, 0, center.Z)).Magnitude < lair.leash then
			g.pos = Vector3.new(nextPos.X, groundY(nextPos), nextPos.Z)
		end
		g.facing = g.facing:Lerp(delta.Unit, math.min(1, dt * 6))
	end
	-- i client disegnano e animano la guardiana partendo da questi attributi (10 volte al secondo):
	-- le parti restano ferme sul server, cosi' non si replicano 60 CFrame al secondo
	if now - g.sent >= 0.1 then
		g.sent = now
		local look = if g.facing.Magnitude > 0.01 then g.facing.Unit else Vector3.zAxis
		g.model:SetAttribute("Pos", g.pos)
		g.model:SetAttribute("Look", look)
	end
end

function GuardianService.Start()
	S.MapService.WaitReady()
	for _, lair in MapLayout.Lairs do
		spawnGuardian(lair)
	end
	RunService.Heartbeat:Connect(function(dt)
		for _, g in guardians do
			step(g, dt)
		end
	end)
end

return GuardianService
