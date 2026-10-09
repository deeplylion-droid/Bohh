-- Controllo del controller World (client) nell'ambiente finto: etichetta col timer sopra le
-- incubatrici e soldi sopra le pedane. Uso (dalla radice): .tools/bin/lune run tests/ui/check_world.luau
local process = require("@lune/process")
local roblox = require("@lune/roblox")

local G = require("./gui_env")

local Vector2, Vector3, CFrame = roblox.Vector2, roblox.Vector3, roblox.CFrame
local NOW = 1760000000
local CLIENT = "StarterPlayer/StarterPlayerScripts/Client"

local services = G.makeServices({ viewport = Vector2.new(1280, 720), now = NOW, attributes = { PlotIndex = 1 } })
services.camera.CFrame = CFrame.new(0, 8, 20)
local fakeNet = {
	Event = function()
		return { OnClientEvent = G.newSignal(), FireServer = function() end }
	end,
	Function = function()
		return { InvokeServer = function() end }
	end,
}
local loader = G.makeLoader(services, { ["ReplicatedStorage/Shared/Net"] = fakeNet })
local req = loader.require

local C = {}
C.State = {
	Data = { Settings = {} },
	Ready = true,
	Watch = function(key, fn)
		G.task.spawn(fn, C.State.Data[key])
		return function() end
	end,
	WaitReady = function() end,
}
C.Lang = req(CLIENT .. "/Controllers/Lang")
C.Lang.Init(C)
C.UI = { Kit = req(CLIENT .. "/UI/Kit"), Scale = 1 }
local World = req(CLIENT .. "/Controllers/World")
World.Init(C)

-- un'incubatrice con un uovo che si schiude tra 95 s, una vuota e una pedana con 1234 monete
local Instance = G.Instance
local collection = services.CollectionService
local function part(name: string, pos: Vector3, parent)
	local p = Instance.new("Part")
	p.Name = name
	p.Position = pos
	p.CFrame = CFrame.new(pos)
	p.Size = Vector3.new(4, 1, 4)
	p.Parent = parent
	return p
end
local inc = part("Incubator1", Vector3.new(0, 1, 0), services.Workspace)
part("Ring", Vector3.new(0, 1.5, 0), inc)
inc:SetAttribute("EggRarity", "Rare")
inc:SetAttribute("Duration", 120)
inc:SetAttribute("ReadyAt", NOW + 95)
collection:AddTag(inc, "Incubator")
local empty = part("Incubator2", Vector3.new(8, 1, 0), services.Workspace)
part("Ring", Vector3.new(8, 1.5, 0), empty)
collection:AddTag(empty, "Incubator")
local egg = Instance.new("Model")
egg.Name = "IncubatingEgg"
part("Shell", Vector3.new(0, 3, 0), egg)
egg.Parent = inc
collection:AddTag(egg, "IncubatingEgg")
local pad = part("CollectPad", Vector3.new(0, 0.2, 6), services.Workspace)
pad:SetAttribute("Bank", 1234)
collection:AddTag(pad, "CollectPad")

G.task.spawn(World.Start)
G.advance(1)

local failures = {}
local function check(cond: boolean, msg: string)
	print((if cond then "ok   " else "FAIL ") .. msg)
	if not cond then
		table.insert(failures, msg)
	end
end

local gui = inc:FindFirstChild("IncubatorInfo")
check(gui ~= nil, "etichetta creata sull'incubatrice")
if gui then
	check(gui.Enabled == true, "etichetta visibile con un uovo in cova")
	local texts = {}
	for _, d in gui:GetDescendants() do
		if d:IsA("TextLabel") and d.Text ~= "" then
			table.insert(texts, d.Text)
		end
	end
	check(table.find(texts, "1:35") ~= nil, "timer 1:35 (trovato: " .. table.concat(texts, ", ") .. ")")
end
local emptyGui = empty:FindFirstChild("IncubatorInfo")
check(emptyGui ~= nil and emptyGui.Enabled == false, "nessuna etichetta sull'incubatrice vuota")

-- l'uovo e' pronto: la scritta cambia
inc:SetAttribute("ReadyAt", NOW - 1)
G.advance(0.5)
if gui then
	local ready = false
	for _, d in gui:GetDescendants() do
		if d:IsA("TextLabel") and d.Text == C.Lang.T("Ready") then
			ready = true
		end
	end
	check(ready, "scritta PRONTO! quando l'uovo e' pronto")
end

local bank = pad:FindFirstChild("Bank")
local bankText = ""
if bank then
	for _, d in bank:GetDescendants() do
		if d:IsA("TextLabel") then
			bankText = d.Text
		end
	end
end
check(bankText == "$1.23K", "soldi sulla pedana (trovato: " .. bankText .. ")")

if #failures > 0 then
	print(`{#failures} controlli falliti`)
	process.exit(1)
end
print("tutto ok")
