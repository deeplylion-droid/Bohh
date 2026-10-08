-- Schiusa: scena a tutto schermo quando un uovo si schiude. L'uovo trema sempre piu' forte
-- (piu' a lungo per le rarita' alte), lampo bianco, poi il pet compare girando su se stesso con
-- nome, rarita', mutazione, taglia, guadagno al secondo e il badge NUOVO se e' una scoperta.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local RunService = game:GetService("RunService")

local Format = require(ReplicatedStorage.Shared.Util.Format)
local Net = require(ReplicatedStorage.Shared.Net)
local Pets = require(ReplicatedStorage.Shared.Config.Pets)
local Rarities = require(ReplicatedStorage.Shared.Config.Rarities)
local Variants = require(ReplicatedStorage.Shared.Config.Variants)
local Visuals = require(ReplicatedStorage.Shared.Visuals)

local Hatch = {}

local C
local Kit
local queue = {}
local busy = false

function Hatch.Init(controllers)
	C = controllers
end

-- Inquadra un modello nella ViewportFrame: restituisce centro e distanza della camera
local function frame(model: Model): (Vector3, number, number)
	local cf, size = model:GetBoundingBox()
	local radius = math.max(size.X, size.Y, size.Z) / 2
	local dist = radius / math.tan(math.rad(20)) * 1.35
	return cf.Position, dist, size.Y
end

local function placeCamera(cam: Camera, center: Vector3, dist: number, height: number, angle: number)
	local offset = CFrame.Angles(0, angle, 0) * Vector3.new(0, height * 0.12, -dist)
	cam.CFrame = CFrame.lookAt(center + offset, center)
end

-- Raggi colorati che ruotano dietro al pet
local function rays(parent: Instance, color: Color3, zindex: number): Frame
	local holder = Kit.New("Frame", {
		Name = "Rays",
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(1100, 1100),
		Position = UDim2.fromScale(0.5, 0.5),
		AnchorPoint = Vector2.new(0.5, 0.5),
		ZIndex = zindex,
		Parent = parent,
	})
	for i = 0, 11 do
		local ray = Kit.New("Frame", {
			BackgroundColor3 = color,
			BorderSizePixel = 0,
			Size = UDim2.new(0, 70, 1, 0),
			Position = UDim2.fromScale(0.5, 0.5),
			AnchorPoint = Vector2.new(0.5, 0.5),
			Rotation = i * 15,
			ZIndex = zindex,
			Parent = holder,
		})
		Kit.New("UIGradient", {
			Rotation = 90,
			Transparency = NumberSequence.new({
				NumberSequenceKeypoint.new(0, 1),
				NumberSequenceKeypoint.new(0.3, 0.75),
				NumberSequenceKeypoint.new(0.5, 0.35),
				NumberSequenceKeypoint.new(0.7, 0.75),
				NumberSequenceKeypoint.new(1, 1),
			}),
			Parent = ray,
		})
	end
	return holder
end

-- Coriandoli che esplodono dal centro (rarita' alte)
local function confetti(parent: Instance, colors: { Color3 }, count: number)
	for i = 1, count do
		local c = Kit.New("Frame", {
			BackgroundColor3 = colors[(i % #colors) + 1],
			BorderSizePixel = 0,
			Size = UDim2.fromOffset(math.random(10, 18), math.random(6, 10)),
			Position = UDim2.fromScale(0.5, 0.45),
			AnchorPoint = Vector2.new(0.5, 0.5),
			Rotation = math.random(0, 360),
			ZIndex = 60,
			Parent = parent,
		}, { Kit.Corner(UDim.new(0, 3)) })
		local ang = math.random() * math.pi * 2
		local dist = math.random(260, 560)
		local target = UDim2.new(0.5, math.cos(ang) * dist, 0.45, math.sin(ang) * dist * 0.7 + 120)
		Kit.Tween(c, math.random(10, 16) / 10, { Position = target, Rotation = c.Rotation + math.random(-360, 360), BackgroundTransparency = 1 }, Enum.EasingStyle.Quad, Enum.EasingDirection.Out)
		task.delay(1.7, function()
			c:Destroy()
		end)
	end
end

local function chip(parent: Instance, text: string, colors: { Color3 }, order: number): Frame
	local f = Kit.New("Frame", {
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromOffset(0, 40),
		AutomaticSize = Enum.AutomaticSize.X,
		LayoutOrder = order,
		ZIndex = 62,
		Parent = parent,
	}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(4), Kit.Gradient(colors[1], colors[2]), Kit.New("UIPadding", { PaddingLeft = UDim.new(0, 16), PaddingRight = UDim.new(0, 16) }), Kit.New("UIScale") })
	Kit.Text({ Text = text, Size = UDim2.fromOffset(0, 30), AutomaticSize = Enum.AutomaticSize.X, TextScaled = false, TextSize = 26, Position = UDim2.fromOffset(0, 5), ZIndex = 63, Parent = f })
	return f
end

local function play(info)
	local T = C.Lang.T
	local rarity = Rarities.List[info.rarity] or Rarities.List.Common
	local def = Pets.ById[info.pet]
	local mutation = Variants.Mutations[info.mutation or "None"] or Variants.Mutations.None
	local size = Variants.Sizes[info.size or "Normal"] or Variants.Sizes.Normal
	local overlay = C.UI.Gui("Overlay")

	-- fondo scuro, palco centrale in scala con l'interfaccia
	local root = Kit.New("TextButton", {
		Name = "HatchScene",
		Text = "",
		AutoButtonColor = false,
		BackgroundColor3 = Color3.fromRGB(14, 10, 30),
		BackgroundTransparency = 1,
		Size = UDim2.fromScale(1, 1),
		ZIndex = 55,
		Parent = overlay,
	})
	Kit.Tween(root, 0.3, { BackgroundTransparency = 0.3 })
	local stage = Kit.New("Frame", {
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(900, 700),
		Position = UDim2.fromScale(0.5, 0.5),
		AnchorPoint = Vector2.new(0.5, 0.5),
		ZIndex = 56,
		Parent = root,
	}, { Kit.New("UIScale", { Scale = C.UI.Scale or 1 }) })
	local rayFrame = rays(stage, rarity.color, 56)
	local glow = Kit.New("Frame", {
		BackgroundColor3 = rarity.color,
		BackgroundTransparency = 0.55,
		Size = UDim2.fromOffset(380, 380),
		Position = UDim2.fromScale(0.5, 0.45),
		AnchorPoint = Vector2.new(0.5, 0.5),
		ZIndex = 57,
		Parent = stage,
	}, { Kit.Corner(UDim.new(1, 0)), Kit.New("UIScale") })
	local viewport = Kit.New("ViewportFrame", {
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(460, 460),
		Position = UDim2.fromScale(0.5, 0.45),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Ambient = Color3.fromRGB(170, 170, 190),
		LightColor = Color3.fromRGB(255, 250, 240),
		LightDirection = Vector3.new(-0.6, -1, 0.8),
		ZIndex = 58,
		Parent = stage,
	}, { Kit.New("UIScale") })
	local cam = Instance.new("Camera")
	cam.FieldOfView = 40
	cam.Parent = viewport
	viewport.CurrentCamera = cam
	local title = Kit.Text({ Text = T("Hatching"), Size = UDim2.fromOffset(700, 54), Position = UDim2.new(0.5, 0, 0, 40), AnchorPoint = Vector2.new(0.5, 0), ZIndex = 61, Parent = stage })
	Kit.Pop(title)

	-- l'uovo
	local egg = Visuals.MakeEgg(info.rarity, false)
	egg:PivotTo(CFrame.new())
	egg.Parent = viewport
	local center, dist, h = frame(egg)
	placeCamera(cam, center, dist * 1.25, h, 0)
	Kit.Pop(viewport)

	local t0 = os.clock()
	local shakeTime = 1.5 + rarity.order * 0.22
	local spinRays = 0.15
	local conn = RunService.RenderStepped:Connect(function(dt)
		rayFrame.Rotation += dt * 20 * spinRays
	end)

	-- tremolio crescente, con un "toc" a ogni scossone
	local nextTick = 0
	while os.clock() - t0 < shakeTime do
		local k = (os.clock() - t0) / shakeTime
		local freq = 10 + k * 22
		local amp = math.rad(4 + k * 18)
		local tt = os.clock() - t0
		egg:PivotTo(CFrame.new(0, math.abs(math.sin(tt * freq * 0.5)) * k * 0.25, 0) * CFrame.Angles(0, 0, math.sin(tt * freq) * amp))
		spinRays = 0.15 + k * 2.5
		glow.BackgroundTransparency = 0.55 - k * 0.3
		if tt >= nextTick then
			nextTick = tt + math.max(0.12, 0.42 - k * 0.32)
			C.Audio.Play("Click", nil, 0.4 + k * 0.4)
		end
		RunService.RenderStepped:Wait()
	end

	-- lampo
	local flash = Kit.New("Frame", { BackgroundColor3 = Color3.new(1, 1, 1), BackgroundTransparency = 0, Size = UDim2.fromScale(1, 1), ZIndex = 70, Parent = root })
	Kit.Tween(flash, 0.7, { BackgroundTransparency = 1 })
	task.delay(0.75, function()
		flash:Destroy()
	end)
	C.Audio.Play(if rarity.order >= 5 or mutation.id ~= "None" then "Fanfare" else "Success")
	egg:Destroy()

	-- il pet
	local pet = Visuals.MakePet(info.pet, info.mutation, info.size)
	pet:PivotTo(CFrame.new())
	pet.Parent = viewport
	center, dist, h = frame(pet)
	local zoom = 2.2
	placeCamera(cam, center, dist * zoom, h, 0)
	if rarity.order >= 5 or mutation.id ~= "None" then
		local colors = if mutation.id ~= "None" then { mutation.color, Color3.new(1, 1, 1), rarity.color } else { rarity.color, Color3.new(1, 1, 1), Color3.fromRGB(255, 225, 77) }
		confetti(stage, colors, 40 + rarity.order * 6)
	end
	spinRays = 0.6

	-- testi
	title.Text = T("YouGot")
	Kit.Pop(title)
	local nameLabel = Kit.Text({ Text = T("Pet_" .. info.pet), TextColor3 = rarity.color, Size = UDim2.fromOffset(760, 70), Position = UDim2.new(0.5, 0, 0, 520), AnchorPoint = Vector2.new(0.5, 0), ZIndex = 61, Stroke = 5, Parent = stage })
	local gradient = Rarities.Gradients[info.rarity]
	if gradient then
		nameLabel.TextColor3 = Color3.new(1, 1, 1)
		Kit.New("UIGradient", { Color = gradient, Parent = nameLabel })
	end
	Kit.Pop(nameLabel, 0.1)
	local chips = Kit.New("Frame", {
		BackgroundTransparency = 1,
		Size = UDim2.fromOffset(800, 44),
		Position = UDim2.new(0.5, 0, 0, 596),
		AnchorPoint = Vector2.new(0.5, 0),
		ZIndex = 61,
		Parent = stage,
	}, { Kit.New("UIListLayout", { FillDirection = Enum.FillDirection.Horizontal, HorizontalAlignment = Enum.HorizontalAlignment.Center, Padding = UDim.new(0, 10), SortOrder = Enum.SortOrder.LayoutOrder }) })
	local rc = { rarity.color, rarity.colorDark }
	local order = 0
	local function addChip(text: string, colors: { Color3 })
		order += 1
		local c = chip(chips, text, colors, order)
		Kit.Pop(c, 0.15 + order * 0.12)
	end
	addChip(T("Rarity_" .. info.rarity), rc)
	if mutation.id ~= "None" then
		addChip(`{T("Mutation_" .. mutation.id)} ×{mutation.mult}`, { mutation.color, mutation.color:Lerp(Color3.new(0, 0, 0), 0.35) })
	end
	if size.id ~= "Normal" then
		addChip(T("Size_" .. size.id), { Color3.fromRGB(120, 220, 255), Color3.fromRGB(30, 120, 230) })
	end
	if def then
		local income = def.income * mutation.mult * size.mult
		addChip(Format.Rate(income), { Color3.fromRGB(141, 255, 98), Color3.fromRGB(34, 170, 59) })
	end
	if info.new then
		local badge = Kit.New("Frame", {
			BackgroundColor3 = Color3.new(1, 1, 1),
			Size = UDim2.fromOffset(150, 58),
			Position = UDim2.new(0.5, 170, 0, 150),
			AnchorPoint = Vector2.new(0.5, 0.5),
			Rotation = 12,
			ZIndex = 64,
			Parent = stage,
		}, { Kit.Corner(UDim.new(0, 16)), Kit.Stroke(5), Kit.Gradient(Color3.fromRGB(255, 236, 120), Color3.fromRGB(255, 150, 20)), Kit.New("UIScale") })
		Kit.Text({ Text = T("NewPet"), Size = UDim2.fromScale(0.86, 0.7), Position = UDim2.fromScale(0.07, 0.15), ZIndex = 65, Parent = badge })
		Kit.Pop(badge, 0.35)
		task.spawn(function()
			while badge.Parent do
				Kit.Bounce(badge, 0.08)
				task.wait(0.8)
			end
		end)
	end
	local hint = Kit.Text({ Text = T("TapToContinue"), Font = Kit.Theme.BodyFont, TextColor3 = Kit.Theme.Muted, Size = UDim2.fromOffset(400, 26), Position = UDim2.new(0.5, 0, 1, -24), AnchorPoint = Vector2.new(0.5, 1), Stroke = 2, ZIndex = 61, TextTransparency = 1, Parent = stage })

	-- il pet si avvicina e gira lentamente
	local revealAt = os.clock()
	local closing = false
	conn:Disconnect()
	conn = RunService.RenderStepped:Connect(function(dt)
		rayFrame.Rotation += dt * 20 * spinRays
		local e = math.clamp((os.clock() - revealAt) / 0.45, 0, 1)
		local back = 1 + 2.7 * (e - 1) ^ 3 + 1.7 * (e - 1) ^ 2 -- easing "back"
		zoom = 2.2 + (1 - 2.2) * back
		placeCamera(cam, center, dist * zoom, h, math.sin((os.clock() - revealAt) * 0.9) * 0.6)
	end)
	task.delay(1, function()
		Kit.Tween(hint, 0.4, { TextTransparency = 0 })
	end)
	local done = Instance.new("BindableEvent")
	root.Activated:Connect(function()
		if os.clock() - revealAt > 0.9 and not closing then
			closing = true
			done:Fire()
		end
	end)
	task.delay(6, function()
		if not closing then
			closing = true
			done:Fire()
		end
	end)
	done.Event:Wait()
	done:Destroy()

	-- chiusura
	Kit.Tween(root, 0.3, { BackgroundTransparency = 1 })
	local sc = stage:FindFirstChildOfClass("UIScale")
	if sc then
		Kit.Tween(sc, 0.3, { Scale = 0 }, Enum.EasingStyle.Back, Enum.EasingDirection.In)
	end
	task.wait(0.32)
	conn:Disconnect()
	root:Destroy()
end

local function pump()
	if busy then
		return
	end
	busy = true
	while #queue > 0 do
		local info = table.remove(queue, 1)
		local ok, err = pcall(play, info)
		if not ok then
			warn("[Hatch] " .. tostring(err))
			local leftover = C.UI.Gui("Overlay"):FindFirstChild("HatchScene")
			if leftover then
				leftover:Destroy()
			end
		end
	end
	busy = false
end

function Hatch.Start()
	Kit = C.UI.Kit
	Net.Event("HatchReveal").OnClientEvent:Connect(function(info)
		if type(info) ~= "table" or not info.pet then
			return
		end
		table.insert(queue, info)
		C.UI.Close()
		task.spawn(pump)
	end)
end

return Hatch
