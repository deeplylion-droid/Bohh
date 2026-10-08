-- Opzioni: musica, effetti sonori, grafica leggera, lingua.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Net = require(ReplicatedStorage.Shared.Net)
local Kit = require(script.Parent.Parent.Kit)

local Panel = {}

local ROWS = {
	{ key = "Music", label = "Setting_Music", icon = "Music" },
	{ key = "Sfx", label = "Setting_Sfx", icon = "Sound" },
	{ key = "LowGfx", label = "Setting_LowGfx", icon = "Graphics" },
	{ key = "Lang", label = "Setting_Language", icon = "Language" },
}

function Panel.Build(parent: Instance, C)
	local T = C.Lang.T
	local p = Kit.Panel(T("SettingsTitle"), UDim2.fromOffset(580, 450), "Grey", parent)
	local rows = {}
	for i, r in ROWS do
		local card = Kit.Card({ Size = UDim2.new(1, -10, 0, 74), Position = UDim2.new(0, 5, 0, 30 + (i - 1) * 86), Parent = p.Body })
		Kit.Icon(r.icon, { Size = UDim2.fromOffset(46, 46), Position = UDim2.fromOffset(14, 14), Parent = card })
		local label = Kit.Text({ Size = UDim2.new(0.55, 0, 0, 34), Position = UDim2.fromOffset(74, 20), TextXAlignment = Enum.TextXAlignment.Left, Parent = card })
		local btn = Kit.Button({ Text = "", Color = "Green", Size = UDim2.fromOffset(150, 54), Position = UDim2.new(1, -162, 0, 10), TextSize = 26, Parent = card, OnClick = function()
			local settings = C.State.Get("Settings") or {}
			local value
			if r.key == "Lang" then
				value = if C.Lang.Current == "it" then "en" else "it"
				C.Lang.Set(value)
			else
				value = not settings[r.key]
			end
			settings[r.key] = value
			Net.Event("SetSetting"):FireServer(r.key, value)
			C.Audio.ApplySettings(settings)
			Panel.refresh()
		end })
		rows[r.key] = { label = label, btn = btn, def = r }
	end
	function Panel.refresh()
		local settings = C.State.Get("Settings") or {}
		p.Title.Text = T("SettingsTitle")
		for key, row in rows do
			row.label.Text = T(row.def.label)
			if key == "Lang" then
				row.btn.SetText(if C.Lang.Current == "it" then "ITALIANO" else "ENGLISH")
				row.btn.SetColor("Blue")
			else
				local on = settings[key]
				if key == "LowGfx" then
					on = settings[key] == true
				elseif on == nil then
					on = true
				end
				row.btn.SetText(if on then T("On") else T("Off"))
				row.btn.SetColor(if on then "Green" else "Grey")
			end
		end
	end
	C.Lang.Changed:Connect(Panel.refresh)
	return { Frame = p.Frame, Close = p.Close, OnOpen = Panel.refresh }
end

return Panel
