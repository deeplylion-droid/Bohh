-- Lato client del ragdoll: il proprio umanoide passa allo stato Physics e riceve la spinta.

local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)

local Ragdoll = {}

local C
local player = Players.LocalPlayer

function Ragdoll.Init(controllers)
	C = controllers
end

local function humanoid(): Humanoid?
	local char = player.Character
	return char and char:FindFirstChildOfClass("Humanoid")
end

function Ragdoll.Start()
	Net.Event("Knockback").OnClientEvent:Connect(function(velocity: Vector3, _duration: number)
		local hum = humanoid()
		local char = player.Character
		local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
		if not hum or not hrp then
			return
		end
		hum:SetStateEnabled(Enum.HumanoidStateType.GettingUp, false)
		hum:ChangeState(Enum.HumanoidStateType.Physics)
		hrp.AssemblyLinearVelocity = velocity
		hrp.AssemblyAngularVelocity = Vector3.new(math.random(-6, 6), math.random(-3, 3), math.random(-6, 6))
		C.Effects.CameraShake(0.35, 0.6)
	end)
	player:GetAttributeChangedSignal("Ragdolled"):Connect(function()
		if player:GetAttribute("Ragdolled") == false then
			local hum = humanoid()
			if hum then
				hum:SetStateEnabled(Enum.HumanoidStateType.GettingUp, true)
				hum:ChangeState(Enum.HumanoidStateType.GettingUp)
			end
		end
	end)
	player.CharacterAdded:Connect(function(char)
		local hum = char:WaitForChild("Humanoid") :: Humanoid
		hum:SetStateEnabled(Enum.HumanoidStateType.GettingUp, true)
	end)
end

return Ragdoll
