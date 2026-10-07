-- Obiettivi di partita: Ricognizione, Caccia, Sopravvivenza, Reperto.
-- La cattura della creatura vale come vittoria con qualsiasi obiettivo.
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Config = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Config"))
local Forest = require(script.Parent.Forest)

local make = Forest.make

local Objectives = {}

local LIST = { "Ricognizione", "Caccia", "Sopravvivenza", "Reperto" }

local ctx
local current = "Caccia"
local tape: Model? = nil
local tapePoi = ""

local function tapeCarrier(): Player?
	for _, player in Players:GetPlayers() do
		if player:GetAttribute("CarryingTape") then
			return player
		end
	end
	return nil
end

local function setCarrierHighlight(player: Player, on: boolean)
	local char = player.Character
	if not char then
		return
	end
	local existing = char:FindFirstChild("NastroHighlight")
	if on and not existing then
		make("Highlight", char, {
			Name = "NastroHighlight",
			FillTransparency = 1,
			OutlineColor = Color3.fromRGB(255, 70, 70),
		})
	elseif not on and existing then
		existing:Destroy()
	end
end

local function spawnTape(pos: Vector3)
	if tape then
		tape:Destroy()
	end
	local m = Instance.new("Model")
	m.Name = "NastroAudio"
	local part = make("Part", m, {
		Name = "Nastro",
		Size = Vector3.new(1.2, 0.35, 0.8),
		CFrame = CFrame.new(pos + Vector3.new(0, 0.4, 0)),
		Color = Color3.fromRGB(20, 20, 20),
		Material = Enum.Material.SmoothPlastic,
	})
	make("Part", m, {
		Size = Vector3.new(0.8, 0.05, 0.5),
		CFrame = CFrame.new(pos + Vector3.new(0, 0.6, 0)),
		Color = Color3.fromRGB(200, 40, 40),
		Material = Enum.Material.Neon,
		CanCollide = false,
	})
	make("PointLight", part, { Range = 7, Brightness = 0.8, Color = Color3.fromRGB(255, 60, 60) })
	local prompt = make("ProximityPrompt", part, {
		ActionText = "Prendi",
		ObjectText = "Nastro audio",
		HoldDuration = 1,
		MaxActivationDistance = 9,
		RequiresLineOfSight = false,
	})
	prompt.Triggered:Connect(function(player)
		if not ctx.round.active or not ctx.team.isStanding(player) or tape ~= m then
			return
		end
		m:Destroy()
		tape = nil
		player:SetAttribute("CarryingTape", true)
		setCarrierHighlight(player, true)
		ctx.notifyAll(("📼 %s ha il nastro audio! Riportatelo alla Ranger Station."):format(player.DisplayName))
	end)
	m.Parent = ctx.world
	tape = m
end

function Objectives.init(c)
	ctx = c
end

function Objectives.start(rng: Random)
	current = Config.FORCED_OBJECTIVE or LIST[rng:NextInteger(1, #LIST)]
	ctx.aggressionMultiplier = current == "Sopravvivenza" and 1.5 or 1
	local text
	if current == "Ricognizione" then
		text = ("Piazza %d telecamere attive e documenta %d prove."):format(Config.RECON_CAMERAS, Config.RECON_EVIDENCE)
	elseif current == "Caccia" then
		text = "Trova The Rake, stordiscilo con i dardi tranquillanti e catturalo."
	elseif current == "Sopravvivenza" then
		text = "Resta vivo fino all'alba. Stanotte la creatura è più aggressiva."
	else
		local poi = Forest.POIS[rng:NextInteger(2, #Forest.POIS)]
		tapePoi = poi.name
		-- Sul lato del punto di interesse rivolto verso la stazione (mai dentro rocce o acqua)
		local toStation = (Forest.STATION - poi.pos) * Vector3.new(1, 0, 1)
		local side = Vector3.new(-toStation.Z, 0, toStation.X).Unit
		local sign = rng:NextNumber() < 0.5 and -1 or 1
		local spot = poi.pos + toStation.Unit * rng:NextNumber(10, 14) + side * sign * rng:NextNumber(3.5, 6)
		spawnTape(Forest.groundAt(spot.X, spot.Z))
		text = ("Recupera il nastro audio (%s) e riportalo alla Ranger Station."):format(tapePoi)
	end
	ctx.state:SetAttribute("Objective", current)
	ctx.state:SetAttribute("ObjectiveText", text)
end

function Objectives.current(): string
	return current
end

function Objectives.progressText(): string
	local s = ctx.state
	if current == "Ricognizione" then
		return ("Camere attive %d/%d · Prove %d/%d"):format(
			s:GetAttribute("CamerasActive") or 0,
			Config.RECON_CAMERAS,
			s:GetAttribute("Evidence") or 0,
			Config.RECON_EVIDENCE
		)
	elseif current == "Caccia" then
		return ("Tracciamento %d%%"):format(math.floor(s:GetAttribute("Tracking") or 0))
	elseif current == "Sopravvivenza" then
		return "Resisti fino alle 06:00"
	end
	local carrier = tapeCarrier()
	return carrier and ("Il nastro è in mano a %s"):format(carrier.DisplayName) or ("Il nastro è %s"):format(tape and "nel bosco" or "perso")
end

-- Restituisce "win" e una descrizione quando l'obiettivo è completato
function Objectives.check(): (string?, string?)
	if ctx.round.captured then
		return "win", "The Rake è stato catturato!"
	end
	local s = ctx.state
	if current == "Ricognizione" then
		if (s:GetAttribute("CamerasActive") or 0) >= Config.RECON_CAMERAS and (s:GetAttribute("Evidence") or 0) >= Config.RECON_EVIDENCE then
			return "win", "Ricognizione completata: il bosco è sotto sorveglianza."
		end
	elseif current == "Reperto" then
		local carrier = tapeCarrier()
		if carrier and ctx.team.isStanding(carrier) then
			local hrp = carrier.Character and carrier.Character:FindFirstChild("HumanoidRootPart")
			if hrp and Forest.inStation(hrp.Position) then
				return "win", ("%s ha riportato il nastro alla Ranger Station."):format(carrier.DisplayName)
			end
		end
	end
	return nil, nil
end

function Objectives.onDawn(): (string, string)
	if current == "Sopravvivenza" then
		return "win", "È l'alba: la squadra è sopravvissuta alla notte."
	end
	return "lose", "È sorta l'alba prima che completaste l'obiettivo."
end

-- Chi porta il nastro e viene colpito lo lascia cadere
function Objectives.onDowned(player: Player)
	if not player:GetAttribute("CarryingTape") then
		return
	end
	player:SetAttribute("CarryingTape", false)
	setCarrierHighlight(player, false)
	local hrp = player.Character and player.Character:FindFirstChild("HumanoidRootPart")
	if hrp and ctx.round.active then
		spawnTape(Forest.groundAt(hrp.Position.X, hrp.Position.Z))
		ctx.notifyAll("📼 Il nastro è caduto a terra!")
	end
end

function Objectives.cleanup()
	if tape then
		tape:Destroy()
		tape = nil
	end
	for _, player in Players:GetPlayers() do
		player:SetAttribute("CarryingTape", false)
		setCarrierHighlight(player, false)
	end
end

return Objectives
