-- Mirino telescopico del fucile a dardi: tasto destro (o pulsante "Mirino") con il fucile in mano.
-- Prima persona, zoom 2x-8x con la rotella, reticolo con tacche, oscillazione del respiro che
-- cresce con paura e fiatone, leggera intensificazione della luce.
local RunService = game:GetService("RunService")
local Lighting = game:GetService("Lighting")
local UserInputService = game:GetService("UserInputService")
local ContextActionService = game:GetService("ContextActionService")
local TweenService = game:GetService("TweenService")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")

local Sfx = require(ReplicatedStorage:WaitForChild("Shared"):WaitForChild("Sfx"))

local Scope = {}
Scope.__index = Scope

local function make(className: string, props: { [string]: any }, parent: Instance?): any
	local inst = Instance.new(className)
	for k, v in props do
		(inst :: any)[k] = v
	end
	inst.Parent = parent
	return inst
end

function Scope.new(player: Player)
	local self = setmetatable({}, Scope)
	self.player = player
	self.active = false
	self.zoom = 4
	self.sway = 0

	local gui = make("ScreenGui", { Name = "Mirino", ResetOnSpawn = false, IgnoreGuiInset = true, Enabled = false, DisplayOrder = 4 }, player:WaitForChild("PlayerGui"))
	self.gui = gui
	-- lente circolare: tutto il resto è coperto da un bordo nero spessissimo
	local lens = make("Frame", {
		AnchorPoint = Vector2.new(0.5, 0.5),
		Position = UDim2.fromScale(0.5, 0.5),
		Size = UDim2.fromScale(0.78, 0.78),
		BackgroundTransparency = 1,
	}, gui)
	make("UIAspectRatioConstraint", { AspectRatio = 1 }, lens)
	make("UICorner", { CornerRadius = UDim.new(0.5, 0) }, lens)
	make("UIStroke", { Thickness = 3000, Color = Color3.new(0, 0, 0) }, lens)
	self.lens = lens
	-- anello interno e vignetta della lente
	local ring = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundTransparency = 1 }, lens)
	make("UICorner", { CornerRadius = UDim.new(0.5, 0) }, ring)
	make("UIStroke", { Thickness = 26, Color = Color3.fromRGB(0, 0, 0), Transparency = 0.25 }, ring)
	local inner = make("Frame", { AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromScale(0.94, 0.94), BackgroundTransparency = 1 }, lens)
	make("UICorner", { CornerRadius = UDim.new(0.5, 0) }, inner)
	make("UIStroke", { Thickness = 40, Color = Color3.fromRGB(0, 0, 0), Transparency = 0.6 }, inner)
	-- riflesso sul vetro
	local glare = make("Frame", { Size = UDim2.fromScale(1, 1), BackgroundColor3 = Color3.fromRGB(140, 170, 255), BackgroundTransparency = 0.94 }, lens)
	make("UICorner", { CornerRadius = UDim.new(0.5, 0) }, glare)
	make("UIGradient", { Rotation = 35, Transparency = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.4), NumberSequenceKeypoint.new(0.45, 1), NumberSequenceKeypoint.new(1, 1) }) }, glare)

	-- reticolo
	local ink = Color3.fromRGB(10, 10, 10)
	local function line(pos: UDim2, size: UDim2)
		make("Frame", { AnchorPoint = Vector2.new(0.5, 0.5), Position = pos, Size = size, BackgroundColor3 = ink, BorderSizePixel = 0 }, lens)
	end
	line(UDim2.fromScale(0.5, 0.5), UDim2.new(1, 0, 0, 1))
	line(UDim2.fromScale(0.5, 0.5), UDim2.new(0, 1, 1, 0))
	line(UDim2.fromScale(0.13, 0.5), UDim2.new(0.26, 0, 0, 4))
	line(UDim2.fromScale(0.87, 0.5), UDim2.new(0.26, 0, 0, 4))
	line(UDim2.fromScale(0.5, 0.87), UDim2.new(0, 4, 0.26, 0))
	for i = -4, 4 do
		if i ~= 0 then
			local len = i % 2 == 0 and 14 or 8
			line(UDim2.new(0.5 + i * 0.035, 0, 0.5, 0), UDim2.fromOffset(1, len))
			line(UDim2.new(0.5, 0, 0.5 + i * 0.035, 0), UDim2.fromOffset(len, 1))
		end
	end
	local dot = make("Frame", { AnchorPoint = Vector2.new(0.5, 0.5), Position = UDim2.fromScale(0.5, 0.5), Size = UDim2.fromOffset(4, 4), BackgroundColor3 = Color3.fromRGB(255, 40, 30), BorderSizePixel = 0 }, lens)
	make("UICorner", { CornerRadius = UDim.new(1, 0) }, dot)
	self.label = make("TextLabel", {
		AnchorPoint = Vector2.new(0.5, 0),
		Position = UDim2.new(0.5, 0, 1, 14),
		Size = UDim2.fromOffset(300, 20),
		BackgroundTransparency = 1,
		Font = Enum.Font.Code,
		TextSize = 15,
		TextColor3 = Color3.fromRGB(170, 175, 170),
	}, lens)

	self.cc = make("ColorCorrectionEffect", { Name = "Mirino", Enabled = false, Brightness = 0.12, Contrast = 0.15, TintColor = Color3.fromRGB(235, 245, 255) }, Lighting)
	return self
end

function Scope:holdingRifle(): boolean
	local char = self.player.Character
	return char ~= nil and char:FindFirstChild("Fucile a dardi") ~= nil
end

function Scope:enter()
	if self.active or not self:holdingRifle() or self.player:GetAttribute("Status") ~= "OK" then
		return
	end
	self.active = true
	self.gui.Enabled = true
	self.cc.Enabled = true
	self.savedMode = self.player.CameraMode
	self.player.CameraMode = Enum.CameraMode.LockFirstPerson
	UserInputService.MouseDeltaSensitivity = 0.3
	Sfx.new("ScopeZoom", SoundService, { Volume = 0.7, PlayOnRemove = true }):Destroy()
	local camera = workspace.CurrentCamera
	self.savedFov = camera.FieldOfView
	TweenService:Create(camera, TweenInfo.new(0.18), { FieldOfView = 70 / self.zoom }):Play()
	self.wheel = UserInputService.InputChanged:Connect(function(input)
		if input.UserInputType == Enum.UserInputType.MouseWheel then
			self.zoom = math.clamp(self.zoom + input.Position.Z, 2, 8)
			workspace.CurrentCamera.FieldOfView = 70 / self.zoom
		end
	end)
	RunService:BindToRenderStep("MirinoOscillazione", Enum.RenderPriority.Camera.Value + 2, function()
		local t = os.clock()
		local amp = (0.0012 + self.sway * 0.006) * (4 / self.zoom + 0.5)
		local camera2 = workspace.CurrentCamera
		camera2.CFrame *= CFrame.Angles(math.sin(t * 1.3) * amp, math.sin(t * 0.9 + 1) * amp * 1.4, 0)
		self.label.Text = ("%dx · dardi %d"):format(self.zoom, self.player:GetAttribute("Darts") or 0)
	end)
end

function Scope:exit()
	if not self.active then
		return
	end
	self.active = false
	self.gui.Enabled = false
	self.cc.Enabled = false
	self.player.CameraMode = self.savedMode or Enum.CameraMode.Classic
	UserInputService.MouseDeltaSensitivity = 1
	RunService:UnbindFromRenderStep("MirinoOscillazione")
	if self.wheel then
		self.wheel:Disconnect()
		self.wheel = nil
	end
	workspace.CurrentCamera.FieldOfView = self.savedFov or 70
end

function Scope:bind()
	ContextActionService:BindAction("Mirino", function(_, inputState)
		if inputState == Enum.UserInputState.Begin then
			if self.active then
				self:exit()
			else
				self:enter()
			end
		end
		return self:holdingRifle() and Enum.ContextActionResult.Sink or Enum.ContextActionResult.Pass
	end, true, Enum.UserInputType.MouseButton2, Enum.KeyCode.ButtonL2)
	ContextActionService:SetTitle("Mirino", "Mirino")
	RunService.Heartbeat:Connect(function()
		if self.active and (not self:holdingRifle() or self.player:GetAttribute("Status") ~= "OK") then
			self:exit()
		end
	end)
end

return Scope
