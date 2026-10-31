-- Percorso Estremo (server): corse, checkpoint, controlli anti-trucchi, portali di ritorno e uova dei
-- santuari.
--
-- Una corsa parte solo attraversando la bocca del canyon dal ponte, a mani vuote. Morire (acqua,
-- sabbie mobili, lava, laser, fiamme, presse) riporta all'ultimo checkpoint raggiunto in questa corsa.
-- Il server controlla da solo, dieci volte al secondo, la posizione di chi corre:
--   - teletrasporto (salto di posizione) e velocita' in avanti oltre il limite;
--   - muri (fuori dal canyon) e quota massima (volo o super salto);
--   - tempo senza appoggi sotto i piedi (volo, camminare sull'acqua);
--   - volumi mortali ed elementi mortali accesi (chi li ignora col "god mode");
--   - checkpoint in ordine: non si salta una sezione.
-- Chi bara torna al checkpoint; dopo troppe infrazioni la corsa finisce e si torna in piazza.
-- La velocita' di camminata e' la stessa per tutti durante la corsa e nessuno puo' colpire chi corre.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Extreme = require(ReplicatedStorage.Shared.Extreme)
local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)

local ExtremeService = {}

local S

type Run = {
	checkpoint: number,
	started: number, -- tempo del server all'inizio della corsa
	samples: { { t: number, x: number, y: number } }, -- posizioni recenti (velocita' e sospensione)
	airSince: number?,
	grace: number, -- fino a quando (os.clock) i controlli sono sospesi: appena rinato
	knockGrace: number, -- spinta di un ostacolo in corso: velocita' piu' alta consentita
	lastKnock: number,
	lastRespawn: number,
	violations: { number },
	deaths: number,
	taken: { [number]: boolean }, -- uova dei santuari prese in questa corsa
}

local runs: { [Player]: Run } = {}
local lastPos: { [Player]: Vector3 } = {}
local lastStart: { [Player]: number } = {} -- per non ripetere l'avviso a chi entra ed esce di continuo
local runEvent: RemoteEvent

local TICK = 0.1
local AIR_LIMIT = 2.4 -- secondi senza appoggi sotto i piedi
local HOVER_TIME = 0.6 -- senza appoggi e alla stessa quota per tanto cosi': si sta "in piedi sul nulla"
local HOVER_RANGE = 1.5
local SPEED_WINDOW = 1 -- secondi su cui si misura l'avanzamento
local FORWARD_LIMIT = Extreme.WalkSpeed * 1.35 + 5 -- stud/s di avanzamento (verso -X)
local KNOCK_LIMIT = 80
local TELEPORT_STEP = 30 -- stud in un campione
local VIOLATION_WINDOW = 60
local VIOLATION_KICK = 5
local DIR = Vector3.new(math.sin(Extreme.GateAngle), 0, math.cos(Extreme.GateAngle))

-- morte per tipo di sezione (effetto e messaggio)
local FALL_KIND = { Rapids = "Water", Desert = "Sand", Lab = "Zap", Inferno = "Lava" }

function ExtremeService.Init(services)
	S = services
end

local function now(): number
	return os.clock()
end

function ExtremeService.InRun(player: Player): boolean
	return runs[player] ~= nil
end

function ExtremeService.Checkpoint(player: Player): number?
	local run = runs[player]
	return run and run.checkpoint
end

local function root(player: Player): BasePart?
	return S.CharacterService.Root(player)
end

local function send(player: Player)
	local run = runs[player]
	if run then
		local data = S.DataService.Get(player)
		runEvent:FireClient(player, {
			active = true,
			checkpoint = run.checkpoint,
			started = run.started,
			best = data and data.Extreme and data.Extreme.Best or 0,
		})
	else
		runEvent:FireClient(player, nil)
	end
end

local function spawnFrame(run: Run): CFrame
	if run.checkpoint <= 0 then
		return Extreme.StartSpawn
	end
	return Extreme.Shrines[run.checkpoint].spawn
end

-- Davanti al portale del santuario k, rivolti verso il portale (chi ha l'uovo non va oltre)
local function holdFrame(k: number): CFrame
	local s = Extreme.Sections[k]
	local mid = s.length + s.shrineLength / 2
	return CFrame.lookAt(
		Extreme.At(k, mid + 8, s.floor + 3.5, -7),
		Extreme.At(k, mid + 8, s.floor + 3.5, -Extreme.HalfWidth)
	)
end

-- Sul ponte, rivolti verso la piazza (chi prova a entrare con qualcosa in mano)
local function bridgeFrame(): CFrame
	local c = Vector3.new(0, 334.5, 0)
	local p = c + DIR * 186
	return CFrame.lookAt(p, c + DIR * 150)
end

local function teleport(player: Player, cf: CFrame)
	local char = player.Character
	if not char then
		return
	end
	S.RagdollService.Recover(player)
	char:PivotTo(cf)
	local hrp = root(player)
	if hrp then
		hrp.AssemblyLinearVelocity = Vector3.zero
		hrp.AssemblyAngularVelocity = Vector3.zero
	end
	lastPos[player] = cf.Position
end

local function startRun(player: Player)
	local data = S.DataService.Get(player)
	runs[player] = {
		checkpoint = 0,
		started = workspace:GetServerTimeNow(),
		samples = {},
		airSince = nil,
		grace = 0,
		knockGrace = 0,
		lastKnock = 0,
		lastRespawn = 0,
		violations = {},
		deaths = 0,
		taken = {},
	}
	if data and data.Extreme then
		data.Extreme.Runs += 1
	end
	S.CharacterService.UpdateSpeed(player)
	if now() - (lastStart[player] or -math.huge) > 20 then
		S.StateService.Notify(player, "ExtremeStart", nil, "Gold")
	end
	lastStart[player] = now()
	S.AnalyticsService.Custom(player, "ExtremeStart", 1)
	send(player)
end

local function endRun(player: Player, reason: string)
	local run = runs[player]
	if not run then
		return
	end
	runs[player] = nil
	S.CharacterService.UpdateSpeed(player)
	S.AnalyticsService.Custom(player, "ExtremeEnd", run.checkpoint, { reason = reason })
	send(player)
end

-- Torna all'ultimo checkpoint della corsa (morte o infrazione)
local function respawn(player: Player, kind: string)
	local run = runs[player]
	if not run then
		return
	end
	local t = now()
	if t - run.lastRespawn < 0.9 then
		return
	end
	run.lastRespawn = t
	run.deaths += 1
	run.samples = {}
	run.airSince = nil
	run.grace = t + 0.9
	local hrp = root(player)
	if hrp then
		S.StateService.Effect(nil, "ExtremeSplash", { position = hrp.Position, kind = kind })
	end
	if S.CarryService.Count(player) > 0 then
		S.CarryService.DropAll(player, "Void")
	end
	teleport(player, spawnFrame(run))
	S.StateService.Effect(player, "ExtremeRespawn", { kind = kind })
end

local function violation(player: Player, what: string)
	local run = runs[player]
	if not run then
		return
	end
	local t = now()
	if t < run.grace then
		return
	end
	table.insert(run.violations, t)
	while #run.violations > 0 and t - run.violations[1] > VIOLATION_WINDOW do
		table.remove(run.violations, 1)
	end
	S.AnalyticsService.Custom(player, "ExtremeViolation", 1, { kind = what })
	if #run.violations >= VIOLATION_KICK then
		endRun(player, "Cheat")
		teleport(player, Extreme.ReturnCFrame)
		S.StateService.Notify(player, "ExtremeKicked", nil, "Bad")
		return
	end
	respawn(player, "Cheat")
	S.StateService.Notify(player, "ExtremeCheat", nil, "Bad")
end

local function reached(player: Player, run: Run, k: number)
	run.checkpoint = k
	local s = Extreme.Sections[k]
	S.StateService.Effect(player, "ExtremeCheckpoint", { n = k })
	S.AnalyticsService.Custom(player, "ExtremeCheckpoint", k)
	local data = S.DataService.Get(player)
	if k < #Extreme.Sections then
		S.StateService.Notify(player, "ExtremeCheckpoint", { n = k, zone = "Zone_" .. s.id }, "Gold")
	else
		local time = workspace:GetServerTimeNow() - run.started
		local best = data and data.Extreme and data.Extreme.Best or 0
		if data and data.Extreme then
			data.Extreme.Completed += 1
			if best == 0 or time < best then
				data.Extreme.Best = time
			end
		end
		S.StateService.Notify(player, "ExtremeComplete", { time = Format.Clock(time) }, "Gold")
		S.StateService.Announce("AnnounceExtreme", { name = player.DisplayName, time = Format.Clock(time) }, "Extreme")
		S.StateService.Effect(nil, "ExtremeComplete", { userId = player.UserId })
	end
	if data and data.Extreme then
		data.Extreme.Sections = math.max(data.Extreme.Sections or 0, k)
	end
	send(player)
end

-- Il giocatore e' nel disco del portale del santuario k?
local function inPortal(pos: Vector3, k: number): boolean
	local portal = Extreme.Shrines[k].portal
	local rel = portal:PointToObjectSpace(pos)
	return math.abs(rel.Z) < 2.6 and Vector2.new(rel.X, rel.Y).Magnitude < 5.6
end

-- Ingresso valido: dal ponte, attraverso l'apertura della bocca del canyon
local function crossedGate(prev: Vector3?, pos: Vector3): boolean
	if not prev then
		return false
	end
	return prev.X >= Extreme.StartX
		and prev.X < Extreme.StartX + 14
		and math.abs(prev.Z - Extreme.Z) < 7
		and prev.Y > 326
		and prev.Y < 346
		and math.abs(pos.Z - Extreme.Z) < 8
		and (pos - prev).Magnitude < 12
end

local function checkRunner(player: Player, run: Run, pos: Vector3, prev: Vector3?)
	local t = now()
	local st = workspace:GetServerTimeNow()
	-- portali di ritorno: quelli dei santuari gia' raggiunti
	for k = 1, run.checkpoint do
		if inPortal(pos, k) then
			endRun(player, "Portal")
			teleport(player, Extreme.ReturnCFrame)
			player:SetAttribute("ProtectedUntil", workspace:GetServerTimeNow() + 3)
			S.StateService.Effect(player, "ExtremePortal", {})
			return
		end
	end
	if t < run.grace then
		return
	end
	-- con l'uovo in mano non si prosegue: solo il portale
	if run.checkpoint >= 1 and S.CarryService.Count(player) > 0 then
		local sh = Extreme.Shrines[run.checkpoint]
		if pos.X < sh.exitX + 1 then
			teleport(player, holdFrame(run.checkpoint))
			run.grace = t + 0.6
			S.StateService.Notify(player, "ExtremeEggPortal", nil, "Bad")
			return
		end
	end
	-- teletrasporto
	if prev and (pos - prev).Magnitude > TELEPORT_STEP then
		violation(player, "Teleport")
		return
	end
	-- muri e quota massima
	if math.abs(pos.Z - Extreme.Z) > Extreme.HalfWidth + 1.5 then
		violation(player, "Wall")
		return
	end
	if pos.Y > Extreme.CeilingAt(pos.X) then
		violation(player, "Height")
		return
	end
	-- velocita' in avanti (verso -X) misurata sull'ultimo secondo
	table.insert(run.samples, { t = t, x = pos.X, y = pos.Y })
	while #run.samples > 0 and t - run.samples[1].t > SPEED_WINDOW + 0.25 do
		table.remove(run.samples, 1)
	end
	local first = run.samples[1]
	local age = t - first.t
	if age >= 0.5 then
		local limit = if t < run.knockGrace then KNOCK_LIMIT else FORWARD_LIMIT
		if first.x - pos.X > limit * age + 3 then
			violation(player, "Speed")
			return
		end
	end
	-- appoggi sotto i piedi
	if Extreme.GroundBelow(pos, st, 16, 3) then
		run.airSince = nil
	else
		run.airSince = run.airSince or t
		local air = t - (run.airSince :: number)
		if air > AIR_LIMIT then
			violation(player, "Air")
			return
		end
		-- chi non ha appoggi cade o salta: restare alla stessa quota vuol dire stare su qualcosa che
		-- per il server non c'e' (mattonelle crollate "congelate", piattaforme create dal client)
		if air >= HOVER_TIME and not S.RagdollService.IsRagdolled(player) then
			local lo, hi = math.huge, -math.huge
			for _, smp in run.samples do
				if t - smp.t <= HOVER_TIME then
					lo = math.min(lo, smp.y)
					hi = math.max(hi, smp.y)
				end
			end
			if hi - lo < HOVER_RANGE then
				violation(player, "Hover")
				return
			end
		end
	end
	-- volumi mortali (piedi) ed elementi mortali accesi
	local feet = pos - Vector3.new(0, Extreme.BodyDown, 0)
	if Extreme.InKill(feet) then
		local s = Extreme.Sections[Extreme.SectionAt(pos.X)]
		respawn(player, FALL_KIND[s.theme] or "Water")
		return
	end
	local hit = Extreme.PulseKillAt(pos, st)
	if hit then
		respawn(player, hit.style or "Zap")
		return
	end
	-- checkpoint in ordine
	local nextK = run.checkpoint + 1
	local nextX = Extreme.CheckpointX[nextK]
	if nextX and pos.X < nextX then
		local after = Extreme.CheckpointX[nextK + 1]
		if after and pos.X < after then
			violation(player, "Skip")
			return
		end
		reached(player, run, nextK)
	end
end

local function step()
	for _, player in Players:GetPlayers() do
		local hrp = root(player)
		local char = player.Character
		local hum = char and char:FindFirstChildOfClass("Humanoid")
		if not hrp or not hum or hum.Health <= 0 then
			if runs[player] then
				endRun(player, "Died")
			end
			lastPos[player] = nil
			continue
		end
		local pos = hrp.Position
		local prev = lastPos[player]
		lastPos[player] = pos
		local run = runs[player]
		local inside = Extreme.InCourse(pos)
		if run then
			if inside then
				checkRunner(player, run, pos, prev)
			elseif runs[player] then
				-- uscito dal percorso: indietro dal ponte, portale, caduta nel vuoto o morte
				endRun(player, "Left")
			end
		elseif inside then
			if crossedGate(prev, pos) then
				if S.CarryService.Count(player) > 0 then
					teleport(player, bridgeFrame())
					S.StateService.Notify(player, "ExtremeNoCarry", nil, "Bad")
				else
					startRun(player)
					checkRunner(player, runs[player], pos, prev)
				end
			else
				-- dentro il percorso senza essere passato dall'ingresso: si torna in piazza
				teleport(player, Extreme.ReturnCFrame)
			end
		end
	end
end

---------------------------------------------------------------------------------------------
-- Colpi segnalati dal client (per una risposta immediata; il server controlla comunque da solo)
---------------------------------------------------------------------------------------------
local function onHit(player: Player, id: any)
	if type(id) ~= "string" then
		return
	end
	local run = runs[player]
	local hrp = root(player)
	if not run or not hrp or now() < run.grace then
		return
	end
	local pos = hrp.Position
	local section = Extreme.Sections[Extreme.SectionAt(pos.X)]
	if id == "Fall" then
		-- cadere non conviene a nessuno: basta che sia dentro il percorso
		respawn(player, FALL_KIND[section.theme] or "Water")
		return
	end
	local p = Extreme.Get(id)
	if not p then
		return
	end
	local reach = p.size.Magnitude / 2 + (p.length or 0) + 14
	if (pos - p.cframe.Position).Magnitude > reach then
		return
	end
	if p.effect == "Kill" then
		respawn(player, p.style or "Zap")
		return
	end
	-- spinte: tronchi e uncini, lame, getti d'acqua
	local t = now()
	if t - run.lastKnock < 1.2 or S.RagdollService.IsRagdolled(player) then
		return
	end
	local st = workspace:GetServerTimeNow()
	local power = p.power or 60
	local push: Vector3
	if p.kind == "Swing" then
		-- verso del moto del peso: oscilla attorno all'asse X del perno e, quando l'angolo cresce
		-- (coseno positivo), il peso va verso -Z; la spinta segue il moto
		local a = math.pi * 2 * (st / (p.period or 3) + (p.phase or 0))
		local dir = if math.cos(a) > 0 then -1 else 1
		push = Vector3.new(0, 26, dir * power)
	elseif p.kind == "Sweeper" then
		local hub = p.cframe.Position
		local r = (pos - hub) * Vector3.new(1, 0, 1)
		if r.Magnitude < 0.1 then
			r = Vector3.xAxis
		end
		local tangent = Vector3.yAxis:Cross(r.Unit) * (if (p.period or 1) > 0 then 1 else -1)
		push = tangent * power + Vector3.new(0, 22, 0)
	elseif p.kind == "Pulse" then
		if Extreme.PulsePhase(p, st) ~= "active" and Extreme.PulsePhase(p, st - 0.4) ~= "active" then
			return
		end
		push = Vector3.new(0, power, 0)
	else
		return
	end
	run.lastKnock = t
	run.knockGrace = t + 1.6
	S.RagdollService.Ragdoll(player, 1, push)
	S.StateService.Effect(nil, "Hit", { position = pos, kind = "Extreme" })
end

---------------------------------------------------------------------------------------------
-- Uova dei santuari
---------------------------------------------------------------------------------------------
local function shrineOf(zone: string): number?
	for i, s in Extreme.Sections do
		if s.id == zone then
			return i
		end
	end
	return nil
end

function ExtremeService.IsZone(zone: string?): boolean
	return zone ~= nil and shrineOf(zone) ~= nil
end

-- Si puo' prendere l'uovo del santuario della zona? (solo in corsa, arrivati li', uno per corsa)
function ExtremeService.CanPickup(player: Player, zone: string): boolean
	local k = shrineOf(zone)
	if not k then
		return true
	end
	local run = runs[player]
	if not run or run.checkpoint < k then
		S.StateService.Notify(player, "ExtremeNeedRun", nil, "Bad")
		return false
	end
	if run.taken[k] then
		S.StateService.Notify(player, "ExtremeOneEgg", nil, "Bad")
		return false
	end
	local hrp = root(player)
	if not hrp or (hrp.Position - Extreme.Shrines[k].altar).Magnitude > 16 then
		return false
	end
	return true
end

function ExtremeService.Took(player: Player, zone: string)
	local k = shrineOf(zone)
	local run = runs[player]
	if k and run then
		run.taken[k] = true
		local data = S.DataService.Get(player)
		if data and data.Extreme then
			data.Extreme.Eggs += 1
		end
		S.StateService.Notify(player, "ExtremeEggTaken", nil, "Gold")
	end
end

---------------------------------------------------------------------------------------------
function ExtremeService.Start()
	runEvent = Net.Event("ExtremeRun")
	Net.Event("ExtremeHit").OnServerEvent:Connect(onHit)
	Players.PlayerRemoving:Connect(function(player)
		runs[player] = nil
		lastPos[player] = nil
		lastStart[player] = nil
	end)
	if S.Options.test then
		return
	end
	local acc = 0
	RunService.Heartbeat:Connect(function(dt)
		acc += dt
		if acc < TICK then
			return
		end
		acc = 0
		step()
	end)
end

-- Per i test: un passo dei controlli e accesso alle corse
ExtremeService.Step = step
ExtremeService.Runs = runs

return ExtremeService
