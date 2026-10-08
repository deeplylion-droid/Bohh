-- Schiaffo: animazione del braccio quando qualcuno colpisce, e pulsante per gli schermi touch.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Net = require(ReplicatedStorage.Shared.Net)

local Combat = {}

local C
local player = Players.LocalPlayer
local swings: { [Model]: number } = {} -- personaggio -> istante di inizio dello swing

function Combat.Init(controllers)
	C = controllers
end

-- Pulsante touch: impugna la mazza (se non ce l'ha in mano) e colpisce
function Combat.SlapButton()
	local char = player.Character
	local hum = char and char:FindFirstChildOfClass("Humanoid")
	if not hum then
		return
	end
	if (player:GetAttribute("Carrying") or 0) > 0 then
		return
	end
	local tool = char:FindFirstChild("Bat")
	if not tool then
		local backpack = player:FindFirstChildOfClass("Backpack")
		tool = backpack and backpack:FindFirstChild("Bat")
		if tool then
			hum:EquipTool(tool :: Tool)
		end
	end
	if tool then
		(tool :: Tool):Activate()
	end
	Net.Event("Swing"):FireServer()
end

local function swingPose(char: Model, t: number)
	-- arco veloce del braccio destro in 0.35 s
	local k = math.clamp(t / 0.35, 0, 1)
	local angle = math.sin(k * math.pi) * math.rad(120)
	local upper = char:FindFirstChild("RightUpperArm")
	local torso = char:FindFirstChild("Torso")
	local motor = if upper then upper:FindFirstChild("RightShoulder") elseif torso then torso:FindFirstChild("Right Shoulder") else nil
	if motor and motor:IsA("Motor6D") then
		if upper then
			motor.Transform = motor.Transform * CFrame.Angles(angle, 0, -angle * 0.4)
		else
			motor.Transform = motor.Transform * CFrame.Angles(0, 0, angle)
		end
	end
end

function Combat.Start()
	-- lo swing di qualsiasi giocatore (inviato dal server come effetto)
	C.Effects.On("Swing", function(params)
		local p = Players:GetPlayerByUserId(params.userId)
		if p and p.Character then
			swings[p.Character] = os.clock()
			C.Audio.Play("Whoosh", (p.Character:GetPivot()).Position, 0.6)
		end
	end)
	RunService.Stepped:Connect(function()
		local now = os.clock()
		for char, t0 in swings do
			local t = now - t0
			if t > 0.35 or not char.Parent then
				swings[char] = nil
			else
				swingPose(char, t)
			end
		end
	end)
end

return Combat
