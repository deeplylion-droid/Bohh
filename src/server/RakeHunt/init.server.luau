-- The Rake: Caccia nei Boschi — ciclo della partita.
-- Attesa -> Briefing (alla Ranger Station) -> Notte (caccia) -> Debriefing (XP e ranghi).
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local Lighting = game:GetService("Lighting")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local Forest = require(script.Forest)
local Rake = require(script.Rake)
local Cameras = require(script.Cameras)
local Evidence = require(script.Evidence)
local Team = require(script.Team)
local Objectives = require(script.Objectives)
local Progression = require(script.Progression)

Players.CharacterAutoLoads = false

-- Stato condiviso letto dai client (attributi)
local state = Instance.new("Folder")
state.Name = "RakeState"
state.Parent = ReplicatedStorage

local remotes = Instance.new("Folder")
remotes.Name = "RakeRemotes"
for _, name in { "Notify", "Debrief", "OpenTablet", "FireDart", "CycleCameraType", "RotateCamera" } do
	local remote = Instance.new("RemoteEvent")
	remote.Name = name
	remote.Parent = remotes
end
remotes.Parent = ReplicatedStorage

local world = Instance.new("Folder")
world.Name = "RakeHunt"
world.Parent = workspace

local rng = Random.new()

local ctx = {
	state = state,
	remotes = remotes,
	world = world,
	round = { active = false, captured = false },
	stats = {},
	weather = Config.WEATHER[1],
	aggressionMultiplier = 1,
	nightProgress = 0,
	forest = Forest,
	rake = Rake,
	cameras = Cameras,
	evidence = Evidence,
	team = Team,
	objectives = Objectives,
}

function ctx.notify(text: string, player: Player)
	remotes.Notify:FireClient(player, text)
end

function ctx.notifyAll(text: string)
	remotes.Notify:FireAllClients(text)
end

function ctx.isNight(): boolean
	return Lighting.ClockTime >= 19.5 or Lighting.ClockTime < 6
end

function ctx.credit(userId: number?, field: string)
	local s = userId and ctx.stats[userId]
	if s then
		s[field] = (s[field] or 0) + 1
	end
end

local revealed = { zone = false, area = false, exact = false }
local nextAreaUpdate, nextPulse = 0, 0
local areaMarker: BasePart? = nil

function ctx.setLastSeen(pos: Vector3)
	state:SetAttribute("LastSeenX", pos.X)
	state:SetAttribute("LastSeenZ", pos.Z)
	state:SetAttribute("LastSeenTime", workspace:GetServerTimeNow())
end

function ctx.addTracking(amount: number)
	if not ctx.round.active then
		return
	end
	local t = math.clamp((state:GetAttribute("Tracking") or 0) + amount, 0, 100)
	state:SetAttribute("Tracking", t)
	local R = Config.EVIDENCE.REVEAL
	if t >= R.ZONE and not revealed.zone then
		revealed.zone = true
		local zone = Forest.biomeAt(ctx.round.lair)
		state:SetAttribute("ZoneHint", zone)
		ctx.notifyAll(("🗺 Tracciamento %d%%: la tana della creatura è nella zona \"%s\"."):format(R.ZONE, zone))
	end
	if t >= R.AREA and not revealed.area then
		revealed.area = true
		nextAreaUpdate = 0
		ctx.notifyAll(("🗺 Tracciamento %d%%: l'area di caccia è segnata in rosso sulla mappa e nel bosco."):format(R.AREA))
	end
	if t >= R.EXACT and not revealed.exact then
		revealed.exact = true
		nextPulse = 0
		ctx.notifyAll("🎯 Tracciamento completo: la posizione della creatura viene rivelata a intervalli!")
	end
end

function ctx.onCapture(player: Player)
	ctx.round.captured = true
	ctx.credit(player.UserId, "capture")
	ctx.notifyAll(("🏆 %s ha catturato The Rake!"):format(player.DisplayName))
end

for _, module in { Rake, Cameras, Evidence, Team, Objectives } do
	module.init(ctx)
end

---------------------------------------------------------------------------------------------
-- Mappa e luci

Forest.build(world)
Forest.regenerate(rng)

local prompts = Forest.stationPrompts
prompts.control.Triggered:Connect(function(player)
	remotes.OpenTablet:FireClient(player)
end)
prompts.supply.Triggered:Connect(function(player)
	Team.supply(player)
end)
prompts.lab.Triggered:Connect(function(player)
	Evidence.analyze(player)
end)

remotes.FireDart.OnServerEvent:Connect(function(player, targetPos)
	Team.fireDart(player, targetPos)
end)
remotes.CycleCameraType.OnServerEvent:Connect(function(player)
	Team.cycleCamType(player)
end)
remotes.RotateCamera.OnServerEvent:Connect(function(player, id, dir)
	Cameras.rotate(player, id, dir)
end)

Lighting.GlobalShadows = true
Lighting.Ambient = Color3.fromRGB(14, 14, 20)
Lighting.OutdoorAmbient = Color3.fromRGB(30, 32, 42)
Lighting.FogColor = Color3.fromRGB(8, 10, 16)
Lighting.FogStart = 0

local function setDusk()
	Lighting.ClockTime = 18.8
	Lighting.Brightness = 1
	Lighting.FogEnd = 300
end

local function applyNight(progress: number)
	local hour = Config.NIGHT_START_HOUR + progress * Config.NIGHT_HOURS
	Lighting.ClockTime = hour % 24
	-- Verso l'alba la luce torna e la nebbia si dirada
	local dawn = math.clamp((progress - 0.9) / 0.1, 0, 1)
	Lighting.Brightness = 0.25 + dawn * 1.5
	Lighting.FogEnd = ctx.weather.fogEnd + dawn * 300
end

setDusk()

---------------------------------------------------------------------------------------------
-- Giocatori

local function setPhase(name: string)
	state:SetAttribute("Phase", name)
end

local function newStats(player: Player)
	ctx.stats[player.UserId] = { name = player.DisplayName, evidence = 0, sightings = 0, revives = 0, capture = 0 }
end

local function onPlayerAdded(player: Player)
	player.CharacterAdded:Connect(function(char)
		Team.watchCharacter(player, char)
	end)
	Progression.load(player)
	local phase = state:GetAttribute("Phase")
	if phase == "Briefing" or phase == "Notte" then
		-- Chi entra a partita in corso si unisce alla squadra alla stazione
		newStats(player)
		Team.spawn(player, true)
		ctx.notifyAll(("%s si è unito alla spedizione."):format(player.DisplayName))
	else
		Team.spawn(player, false)
	end
end

Players.PlayerAdded:Connect(onPlayerAdded)
for _, player in Players:GetPlayers() do
	task.spawn(onPlayerAdded, player)
end

Players.PlayerRemoving:Connect(function(player)
	Objectives.onDowned(player)
	Progression.release(player)
end)

---------------------------------------------------------------------------------------------
-- Ciclo della partita

local function countdown(seconds: number)
	for t = seconds, 1, -1 do
		state:SetAttribute("TimeLeft", t)
		task.wait(1)
	end
	state:SetAttribute("TimeLeft", 0)
end

local function chooseWeather()
	local total = 0
	for _, w in Config.WEATHER do
		total += w.weight
	end
	local roll = rng:NextNumber(0, total)
	for _, w in Config.WEATHER do
		roll -= w.weight
		if roll <= 0 then
			return w
		end
	end
	return Config.WEATHER[1]
end

local function resetState()
	for name, value in {
		Tracking = 0,
		Evidence = 0,
		Coverage = 0,
		CamerasActive = 0,
		ZoneHint = "",
		HintX = 0,
		HintZ = 0,
		HintR = 0,
		LastSeenTime = 0,
		RakeState = "Assente",
		ObjectiveProgress = "",
	} do
		state:SetAttribute(name, value)
	end
	revealed = { zone = false, area = false, exact = false }
	if areaMarker then
		areaMarker:Destroy()
		areaMarker = nil
	end
end

local function updateReveal()
	local now = os.clock()
	local pos = Rake.position()
	if not pos then
		return
	end
	if revealed.area and now >= nextAreaUpdate then
		nextAreaUpdate = now + 20
		local center = Forest.randomGround(rng, pos, 0, 35)
		local radius = 70
		state:SetAttribute("HintX", center.X)
		state:SetAttribute("HintZ", center.Z)
		state:SetAttribute("HintR", radius)
		if not areaMarker then
			areaMarker = Forest.make("Part", world, {
				Name = "AreaDiCaccia",
				Shape = Enum.PartType.Cylinder,
				Material = Enum.Material.Neon,
				Color = Color3.fromRGB(255, 40, 40),
				Transparency = 0.85,
				CanCollide = false,
				CanQuery = false,
				CastShadow = false,
			})
		end
		local marker = areaMarker :: BasePart
		marker.Size = Vector3.new(0.3, radius * 2, radius * 2)
		marker.CFrame = CFrame.new(center.X, 0.3, center.Z) * CFrame.Angles(0, 0, math.pi / 2)
	end
	if revealed.exact and now >= nextPulse then
		nextPulse = now + 30
		Rake.setRevealed(true)
		ctx.setLastSeen(pos)
		task.delay(8, function()
			Rake.setRevealed(false)
		end)
	end
end

local function runNight(): (string, string)
	-- La tana è in un punto di interesse a caso (mai la stazione)
	local poi = Forest.POIS[rng:NextInteger(2, #Forest.POIS)]
	local lair = Forest.randomGround(rng, poi.pos, 50, 110)
	ctx.round.lair = lair
	ctx.round.active = true
	Rake.spawn(lair)
	Evidence.seed(lair)
	setPhase("Notte")
	ctx.notifyAll("🌲 Cala la notte. Qualcosa si muove tra gli alberi…")

	local start = os.clock()
	local last = start
	while true do
		task.wait(0.25)
		local now = os.clock()
		local dt = now - last
		last = now
		local progress = math.clamp((now - start) / Config.NIGHT_DURATION, 0, 1)
		ctx.nightProgress = progress
		applyNight(progress)
		state:SetAttribute("TimeLeft", math.max(0, math.ceil(Config.NIGHT_DURATION - (now - start))))

		Team.tick(dt)
		Cameras.tick(dt)
		updateReveal()
		state:SetAttribute("ObjectiveProgress", Objectives.progressText())

		local result, reason = Objectives.check()
		if result then
			return result, reason :: string
		end
		if #Players:GetPlayers() == 0 then
			return "lose", "La squadra ha abbandonato il bosco."
		end
		if not Team.anyStanding() then
			return "lose", "Tutta la squadra è stata abbattuta."
		end
		if progress >= 1 then
			return Objectives.onDawn()
		end
	end
end

local function debrief(result: string, reason: string)
	ctx.round.active = false
	setPhase("Debriefing")
	Rake.despawn()
	state:SetAttribute("RakeState", "Assente")
	local XP = Config.XP
	local won = result == "win"
	ctx.notifyAll((won and "✅ " or "❌ ") .. reason)

	for _, player in Players:GetPlayers() do
		local s = ctx.stats[player.UserId]
		if s then
			local survived = player:GetAttribute("Status") == "OK"
			local breakdown = {
				{ "Prove raccolte", s.evidence * XP.EVIDENCE },
				{ "Telecamere utili", s.sightings * XP.CAMERA_SIGHTING },
				{ "Rianimazioni", s.revives * XP.REVIVE },
				{ "Cattura", s.capture * XP.CAPTURE },
				{ "Sopravvivenza", survived and XP.SURVIVE or 0 },
				{ "Obiettivo", won and XP.WIN or 0 },
			}
			local xp = 0
			for _, row in breakdown do
				xp += row[2]
			end
			if not won then
				xp = math.floor(xp * XP.LOSS_MULTIPLIER)
			end
			Progression.award(player, xp, {
				Runs = 1,
				Wins = won and 1 or 0,
				Captures = s.capture,
				Evidence = s.evidence,
				Revives = s.revives,
			})
			local profile = Progression.get(player)
			local total = profile and profile.XP or xp
			local rank, nextXp = Progression.rankFor(total)
			remotes.Debrief:FireClient(player, {
				won = won,
				reason = reason,
				objective = Objectives.current(),
				xp = xp,
				halved = not won,
				breakdown = breakdown,
				totalXP = total,
				rank = rank,
				nextXP = nextXp,
				level = Progression.levelFor(total),
			})
		end
	end
	countdown(Config.DEBRIEF)
end

while true do
	-- Attesa
	setPhase("Attesa")
	setDusk()
	resetState()
	while #Players:GetPlayers() < Config.MIN_PLAYERS do
		state:SetAttribute("TimeLeft", 0)
		task.wait(1)
	end

	-- Briefing: nuova foresta, meteo e obiettivo; tutti alla Ranger Station con l'attrezzatura
	setPhase("Briefing")
	ctx.round = { active = false, captured = false }
	ctx.stats = {}
	Rake.despawn()
	Cameras.reset()
	Evidence.reset()
	Objectives.cleanup()
	Forest.regenerate(rng)
	ctx.weather = chooseWeather()
	state:SetAttribute("Weather", ctx.weather.name)
	Objectives.start(rng)
	for _, player in Players:GetPlayers() do
		newStats(player)
		task.spawn(Team.spawn, player, true)
	end
	countdown(Config.BRIEFING)

	local result, reason = runNight()
	debrief(result, reason)

	-- Pulizia e ritorno alla lobby
	Objectives.cleanup()
	Cameras.reset()
	Evidence.reset()
	resetState()
	for _, player in Players:GetPlayers() do
		task.spawn(Team.spawn, player, false)
	end
end
