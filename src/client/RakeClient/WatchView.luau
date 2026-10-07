-- Consultare lo smartwatch: con G il braccio sinistro del personaggio si alza (ArmPose) e la visuale
-- si avvicina al polso fino a inquadrare il quadrante 3D con i parametri vitali; con G torna normale.
local RunService = game:GetService("RunService")

local WatchView = {}

local ARM_PARTS = { "LeftUpperArm", "LeftLowerArm", "LeftHand", "Left Arm" }

local function ease(t: number): number
	return t * t * (3 - 2 * t)
end

function WatchView.start(player: Player, hud, isBlocked: () -> boolean)
	local blend = 0
	local fromCF: CFrame? = nil
	local active = false

	RunService:BindToRenderStep("VistaOrologio", Enum.RenderPriority.Camera.Value + 6, function(dt)
		local char = player.Character
		local hum = char and char:FindFirstChildOfClass("Humanoid")
		if hud.watchShown and (player:GetAttribute("Status") ~= "OK" or isBlocked()) then
			hud:setWatchVisible(false)
		end
		local want = hud.watchShown and 1 or 0
		blend = math.clamp(blend + (want > blend and dt / 0.5 or -dt / 0.35), 0, 1)
		local camera = workspace.CurrentCamera
		if blend <= 0 then
			if active then
				active = false
				camera.CameraType = Enum.CameraType.Custom
				if hum then
					camera.CameraSubject = hum
				end
			end
			fromCF = nil
			return
		end
		local arm = char and (char:FindFirstChild("LeftLowerArm") or char:FindFirstChild("Left Arm"))
		local face = arm and arm:FindFirstChild("SchermoOrologio") :: BasePart?
		if not face then
			return
		end
		if not active then
			active = true
			fromCF = camera.CFrame
			camera.CameraType = Enum.CameraType.Scriptable
		end
		-- il braccio e l'orologio restano visibili anche in prima persona
		for _, name in ARM_PARTS do
			local p = char:FindFirstChild(name)
			if p and p:IsA("BasePart") then
				p.LocalTransparencyModifier = 0
				for _, d in p:GetChildren() do
					if d:IsA("BasePart") then
						d.LocalTransparencyModifier = 0
					end
				end
			end
		end
		local normal = face.CFrame.LookVector
		local goal = CFrame.lookAt(face.Position + normal * 1.35 + Vector3.new(0, 0.12, 0), face.Position)
		camera.CFrame = (fromCF or camera.CFrame):Lerp(goal, ease(blend))
	end)
end

return WatchView
