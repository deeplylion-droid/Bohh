-- Ambiente finto per eseguire il codice dell'interfaccia con Lune: istanze GUI con proprieta' e
-- figli, servizi minimi, segnali muti e uno scheduler che esegue solo il "primo istante".
-- Serve a tests/ui/render_ui.luau, che esporta l'albero delle istanze per disegnarlo in HTML.
local fs = require("@lune/fs")
local luau = require("@lune/luau")
local serde = require("@lune/serde")
local roblox = require("@lune/roblox")

local G = {}

local UDim2, UDim, Vector2, Vector3, Color3 = roblox.UDim2, roblox.UDim, roblox.Vector2, roblox.Vector3, roblox.Color3
local ColorSequence, NumberSequence, Enum = roblox.ColorSequence, roblox.NumberSequence, roblox.Enum
local CFrame = roblox.CFrame

G.unknown = {} -- membri sconosciuti letti dal codice (aiuta a completare il finto)

---------------------------------------------------------------------------------------------
-- Segnali muti
---------------------------------------------------------------------------------------------
local frameSignals = {} -- RenderStepped/Heartbeat/Stepped: chiamati a ogni fotogramma di G.advance
local function newSignal(frame: boolean?)
	local sig = { handlers = {}, waiting = {}, frame = frame == true }
	if frame then
		table.insert(frameSignals, sig)
	end
	function sig:Connect(fn)
		table.insert(self.handlers, fn)
		local conn = { Connected = true }
		function conn.Disconnect()
			conn.Connected = false
			local i = table.find(self.handlers, fn)
			if i then
				table.remove(self.handlers, i)
			end
		end
		return conn
	end
	sig.Once = sig.Connect
	function sig:Wait()
		if not coroutine.isyieldable() then
			return nil
		end
		if self.frame then
			-- segnali di ogni fotogramma: si riprende al fotogramma successivo del tempo virtuale
			return G.task.wait(1 / 60)
		end
		table.insert(self.waiting, coroutine.running())
		return coroutine.yield()
	end
	function sig:Fire(...)
		for _, fn in table.clone(self.handlers) do
			G.task.spawn(fn, ...)
		end
		local waiting = self.waiting
		self.waiting = {}
		for _, co in waiting do
			G.task.spawn(co, ...)
		end
	end
	return sig
end
G.newSignal = newSignal

local EVENTS = {}
for _, n in
	{
		"Activated",
		"MouseButton1Down",
		"MouseButton1Up",
		"MouseButton1Click",
		"MouseEnter",
		"MouseLeave",
		"Changed",
		"Destroying",
		"FocusLost",
		"Focused",
		"InputBegan",
		"InputEnded",
		"InputChanged",
		"ChildAdded",
		"ChildRemoved",
		"AncestryChanged",
		"Completed",
		"Triggered",
		"PromptShown",
		"PromptHidden",
		"RenderStepped",
		"Heartbeat",
		"Stepped",
		"CharacterAdded",
		"CharacterRemoving",
		"PlayerAdded",
		"PlayerRemoving",
		"OnClientEvent",
		"Event",
		"Ended",
		"PromptButtonHoldBegan",
		"PromptButtonHoldEnded",
		"TriggerEnded",
		"MouseWheelForward",
		"MouseWheelBackward",
	}
do
	EVENTS[n] = true
end

---------------------------------------------------------------------------------------------
-- Istanze
---------------------------------------------------------------------------------------------
local white = Color3.new(1, 1, 1)
local TEXT = {
	Text = "Label",
	TextColor3 = Color3.fromRGB(27, 42, 53),
	TextSize = 14,
	Font = Enum.Font.Legacy,
	TextScaled = false,
	TextWrapped = false,
	TextXAlignment = Enum.TextXAlignment.Center,
	TextYAlignment = Enum.TextYAlignment.Center,
	RichText = false,
	TextTransparency = 0,
	TextStrokeTransparency = 1,
	LineHeight = 1,
}
local GUI = {
	Size = UDim2.new(0, 100, 0, 100),
	Position = UDim2.new(),
	AnchorPoint = Vector2.new(),
	BackgroundColor3 = Color3.fromRGB(163, 162, 165),
	BackgroundTransparency = 0,
	Visible = true,
	ZIndex = 1,
	Rotation = 0,
	LayoutOrder = 0,
	BorderSizePixel = 1,
	ClipsDescendants = false,
	AutomaticSize = Enum.AutomaticSize.None,
	SizeConstraint = Enum.SizeConstraint.RelativeXY,
	Active = false,
	Selectable = false,
}
local DEFAULTS = {
	Frame = {},
	CanvasGroup = {},
	TextLabel = TEXT,
	TextButton = setmetatable({ Text = "Button", AutoButtonColor = true }, { __index = TEXT }),
	TextBox = setmetatable(
		{ Text = "", PlaceholderText = "", ClearTextOnFocus = true, PlaceholderColor3 = Color3.fromRGB(178, 178, 178) },
		{ __index = TEXT }
	),
	ImageLabel = { Image = "", ImageColor3 = white, ImageTransparency = 0, ScaleType = Enum.ScaleType.Stretch },
	ImageButton = {
		Image = "",
		ImageColor3 = white,
		ImageTransparency = 0,
		ScaleType = Enum.ScaleType.Stretch,
		AutoButtonColor = true,
	},
	ScrollingFrame = {
		CanvasSize = UDim2.new(0, 0, 2, 0),
		ScrollBarThickness = 12,
		CanvasPosition = Vector2.new(),
		ScrollingDirection = Enum.ScrollingDirection.XY,
	},
	ViewportFrame = { Ambient = Color3.fromRGB(200, 200, 200), LightColor = Color3.fromRGB(140, 140, 140) },
	ScreenGui = { Enabled = true, DisplayOrder = 0, IgnoreGuiInset = false, ResetOnSpawn = true },
	BillboardGui = { Enabled = true, Size = UDim2.new(0, 100, 0, 50) },
	UIListLayout = {
		FillDirection = Enum.FillDirection.Vertical,
		Padding = UDim.new(0, 0),
		HorizontalAlignment = Enum.HorizontalAlignment.Left,
		VerticalAlignment = Enum.VerticalAlignment.Top,
		SortOrder = Enum.SortOrder.LayoutOrder,
		Wraps = false,
	},
	UIGridLayout = {
		CellSize = UDim2.new(0, 100, 0, 100),
		CellPadding = UDim2.new(0, 5, 0, 5),
		FillDirection = Enum.FillDirection.Horizontal,
		HorizontalAlignment = Enum.HorizontalAlignment.Left,
		VerticalAlignment = Enum.VerticalAlignment.Top,
		SortOrder = Enum.SortOrder.LayoutOrder,
	},
	UIPadding = {
		PaddingLeft = UDim.new(),
		PaddingRight = UDim.new(),
		PaddingTop = UDim.new(),
		PaddingBottom = UDim.new(),
	},
	UICorner = { CornerRadius = UDim.new(0, 8) },
	UIStroke = {
		Thickness = 1,
		Color = Color3.new(0, 0, 0),
		Transparency = 0,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Contextual,
		Enabled = true,
	},
	UIGradient = {
		Color = ColorSequence.new(white),
		Rotation = 0,
		Transparency = NumberSequence.new(0),
		Offset = Vector2.new(),
		Enabled = true,
	},
	UIScale = { Scale = 1 },
	UITextSizeConstraint = { MaxTextSize = 100, MinTextSize = 1 },
	UIAspectRatioConstraint = { AspectRatio = 1 },
	UISizeConstraint = {},
}
local GUIOBJECT = {
	Frame = true,
	TextLabel = true,
	TextButton = true,
	TextBox = true,
	ImageLabel = true,
	ImageButton = true,
	ScrollingFrame = true,
	ViewportFrame = true,
	CanvasGroup = true,
}
local ISA = {
	GuiObject = GUIOBJECT,
	GuiButton = { TextButton = true, ImageButton = true },
	GuiBase2d = setmetatable({ ScreenGui = true, BillboardGui = true, SurfaceGui = true }, { __index = GUIOBJECT }),
	LayerCollector = { ScreenGui = true, BillboardGui = true, SurfaceGui = true },
	BasePart = { Part = true, MeshPart = true, WedgePart = true },
	PVInstance = { Part = true, MeshPart = true, Model = true },
	UIComponent = {
		UIListLayout = true,
		UIGridLayout = true,
		UIPadding = true,
		UICorner = true,
		UIStroke = true,
		UIGradient = true,
		UIScale = true,
		UITextSizeConstraint = true,
		UIAspectRatioConstraint = true,
		UISizeConstraint = true,
	},
}

local Instance = {}
local nextId = 0
local mt = {}

local function new(className: string)
	nextId += 1
	local obj = {
		__props = { Name = className, ClassName = className },
		__children = {},
		__attrs = {},
		__parent = nil,
		__id = nextId,
		__class = className,
	}
	return setmetatable(obj, mt)
end

local METHODS = {}
function METHODS.GetChildren(self)
	return table.clone(self.__children)
end
function METHODS.GetDescendants(self)
	local out = {}
	local function walk(o)
		for _, c in o.__children do
			table.insert(out, c)
			walk(c)
		end
	end
	walk(self)
	return out
end
function METHODS.FindFirstChild(self, name, recursive)
	for _, c in self.__children do
		if c.Name == name then
			return c
		end
	end
	if recursive then
		for _, c in self.__children do
			local f = c:FindFirstChild(name, true)
			if f then
				return f
			end
		end
	end
	return nil
end
METHODS.WaitForChild = METHODS.FindFirstChild
function METHODS.FindFirstChildOfClass(self, cls)
	for _, c in self.__children do
		if c.__class == cls then
			return c
		end
	end
	return nil
end
function METHODS.FindFirstChildWhichIsA(self, cls, recursive)
	for _, c in self.__children do
		if c:IsA(cls) then
			return c
		end
	end
	if recursive then
		for _, c in self.__children do
			local f = c:FindFirstChildWhichIsA(cls, true)
			if f then
				return f
			end
		end
	end
	return nil
end
function METHODS.FindFirstAncestorWhichIsA(self, cls)
	local p = self.__parent
	while p do
		if p:IsA(cls) then
			return p
		end
		p = p.__parent
	end
	return nil
end
function METHODS.IsA(self, cls)
	if cls == "Instance" or cls == self.__class then
		return true
	end
	local set = ISA[cls]
	return set ~= nil and set[self.__class] == true
end
function METHODS.IsDescendantOf(self, other)
	local p = self.__parent
	while p do
		if p == other then
			return true
		end
		p = p.__parent
	end
	return false
end
function METHODS.Destroy(self)
	self.Parent = nil
	self.__destroyed = true
end
METHODS.Remove = METHODS.Destroy
function METHODS.ClearAllChildren(self)
	for _, c in table.clone(self.__children) do
		c:Destroy()
	end
end
-- segnali di cambio (proprieta' e attributi), conservati per istanza e chiamati alle modifiche
local function changeSignal(self, key: string)
	local sigs = rawget(self, "__sigs")
	if not sigs then
		sigs = {}
		rawset(self, "__sigs", sigs)
	end
	sigs[key] = sigs[key] or newSignal()
	return sigs[key]
end
local function fireChange(self, key: string)
	local sigs = rawget(self, "__sigs")
	local sig = sigs and sigs[key]
	if sig then
		sig:Fire()
	end
end
function METHODS.GetAttribute(self, k)
	return self.__attrs[k]
end
function METHODS.SetAttribute(self, k, v)
	local old = self.__attrs[k]
	self.__attrs[k] = v
	if old ~= v then
		fireChange(self, "@" .. k)
	end
end
function METHODS.GetAttributes(self)
	return table.clone(self.__attrs)
end
function METHODS.GetAttributeChangedSignal(self, name)
	return changeSignal(self, "@" .. name)
end
function METHODS.GetPropertyChangedSignal(self, name)
	return changeSignal(self, name)
end
function METHODS.Clone(self)
	local c = new(self.__class)
	for k, v in self.__props do
		c.__props[k] = v
	end
	for k, v in self.__attrs do
		c.__attrs[k] = v
	end
	for _, ch in self.__children do
		ch:Clone().Parent = c
	end
	return c
end
-- modelli 3D (solo quanto serve alle anteprime: non vengono disegnati)
function METHODS.PivotTo(self, cf)
	self.__props.WorldPivot = cf
end
function METHODS.GetPivot(self)
	return self.__props.WorldPivot or CFrame.new()
end
function METHODS.GetBoundingBox(_self)
	return CFrame.new(0, 1.5, 0), Vector3.new(3, 3, 3)
end
function METHODS.ScaleTo(self, s)
	self.__props.__scale = s
end
function METHODS.GetScale(self)
	return self.__props.__scale or 1
end
function METHODS.Play() end
function METHODS.Stop() end
function METHODS.Pause() end
function METHODS.Resume() end
function METHODS.Emit() end
function METHODS.CaptureFocus() end
function METHODS.ReleaseFocus() end
function METHODS.Fire(self, ...)
	self.Event:Fire(...)
end
function METHODS.FireServer() end
function METHODS.InvokeServer()
	return nil
end

mt.__index = function(self, key)
	if key == "Parent" then
		return rawget(self, "__parent")
	elseif type(key) == "string" and string.sub(key, 1, 2) == "__" then
		return nil
	end
	local props = rawget(self, "__props")
	local v = props[key]
	if v ~= nil then
		return v
	end
	if METHODS[key] then
		return METHODS[key]
	end
	local defs = DEFAULTS[self.__class]
	if defs and defs[key] ~= nil then
		return defs[key]
	end
	if GUIOBJECT[self.__class] and GUI[key] ~= nil then
		return GUI[key]
	end
	for _, c in self.__children do
		if c.Name == key then
			return c
		end
	end
	if EVENTS[key] then
		local s = newSignal(key == "RenderStepped" or key == "Heartbeat" or key == "Stepped")
		props[key] = s
		return s
	end
	if key == "AbsoluteSize" then
		return Vector2.new(100, 100)
	elseif key == "AbsolutePosition" then
		return Vector2.new(0, 0)
	elseif key == "TextBounds" then
		return Vector2.new(100, 20)
	end
	G.unknown[self.__class .. "." .. tostring(key)] = true
	return nil
end

mt.__newindex = function(self, key, value)
	if key == "Parent" then
		local old = self.__parent
		if old then
			local i = table.find(old.__children, self)
			if i then
				table.remove(old.__children, i)
			end
		end
		rawset(self, "__parent", value)
		if value then
			table.insert(value.__children, self)
		end
		return
	end
	local old = self.__props[key]
	self.__props[key] = value
	if old ~= value and type(key) == "string" and string.sub(key, 1, 2) ~= "__" then
		fireChange(self, key)
	end
end
mt.__tostring = function(self)
	return self.Name
end

function Instance.new(className: string, parent)
	local o = new(className)
	if parent then
		o.Parent = parent
	end
	return o
end
G.Instance = Instance

---------------------------------------------------------------------------------------------
-- Scheduler con tempo virtuale: spawn esegue subito fino alla prima attesa; wait e delay
-- riprendono quando G.advance(secondi) porta avanti l'orologio (os.clock nei moduli)
---------------------------------------------------------------------------------------------
local taskLib = {}
local vt = 0 -- tempo virtuale
local sleepers: { { co: thread, at: number, args: { any }? } } = {}

local function resume(co: thread, ...)
	local ok, err = coroutine.resume(co, ...)
	if not ok then
		print("[gui_env] errore: " .. tostring(err) .. "\n" .. debug.traceback(co))
	end
end

function taskLib.spawn(fn, ...)
	if type(fn) == "thread" then
		resume(fn, ...)
		return fn
	end
	local co = coroutine.create(fn)
	resume(co, ...)
	return co
end
taskLib.defer = taskLib.spawn
function taskLib.delay(t, fn, ...)
	local co = coroutine.create(fn)
	table.insert(sleepers, { co = co, at = vt + (t or 0), args = table.pack(...) })
	return co
end
function taskLib.wait(t)
	if not coroutine.isyieldable() then
		return 0
	end
	local dt = t or 1 / 60
	table.insert(sleepers, { co = coroutine.running(), at = vt + dt })
	coroutine.yield()
	return dt
end
function taskLib.cancel(co)
	for i, sl in sleepers do
		if sl.co == co then
			table.remove(sleepers, i)
			return
		end
	end
end

-- Porta avanti il tempo virtuale a fotogrammi di 1/60 s: risveglia nell'ordine i thread in
-- attesa e chiama i gestori di RenderStepped/Heartbeat a ogni fotogramma
function G.advance(seconds: number)
	local target = vt + seconds
	local frame = 1 / 60
	local guard = 0
	while vt < target - 1e-9 do
		local stepEnd = math.min(target, vt + frame)
		while true do
			local best = nil
			for i, sl in sleepers do
				if sl.at <= stepEnd and (best == nil or sl.at < sleepers[best].at) then
					best = i
				end
			end
			if best == nil then
				break
			end
			local sl = table.remove(sleepers, best)
			vt = math.max(vt, sl.at)
			if sl.args then
				resume(sl.co, table.unpack(sl.args, 1, sl.args.n))
			else
				resume(sl.co)
			end
			guard += 1
			if guard > 200000 then
				error("G.advance: troppi risvegli (ciclo senza attese?)")
			end
		end
		vt = stepEnd
		for _, sig in frameSignals do
			for _, fn in table.clone(sig.handlers) do
				taskLib.spawn(fn, frame)
			end
		end
	end
end
function G.now(): number
	return vt
end
G.task = taskLib

---------------------------------------------------------------------------------------------
-- Servizi
---------------------------------------------------------------------------------------------
function G.makeServices(opts)
	local playerGui = Instance.new("PlayerGui")
	local player = Instance.new("Player")
	player.Name = "Tester"
	player.DisplayName = "Tester"
	player.UserId = 118377242
	player.LocaleId = "it-it"
	playerGui.Parent = player
	for k, v in opts.attributes or {} do
		player:SetAttribute(k, v)
	end
	local camera = Instance.new("Camera")
	camera.ViewportSize = opts.viewport or Vector2.new(1280, 720)
	local workspaceObj = Instance.new("Workspace")
	workspaceObj.CurrentCamera = camera
	workspaceObj.GetServerTimeNow = function()
		return opts.now or 1760000000
	end
	for k, v in opts.workspaceAttributes or {} do
		workspaceObj:SetAttribute(k, v)
	end
	local players = Instance.new("Players")
	players.LocalPlayer = player
	players.GetPlayers = function()
		return { player }
	end
	players.GetPlayerByUserId = function()
		return player
	end
	local tween = Instance.new("TweenService")
	tween.Create = function(_, inst, _info, goal)
		-- tween istantaneo: per la foto conta lo stato finale
		local t = Instance.new("Tween")
		t.Play = function()
			for k, v in goal do
				inst[k] = v
			end
			taskLib.delay(0, function()
				t.Completed:Fire(Enum.PlaybackState.Completed)
			end)
		end
		t.Cancel = function() end
		return t
	end
	local uis = Instance.new("UserInputService")
	uis.TouchEnabled = opts.touch == true
	uis.KeyboardEnabled = opts.touch ~= true
	local run = Instance.new("RunService")
	run.IsStudio = function()
		return false
	end
	run.IsClient = function()
		return true
	end
	run.IsServer = function()
		return false
	end
	local sound = Instance.new("SoundService")
	sound.PlayLocalSound = function() end
	local market = Instance.new("MarketplaceService")
	market.PromptGamePassPurchase = function() end
	market.PromptProductPurchase = function() end
	local loc = Instance.new("LocalizationService")
	loc.RobloxLocaleId = opts.locale or "it-it"
	local collection = Instance.new("CollectionService")
	collection.GetTagged = function()
		return {}
	end
	collection.GetInstanceAddedSignal = function()
		return newSignal()
	end
	local replicatedFirst = Instance.new("ReplicatedFirst")
	replicatedFirst.RemoveDefaultLoadingScreen = function() end
	local guiService = Instance.new("GuiService")
	guiService.GetGuiInset = function()
		return Vector2.new(0, opts.inset or 58), Vector2.new(0, 0)
	end
	local starterGui = Instance.new("StarterGui")
	starterGui.SetCoreGuiEnabled = function(_, coreType, enabled)
		starterGui:SetAttribute("Core_" .. tostring(coreType), enabled)
	end
	starterGui.SetCore = function() end
	return {
		GuiService = guiService,
		StarterGui = starterGui,
		ReplicatedFirst = replicatedFirst,
		Players = players,
		TweenService = tween,
		UserInputService = uis,
		RunService = run,
		SoundService = sound,
		MarketplaceService = market,
		LocalizationService = loc,
		CollectionService = collection,
		Workspace = workspaceObj,
		player = player,
		playerGui = playerGui,
		camera = camera,
	}
end

---------------------------------------------------------------------------------------------
-- Caricamento dei moduli del progetto (come Rojo), con i servizi finti
---------------------------------------------------------------------------------------------
local project = serde.decode("json", fs.readFile("default.project.json"))
local mounts: { [string]: string } = {}
local function walk(node, prefix: string)
	for k, v in node do
		if type(v) == "table" and string.sub(k, 1, 1) ~= "$" then
			local p = if prefix == "" then k else prefix .. "/" .. k
			if v["$path"] then
				mounts[p] = v["$path"]
			end
			walk(v, p)
		end
	end
end
walk(project.tree, "")

local function resolveFs(dmPath: string): string?
	local best, bestLen = nil, -1
	for m, fsPath in mounts do
		if (dmPath == m or string.sub(dmPath, 1, #m + 1) == m .. "/") and #m > bestLen then
			best, bestLen = fsPath, #m
		end
	end
	if not best then
		return nil
	end
	local rest = string.sub(dmPath, bestLen + 2)
	local base = if rest == "" then best else best .. "/" .. rest
	if fs.isFile(base) then
		return base
	end
	for _, cand in { base .. ".luau", base .. ".client.luau", base .. "/init.luau", base } do
		local ok, found = pcall(function()
			return fs.isFile(cand) or fs.isDir(cand)
		end)
		if ok and found then
			return cand
		end
	end
	return nil
end

local Proxy = {}
local function proxy(dmPath: string)
	return setmetatable({ __dm = dmPath }, Proxy)
end
Proxy.__index = function(self, key)
	if key == "Parent" then
		return proxy(string.match(self.__dm, "^(.*)/[^/]+$") or "")
	elseif key == "Name" then
		return string.match(self.__dm, "([^/]+)$")
	elseif key == "FindFirstChild" or key == "WaitForChild" then
		return function(s, name)
			local child = s.__dm .. "/" .. name
			return if resolveFs(child) then proxy(child) else nil
		end
	elseif key == "IsA" then
		return function()
			return false
		end
	elseif key == "GetChildren" then
		return function()
			return {}
		end
	end
	return proxy(self.__dm .. "/" .. key)
end

function G.makeLoader(services, overrides)
	local cache = {}
	local env = {}
	local gameObj = setmetatable({
		GetService = function(_, name)
			if services[name] then
				return services[name]
			end
			return proxy(name)
		end,
		IsLoaded = function()
			return true
		end,
		Loaded = newSignal(),
	}, {
		__index = function(_, k)
			return if services[k] then services[k] else proxy(k)
		end,
	})
	local loadModule
	local runAsScript = false
	local function requireProxy(p)
		if type(p) == "string" then
			return require(p)
		end
		return loadModule(p.__dm)
	end
	loadModule = function(dmPath: string)
		if overrides[dmPath] then
			return overrides[dmPath]
		end
		if cache[dmPath] ~= nil then
			return cache[dmPath]
		end
		local file = resolveFs(dmPath)
		assert(file, "modulo non trovato: " .. dmPath)
		if fs.isDir(file) then
			file = file .. "/init.luau"
		end
		local g = setmetatable({}, { __index = _G })
		for _, n in
			{
				"UDim2",
				"UDim",
				"Vector2",
				"Vector3",
				"Color3",
				"ColorSequence",
				"ColorSequenceKeypoint",
				"NumberSequence",
				"NumberSequenceKeypoint",
				"NumberRange",
				"Enum",
				"CFrame",
				"Rect",
				"BrickColor",
				"Font",
			}
		do
			g[n] = (roblox :: any)[n]
		end
		g.TweenInfo = {
			new = function(...)
				return { ... }
			end,
		}
		g.Instance = Instance
		g.game = gameObj
		g.workspace = services.Workspace
		g.script = proxy(dmPath)
		g.require = requireProxy
		g.typeof = function(v)
			if type(v) == "table" and getmetatable(v) == mt then
				return "Instance"
			end
			return typeof(v)
		end
		g.warn = function(...)
			print("[warn]", ...)
		end
		g.task = taskLib
		g.tick = G.now
		g.time = G.now
		g.os = setmetatable({ clock = G.now }, { __index = os })
		g.Random = {
			new = function()
				return {
					NextNumber = function(_, a, b)
						return (a or 0) + ((b or 1) - (a or 0)) * 0.5
					end,
					NextInteger = function(_, a, b)
						return math.floor((a + b) / 2)
					end,
				}
			end,
		}
		local fn = luau.load(fs.readFile(file), { debugName = file, environment = g })
		if runAsScript then
			runAsScript = false
			return taskLib.spawn(fn)
		end
		local result = fn()
		cache[dmPath] = result
		return result
	end
	env.require = loadModule
	-- LocalScript: eseguito in un thread (puo' aspettare con task.wait)
	function env.runScript(dmPath: string)
		runAsScript = true
		return loadModule(dmPath)
	end
	return env
end

---------------------------------------------------------------------------------------------
-- Esportazione dell'albero (per il disegno in HTML)
---------------------------------------------------------------------------------------------
local function ser(v)
	local t = typeof(v)
	if t == "UDim2" then
		return { "UDim2", v.X.Scale, v.X.Offset, v.Y.Scale, v.Y.Offset }
	elseif t == "UDim" then
		return { "UDim", v.Scale, v.Offset }
	elseif t == "Vector2" then
		return { "Vector2", v.X, v.Y }
	elseif t == "Color3" then
		return { "Color3", math.floor(v.R * 255 + 0.5), math.floor(v.G * 255 + 0.5), math.floor(v.B * 255 + 0.5) }
	elseif t == "ColorSequence" then
		local out = { "ColorSequence" }
		for _, k in v.Keypoints do
			table.insert(out, {
				k.Time,
				math.floor(k.Value.R * 255 + 0.5),
				math.floor(k.Value.G * 255 + 0.5),
				math.floor(k.Value.B * 255 + 0.5),
			})
		end
		return out
	elseif t == "NumberSequence" then
		local out = { "NumberSequence" }
		for _, k in v.Keypoints do
			table.insert(out, { k.Time, k.Value })
		end
		return out
	elseif t == "EnumItem" then
		return { "Enum", v.Name }
	elseif t == "number" or t == "string" or t == "boolean" then
		return v
	end
	return nil
end

function G.dump(root)
	local function node(o)
		local props = {}
		for k, v in o.__props do
			if string.sub(k, 1, 2) ~= "__" then
				local s = ser(v)
				if s ~= nil then
					props[k] = s
				end
			end
		end
		local defs = DEFAULTS[o.__class]
		local function fill(tbl)
			for k, v in tbl do
				if props[k] == nil then
					local s = ser(v)
					if s ~= nil then
						props[k] = s
					end
				end
			end
		end
		if defs then
			fill(defs)
			local m = getmetatable(defs)
			if m and m.__index then
				fill(m.__index)
			end
		end
		if GUIOBJECT[o.__class] then
			fill(GUI)
		end
		local kids = {}
		for _, c in o.__children do
			table.insert(kids, node(c))
		end
		local attrs = nil
		for k, v in o.__attrs do
			local s = ser(v)
			if s ~= nil then
				attrs = attrs or {}
				attrs[k] = s
			end
		end
		return { c = o.__class, n = o.Name, p = props, k = kids, a = attrs }
	end
	return node(root)
end

return G
