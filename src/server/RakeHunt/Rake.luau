-- The Rake: creatura controllata dal server con una macchina a stati.
-- Inattiva -> Curiosa -> Territoriale -> Aggressiva in base all'aggressività, che cresce con la notte,
-- il rumore, le luci lontane e i giocatori isolati. Più gli stati speciali Fuga e Stordita.
local PathfindingService = game:GetService("PathfindingService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Shared = ReplicatedStorage:WaitForChild("Shared")
local Config = require(Shared:WaitForChild("Config"))
local RakeRig = require(Shared:WaitForChild("RakeRig"))
local Sfx = require(Shared:WaitForChild("Sfx"))
local Forest = require(script.Parent.Forest)

local R = Config.RAKE

local Rake = {}
Rake.model = nil :: Model?

local ctx
local rng = Random.new()
local hum: Humanoid, root: BasePart, head: BasePart
local highlight: Highlight, capturePrompt: ProximityPrompt
local footsteps: Sound?, callSound: Sound?, screechSound: Sound?
local brain: { [string]: any } = {}
local rig
local jawSound: Sound?, growlSound: Sound?
local revealed = false
local loopToken = nil

local function flat(v: Vector3): Vector3
	return Vector3.new(v.X, 0, v.Z)
end

local function setState(name: string)
	if brain.state ~= name then
		brain.state = name
		ctx.state:SetAttribute("RakeState", name)
	end
end

---------------------------------------------------------------------------------------------
-- Modello

local function build(pos: Vector3): Model
	local m = Instance.new("Model")
	m.Name = "TheRake"
	rig = RakeRig.build(m, CFrame.new(pos + Vector3.new(0, RakeRig.ROOT_HEIGHT, 0)))
	root = rig.root
	head = rig.head

	hum = Instance.new("Humanoid")
	hum.RigType = Enum.HumanoidRigType.R15
	hum.HipHeight = RakeRig.HIP_HEIGHT
	hum.MaxHealth = 1e6
	hum.Health = 1e6
	hum.WalkSpeed = R.WALK_SPEED
	hum.UseJumpPower = true
	hum.JumpPower = 0
	hum.AutoJumpEnabled = false
	hum.BreakJointsOnDeath = false
	hum.RequiresNeck = false
	hum.DisplayDistanceType = Enum.HumanoidDisplayDistanceType.None
	hum.HealthDisplayType = Enum.HumanoidHealthDisplayType.AlwaysOff
	hum.Parent = m

	highlight = Instance.new("Highlight")
	highlight.Enabled = false
	highlight.FillTransparency = 0.7
	highlight.FillColor = Color3.fromRGB(255, 60, 60)
	highlight.OutlineColor = Color3.fromRGB(255, 80, 80)
	highlight.DepthMode = Enum.HighlightDepthMode.AlwaysOnTop
	highlight.Parent = m

	capturePrompt = Instance.new("ProximityPrompt")
	capturePrompt.ActionText = "Cattura"
	capturePrompt.ObjectText = "The Rake (stordito)"
	capturePrompt.HoldDuration = R.CAPTURE_TIME
	capturePrompt.MaxActivationDistance = 12
	capturePrompt.RequiresLineOfSight = false
	capturePrompt.Enabled = false
	capturePrompt.Parent = root

	footsteps = Sfx.new("Steps", root, { Volume = 1.2, RollOffMaxDistance = 110, PlaybackSpeed = 0.8 })
	callSound = Sfx.new("Call", head, { Volume = 2.2, RollOffMinDistance = 12, RollOffMaxDistance = 320 })
	screechSound = Sfx.new("Screech", head, { Volume = 2.5, RollOffMinDistance = 10, RollOffMaxDistance = 220 })
	jawSound = Sfx.new("JawClicks", head, { Volume = 1.8, RollOffMinDistance = 6, RollOffMaxDistance = 90 })
	growlSound = Sfx.new("Growl", head, { Volume = 2, RollOffMinDistance = 8, RollOffMaxDistance = 130 })
	return m
end

---------------------------------------------------------------------------------------------
-- Movimento con pathfinding

local function computePath(dest: Vector3)
	local path = PathfindingService:CreatePath({
		AgentRadius = 2.5,
		AgentHeight = 7,
		AgentCanJump = false,
		WaypointSpacing = 6,
	})
	local ok = pcall(function()
		path:ComputeAsync(root.Position, dest)
	end)
	if ok and path.Status == Enum.PathStatus.Success then
		brain.path = path:GetWaypoints()
		brain.pathIndex = 2
	else
		brain.path = nil
	end
	brain.pathGoal = dest
	brain.pathTime = os.clock()
end

local function moveTo(dest: Vector3, speed: number)
	hum.WalkSpeed = speed
	if not brain.pathGoal or flat(brain.pathGoal - dest).Magnitude > 10 or os.clock() - brain.pathTime > 2 then
		computePath(dest)
	end
	local waypoints = brain.path
	if waypoints and waypoints[brain.pathIndex] then
		local wp = waypoints[brain.pathIndex].Position
		if flat(wp - root.Position).Magnitude < 4 then
			brain.pathIndex += 1
			local nextWp = waypoints[brain.pathIndex]
			if nextWp then
				hum:MoveTo(nextWp.Position)
			end
		else
			hum:MoveTo(wp)
		end
	else
		hum:MoveTo(dest)
	end
end

-- Fuori dall'area della stazione, salvo quando è Aggressiva
local function avoidStation(goal: Vector3): Vector3
	if brain.state ~= "Aggressiva" and Forest.inStation(goal, 12) then
		local away = flat(goal - Forest.STATION)
		if away.Magnitude < 1 then
			away = Vector3.new(1, 0, 0)
		end
		return Forest.STATION + away.Unit * (Config.MAP.STATION_RADIUS + 18)
	end
	return goal
end

---------------------------------------------------------------------------------------------
-- Percezione

local function visibleFrom(origin: Vector3, ignore: { Instance }): boolean
	if not Rake.model then
		return false
	end
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = ignore
	for _, target in { head.Position, root.Position } do
		local result = workspace:Raycast(origin, target - origin, params)
		if not result or result.Instance:IsDescendantOf(Rake.model) then
			return true
		end
	end
	return false
end

function Rake.visibleFrom(origin: Vector3, ignore: { Instance }): boolean
	return visibleFrom(origin, ignore)
end

function Rake.position(): Vector3?
	if Rake.model and root and root.Parent then
		return root.Position
	end
	return nil
end

-- Il giocatore più "appetibile": isolato, lontano dalla stazione, con il nastro o una luce accesa
local function pickTarget(survivors)
	local best, bestScore = nil, -math.huge
	for _, s in survivors do
		local iso = 150
		for _, other in survivors do
			if other ~= s then
				iso = math.min(iso, (other.root.Position - s.root.Position).Magnitude)
			end
		end
		local score = iso - (s.root.Position - root.Position).Magnitude * 0.3
		if s.player:GetAttribute("CarryingTape") then
			score += 60
		end
		if s.player:GetAttribute("TorchOn") then
			score += 10
		end
		if Forest.inStation(s.root.Position) and brain.state ~= "Aggressiva" then
			score -= 200
		end
		s.isolation = iso
		if score > bestScore then
			best, bestScore = s, score
		end
	end
	return best
end

local function flee(from: Vector3, duration: number)
	brain.fleeUntil = os.clock() + duration
	brain.fleeFrom = from
	brain.goal = nil
end

local function playSound(s: Sound?)
	if s then
		s:Play()
	end
end

-- Verso finto da un'altra direzione per depistare la squadra
local function fakeCall()
	Sfx.at("Call", Forest.randomGround(rng, root.Position, 80, 140) + Vector3.new(0, 5, 0), {
		Volume = 2.2,
		RollOffMinDistance = 12,
		RollOffMaxDistance = 320,
	})
end

local function updateLight(dt: number, survivors)
	local exposedBy = nil
	for _, s in survivors do
		if s.player:GetAttribute("TorchOn") and s.head then
			local toRake = root.Position - s.head.Position
			local d = toRake.Magnitude
			if d < R.LIGHT_RANGE and d > 0.1 then
				local look = s.root.CFrame.LookVector
				local angle = math.deg(math.acos(math.clamp(look:Dot(toRake.Unit), -1, 1)))
				if angle < R.LIGHT_ANGLE and visibleFrom(s.head.Position, { s.char }) then
					exposedBy = s
					break
				end
			end
		end
	end
	if exposedBy then
		brain.light += dt
		if brain.light >= R.LIGHT_TO_FLEE then
			brain.light = 0
			brain.aggression = math.max(0, brain.aggression - 12)
			flee(exposedBy.root.Position, R.FLEE_TIME)
			ctx.notify("🔦 La luce l'ha respinto! Ma tornerà…", exposedBy.player)
		end
	else
		brain.light = math.max(0, brain.light - dt * 0.5)
	end
end

---------------------------------------------------------------------------------------------
-- Stordimento e cattura

local function knockout()
	brain.knockedUntil = os.clock() + R.KNOCKOUT_TIME
	hum.WalkSpeed = 0
	hum:MoveTo(root.Position)
	hum.PlatformStand = true
	capturePrompt.Enabled = true
	highlight.FillColor = Color3.fromRGB(255, 255, 255)
	highlight.OutlineColor = Color3.fromRGB(255, 255, 255)
	highlight.Enabled = true
	if footsteps then
		footsteps:Stop()
	end
	setState("Stordita")
	ctx.notifyAll(("💤 The Rake è a terra! Catturalo (tieni premuto E) entro %d secondi."):format(R.KNOCKOUT_TIME))
end

local function wake()
	brain.knockedUntil = 0
	brain.sedation = 1
	brain.aggression = 90
	hum.PlatformStand = false
	hum:ChangeState(Enum.HumanoidStateType.GettingUp)
	capturePrompt.Enabled = false
	highlight.FillColor = Color3.fromRGB(255, 60, 60)
	highlight.OutlineColor = Color3.fromRGB(255, 80, 80)
	highlight.Enabled = revealed
	ctx.notifyAll("⚠ The Rake si è risvegliato… ed è furioso!")
	playSound(screechSound)
end

function Rake.hitByDart(player: Player)
	if not Rake.model or brain.knockedUntil > 0 or brain.captured then
		return
	end
	brain.sedation += 1
	if brain.sedation >= R.DARTS_TO_KNOCKOUT then
		knockout()
	else
		brain.aggression = math.min(100, brain.aggression + 6)
		brain.staggerUntil = os.clock() + 0.7
		ctx.notify(("🎯 Dardo a segno! Sedazione %d/%d"):format(math.floor(brain.sedation), R.DARTS_TO_KNOCKOUT), player)
	end
end

function Rake.addAggression(amount: number)
	if brain.aggression then
		brain.aggression = math.clamp(brain.aggression + amount, 0, 100)
	end
end

function Rake.setRevealed(on: boolean)
	revealed = on
	if highlight and brain.knockedUntil == 0 then
		highlight.Enabled = on
	end
end

---------------------------------------------------------------------------------------------
-- Cervello

local function step(dt: number)
	local now = os.clock()
	local b = brain
	if b.captured then
		return
	end
	if b.knockedUntil > 0 then
		if now < b.knockedUntil then
			return
		end
		wake()
	end

	local survivors = ctx.team.standing()
	updateLight(dt, survivors)
	b.sedation = math.max(0, b.sedation - R.SEDATION_DECAY * dt)

	-- Aggressività: tempo, rumore, luci lontane, giocatori isolati
	local gain = R.AGGRESSION_PER_SECOND * (1 + ctx.nightProgress * 1.5) * ctx.aggressionMultiplier
	local target = pickTarget(survivors)
	for _, s in survivors do
		local d = (s.root.Position - root.Position).Magnitude
		if d < 140 then
			if s.root.AssemblyLinearVelocity.Magnitude > Config.PLAYER.WALK_SPEED + 3 then
				gain += 0.25
			end
			if s.player:GetAttribute("TorchOn") and d > R.LIGHT_RANGE then
				gain += 0.1
			end
		end
		if s.isolation and s.isolation > 60 then
			gain += 0.15
		end
	end
	b.aggression = math.clamp(b.aggression + gain * dt, 0, 100)

	local T = R.THRESHOLDS
	if now < b.fleeUntil then
		setState("Fuga")
	elseif not target then
		setState("Inattiva")
	elseif b.aggression >= T.Aggressiva then
		setState("Aggressiva")
	elseif b.aggression >= T.Territoriale then
		setState("Territoriale")
	elseif b.aggression >= T.Curiosa then
		setState("Curiosa")
	else
		setState("Inattiva")
	end

	if now < b.staggerUntil then
		hum.WalkSpeed = 0
		return
	end

	local state = b.state
	local goalReached = b.goal and flat(b.goal - root.Position).Magnitude < 6
	if state == "Fuga" then
		if not b.goal or goalReached then
			local away = flat(root.Position - (b.fleeFrom or root.Position))
			if away.Magnitude < 1 then
				away = Vector3.new(rng:NextNumber(-1, 1), 0, rng:NextNumber(-1, 1))
			end
			b.goal = Forest.clampToMap(root.Position + away.Unit * 110)
		end
		moveTo(b.goal, R.CHASE_SPEED)
	elseif state == "Inattiva" then
		if not b.goal or goalReached or now - b.goalTime > 25 then
			b.goal = Forest.randomGround(rng, b.lair, 0, 120)
			b.goalTime = now
		end
		moveTo(avoidStation(b.goal), R.WALK_SPEED)
	elseif state == "Curiosa" then
		-- Pedina il bersaglio restando a distanza, nascosto tra gli alberi
		local t = target.root.Position
		b.orbit += dt * 0.05
		local dir = flat(root.Position - t)
		if dir.Magnitude < 1 then
			dir = Vector3.new(1, 0, 0)
		end
		dir = (CFrame.Angles(0, math.sin(b.orbit) * 0.6, 0) * dir.Unit)
		b.goal = avoidStation(Forest.clampToMap(t + dir * 55))
		local d = flat(t - root.Position).Magnitude
		moveTo(b.goal, d < 45 and R.STALK_SPEED or R.WALK_SPEED)
	elseif state == "Territoriale" then
		-- Gira intorno al bersaglio e ogni tanto finge una carica
		local t = target.root.Position
		local d = flat(t - root.Position).Magnitude
		if now < b.bluffUntil then
			moveTo(t, R.CHASE_SPEED)
			if d < 14 then
				b.bluffUntil = 0
				b.orbit += math.pi
			end
		else
			b.orbit += dt * 0.25
			b.goal = avoidStation(Forest.clampToMap(t + Vector3.new(math.cos(b.orbit), 0, math.sin(b.orbit)) * 30))
			moveTo(b.goal, R.STALK_SPEED)
			if now > b.nextBluff then
				b.nextBluff = now + rng:NextNumber(15, 35)
				b.bluffUntil = now + 4
				playSound(callSound)
			end
		end
	elseif state == "Aggressiva" then
		if b.lastGrowl == nil or now - b.lastGrowl > 12 then
			b.lastGrowl = now
			playSound(growlSound)
		end
		local t = target.root.Position
		moveTo(t, R.CHASE_SPEED)
		if (t - root.Position).Magnitude < R.ATTACK_RANGE and now - b.lastAttack > R.ATTACK_COOLDOWN then
			b.lastAttack = now
			playSound(screechSound)
			ctx.team.down(target.player)
			b.aggression = 40
			flee(t, R.FLEE_TIME * 1.5)
		end
	end

	-- Tracce lasciate lungo il percorso e versi (a volte finti)
	if state ~= "Fuga" and now - b.lastDrop > Config.EVIDENCE.DROP_INTERVAL then
		b.lastDrop = now
		ctx.evidence.dropNear(root.Position)
	end
	if state ~= "Inattiva" and now > b.nextCall then
		b.nextCall = now + rng:NextNumber(18, 40)
		local roll = rng:NextNumber()
		if roll < 0.25 then
			fakeCall()
		elseif roll < 0.5 then
			playSound(callSound)
		elseif roll < 0.8 then
			playSound(jawSound)
		else
			playSound(growlSound)
		end
	end

	if footsteps then
		local moving = root.AssemblyLinearVelocity.Magnitude > 2
		if moving and not footsteps.IsPlaying then
			footsteps:Play()
		elseif not moving and footsteps.IsPlaying then
			footsteps:Stop()
		end
		footsteps.PlaybackSpeed = hum.WalkSpeed > R.STALK_SPEED and 1.25 or 0.8
	end
end

---------------------------------------------------------------------------------------------

function Rake.init(c)
	ctx = c
end

function Rake.spawn(lair: Vector3)
	Rake.despawn()
	local now = os.clock()
	brain = {
		state = "",
		aggression = 10,
		sedation = 0,
		light = 0,
		fleeUntil = 0,
		fleeFrom = nil,
		knockedUntil = 0,
		staggerUntil = 0,
		lastAttack = 0,
		bluffUntil = 0,
		nextBluff = now + 20,
		goal = nil,
		goalTime = 0,
		orbit = rng:NextNumber(0, math.pi * 2),
		lair = lair,
		lastDrop = now,
		nextCall = now + 30,
		captured = false,
		path = nil,
		pathIndex = 0,
		pathGoal = nil,
		pathTime = 0,
	}
	revealed = false
	local m = build(lair)
	m.Parent = ctx.world
	root:SetNetworkOwner(nil)
	Rake.model = m
	setState("Inattiva")

	capturePrompt.Triggered:Connect(function(player)
		if brain.knockedUntil > 0 and not brain.captured and ctx.team.isStanding(player) then
			brain.captured = true
			capturePrompt.Enabled = false
			root.Anchored = true
			setState("Catturata")
			ctx.onCapture(player)
		end
	end)

	local token = {}
	loopToken = token
	task.spawn(function()
		local last = os.clock()
		while loopToken == token and m.Parent do
			task.wait(0.2)
			local now = os.clock()
			local ok, err = pcall(step, now - last)
			if not ok then
				warn("[TheRake] " .. tostring(err))
			end
			last = now
		end
	end)
end

function Rake.despawn()
	loopToken = nil
	if Rake.model then
		Rake.model:Destroy()
		Rake.model = nil
	end
end

return Rake
