-- Pose delle braccia (client, sul proprio personaggio R15):
--  - braccio destro: con torcia o fucile in mano segue la visuale anche in verticale, così il fascio
--    della torcia illumina dove guardi;
--  - braccio sinistro: si alza davanti al viso quando guardi lo smartwatch.
-- Modifica il C0 delle giunture partendo da quello originale, così si somma alle animazioni.
local RunService = game:GetService("RunService")

local ArmPose = {}

function ArmPose.start(player: Player, watchShown: () -> boolean, remotes: Folder)
	-- fascio della torcia: orientato ogni frame come la visuale (anche in verticale), e inviato al
	-- server perché anche gli altri giocatori e la creatura lo vedano puntare dove guardi
	local lastSent, lastLook = 0, Vector3.zero
	RunService:BindToRenderStep("PuntaTorcia", Enum.RenderPriority.Camera.Value + 5, function()
		local char = player.Character
		local tool = char and char:FindFirstChild("Torcia")
		local lens = tool and tool:FindFirstChild("Lente")
		local beam = lens and lens:FindFirstChild("Fascio") :: Attachment?
		if not beam or not lens or not lens:IsA("BasePart") then
			return
		end
		local look = workspace.CurrentCamera.CFrame.LookVector
		beam.WorldCFrame = CFrame.lookAt(lens.Position, lens.Position + look)
		local now = os.clock()
		if now - lastSent > 0.07 and look:Dot(lastLook) < 0.9995 then
			lastSent, lastLook = now, look
			remotes.AimTorch:FireServer(look)
		end
	end)

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
		watchBlend = math.clamp(watchBlend + (target > watchBlend and dt / 0.45 or -dt / 0.3), 0, 1)
		local left = motor(char, "LeftUpperArm", "LeftShoulder")
		local elbow = motor(char, "LeftLowerArm", "LeftElbow")
		-- braccio sinistro: spalla in avanti e verso il centro, gomito piegato, avambraccio ruotato
		-- in modo che il quadrante (lato esterno del polso) guardi verso il viso
		local e = watchBlend * watchBlend * (3 - 2 * watchBlend)
		if left then
			left.C0 = originals[left] * CFrame.Angles(1.25 * e, -0.5 * e, -0.35 * e)
		end
		if elbow then
			elbow.C0 = originals[elbow] * CFrame.Angles(1.45 * e, 1.2 * e, 0)
		end
	end)
end

return ArmPose
