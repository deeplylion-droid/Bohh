-- Codici premio.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)
local Kit = require(script.Parent.Parent.Kit)

local Theme = Kit.Theme
local New = Kit.New

local Panel = {}

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("CodesTitle"), UDim2.fromOffset(560, 330), "Orange", parent, "Codes")
	local box = New("TextBox", {
		BackgroundColor3 = Theme.Card,
		Size = UDim2.new(1, -20, 0, 66),
		Position = UDim2.fromOffset(10, 40),
		FontFace = Theme.TitleFont,
		TextScaled = true,
		TextColor3 = Theme.Ink,
		PlaceholderColor3 = Color3.fromRGB(160, 156, 192),
		ClearTextOnFocus = false,
		Text = "",
		Parent = p.Body,
	}, {
		Kit.Corner(UDim.new(0, 20)),
		Kit.Stroke(3, Theme.Buttons.Orange[2]),
		New("UIPadding", {
			PaddingLeft = UDim.new(0, 20),
			PaddingRight = UDim.new(0, 20),
			PaddingTop = UDim.new(0, 14),
			PaddingBottom = UDim.new(0, 14),
		}),
	})
	local resultPill = New("Frame", {
		Size = UDim2.new(1, -60, 0, 34),
		Position = UDim2.new(0.5, 0, 0, 114),
		AnchorPoint = Vector2.new(0.5, 0),
		Visible = false,
		Parent = p.Body,
	}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(2.5, Theme.Text) })
	local result = Kit.Text({
		Font = Theme.HeadFont,
		Size = UDim2.new(1, -28, 0.7, 0),
		Position = UDim2.new(0, 14, 0.15, 0),
		Stroke = false,
		Text = "",
		Parent = resultPill,
	})
	-- la pillola compare quando c'e' un esito
	result:GetPropertyChangedSignal("Text"):Connect(function()
		resultPill.Visible = result.Text ~= ""
	end)
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
				Kit.PaintNamed(resultPill, if okRes then "Green" else "Red")
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
