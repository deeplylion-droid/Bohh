-- Eventi del server: pioggia di meteore, ora d'oro, super valanga.
-- Partono da soli a intervalli casuali o dal pannello admin. Lo stato e' negli attributi di workspace
-- (EventId, EventEndsAt) cosi' tutti i client lo vedono.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Events = require(ReplicatedStorage.Shared.Config.Events)
local GameConfig = require(ReplicatedStorage.Shared.Config.Game)
local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Weighted = require(ReplicatedStorage.Shared.Util.Weighted)

local EventService = {}

local S
local rng = Random.new()
local current: string? = nil
local token = 0

function EventService.Init(services)
	S = services
end

function EventService.IsActive(id: string): boolean
	return current == id
end

function EventService.Current(): string?
	return current
end

-- Punto casuale sul sentiero di una zona (o sul fondo del cratere)
local function randomSpot(zone: string): Vector3
	if zone == "Crater" and rng:NextNumber() < 0.6 then
		local c = MapLayout.Crater.Center
		local a, r = rng:NextNumber(0, math.pi * 2), rng:NextNumber(10, MapLayout.Crater.Radius - 12)
		return c + Vector3.new(math.cos(a) * r, 0, math.sin(a) * r)
	end
	local candidates = {}
	for _, smp in MapLayout.SamplePath(20) do
		if smp.zone == zone then
			table.insert(candidates, smp)
		end
	end
	local smp = candidates[rng:NextInteger(1, #candidates)]
	local side = smp.dir:Cross(Vector3.yAxis).Unit
	return smp.pos + side * rng:NextNumber(-14, 14)
end

local function meteor()
	local zone = Events.Meteor.zones[rng:NextInteger(1, #Events.Meteor.zones)]
	local spot = randomSpot(zone)
	local y = S.MapService.HeightAt(spot.X, spot.Z)
	local pos = Vector3.new(spot.X, y, spot.Z)
	-- avviso a terra, poi impatto
	S.StateService.Effect(nil, "MeteorWarn", { position = pos, time = 2.5 })
	task.wait(2.5)
	S.StateService.Effect(nil, "MeteorImpact", { position = pos })
	for _, p in Players:GetPlayers() do
		local hrp = S.CharacterService.Root(p)
		if hrp and (hrp.Position - pos).Magnitude < Events.Meteor.blastRadius then
			local dir = (hrp.Position - pos) * Vector3.new(1, 0, 1)
			dir = if dir.Magnitude > 0.1 then dir.Unit else Vector3.xAxis
			S.CarryService.DropAll(p, "Obstacle")
			S.RagdollService.Ragdoll(p, 1.4, dir * 60 + Vector3.new(0, 50, 0))
		end
	end
	local rarity = Weighted.Pick(Weighted.FromMap(Events.Meteor.eggs, Rarities.Order), rng)
	S.NestService.SpawnLoose(pos + Vector3.new(0, 0.3, 0), rarity, { cosmicMin = Events.Meteor.cosmicMin })
	if Rarities.Get(rarity).order >= 6 then
		S.StateService.Announce("AnnounceEgg", { rarity = "Rarity_" .. rarity, zone = "Zone_" .. MapLayout.ZoneAt(pos) }, rarity)
	end
end

function EventService.StopEvent()
	token += 1
	current = nil
	workspace:SetAttribute("EventId", nil)
	workspace:SetAttribute("EventEndsAt", nil)
end

function EventService.StartEvent(id: string)
	local def = Events.Get(id)
	token += 1
	local my = token
	current = id
	local endsAt = workspace:GetServerTimeNow() + def.duration
	workspace:SetAttribute("EventId", id)
	workspace:SetAttribute("EventEndsAt", endsAt)
	S.StateService.Announce("EventStarted", { event = "Event_" .. id }, "Legendary")
	if id == "MeteorShower" then
		task.spawn(function()
			while token == my and workspace:GetServerTimeNow() < endsAt do
				task.spawn(meteor)
				task.wait(rng:NextNumber(Events.Meteor.interval[1], Events.Meteor.interval[2]))
			end
		end)
	elseif id == "SuperAvalanche" then
		S.AvalancheService.TriggerSoon(Events.SuperAvalancheInterval * 0.4)
	end
	task.delay(def.duration, function()
		if token == my then
			EventService.StopEvent()
		end
	end)
end

function EventService.Start()
	if S.Options.test then
		return
	end
	task.spawn(function()
		task.wait(GameConfig.EventFirstDelay)
		local last
		while true do
			local choices = {}
			for _, id in Events.Order do
				if id ~= last then
					table.insert(choices, id)
				end
			end
			local id = choices[rng:NextInteger(1, #choices)]
			last = id
			EventService.StartEvent(id)
			task.wait(Events.Get(id).duration + rng:NextNumber(GameConfig.EventMinGap, GameConfig.EventMaxGap))
		end
	end)
end

return EventService
