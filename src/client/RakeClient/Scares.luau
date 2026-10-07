-- Spaventi locali: jumpscare quando la creatura ti abbatte (la visuale viene strappata sulla sua
-- faccia, urlo distorto, tremore e lampi rossi) e stacco musicale quando ti si mostra davanti.
local RunService = game:GetService("RunService")
local SoundService = game:GetService("SoundService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Sfx = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Sfx"))

local Scares = {}

local function rakeParts()
	local folder = workspace:FindFirstChild("RakeHunt")
	local rake = folder and folder:FindFirstChild("TheRake")
	local root = rake and rake:FindFirstChild("HumanoidRootPart") :: BasePart?
	local head = rake and rake:FindFirstChild("Head", true)
	return root, (head and head:IsA("Bone")) and head or nil
end

function Scares.start(player: Player, state: Folder, onFlash: () -> ())
	local gui = Instance.new("ScreenGui")
	gui.Name = "Jumpscare"
	gui.IgnoreGuiInset = true
	gui.ResetOnSpawn = false
	gui.DisplayOrder = 20
	gui.Parent = player:WaitForChild("PlayerGui")
	local red = Instance.new("Frame")
	red.Size = UDim2.fromScale(1, 1)
	red.BackgroundColor3 = Color3.fromRGB(160, 0, 0)
	red.BackgroundTransparency = 1
	red.BorderSizePixel = 0
	red.Parent = gui
	local active = false

	local function jumpscare()
		local root, head = rakeParts()
		local char = player.Character
		local hrp = char and char:FindFirstChild("HumanoidRootPart") :: BasePart?
		if active or not root or not head or not hrp or (root.Position - hrp.Position).Magnitude > 18 then
			return
		end
		active = true
		local camera = workspace.CurrentCamera
		local savedType, savedFov = camera.CameraType, camera.FieldOfView
		camera.CameraType = Enum.CameraType.Scriptable
		camera.FieldOfView = 52
		Sfx.new("Jumpscare", SoundService, { Volume = 2.6, PlayOnRemove = true }):Destroy()
		onFlash()
		local start = os.clock()
		RunService:BindToRenderStep("Jumpscare", Enum.RenderPriority.Camera.Value + 10, function()
			local t = os.clock() - start
			local headCF = head.TransformedWorldCFrame
			local face = root.CFrame.LookVector
			local eyePos = headCF.Position
			local shake = math.max(0.05, 0.35 * (1 - t / 1.3))
			local camPos = eyePos + face * (2.2 - math.min(t, 0.25) * 2) + Vector3.new(0, 0.15, 0)
			camera.CFrame = CFrame.lookAt(camPos, eyePos) * CFrame.Angles((math.random() - 0.5) * shake, (math.random() - 0.5) * shake, (math.random() - 0.5) * shake * 1.5)
			red.BackgroundTransparency = (math.floor(t * 18) % 2 == 0) and 0.55 or 0.85
		end)
		task.delay(1.3, function()
			RunService:UnbindFromRenderStep("Jumpscare")
			red.BackgroundTransparency = 1
			camera.CameraType = savedType == Enum.CameraType.Scriptable and Enum.CameraType.Custom or savedType
			camera.FieldOfView = savedFov
			local hum = player.Character and player.Character:FindFirstChildOfClass("Humanoid")
			if hum then
				camera.CameraSubject = hum
			end
			active = false
		end)
	end

	player:GetAttributeChangedSignal("Status"):Connect(function()
		if player:GetAttribute("Status") == "Braccato" then
			jumpscare()
		end
	end)

	-- stacco musicale quando si mostra immobile nel tuo campo visivo
	local stung = false
	RunService.Heartbeat:Connect(function()
		if state:GetAttribute("RakeState") ~= "Territoriale" then
			stung = false
			return
		end
		if stung then
			return
		end
		local root = rakeParts()
		if not root or root.AssemblyLinearVelocity.Magnitude > 3 then
			return
		end
		local camera = workspace.CurrentCamera
		local to = root.Position - camera.CFrame.Position
		if to.Magnitude < 70 and camera.CFrame.LookVector:Dot(to.Unit) > 0.6 then
			stung = true
			Sfx.new("Sting", SoundService, { Volume = 1.6, PlayOnRemove = true }):Destroy()
		end
	end)
end

return Scares
