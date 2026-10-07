-- Pose delle braccia (client, sul proprio personaggio R15):
--  - braccio destro: con torcia o fucile in mano segue la visuale anche in verticale, così il fascio
--    della torcia illumina dove guardi;
--  - braccio sinistro: si alza davanti al viso quando guardi lo smartwatch.
-- Modifica il C0 delle giunture partendo da quello originale, così si somma alle animazioni.
local RunService = game:GetService("RunService")

local ArmPose = {}

function ArmPose.start(player: Player, watchShown: () -> boolean)
	local originals: { [Motor6D]: CFrame } = {}
	local watchBlend = 0

	local function motor(char: Model, partName: string, jointName: string): Motor6D?
		local part = char:FindFirstChild(partName)
		local joint = part and part:FindFirstChild(jointName)
		if joint and joint:IsA("Motor6D") then
			if not originals[joint] then
				originals[joint] = joint.C0
			end
			return joint
		end
		return nil
	end

	player.CharacterAdded:Connect(function()
		table.clear(originals)
	end)

	RunService.Stepped:Connect(function(_, dt)
		local char = player.Character
		if not char then
			return
		end
		local camera = workspace.CurrentCamera
		local holding = char:FindFirstChild("Torcia") or char:FindFirstChild("Fucile a dardi")
		local right = motor(char, "RightUpperArm", "RightShoulder")
		if right then
			local pitch = 0
			if holding and player:GetAttribute("Status") == "OK" then
				pitch = math.clamp(math.asin(math.clamp(camera.CFrame.LookVector.Y, -1, 1)), -1.1, 1.2)
			end
			right.C0 = originals[right] * CFrame.Angles(pitch, 0, 0)
		end
		local target = watchShown() and 1 or 0
		watchBlend += (target - watchBlend) * math.min(1, dt * 10)
		local left = motor(char, "LeftUpperArm", "LeftShoulder")
		local elbow = motor(char, "LeftLowerArm", "LeftElbow")
		if left then
			left.C0 = originals[left] * CFrame.Angles(1.35 * watchBlend, 0, -0.55 * watchBlend)
		end
		if elbow then
			elbow.C0 = originals[elbow] * CFrame.Angles(1.3 * watchBlend, 0, 0)
		end
	end)
end

return ArmPose
