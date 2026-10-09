-- Mattoni dell'interfaccia: creazione di istanze, testi con contorno, pulsanti "gommosi" con
-- gradiente, ombra e animazioni, pannelli e piccole animazioni (comparsa, rimbalzo).

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")

local Assets = require(ReplicatedStorage.Shared.Assets)
local Theme = require(script.Parent.Theme)

local Kit = {}

Kit.Theme = Theme

-- Crea un'istanza: props (proprieta' ed eventi "On<Evento>"), children (lista di istanze)
function Kit.New(className: string, props: { [string]: any }?, children: { Instance }?): any
	local inst = Instance.new(className)
	local parent = nil
	if props then
		for k, v in props do
			if k == "Parent" then
				parent = v
			elseif string.sub(k, 1, 2) == "On" and typeof(v) == "function" then
				(inst :: any)[string.sub(k, 3)]:Connect(v)
			else
				(inst :: any)[k] = v
			end
		end
	end
	if children then
		for _, c in children do
			c.Parent = inst
		end
	end
	if parent then
		inst.Parent = parent
	end
	return inst
end

local New = Kit.New

function Kit.Corner(radius: UDim?): UICorner
	return New("UICorner", { CornerRadius = radius or Theme.Corner })
end

function Kit.Stroke(thickness: number?, color: Color3?): UIStroke
	return New("UIStroke", {
		Thickness = thickness or Theme.Stroke,
		Color = color or Theme.Outline,
		ApplyStrokeMode = Enum.ApplyStrokeMode.Border,
		LineJoinMode = Enum.LineJoinMode.Round,
	})
end

function Kit.Gradient(top: Color3, bottom: Color3, rotation: number?): UIGradient
	return New("UIGradient", {
		Color = ColorSequence.new(top, bottom),
		Rotation = rotation or 90,
	})
end

function Kit.Padding(px: number): UIPadding
	local u = UDim.new(0, px)
	return New("UIPadding", { PaddingLeft = u, PaddingRight = u, PaddingTop = u, PaddingBottom = u })
end

-- Testo con contorno scuro (stile titolo)
function Kit.Text(props: { [string]: any }): TextLabel
	local stroke = props.Stroke
	props.Stroke = nil
	local maxSize = props.MaxTextSize
	props.MaxTextSize = nil
	local label = New("TextLabel", {
		BackgroundTransparency = 1,
		Font = props.Font or Theme.TitleFont,
		TextColor3 = props.TextColor3 or Theme.Text,
		TextScaled = true,
		RichText = props.RichText or false,
		Size = props.Size or UDim2.fromScale(1, 1),
	})
	for k, v in props do
		if k ~= "Font" and k ~= "TextColor3" and k ~= "Size" and k ~= "RichText" then
			if k == "Parent" then
				continue
			end
			(label :: any)[k] = v
		end
	end
	if stroke ~= false then
		New("UIStroke", {
			Thickness = if type(stroke) == "number" then stroke else Theme.TextStroke,
			Color = Theme.Outline,
			ApplyStrokeMode = Enum.ApplyStrokeMode.Contextual,
			LineJoinMode = Enum.LineJoinMode.Round,
			Parent = label,
		})
	end
	if maxSize then
		New("UITextSizeConstraint", { MaxTextSize = maxSize, Parent = label })
	end
	label.Parent = props.Parent
	return label
end

-- Icona: immagine caricata se disponibile, altrimenti emoji
function Kit.Icon(name: string, props: { [string]: any }?): GuiObject
	local p = props or {}
	local image = Assets.Images["Icon" .. name]
	local inst
	if image then
		inst = New("ImageLabel", { BackgroundTransparency = 1, Image = image, ScaleType = Enum.ScaleType.Fit })
	else
		inst = New("TextLabel", {
			BackgroundTransparency = 1,
			Text = Theme.Emoji[name] or "•",
			TextScaled = true,
			Font = Enum.Font.SourceSans,
			TextColor3 = Color3.new(1, 1, 1),
		})
	end
	for k, v in p do
		(inst :: any)[k] = v
	end
	return inst
end

function Kit.Tween(
	inst: Instance,
	time: number,
	goal: { [string]: any },
	style: Enum.EasingStyle?,
	dir: Enum.EasingDirection?
): Tween
	local t = TweenService:Create(
		inst,
		TweenInfo.new(time, style or Enum.EasingStyle.Quad, dir or Enum.EasingDirection.Out),
		goal
	)
	t:Play()
	return t
end

-- Animazione di comparsa con rimbalzo (serve un UIScale figlio). La scala finale e' l'attributo
-- "BaseScale" del riquadro (i pannelli si rimpiccioliscono sugli schermi bassi), altrimenti 1.
function Kit.Pop(inst: GuiObject, delay: number?)
	local scale = inst:FindFirstChildOfClass("UIScale") or New("UIScale", { Parent = inst })
	local base = inst:GetAttribute("BaseScale") or 1
	scale.Scale = 0.4 * base
	task.delay(delay or 0, function()
		Kit.Tween(scale, 0.35, { Scale = base }, Enum.EasingStyle.Back)
	end)
end

function Kit.Bounce(inst: GuiObject, amount: number?)
	local scale = inst:FindFirstChildOfClass("UIScale") or New("UIScale", { Parent = inst })
	local base = inst:GetAttribute("BaseScale") or 1
	scale.Scale = base * (1 + (amount or 0.12))
	Kit.Tween(scale, 0.3, { Scale = base }, Enum.EasingStyle.Back)
end

local clickSound: Sound? = nil
function Kit.Click()
	if not clickSound then
		local id = Assets.Sounds.Click
		if not id then
			return
		end
		clickSound = New("Sound", { SoundId = id, Volume = 0.5, Parent = SoundService })
	end
	if Kit.SfxEnabled ~= false then
		SoundService:PlayLocalSound(clickSound :: Sound)
	end
end
Kit.SfxEnabled = true

-- Pulsante gommoso: gradiente, contorno, riflesso in alto, ombra 3D, testo e/o icona, badge.
export type ButtonProps = {
	Text: string?,
	Icon: string?,
	Color: string?,
	Size: UDim2,
	Position: UDim2?,
	AnchorPoint: Vector2?,
	Parent: Instance?,
	TextSize: number?,
	OnClick: (() -> ())?,
	Rotation: number?,
	LayoutOrder: number?,
	Name: string?,
	Corner: UDim?,
}

function Kit.Button(p: ButtonProps)
	local colors = Theme.Buttons[p.Color or "Green"] or Theme.Buttons.Green
	local holder = New("Frame", {
		Name = p.Name or "Button",
		BackgroundTransparency = 1,
		Size = p.Size,
		Position = p.Position or UDim2.new(),
		AnchorPoint = p.AnchorPoint or Vector2.zero,
		Rotation = p.Rotation or 0,
		LayoutOrder = p.LayoutOrder or 0,
	})
	local scale = New("UIScale", { Parent = holder })
	-- ombra sotto (spessore 3D)
	New("Frame", {
		Name = "Shadow",
		BackgroundColor3 = Theme.Outline,
		Size = UDim2.new(1, 0, 1, 0),
		Position = UDim2.new(0, 0, 0, 6),
		ZIndex = 1,
		Parent = holder,
	}, { Kit.Corner(p.Corner) })
	local face = New("TextButton", {
		Name = "Face",
		Text = "",
		AutoButtonColor = false,
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.fromScale(1, 1),
		ZIndex = 2,
		Parent = holder,
	}, { Kit.Corner(p.Corner), Kit.Stroke(Theme.Stroke), Kit.Gradient(colors[1], colors[2]) })
	-- riflesso lucido in alto
	New("Frame", {
		Name = "Shine",
		BackgroundColor3 = Color3.new(1, 1, 1),
		BackgroundTransparency = 0.72,
		Size = UDim2.new(0.86, 0, 0.32, 0),
		Position = UDim2.new(0.07, 0, 0.07, 0),
		ZIndex = 3,
		Parent = face,
	}, { Kit.Corner(UDim.new(1, 0)) })
	local label, icon
	if p.Icon and p.Text then
		icon = Kit.Icon(
			p.Icon,
			{ Size = UDim2.fromScale(0.3, 0.7), Position = UDim2.fromScale(0.05, 0.15), ZIndex = 4, Parent = face }
		)
		label = Kit.Text({
			Text = p.Text,
			Size = UDim2.fromScale(0.62, 0.62),
			Position = UDim2.fromScale(0.35, 0.19),
			ZIndex = 4,
			Parent = face,
			MaxTextSize = p.TextSize,
		})
	elseif p.Icon then
		icon = Kit.Icon(
			p.Icon,
			{ Size = UDim2.fromScale(0.68, 0.68), Position = UDim2.fromScale(0.16, 0.14), ZIndex = 4, Parent = face }
		)
	else
		label = Kit.Text({
			Text = p.Text or "",
			Size = UDim2.fromScale(0.86, 0.64),
			Position = UDim2.fromScale(0.07, 0.18),
			ZIndex = 4,
			Parent = face,
			MaxTextSize = p.TextSize,
		})
	end
	face.MouseButton1Down:Connect(function()
		Kit.Tween(scale, 0.08, { Scale = 0.92 })
	end)
	face.MouseButton1Up:Connect(function()
		Kit.Tween(scale, 0.25, { Scale = 1 }, Enum.EasingStyle.Back)
	end)
	face.MouseLeave:Connect(function()
		Kit.Tween(scale, 0.2, { Scale = 1 })
	end)
	face.MouseEnter:Connect(function()
		Kit.Tween(scale, 0.15, { Scale = 1.05 })
	end)
	if p.OnClick then
		face.Activated:Connect(function()
			Kit.Click()
			p.OnClick()
		end)
	end
	if p.Parent then
		holder.Parent = p.Parent
	end
	return {
		Frame = holder,
		Face = face,
		Label = label,
		Icon = icon,
		SetColor = function(name: string)
			local c = Theme.Buttons[name] or colors
			local g = face:FindFirstChildOfClass("UIGradient")
			if g then
				g.Color = ColorSequence.new(c[1], c[2])
			end
		end,
		SetText = function(text: string)
			if label then
				label.Text = text
			end
		end,
	}
end

-- Badge rosso con numero (notifiche sui pulsanti)
function Kit.Badge(parent: GuiObject): TextLabel
	local badge = New("Frame", {
		Name = "Badge",
		BackgroundColor3 = Color3.fromRGB(255, 59, 59),
		Size = UDim2.fromOffset(34, 34),
		Position = UDim2.new(1, -20, 0, -14),
		ZIndex = 10,
		Visible = false,
		Parent = parent,
	}, { Kit.Corner(UDim.new(1, 0)), Kit.Stroke(3) })
	local text = Kit.Text({
		Text = "!",
		Size = UDim2.fromScale(0.8, 0.8),
		Position = UDim2.fromScale(0.1, 0.1),
		ZIndex = 11,
		Parent = badge,
	})
	return text
end

-- Pannello (finestra) con titolo a nastro e pulsante di chiusura
function Kit.Panel(title: string, size: UDim2, color: string?, parent: Instance)
	local colors = Theme.Buttons[color or "Purple"] or Theme.Buttons.Purple
	local frame = New("Frame", {
		Name = "Panel",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = size,
		Position = UDim2.fromScale(0.5, 0.52),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Visible = false,
		ZIndex = 20,
		Parent = parent,
	}, { Kit.Corner(UDim.new(0, 28)), Kit.Stroke(5), Kit.Gradient(Theme.PanelTop, Theme.PanelBottom), New("UIScale") })
	-- nastro del titolo
	local ribbon = New("Frame", {
		Name = "Ribbon",
		BackgroundColor3 = Color3.new(1, 1, 1),
		Size = UDim2.new(0.56, 0, 0, 64),
		Position = UDim2.new(0.5, 0, 0, -26),
		AnchorPoint = Vector2.new(0.5, 0),
		ZIndex = 22,
		Parent = frame,
	}, { Kit.Corner(UDim.new(0, 20)), Kit.Stroke(5), Kit.Gradient(colors[1], colors[2]) })
	local titleLabel = Kit.Text({
		Text = title,
		Size = UDim2.fromScale(0.9, 0.72),
		Position = UDim2.fromScale(0.05, 0.14),
		ZIndex = 23,
		Parent = ribbon,
		Stroke = 4,
	})
	local close = Kit.Button({
		Icon = "Close",
		Color = "Red",
		Size = UDim2.fromOffset(58, 58),
		Position = UDim2.new(1, -30, 0, -22),
		Parent = frame,
	})
	close.Frame.ZIndex = 24
	for _, d in close.Frame:GetDescendants() do
		if d:IsA("GuiObject") then
			d.ZIndex += 22
		end
	end
	local body = New("Frame", {
		Name = "Body",
		BackgroundTransparency = 1,
		Size = UDim2.new(1, -40, 1, -70),
		Position = UDim2.new(0, 20, 0, 52),
		ZIndex = 21,
		Parent = frame,
	})
	return { Frame = frame, Body = body, Close = close, Title = titleLabel }
end

-- Scheda (riquadro) dentro i pannelli
function Kit.Card(props: { [string]: any }): Frame
	local card = New("Frame", {
		BackgroundColor3 = props.Color or Theme.Card,
		Size = props.Size or UDim2.fromScale(1, 1),
		Position = props.Position or UDim2.new(),
		LayoutOrder = props.LayoutOrder or 0,
		ZIndex = props.ZIndex or 22,
		Name = props.Name or "Card",
	}, { Kit.Corner(UDim.new(0, 18)), Kit.Stroke(3) })
	if props.Parent then
		card.Parent = props.Parent
	end
	return card
end

-- Porta tutti i discendenti a uno ZIndex minimo (i pannelli stanno sopra l'HUD)
function Kit.RaiseZ(root: Instance, base: number)
	for _, d in root:GetDescendants() do
		if d:IsA("GuiObject") and d.ZIndex < base then
			d.ZIndex += base
		end
	end
end

return Kit
