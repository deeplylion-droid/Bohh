-- Ragdoll comico: per qualche istante i giunti rigidi lasciano il posto a snodi sferici.
-- Nei personaggi R15 attuali i giunti sono AnimationConstraint e ognuno ha gia' il suo snodo
-- sferico attivo (<Nome>BallSocket): basta spegnere il giunto. Nei personaggi R6 sono Motor6D:
-- si aggiungono snodi sferici spenti che si accendono al loro posto.
-- Il server gestisce i giunti; il client proprietario mette l'umanoide nello stato Physics
-- e applica la spinta (vedi client/Controllers/Ragdoll).

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)

local RagdollService = {}

local _S
local knockEvent: RemoteEvent
local tokens: { [Player]: number } = {}

function RagdollService.Init(services)
	_S = services
end

local function setupRig(character: Model)
	for _, motor in character:GetDescendants() do
		if
			motor:IsA("Motor6D")
			and motor.Part0
			and motor.Part1
			and motor.Name ~= "RootJoint"
			and motor.Name ~= "Root"
		then
			local a0 = Instance.new("Attachment")
			a0.Name = "RagA_" .. motor.Name
			a0.CFrame = motor.C0
			a0.Parent = motor.Part0
			local a1 = Instance.new("Attachment")
			a1.Name = "RagB_" .. motor.Name
			a1.CFrame = motor.C1
			a1.Parent = motor.Part1
			local socket = Instance.new("BallSocketConstraint")
			socket.Name = "Rag_" .. motor.Name
			socket.Attachment0 = a0
			socket.Attachment1 = a1
			socket.LimitsEnabled = true
			socket.TwistLimitsEnabled = true
			socket.UpperAngle = if string.find(motor.Name, "Neck") then 30 else 70
			socket.TwistLowerAngle = -45
			socket.TwistUpperAngle = 45
			socket.Enabled = false
			socket.Parent = motor.Parent
			motor:SetAttribute("RagSocket", socket.Name)
		end
	end
end

local function setRagdoll(character: Model, on: boolean)
	for _, joint in character:GetDescendants() do
		if joint:IsA("Motor6D") then
			local socketName = joint:GetAttribute("RagSocket")
			if socketName then
				local socket = joint.Parent and joint.Parent:FindFirstChild(socketName)
				joint.Enabled = not on
				if socket then
					(socket :: BallSocketConstraint).Enabled = on
				end
			end
		elseif joint:IsA("AnimationConstraint") and joint.Name ~= "Root" and joint.Name ~= "Neck" then
			-- la radice tiene unito il corpo alla HumanoidRootPart; il collo resta rigido perche'
			-- un collo staccato puo' far morire l'umanoide (RequiresNeck)
			local socket = joint.Parent and joint.Parent:FindFirstChild(joint.Name .. "BallSocket")
			if socket and socket:IsA("BallSocketConstraint") then
				socket.Enabled = true
				joint.Enabled = not on
			end
		end
	end
	-- solo le parti del corpo (figlie dirette del personaggio): i modelli portati sopra la testa
	-- possono avere parti chiamate Head, Legs, Feet... che non devono diventare solide
	for _, d in character:GetChildren() do
		if
			d:IsA("BasePart")
			and (
				d.Name == "Head"
				or string.find(d.Name, "Arm")
				or string.find(d.Name, "Leg")
				or string.find(d.Name, "Hand")
				or string.find(d.Name, "Foot")
			)
		then
			d.CanCollide = on
		end
	end
end

-- Scioglie (on = true) o ricompone i giunti di un personaggio (anche senza giocatore: test)
RagdollService.SetRig = setRagdoll

-- Mette a terra il giocatore per 'duration' secondi con una spinta 'velocity' (opzionale)
function RagdollService.Ragdoll(player: Player, duration: number, velocity: Vector3?)
	local character = player.Character
	if not character then
		return
	end
	tokens[player] = (tokens[player] or 0) + 1
	local token = tokens[player]
	setRagdoll(character, true)
	player:SetAttribute("Ragdolled", true)
	knockEvent:FireClient(player, velocity or Vector3.zero, duration)
	task.delay(duration, function()
		if tokens[player] == token then
			RagdollService.Recover(player)
		end
	end)
end

function RagdollService.Recover(player: Player)
	local character = player.Character
	tokens[player] = (tokens[player] or 0) + 1
	if character then
		setRagdoll(character, false)
	end
	player:SetAttribute("Ragdolled", false)
end

function RagdollService.IsRagdolled(player: Player): boolean
	return player:GetAttribute("Ragdolled") == true
end

function RagdollService.Start()
	knockEvent = Net.Event("Knockback")
	local function setup(player: Player)
		player.CharacterAdded:Connect(function(character)
			character:WaitForChild("Humanoid", 10)
			task.wait()
			setupRig(character)
			player:SetAttribute("Ragdolled", false)
		end)
	end
	for _, p in Players:GetPlayers() do
		setup(p)
	end
	Players.PlayerAdded:Connect(setup)
	Players.PlayerRemoving:Connect(function(p)
		tokens[p] = nil
	end)
end

return RagdollService
