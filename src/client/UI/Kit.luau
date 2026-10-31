-- Mattoni dell'interfaccia in stile "giocattolo di stoffa cucito": creazione di istanze, testi con
-- contorno, feltro dai colori accesi con la cucitura bianca attaccata al contorno scuro, pulsanti
-- con ombra e animazioni, pannelli con l'etichetta di stoffa e il bottone da cucito per chiudere.

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

-- Trama del feltro sopra il colore pieno (sotto ai contenuti, con gli stessi angoli arrotondati)
function Kit.Felt(frame: GuiObject, transparency: number?)
	local id = Assets.Images.FeltNoise
	if not id then
		return
	end
	local corner = frame:FindFirstChildOfClass("UICorner")
	New("ImageLabel", {
		Name = "Felt",
		BackgroundTransparency = 1,
		Image = id,
		ScaleType = Enum.ScaleType.Tile,
		TileSize = UDim2.fromOffset(96, 96),
		ImageTransparency = transparency or 0.9, -- trama leggera: i colori restano brillanti
		Size = UDim2.fromScale(1, 1),
		ZIndex = 1,
		Parent = frame,
	}, { New("UICorner", { CornerRadius = if corner then corner.CornerRadius else UDim.new() }) })
end

-- Cucitura tratteggiata attaccata al bordo, dentro il riquadro: tratti ripetuti sui lati e quarti di
-- cerchio negli angoli (raggio in px dell'UICorner; radius < 0 = riquadro rotondo).
local CORNERS = { 8, 12, 16, 20, 28, 40 }
function Kit.Stitch(frame: GuiObject, radius: number, color: Color3?): Frame?
	local images = Assets.Images
	if not images.StitchH then
		return nil
	end
	local col = color or Theme.Stitch
	local holder = New("Frame", {
		Name = "Stitch",
		BackgroundTransparency = 1,
		Size = UDim2.fromScale(1, 1),
		ZIndex = 1,
		Parent = frame,
	})
	if radius < 0 then
		New("ImageLabel", {
			BackgroundTransparency = 1,
			Image = images.StitchRing,
			ImageColor3 = col,
			Size = UDim2.fromScale(1, 1),
			ZIndex = 1,
			Parent = holder,
		})
		return holder
	end
	local r = CORNERS[1]
	for _, c in CORNERS do
		if math.abs(c - radius) < math.abs(r - radius) then
			r = c
		end
	end
	local function strip(name: string, pos: UDim2, size: UDim2, image: string, tile: UDim2)
		New("ImageLabel", {
			Name = name,
			BackgroundTransparency = 1,
			Image = image,
			ScaleType = Enum.ScaleType.Tile,
			TileSize = tile,
			ImageColor3 = col,
			Position = pos,
			Size = size,
			ZIndex = 1,
			Parent = holder,
		})
	end
	local h, v = UDim2.fromOffset(16, 4), UDim2.fromOffset(4, 16)
	strip("Top", UDim2.fromOffset(r, 0.5), UDim2.new(1, -2 * r, 0, 4), images.StitchH, h)
	strip("Bottom", UDim2.new(0, r, 1, -4.5), UDim2.new(1, -2 * r, 0, 4), images.StitchH, h)
	strip("Left", UDim2.fromOffset(0.5, r), UDim2.new(0, 4, 1, -2 * r), images.StitchV, v)
	strip("Right", UDim2.new(1, -4.5, 0, r), UDim2.new(0, 4, 1, -2 * r), images.StitchV, v)
	local corners = { UDim2.fromOffset(0, 0), UDim2.new(1, -r, 0, 0), UDim2.new(1, -r, 1, -r), UDim2.new(0, 0, 1, -r) }
	for i, pos in corners do
		New("ImageLabel", {
			Name = "Corner" .. i,
			BackgroundTransparency = 1,
			Image = images["StitchCorner" .. r] or "",
			ImageColor3 = col,
			Size = UDim2.fromOffset(r, r),
			Position = pos,
			Rotation = (i - 1) * 90,
			ZIndex = 1,
			Parent = holder,
		})
	end
	return holder
end

-- Raggio (px) della cucitura per un riquadro con questo UICorner e queste misure (-1 = rotondo)
function Kit.StitchRadius(size: UDim2, corner: UDim?): number
	local c = corner or Theme.Corner
	if c.Scale > 0 then
		local w, h = size.X.Offset, size.Y.Offset
		if w > 0 and h > 0 and math.abs(w - h) > 2 then
			return math.min(w, h) / 2
		end
		return -1
	end
	return c.Offset
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
		Position = UDim2.new(0, 0, 0, 5),
		ZIndex = 1,
		Parent = holder,
	}, { Kit.Corner(p.Corner) })
	local face = New("TextButton", {
		Name = "Face",
		Text = "",
		AutoButtonColor = false,
		BackgroundColor3 = colors[1],
		Size = UDim2.fromScale(1, 1),
		ZIndex = 2,
		Parent = holder,
	}, { Kit.Corner(p.Corner), Kit.Stroke(Theme.Stroke) })
	-- feltro e cucitura attaccata al contorno
	Kit.Felt(face)
	Kit.Stitch(face, Kit.StitchRadius(p.Size, p.Corner))
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
			face.BackgroundColor3 = c[1]
			-- sul feltro chiaro il testo diventa scuro e senza contorno
			if label then
				local light = name == "White"
				label.TextColor3 = if light then Theme.Ink else Theme.Text
				local st = label:FindFirstChildOfClass("UIStroke")
				if st then
					st.Enabled = not light
				end
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
		BackgroundColor3 = Theme.Buttons.Red[1],
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

-- Bottone da cucito rosso con quattro fori e la X di filo (chiude i pannelli)
function Kit.SewButton(props: { [string]: any })
	local b = Kit.Button({
		Color = props.Color or "Red",
		Size = props.Size or UDim2.fromOffset(58, 58),
		Position = props.Position,
		AnchorPoint = props.AnchorPoint,
		Corner = UDim.new(1, 0),
		Parent = props.Parent,
		OnClick = props.OnClick,
	})
	for _, pos in { { 0.33, 0.33 }, { 0.67, 0.33 }, { 0.33, 0.67 }, { 0.67, 0.67 } } do
		New("Frame", {
			Name = "Hole",
			BackgroundColor3 = Theme.Outline,
			Size = UDim2.fromScale(0.15, 0.15),
			Position = UDim2.fromScale(pos[1], pos[2]),
			AnchorPoint = Vector2.new(0.5, 0.5),
			ZIndex = 5,
			Parent = b.Face,
		}, { Kit.Corner(UDim.new(1, 0)) })
	end
	for _, rot in { 45, -45 } do
		New("Frame", {
			Name = "Thread",
			BackgroundColor3 = Theme.Stitch,
			Size = UDim2.new(0.6, 0, 0.09, 0),
			Position = UDim2.fromScale(0.5, 0.5),
			AnchorPoint = Vector2.new(0.5, 0.5),
			Rotation = rot,
			ZIndex = 6,
			Parent = b.Face,
		}, { Kit.Corner(UDim.new(1, 0)) })
	end
	return b
end

-- Etichetta di stoffa quasi bianca cucita ai lati (titoli dei pannelli, cartellini)
function Kit.FabricLabel(props: { [string]: any }): (Frame, TextLabel)
	local label = New("Frame", {
		Name = props.Name or "Label",
		BackgroundColor3 = props.Color or Theme.Card,
		Size = props.Size,
		Position = props.Position or UDim2.new(),
		AnchorPoint = props.AnchorPoint or Vector2.zero,
		Rotation = props.Rotation or 0,
		ZIndex = props.ZIndex or 1,
		LayoutOrder = props.LayoutOrder or 0,
		Parent = props.Parent,
	}, { Kit.Corner(UDim.new(0, 8)), Kit.Stroke(props.Stroke or 4) })
	local zi = (props.ZIndex or 1) + 1
	if Assets.Images.StitchV then
		for _, pos in { UDim2.new(0, 4, 0, 6), UDim2.new(1, -8, 0, 6) } do
			New("ImageLabel", {
				Name = "SideStitch",
				BackgroundTransparency = 1,
				Image = Assets.Images.StitchV,
				ScaleType = Enum.ScaleType.Tile,
				TileSize = UDim2.fromOffset(4, 16),
				ImageColor3 = props.StitchColor or Theme.Ink,
				Position = pos,
				Size = UDim2.new(0, 4, 1, -12),
				ZIndex = zi,
				Parent = label,
			})
		end
	end
	local text = Kit.Text({
		Text = props.Text or "",
		Font = props.Font,
		Size = UDim2.new(1, -28, 0.74, 0),
		Position = UDim2.new(0, 14, 0.13, 0),
		TextColor3 = props.TextColor3 or Theme.Ink,
		Stroke = false,
		ZIndex = zi,
		Parent = label,
	})
	return label, text
end

-- Pannello (finestra) di feltro colorato con la cucitura, l'etichetta del titolo e il bottone
-- da cucito per chiudere. Frame e' un contenitore trasparente (scalato da UI) con l'ombra e la faccia.
function Kit.Panel(title: string, size: UDim2, color: string?, parent: Instance)
	local felt = (Theme.Buttons[color or "Cyan"] or Theme.Buttons.Cyan)[1]
	local frame = New("Frame", {
		Name = "Panel",
		BackgroundTransparency = 1,
		Size = size,
		Position = UDim2.fromScale(0.5, 0.52),
		AnchorPoint = Vector2.new(0.5, 0.5),
		Visible = false,
		ZIndex = 20,
		Parent = parent,
	}, { New("UIScale") })
	New("Frame", {
		Name = "Shadow",
		BackgroundColor3 = Theme.Outline,
		Size = UDim2.fromScale(1, 1),
		Position = UDim2.fromOffset(0, 8),
		ZIndex = 19,
		Parent = frame,
	}, { Kit.Corner(UDim.new(0, 28)) })
	local face = New("Frame", {
		Name = "Face",
		BackgroundColor3 = felt,
		Size = UDim2.fromScale(1, 1),
		ZIndex = 20,
		Parent = frame,
	}, { Kit.Corner(UDim.new(0, 28)), Kit.Stroke(5) })
	Kit.Felt(face)
	Kit.Stitch(face, 28)
	-- etichetta di stoffa con il titolo, cucita sul bordo in alto
	local ribbon, titleLabel = Kit.FabricLabel({
		Name = "Ribbon",
		Text = title,
		Size = UDim2.new(0.44, 0, 0, 60),
		Position = UDim2.new(0.5, 0, 0, -28),
		AnchorPoint = Vector2.new(0.5, 0),
		Rotation = -2,
		ZIndex = 22,
		Parent = frame,
	})
	local _ = ribbon
	local close = Kit.SewButton({ Position = UDim2.new(1, -30, 0, -22), Parent = frame })
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
	return { Frame = frame, Body = body, Close = close, Title = titleLabel, Face = face }
end

-- Scheda (riquadro) dentro i pannelli: interno quasi bianco con la cucitura chiara
function Kit.Card(props: { [string]: any }): Frame
	local color = props.Color or Theme.Card
	local card = New("Frame", {
		BackgroundColor3 = color,
		Size = props.Size or UDim2.fromScale(1, 1),
		Position = props.Position or UDim2.new(),
		LayoutOrder = props.LayoutOrder or 0,
		ZIndex = props.ZIndex or 22,
		Name = props.Name or "Card",
	}, { Kit.Corner(UDim.new(0, 16)), Kit.Stroke(3) })
	local light = color == Theme.Card or color == Theme.CardLight
	Kit.Felt(card, if light then 0.95 else 0.9)
	Kit.Stitch(card, 16, if light then Theme.StitchCard else nil)
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
