-- Mostra lo stato del round in alto allo schermo e fa ruotare le monete (solo effetto visivo).
local Players = game:GetService("Players")
local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local player = Players.LocalPlayer
local gameState = ReplicatedStorage:WaitForChild("GameState")
local status = gameState:WaitForChild("Status") :: StringValue
local timeLeft = gameState:WaitForChild("TimeLeft") :: IntValue

local gui = Instance.new("ScreenGui")
gui.Name = "CoinRushHUD"
gui.ResetOnSpawn = false

local label = Instance.new("TextLabel")
label.AnchorPoint = Vector2.new(0.5, 0)
label.Position = UDim2.new(0.5, 0, 0, 12)
label.Size = UDim2.new(0, 420, 0, 44)
label.BackgroundColor3 = Color3.fromRGB(20, 20, 30)
label.BackgroundTransparency = 0.25
label.TextColor3 = Color3.fromRGB(255, 255, 255)
label.Font = Enum.Font.GothamBold
label.TextScaled = true
label.Parent = gui

local corner = Instance.new("UICorner")
corner.CornerRadius = UDim.new(0, 10)
corner.Parent = label

local padding = Instance.new("UIPadding")
padding.PaddingLeft = UDim.new(0, 12)
padding.PaddingRight = UDim.new(0, 12)
padding.PaddingTop = UDim.new(0, 6)
padding.PaddingBottom = UDim.new(0, 6)
padding.Parent = label

local function refresh()
	local t = timeLeft.Value
	if t > 0 then
		label.Text = string.format("%s  •  %d:%02d", status.Value, t // 60, t % 60)
	else
		label.Text = status.Value
	end
end

status.Changed:Connect(refresh)
timeLeft.Changed:Connect(refresh)
refresh()

gui.Parent = player:WaitForChild("PlayerGui")

RunService.RenderStepped:Connect(function(dt)
	local folder = workspace:FindFirstChild("CoinRushCoins")
	if not folder then
		return
	end
	for _, coin in folder:GetChildren() do
		if coin:IsA("BasePart") then
			coin.CFrame *= CFrame.Angles(0, dt * 3, 0)
		end
	end
end)
