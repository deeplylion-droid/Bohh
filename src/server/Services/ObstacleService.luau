-- Ostacoli: costruisce le parti fisse (travi dei tronchi, bocche dei geyser, canali di lava,
-- sporgenze delle scorciatoie), convalida i colpi segnalati dai client e gestisce le bombe di lava.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local MapLayout = require(ReplicatedStorage.Shared.MapLayout)
local Net = require(ReplicatedStorage.Shared.Net)
local Obstacles = require(ReplicatedStorage.Shared.Obstacles)
local Build = require(script.Parent.Parent.World.Build)

local ObstacleService = {}

local S
local lastHit: { [Player]: number } = {}
local folder: Model
local rng = Random.new()

local WOOD = Color3.fromRGB(150, 98, 56)

function ObstacleService.Init(services)
	S = services
end

local function ground(cf: CFrame): CFrame
	local p = cf.Position
	local y = S.MapService.HeightAt(p.X, p.Z)
	return CFrame.new(p.X, y, p.Z) * (cf - cf.Position)
end

local function buildStatic()
	folder = Build.Model("Obstacles", workspace:FindFirstChild("Map"))
	-- portali di legno da cui pendono i tronchi
	for _, p in Obstacles.Pendulums do
		local top = p.pivot
		for _, sx in { -1, 1 } do
			local x = sx * (p.logLength / 2 + 3)
			local footCf = ground(top * CFrame.new(x, 0, 0))
			local height = top.Position.Y - footCf.Position.Y + 1
			Build.Part({
				name = "Post",
				size = Vector3.new(2.2, height, 2.2),
				cframe = top * CFrame.new(x, -height / 2 + 1, 0),
				color = WOOD,
				material = Enum.Material.Wood,
				parent = folder,
			})
		end
		Build.Part({
			name = "Beam",
			size = Vector3.new(p.logLength + 10, 2.2, 2.2),
			cframe = top * CFrame.new(0, 1, 0),
			color = WOOD,
			material = Enum.Material.Wood,
			parent = folder,
		})
	end
	-- bocche dei geyser e canali di lava (la parte animata la disegna il client)
	for _, p in Obstacles.Pulses do
		local cf = ground(p.cframe)
		if p.kind == "Geyser" or p.kind == "FireGeyser" then
			local color = if p.kind == "Geyser" then Color3.fromRGB(150, 140, 210) else Color3.fromRGB(70, 56, 64)
			Build.Part({
				name = "Vent",
				size = Vector3.new(1.4, 6.5, 6.5),
				cframe = cf * CFrame.new(0, 0.4, 0) * CFrame.Angles(0, 0, math.rad(90)),
				color = color,
				material = Enum.Material.Slate,
				shape = Enum.PartType.Cylinder,
				parent = folder,
			})
			Build.Part({
				name = "VentHole",
				size = Vector3.new(1.5, 4, 4),
				cframe = cf * CFrame.new(0, 0.45, 0) * CFrame.Angles(0, 0, math.rad(90)),
				color = if p.kind == "Geyser" then Color3.fromRGB(120, 230, 255) else Color3.fromRGB(255, 110, 30),
				material = Enum.Material.Neon,
				shape = Enum.PartType.Cylinder,
				collide = false,
				castShadow = false,
				parent = folder,
			})
		else
			Build.Part({
				name = "LavaChannel",
				size = Vector3.new(p.size.X, 0.6, p.size.Z),
				cframe = cf * CFrame.new(0, 0.1, 0),
				color = Color3.fromRGB(60, 46, 50),
				material = Enum.Material.Basalt,
				collide = false,
				parent = folder,
			})
		end
	end
	-- scorciatoie: sporgenze di legno sul pendio che si sbriciolano quando le calpesti
	for _, sc in MapLayout.Shortcuts do
		local low = MapLayout.Legs[sc.fromLeg]
		local high = MapLayout.Legs[sc.toLeg]
		local yLow = MapLayout.LegHeight(low, sc.x)
		local yHigh = MapLayout.LegHeight(high, sc.x)
		local zLow = low.z - MapLayout.PathWidth / 2 + 1
		local zHigh = high.z + MapLayout.PathWidth / 2 - 1
		local steps = math.ceil((yHigh - yLow) / 4.6)
		for k = 1, steps do
			local t = k / (steps + 1)
			local x = sc.x + (if k % 2 == 0 then 5 else -5)
			local z = zLow + (zHigh - zLow) * t
			local y = yLow + (yHigh - yLow) * (k / steps) - 0.6
			local ledge = Build.Part({
				name = "Ledge",
				size = Vector3.new(6, 1, 4.6),
				cframe = CFrame.new(x, y, z),
				color = Color3.fromRGB(196, 140, 84),
				material = Enum.Material.WoodPlanks,
				parent = folder,
			})
			ledge.CanTouch = true
			ledge:SetAttribute("Shortcut", sc.id)
			local busy = false
			local home = ledge.CFrame
			ledge.Touched:Connect(function(hit)
				if busy or not Players:GetPlayerFromCharacter(hit.Parent) then
					return
				end
				busy = true
				ledge.Color = Color3.fromRGB(160, 100, 56)
				task.wait(0.7)
				ledge.CanCollide = false
				ledge.Transparency = 1
				task.wait(5)
				ledge.CFrame = home
				ledge.CanCollide = true
				ledge.Transparency = 0
				ledge.Color = Color3.fromRGB(196, 140, 84)
				busy = false
			end)
		end
	end
end

-- Convalida un colpo segnalato dal client e applica l'effetto
local function onHit(player: Player, id: any)
	if type(id) ~= "string" then
		return
	end
	local now = os.clock()
	if
		now - (lastHit[player] or 0) < 1.1
		or S.RagdollService.IsRagdolled(player)
		or S.CharacterService.IsProtected(player)
	then
		return
	end
	local hrp = S.CharacterService.Root(player)
	local o = Obstacles.ById(id)
	if not hrp or not o then
		return
	end
	local t = workspace:GetServerTimeNow()
	local pos = hrp.Position
	local push: Vector3
	local burn = false
	local lift = 38
	if o.s0 then
		-- rotolante: deve esserci un rotolante vicino al giocatore
		local near = false
		for _, st in Obstacles.RollerStates(o, t) do
			if (st.cframe.Position - pos).Magnitude < o.radius + 12 then
				near = true
			end
		end
		if not near then
			return
		end
		local p0 = Obstacles.FrameAt(o.s0, 0)
		local p1 = Obstacles.FrameAt(o.s1, 0)
		push = (p1.Position - p0.Position) * Vector3.new(1, 0, 1)
		push = push.Unit * 55
	elseif o.logLength then
		local cf = Obstacles.PendulumCFrame(o, t)
		if (cf.Position - pos).Magnitude > o.logLength / 2 + 12 then
			return
		end
		-- verso del tronco: angolo crescente = verso valle (LookVector del perno)
		push = o.pivot.LookVector * 60 * (if math.cos(t * 2 * math.pi / o.period + o.phase) > 0 then 1 else -1)
	elseif o.halfWidth then
		local cf = Obstacles.GoatCFrame(o, t)
		if (cf.Position - pos).Magnitude > 14 then
			return
		end
		push = cf.LookVector * 65
	elseif o.kind then
		local state = Obstacles.PulseState(o, t)
		local state2 = Obstacles.PulseState(o, t - 0.35)
		if state ~= "Active" and state2 ~= "Active" then
			return
		end
		local cf = ground(o.cframe)
		local lp = cf:PointToObjectSpace(pos)
		if math.abs(lp.X) > o.size.X / 2 + 5 or math.abs(lp.Z) > o.size.Z / 2 + 5 or lp.Y > o.size.Y + 6 then
			return
		end
		if o.kind == "Lava" then
			burn = true
		end
		push = Vector3.new(rng:NextNumber(-8, 8), 0, rng:NextNumber(-8, 8))
		lift = if o.kind == "Lava" then 0 else 95
	else
		return
	end
	lastHit[player] = now
	if burn then
		S.StateService.Effect(nil, "Burn", { position = pos })
		S.CharacterService.ReturnToBase(player, "Burned")
		return
	end
	S.CarryService.DropAll(player, "Obstacle")
	S.RagdollService.Ragdoll(player, 1.3, push + Vector3.new(0, lift, 0))
	S.StateService.Effect(nil, "Hit", { position = pos, kind = o.kind or "Roller" })
end

-- Bombe di lava nel cratere: avviso a terra, poi esplosione che sbalza e fa cadere le uova
local function lavaBombs()
	local c = MapLayout.Crater.Center
	while true do
		task.wait(rng:NextNumber(6, 10))
		local a, r = rng:NextNumber(0, math.pi * 2), rng:NextNumber(8, MapLayout.Crater.Radius - 10)
		local pos = c + Vector3.new(math.cos(a) * r, 0, math.sin(a) * r)
		pos = Vector3.new(pos.X, S.MapService.HeightAt(pos.X, pos.Z), pos.Z)
		S.StateService.Effect(nil, "LavaBombWarn", { position = pos, time = 2 })
		task.delay(2, function()
			S.StateService.Effect(nil, "LavaBombImpact", { position = pos })
			for _, p in Players:GetPlayers() do
				local hrp = S.CharacterService.Root(p)
				if hrp and (hrp.Position - pos).Magnitude < 11 and not S.CharacterService.IsProtected(p) then
					local dir = (hrp.Position - pos) * Vector3.new(1, 0, 1)
					dir = if dir.Magnitude > 0.1 then dir.Unit else Vector3.xAxis
					S.CarryService.DropAll(p, "Obstacle")
					S.RagdollService.Ragdoll(p, 1.4, dir * 55 + Vector3.new(0, 55, 0))
				end
			end
		end)
	end
end

function ObstacleService.Start()
	S.MapService.WaitReady()
	buildStatic()
	Net.Event("ObstacleHit").OnServerEvent:Connect(onHit)
	Players.PlayerRemoving:Connect(function(p)
		lastHit[p] = nil
	end)
	if not S.Options.test then
		task.spawn(lavaBombs)
	end
end

return ObstacleService
