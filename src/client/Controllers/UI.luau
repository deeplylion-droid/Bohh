-- Gestione dell'interfaccia: ScreenGui (HUD, pannelli, overlay), scala per schermo, apertura pannelli.

local Players = game:GetService("Players")
local UserInputService = game:GetService("UserInputService")

local Kit = require(script.Parent.Parent.UI.Kit)

local UI = {}

local C
local player = Players.LocalPlayer
local guis: { [string]: ScreenGui } = {}
local panels: { [string]: any } = {}
local openName: string? = nil

UI.Kit = Kit

local function makeGui(name: string, order: number, ignoreInset: boolean): ScreenGui
	local gui = Kit.New("ScreenGui", {
		Name = name,
		DisplayOrder = order,
		ResetOnSpawn = false,
		IgnoreGuiInset = ignoreInset,
		ZIndexBehavior = Enum.ZIndexBehavior.Sibling,
	})
	Kit.New("UIScale", { Name = "Scale", Parent = gui })
	gui.Parent = player:WaitForChild("PlayerGui")
	guis[name] = gui
	return gui
end

local function rescale()
	local cam = workspace.CurrentCamera
	if not cam then
		return
	end
	local v = cam.ViewportSize
	local s = math.min(v.X / 1280, v.Y / 720)
	if UserInputService.TouchEnabled and v.Y < 600 then
		s *= 1.15 -- telefoni: elementi un po' piu' grandi
	end
	s = math.clamp(s, 0.5, 1.3)
	UI.Scale = s
	for _, gui in guis do
		local sc = gui:FindFirstChild("Scale") :: UIScale?
		if sc and gui.Name ~= "Overlay" then
			sc.Scale = s
		end
	end
end

function UI.Gui(name: string): ScreenGui
	return guis[name]
end

-- Registra un pannello: module.Build(parent, C) -> { Frame, Refresh?, OnOpen? }
function UI.RegisterPanel(name: string, panel)
	panels[name] = panel
	if panel.Close then
		panel.Close.Face.Activated:Connect(function()
			UI.Close()
		end)
	end
end

function UI.Open(name: string)
	if openName == name then
		return
	end
	UI.Close()
	local p = panels[name]
	if not p then
		return
	end
	openName = name
	p.Frame.Visible = true
	Kit.Pop(p.Frame)
	if p.OnOpen then
		task.spawn(p.OnOpen)
	end
	C.Audio.Play("Open")
end

function UI.Close()
	if openName then
		local p = panels[openName]
		openName = nil
		if p then
			p.Frame.Visible = false
			if p.OnClose then
				task.spawn(p.OnClose)
			end
		end
	end
end

function UI.Toggle(name: string)
	if openName == name then
		UI.Close()
	else
		UI.Open(name)
	end
end

function UI.IsOpen(name: string?): boolean
	if name then
		return openName == name
	end
	return openName ~= nil
end

function UI.Init(controllers)
	C = controllers
	makeGui("HUD", 2, false)
	makeGui("Panels", 5, false)
	makeGui("Overlay", 9, true)
	makeGui("Top", 12, true)
end

function UI.Start()
	rescale()
	workspace.CurrentCamera:GetPropertyChangedSignal("ViewportSize"):Connect(rescale)
	C.State.WaitReady()
	local Hud = require(script.Parent.Parent.UI.Hud)
	UI.Hud = Hud.Build(guis.HUD, C)
	for _, name in { "Shop", "Upgrades", "Index", "Gifts", "Codes", "Settings", "Admin" } do
		local module = script.Parent.Parent.UI.Panels:FindFirstChild(name)
		if module then
			local ok, panel = pcall(function()
				return require(module).Build(guis.Panels, C)
			end)
			if ok and panel then
				UI.RegisterPanel(name, panel)
			else
				warn(`[UI] pannello {name}: {panel}`)
			end
		end
	end
	UserInputService.InputBegan:Connect(function(input, processed)
		if not processed and input.KeyCode == Enum.KeyCode.Escape then
			UI.Close()
		end
	end)
end

return UI
