-- Gestione dell'interfaccia: ScreenGui (HUD, pannelli, overlay), scala per schermo, apertura pannelli.

local GuiService = game:GetService("GuiService")
local Players = game:GetService("Players")
local StarterGui = game:GetService("StarterGui")
local UserInputService = game:GetService("UserInputService")

local Kit = require(script.Parent.Parent.UI.Kit)

local UI = {}

local C
local player = Players.LocalPlayer
local guis: { [string]: ScreenGui } = {}
local panels: { [string]: any } = {}
local openName: string? = nil
local fitPanel: (panel: any) -> () -- definita piu' sotto (serve anche a rescale)

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
	if openName and panels[openName] then
		local frame = panels[openName].Frame
		fitPanel(panels[openName])
		local sc = frame:FindFirstChildOfClass("UIScale")
		if sc then
			sc.Scale = frame:GetAttribute("BaseScale") or 1
		end
	end
end

function UI.Gui(name: string): ScreenGui
	return guis[name]
end

-- Spazio libero per i pannelli: sotto le monete (in alto al centro) e sopra il fondo dello schermo
local PANEL_TOP = 92
local PANEL_BOTTOM = 10

-- Adatta un pannello allo spazio libero (coordinate dell'interfaccia scalata). I pannelli che
-- scorrono (Resizable) sugli schermi bassi diventano piu' bassi e larghi invece di rimpicciolire,
-- cosi' sui telefoni i testi restano leggibili; gli altri si rimpiccioliscono.
function fitPanel(panel)
	local frame = panel.Frame :: GuiObject
	local cam = workspace.CurrentCamera
	if not cam then
		return
	end
	local design = frame:GetAttribute("DesignSize")
	if typeof(design) ~= "Vector2" then
		design = Vector2.new(frame.Size.X.Offset, frame.Size.Y.Offset)
		frame:SetAttribute("DesignSize", design)
	end
	local s = UI.Scale or 1
	local inset = GuiService:GetGuiInset().Y
	local w = cam.ViewportSize.X / s
	local h = (cam.ViewportSize.Y - inset) / s
	-- sui telefoni il pannello puo' coprire le monete
	local top = if UserInputService.TouchEnabled and cam.ViewportSize.Y < 600 then 8 else PANEL_TOP
	local freeH = h - top - PANEL_BOTTOM
	-- il nastro del titolo sporge di 26 sopra, la X di chiusura di 28 a destra
	local extraH, extraW = 26 + 8, 2 * 30
	local size = design
	if panel.Resizable and design.Y + extraH > freeH then
		-- sugli schermi molto larghi (telefoni in orizzontale) anche piu' largo
		local width = if w / h > 2.1 then math.min(design.X * 1.3, w - 80) else design.X
		size = Vector2.new(width, math.max(360, freeH - extraH))
	end
	frame.Size = UDim2.fromOffset(size.X, size.Y)
	local fit = math.clamp(math.min(freeH / (size.Y + extraH), (w - 16) / (size.X + extraW)), 0.4, 1)
	frame:SetAttribute("BaseScale", fit)
	frame.Position = UDim2.new(0.5, 0, 0, top + freeH / 2 + 13 * fit)
end

-- Mentre un pannello e' aperto l'elenco dei giocatori e la barra degli strumenti di Roblox
-- (sopra a tutto) non coprono la X di chiusura e il fondo del pannello
local function setCoreHidden(hidden: boolean)
	for _, t in { Enum.CoreGuiType.PlayerList, Enum.CoreGuiType.Backpack } do
		pcall(StarterGui.SetCoreGuiEnabled, StarterGui, t, not hidden)
	end
end
UI.SetCoreHidden = setCoreHidden

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
	fitPanel(p)
	setCoreHidden(true)
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
		setCoreHidden(false)
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
