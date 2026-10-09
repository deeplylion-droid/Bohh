-- Codici premio.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)
local Kit = require(script.Parent.Parent.Kit)

local Theme = Kit.Theme
local New = Kit.New

local Panel = {}

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("CodesTitle"), UDim2.fromOffset(560, 330), "Orange", parent)
	local box = New("TextBox", {
		BackgroundColor3 = Color3.fromRGB(255, 255, 255),
		Size = UDim2.new(1, -20, 0, 66),
		Position = UDim2.fromOffset(10, 40),
		Font = Theme.TitleFont,
		TextScaled = true,
		TextColor3 = Theme.Outline,
		PlaceholderColor3 = Color3.fromRGB(150, 140, 180),
		ClearTextOnFocus = false,
		Text = "",
		Parent = p.Body,
	}, { Kit.Corner(UDim.new(0, 18)), Kit.Stroke(4), Kit.Padding(12) })
	local result = Kit.Text({
		Font = Theme.BodyFont,
		Size = UDim2.new(1, -20, 0, 28),
		Position = UDim2.fromOffset(10, 116),
		Stroke = 2,
		Text = "",
		Parent = p.Body,
	})
	local busy = false
	local redeem = Kit.Button({
		Text = T("Redeem"),
		Color = "Green",
		Size = UDim2.fromOffset(260, 62),
		Position = UDim2.new(0.5, 0, 0, 160),
		AnchorPoint = Vector2.new(0.5, 0),
		TextSize = 30,
		Parent = p.Body,
		OnClick = function()
			if busy or box.Text == "" then
				return
			end
			busy = true
			local ok, okRes, key = pcall(function()
				return Net.Function("RedeemCode"):InvokeServer(box.Text)
			end)
			busy = false
			if ok then
				result.Text = T(key or "CodeInvalid")
				result.TextColor3 = if okRes then Theme.Green else Theme.Red
				if okRes then
					box.Text = ""
				end
			end
		end,
	})
	local function refresh()
		p.Title.Text = T("CodesTitle")
		box.PlaceholderText = T("CodePlaceholder")
		redeem.SetText(T("Redeem"))
	end
	refresh()
	C.Lang.Changed:Connect(refresh)
	return {
		Frame = p.Frame,
		Close = p.Close,
		OnOpen = function()
			result.Text = ""
		end,
	}
end

return Panel
