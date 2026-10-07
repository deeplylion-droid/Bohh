-- The Rake: creatura controllata dal server. Comportamento elusivo "colpisci e scappa":
--   Vaga      → gira intorno alla tana finché non trova qualcuno
--   Pedina    → segue il bersaglio alle spalle, fuori dalla sua vista, nascosto dietro gli alberi
--   Mostra    → compare davanti al bersaglio, resta immobile a fissarlo, poi sparisce
--   Carica    → scatta (più veloce di chi corre) verso dove il bersaglio sta andando, colpisce
--   Finta     → carica e si ferma a pochi metri urlando, poi scappa
--   Attacco   → resta sopra la vittima un istante (jumpscare), poi fugge
--   Fuga      → corre lontano, fuori vista, e torna a pedinare
-- Teme la luce diretta, sente spari e corse, scappa quando viene colpito da un dardo.
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
local footsteps: Sound?, callSound: Sound?, screechSound: Sound?, jawSound: Sound?, growlSound: Sound?
local brain: { [string]: any } = {}
local revealed = false
local loopToken = nil

-- Stato pubblicato per HUD e animazione dei client
local MODE_STATE = {
	Vaga = "Inattiva",
	Pedina = "Curiosa",
	Mostra = "Territoriale",
	Carica = "Aggressiva",
	Finta = "Aggressiva",
	Attacco = "Attacco",
	Fuga = "Fuga",
}

local function flat(v: Vector3): Vector3
	return Vector3.new(v.X, 0, v.Z)
end

local function range(pair: { number }): number
	return rng:NextNumber(pair[1], pair[2])
end

local function setState(name: string)
	if brain.state ~= name then
		brain.state = name
		ctx.state:SetAttribute("RakeState", name)
	end
end

local function setMode(mode: string, duration: number?)
	brain.mode = mode
	brain.modeStart = os.clock()
	brain.modeUntil = duration and os.clock() + duration or math.huge
	brain.goal = nil
	brain.seenTime = 0
	brain.standing = false
	if hum then
		hum.AutoRotate = true
	end
	setState(MODE_STATE[mode] or "Inattiva")
end

local function playSound(s: Sound?)
	if s then
		s:Play()
	end
end

---------------------------------------------------------------------------------------------
-- Modello

local function build(pos: Vector3): Model
	local m = Instance.new("Model")
	m.Name = "TheRake"
	local rig = RakeRig.build(m, CFrame.new(pos + Vector3.new(0, RakeRig.ROOT_HEIGHT, 0)))
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
-- Movimento

-- Zone sicure: la Ranger Station e tutti i luoghi chiave della mappa sono vietati alla creatura.
-- Restituisce il luogo che contiene p (con margine) e il raggio della sua zona.
local function safeZoneAt(p: Vector3, extra: number): (any, number)
	for i, poi in Forest.POIS do
		local r = (i == 1 and math.max(Config.MAP.STATION_RADIUS, poi.radius) or poi.radius) + extra
		if flat(p - poi.pos).Magnitude < r then
			return poi, r
		end
	end
	return nil, 0
end

-- Sposta un punto fuori da ogni zona sicura (sul bordo, nella direzione da cui arriva)
local function keepOut(p: Vector3, extra: number?): Vector3
	local margin = extra or 6
	local moved = false
	for _ = 1, 4 do
		local poi, r = safeZoneAt(p, margin)
		if not poi then
			break
		end
		local away = flat(p - poi.pos)
		if away.Magnitude < 1 then
			away = flat(root.Position - poi.pos)
			if away.Magnitude < 1 then
				away = Vector3.new(1, 0, 0)
			end
		end
		p = poi.pos + away.Unit * (r + 0.5)
		moved = true
	end
	return moved and Forest.groundAt(p.X, p.Z) or p
end

-- I tratti di percorso che attraversano un luogo sicuro diventano un arco lungo il suo bordo
local function detour(points: { Vector3 }): { Vector3 }
	local out = {}
	local i = 1
	while i <= #points do
		local poi, r = safeZoneAt(points[i], 2)
		if not poi then
			table.insert(out, points[i])
			i += 1
		else
			local j = i
			while j < #points and safeZoneAt(points[j + 1], 2) == poi do
				j += 1
			end
			local entry = points[i - 1] or root.Position
			local exit = points[j + 1] or points[j]
			local c = poi.pos
			local radius = r + 3
			local a0 = math.atan2(entry.Z - c.Z, entry.X - c.X)
			local d = math.atan2(exit.Z - c.Z, exit.X - c.X) - a0
			d = (d + math.pi) % (2 * math.pi) - math.pi
			local n = math.max(1, math.ceil(math.abs(d) * radius / 6))
			for k = 0, n do
				local a = a0 + d * k / n
				table.insert(out, Forest.groundAt(c.X + math.cos(a) * radius, c.Z + math.sin(a) * radius))
			end
			i = j + 1
		end
	end
	return out
end
Rake._detour = detour

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
		local points = {}
		for _, w in path:GetWaypoints() do
			table.insert(points, w.Position)
		end
		brain.path = {}
		for _, p in detour(points) do
			table.insert(brain.path, { Position = p })
		end
		brain.pathIndex = 2
	else
		brain.path = nil
	end
	brain.pathGoal = dest
	brain.pathTime = os.clock()
end

local function moveTo(dest: Vector3, speed: number, direct: boolean?)
	dest = keepOut(dest)
	hum.WalkSpeed = speed
	if direct then
		brain.path = nil
		hum:MoveTo(dest)
		return
	end
	local refresh = speed >= R.CHASE_SPEED and 1 or 2
	if not brain.pathGoal or flat(brain.pathGoal - dest).Magnitude > 8 or os.clock() - brain.pathTime > refresh then
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

local function stop()
	hum.WalkSpeed = 0
	hum:MoveTo(root.Position)
end

local function face(pos: Vector3)
	hum.AutoRotate = false
	local look = flat(pos - root.Position)
	if look.Magnitude > 0.5 then
		root.CFrame = CFrame.lookAt(root.Position, root.Position + look)
	end
end

local function avoidStation(goal: Vector3): Vector3
	return keepOut(goal, 18)
end

---------------------------------------------------------------------------------------------
-- Percezione

local function rayClear(from: Vector3, to: Vector3, ignore: { Instance }): boolean
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = ignore
	local result = workspace:Raycast(from, to - from, params)
	return result == nil or (Rake.model ~= nil and result.Instance:IsDescendantOf(Rake.model)) or (result.Position - to).Magnitude < 2
end

function Rake.visibleFrom(origin: Vector3, ignore: { Instance }): boolean
	if not Rake.model then
		return false
	end
	for _, target in { head.Position, root.Position } do
		if rayClear(origin, target, ignore) then
			return true
		end
	end
	return false
end

function Rake.position(): Vector3?
	if Rake.model and root and root.Parent then
		return root.Position
	end
	return nil
end

-- Il giocatore vede il punto? (cono di 60 gradi davanti al personaggio e linea di vista)
local function sees(s, pos: Vector3): boolean
	if not s.head then
		return false
	end
	local to = pos - s.head.Position
	local d = to.Magnitude
	if d > 90 or d < 0.1 then
		return d < 0.1
	end
	local look = flat(s.root.CFrame.LookVector)
	if look.Magnitude < 0.1 or math.deg(math.acos(math.clamp(look.Unit:Dot(flat(to).Unit), -1, 1))) > 60 then
		return false
	end
	return rayClear(s.head.Position, pos, { s.char, ctx.cameras.folder() })
end

local function seenByAnyone(survivors, pos: Vector3): boolean
	for _, s in survivors do
		if sees(s, pos) then
			return true
		end
	end
	return false
end

-- Punto a distanza [rmin, rmax] dal bersaglio, dietro le sue spalle e nascosto a tutti
local function hiddenSpot(survivors, target, rmin: number, rmax: number, spread: number): Vector3
	local back = -flat(target.root.CFrame.LookVector)
	if back.Magnitude < 0.1 then
		back = Vector3.new(0, 0, 1)
	end
	local fallback
	for _ = 1, 14 do
		local dir = CFrame.Angles(0, rng:NextNumber(-spread, spread), 0) * back.Unit
		local p = avoidStation(Forest.clampToMap(target.root.Position + dir * rng:NextNumber(rmin, rmax)))
		if Forest.isDry(p) then
			fallback = fallback or p
			if not seenByAnyone(survivors, p + Vector3.new(0, 4, 0)) then
				return p
			end
		end
	end
	return fallback or Forest.randomGround(rng, target.root.Position, rmin, rmax)
end

-- Punto davanti al bersaglio, nel suo campo visivo e con la vista libera
local function revealSpot(target): Vector3?
	local look = flat(target.root.CFrame.LookVector)
	if look.Magnitude < 0.1 then
		return nil
	end
	for _ = 1, 12 do
		local dir = CFrame.Angles(0, rng:NextNumber(-0.45, 0.45), 0) * look.Unit
		local p = avoidStation(Forest.clampToMap(target.root.Position + dir * rng:NextNumber(22, 32)))
		if Forest.isDry(p) and target.head and rayClear(target.head.Position, p + Vector3.new(0, 5, 0), { target.char }) then
			return p
		end
	end
	return nil
end

local function pickTarget(survivors)
	local best, bestScore = nil, -math.huge
	for _, s in survivors do
		local iso = 150
		for _, other in survivors do
			if other ~= s then
				iso = math.min(iso, (other.root.Position - s.root.Position).Magnitude)
			end
		end
		local d = (s.root.Position - root.Position).Magnitude
		local score = iso * 0.8 - d * 0.5
		if s.player:GetAttribute("CarryingTape") then
			score += 60
		end
		if safeZoneAt(s.root.Position, 0) then
			score -= 150
		end
		if brain.target == s.player then
			score += 25 -- non cambia bersaglio di continuo
		end
		s.isolation = iso
		if score > bestScore then
			best, bestScore = s, score
		end
	end
	return best
end

---------------------------------------------------------------------------------------------
-- Reazioni

local function flee(from: Vector3, duration: number)
	setMode("Fuga", duration)
	brain.fleeFrom = from
	brain.nextAction = os.clock() + duration + rng:NextNumber(4, 9)
end

local function updateLight(dt: number, survivors)
	local exposedBy = nil
	for _, s in survivors do
		if s.player:GetAttribute("TorchOn") and s.head then
			local toRake = root.Position - s.head.Position
			local d = toRake.Magnitude
			if d < R.LIGHT_RANGE and d > 0.1 then
				local aim = ctx.team.aimOf(s.player) or s.root.CFrame.LookVector
				local angle = math.deg(math.acos(math.clamp(aim:Dot(toRake.Unit), -1, 1)))
				if angle < R.LIGHT_ANGLE and Rake.visibleFrom(s.head.Position, { s.char }) then
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
			brain.aggression = math.max(0, brain.aggression - 8)
			playSound(screechSound)
			flee(exposedBy.root.Position, range(R.FLEE_TIME))
			ctx.notify("🔦 La luce l'ha respinto! Ma tornerà…", exposedBy.player)
		end
	else
		brain.light = math.max(0, brain.light - dt * 0.5)
	end
end

-- Rumori (spari, corse, laboratorio): la attirano verso la fonte
function Rake.hearNoise(pos: Vector3, loudness: number)
	if not Rake.model or brain.knockedUntil > 0 or brain.captured then
		return
	end
	local d = (pos - root.Position).Magnitude
	if d > 260 * loudness then
		return
	end
	brain.aggression = math.min(100, brain.aggression + 6 * loudness)
	brain.noise = pos
	brain.noiseTime = os.clock()
end

local function knockout()
	brain.knockedUntil = os.clock() + R.KNOCKOUT_TIME
	stop()
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
	flee(root.Position, 6)
end

function Rake.hitByDart(player: Player)
	if not Rake.model or brain.knockedUntil > 0 or brain.captured then
		return
	end
	brain.sedation += 1
	if brain.sedation >= R.DARTS_TO_KNOCKOUT then
		knockout()
	else
		brain.aggression = math.min(100, brain.aggression + 10)
		ctx.notify(("🎯 Dardo a segno! Sedazione %d/%d"):format(math.floor(brain.sedation), R.DARTS_TO_KNOCKOUT), player)
		-- colpito: scappa subito
		local shooter = player.Character and player.Character:FindFirstChild("HumanoidRootPart") :: BasePart?
		flee(shooter and shooter.Position or root.Position, range(R.FLEE_TIME))
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

local function chooseAction(now: number, target)
	local p = brain.aggression / 100
	local interval = R.ACTION_INTERVAL[1] + (R.ACTION_INTERVAL[2] - R.ACTION_INTERVAL[1]) * p
	brain.nextAction = now + interval + rng:NextNumber(0, 4)
	local roll = rng:NextNumber()
	if roll < 0.45 - p * 0.3 then
		local spot = revealSpot(target)
		if spot then
			brain.revealSpot = spot
			setMode("Mostra", 9)
			return
		end
	end
	if roll < 0.7 - p * 0.25 then
		setMode("Finta", R.CHARGE_TIMEOUT)
	else
		setMode("Carica", R.CHARGE_TIMEOUT)
	end
	playSound(growlSound)
end

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
	if b.mode ~= "Attacco" then
		updateLight(dt, survivors)
	end
	b.sedation = math.max(0, b.sedation - R.SEDATION_DECAY * dt)

	-- aggressività: tempo, rumore, giocatori isolati
	local gain = R.AGGRESSION_PER_SECOND * (1 + ctx.nightProgress * 1.5) * ctx.aggressionMultiplier
	local target = pickTarget(survivors)
	for _, s in survivors do
		local d = (s.root.Position - root.Position).Magnitude
		if d < 160 and s.root.AssemblyLinearVelocity.Magnitude > Config.PLAYER.WALK_SPEED + 3 then
			gain += 0.3
		end
		if s.isolation and s.isolation > 60 then
			gain += 0.2
		end
	end
	b.aggression = math.clamp(b.aggression + gain * dt, 0, 100)
	b.target = target and target.player

	if now >= b.modeUntil then
		if b.mode == "Attacco" then
			flee(root.Position, range(R.FLEE_TIME))
		elseif b.mode == "Mostra" or b.mode == "Carica" or b.mode == "Finta" then
			flee(target and target.root.Position or root.Position, range({ 5, 8 }))
		else
			setMode(target and "Pedina" or "Vaga")
		end
	end
	if not target and b.mode ~= "Fuga" and b.mode ~= "Vaga" then
		setMode("Vaga")
	end

	local mode = b.mode
	local reached = b.goal and flat(b.goal - root.Position).Magnitude < 5
	if mode == "Vaga" then
		if target then
			setMode("Pedina")
		else
			if not b.goal or reached or now - (b.goalTime or 0) > 25 then
				b.goal = avoidStation(Forest.randomGround(rng, b.lair, 0, 120))
				b.goalTime = now
			end
			moveTo(b.goal, R.WALK_SPEED)
		end
	elseif mode == "Pedina" then
		local t = target.root.Position
		local d = flat(t - root.Position).Magnitude
		-- lontano e invisibile: si riposiziona alle spalle del bersaglio
		if d > 150 and not seenByAnyone(survivors, root.Position + Vector3.new(0, 3, 0)) then
			local spot = hiddenSpot(survivors, target, 60, 80, 1.2)
			root.CFrame = CFrame.new(spot + Vector3.new(0, RakeRig.ROOT_HEIGHT, 0))
			b.goal = nil
			b.pathGoal = nil
		end
		-- se si accorge di essere visto: di solito sparisce, a volte attacca
		if sees(target, root.Position + Vector3.new(0, 3, 0)) then
			b.seenTime += dt
			if b.seenTime > 0.7 then
				if rng:NextNumber() < 0.65 - b.aggression / 300 then
					flee(t, range({ 5, 9 }))
				else
					setMode("Carica", R.CHARGE_TIMEOUT)
					playSound(screechSound)
				end
				return
			end
		else
			b.seenTime = 0
		end
		if b.noise and now - (b.noiseTime or 0) < 6 then
			b.goal = avoidStation(Forest.clampToMap(b.noise + Vector3.new(rng:NextNumber(-15, 15), 0, rng:NextNumber(-15, 15))))
			b.goalTime = now
			b.noise = nil
		elseif not b.goal or reached or now - (b.goalTime or 0) > 4 then
			b.goal = hiddenSpot(survivors, target, 32, 50, 0.9)
			b.goalTime = now
		end
		moveTo(b.goal, d > 90 and R.CHASE_SPEED or R.STALK_SPEED)
		if now >= (b.nextAction or 0) and d < 110 then
			chooseAction(now, target)
		end
	elseif mode == "Mostra" then
		local t = target.root.Position
		local d = flat(t - root.Position).Magnitude
		if not b.standing then
			local spot = b.revealSpot or t
			if flat(spot - root.Position).Magnitude < 4 or now - b.modeStart > 5 then
				b.standing = true
				b.modeUntil = now + range(R.REVEAL_TIME)
				stop()
				playSound(rng:NextNumber() < 0.5 and jawSound or growlSound)
			else
				moveTo(spot, R.CHASE_SPEED)
			end
		else
			stop()
			face(t)
			if d < 14 then
				setMode("Carica", R.CHARGE_TIMEOUT)
				playSound(screechSound)
			end
		end
	elseif mode == "Carica" or mode == "Finta" then
		local vel = target.root.AssemblyLinearVelocity
		local predicted = target.root.Position + Vector3.new(vel.X, 0, vel.Z) * 0.45
		local d = (target.root.Position - root.Position).Magnitude
		local direct = d < 35 and rayClear(root.Position + Vector3.new(0, 2, 0), target.root.Position, { target.char })
		moveTo(predicted, R.CHASE_SPEED, direct)
		local refuge, refugeR = safeZoneAt(target.root.Position, 2)
		if refuge and flat(root.Position - refuge.pos).Magnitude < refugeR + 12 then
			-- il bersaglio si è rifugiato in un luogo sicuro: la creatura si ferma al bordo e se ne va
			playSound(growlSound)
			flee(refuge.pos, range({ 6, 10 }))
		elseif mode == "Finta" and d < 11 then
			playSound(screechSound)
			flee(target.root.Position, range({ 6, 10 }))
		elseif d < R.ATTACK_RANGE then
			b.lastAttack = now
			playSound(screechSound)
			ctx.team.hurt(target.player, range(R.DAMAGE), root.Position)
			b.aggression = 45
			setMode("Attacco", R.ATTACK_PAUSE)
			stop()
			face(target.root.Position)
		end
	elseif mode == "Attacco" then
		stop()
	elseif mode == "Fuga" then
		if not b.goal or reached then
			local from = b.fleeFrom or root.Position
			local away = flat(root.Position - from)
			if away.Magnitude < 1 then
				away = Vector3.new(rng:NextNumber(-1, 1), 0, rng:NextNumber(-1, 1))
			end
			b.goal = avoidStation(Forest.clampToMap(root.Position + (CFrame.Angles(0, rng:NextNumber(-0.6, 0.6), 0) * away.Unit) * rng:NextNumber(90, 140)))
		end
		moveTo(b.goal, R.CHASE_SPEED)
	end

	-- barriera: se per qualsiasi motivo (percorso, spinta, comparsa) entra in una zona sicura, viene
	-- rimessa fuori
	local zone = safeZoneAt(root.Position, 3)
	if zone then
		local edge = keepOut(root.Position, 4)
		root.CFrame = CFrame.new(edge + Vector3.new(0, RakeRig.ROOT_HEIGHT, 0)) * root.CFrame.Rotation
		root.AssemblyLinearVelocity = Vector3.zero
		b.goal = nil
		b.pathGoal = nil
		if mode ~= "Fuga" then
			flee(zone.pos, range({ 5, 8 }))
		end
	end

	-- tracce e versi
	if mode ~= "Fuga" and mode ~= "Carica" and now - b.lastDrop > Config.EVIDENCE.DROP_INTERVAL then
		b.lastDrop = now
		ctx.evidence.dropNear(root.Position)
	end
	if (mode == "Pedina" or mode == "Vaga") and now > b.nextCall then
		b.nextCall = now + rng:NextNumber(18, 40)
		local roll = rng:NextNumber()
		if roll < 0.3 then
			Sfx.at("Call", Forest.randomGround(rng, root.Position, 80, 140) + Vector3.new(0, 5, 0), { Volume = 2.2, RollOffMinDistance = 12, RollOffMaxDistance = 320 })
		elseif roll < 0.55 then
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
		footsteps.PlaybackSpeed = hum.WalkSpeed >= R.CHASE_SPEED and 1.4 or 0.8
	end
end

---------------------------------------------------------------------------------------------

function Rake.init(c)
	ctx = c
end

function Rake.spawn(lair: Vector3)
	Rake.despawn()
	lair = keepOut(lair, 10)
	local now = os.clock()
	brain = {
		state = "",
		mode = "Vaga",
		modeStart = now,
		modeUntil = math.huge,
		aggression = 15,
		sedation = 0,
		light = 0,
		knockedUntil = 0,
		lastAttack = 0,
		nextAction = now + 25,
		goal = nil,
		goalTime = 0,
		lair = lair,
		lastDrop = now,
		nextCall = now + 20,
		captured = false,
		seenTime = 0,
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
	setMode("Vaga")

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
			task.wait(0.15)
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
