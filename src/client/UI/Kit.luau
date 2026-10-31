-- Mattoni dell'interfaccia in stile "Vetta Pop": creazione di istanze, testi con il contorno
-- sottile, superfici lisce con il gradiente e l'ombra netta, pulsanti a pillola con il bordo 3D che
-- si abbassa quando si premono, schede bianche, tondi con le icone, barre di avanzamento e pannelli
-- con la linguetta bianca del titolo e la X rotonda per chiudere.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")

local Assets = require(ReplicatedStorage.Shared.Assets)
local Theme = require(script.Parent.Theme)

local Kit = {}

Kit.Theme = Theme

local WHITE = Color3.new(1, 1, 1)
local BLACK = Color3.new(0, 0, 0)

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

function Kit.Stroke(thickness: number?, color: Color3?, transparency: number?): UIStroke
	return New("UIStroke", {
		Thickness = thickness or Theme.Stroke,
		Color = color or Theme.Outline,
		Transparency = transparency or 0,
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

-- Colore schiarito (k > 0, verso il bianco) o scurito (k < 0, verso il nero)
function Kit.Tint(c: Color3, k: number): Color3
	return if k >= 0 then c:Lerp(WHITE, k) else c:Lerp(BLACK, -k)
end

-- Colora un riquadro con un gradiente verticale (dall'alto in basso). Il fondo diventa bianco e il
-- colore lo da' l'UIGradient "Paint": per cambiarlo si richiama Kit.Paint.
function Kit.Paint(frame: GuiObject, top: Color3, bottom: Color3?)
	frame.BackgroundColor3 = WHITE
	local g = frame:FindFirstChild("Paint") :: UIGradient?
	if not g then
		g = New("UIGradient", { Name = "Paint", Rotation = 90, Parent = frame })
	end
	(g :: UIGradient).Color = ColorSequence.new(top, bottom or top)
end

-- Colora con una tinta della palette (Theme.Buttons): chiara in alto, piena in basso
function Kit.PaintNamed(frame: GuiObject, name: string)
	local c = Theme.Buttons[name] or Theme.Buttons.Blue
	Kit.Paint(frame, c[3], c[1])
end

-- Testo (di default: Nunito Heavy bianco con il contorno sottile color inchiostro).
-- Font accetta un Font (FontFace) o un Enum.Font; Stroke = false toglie il contorno, un numero ne
-- cambia lo spessore; StrokeColor il colore; MaxTextSize limita il TextScaled.
function Kit.Text(props: { [string]: any }): TextLabel
	local stroke = props.Stroke
	local strokeColor = props.StrokeColor
	local maxSize = props.MaxTextSize
	local font = props.Font or Theme.TitleFont
	props.Stroke = nil
	props.StrokeColor = nil
	props.MaxTextSize = nil
	props.Font = nil
	local label = New("TextLabel", {
		BackgroundTransparency = 1,
		TextColor3 = Theme.Text,
		TextScaled = true,
		RichText = false,
		Size = UDim2.fromScale(1, 1),
	})
	if typeof(font) == "Font" then
		label.FontFace = font
	else
		label.Font = font
	end
	for k, v in props do
		if k ~= "Parent" then
			(label :: any)[k] = v
		end
	end
	if stroke ~= false then
		New("UIStroke", {
			Thickness = if type(stroke) == "number" then stroke else Theme.TextStroke,
			Color = strokeColor or Theme.Outline,
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
			TextColor3 = WHITE,
		})
	end
	for k, v in p do
		(inst :: any)[k] = v
	end
	return inst
end

-- Tondo colorato (gradiente della palette) con un'icona dentro e l'anello bianco
function Kit.IconBadge(iconName: string?, color: string?, props: { [string]: any }): (Frame, GuiObject?)
	local z = props.ZIndex or 1
	local badge = New("Frame", {
		Name = props.Name or "IconBadge",
		Size = props.Size or UDim2.fromOffset(56, 56),
		Position = props.Position or UDim2.new(),
		AnchorPoint = props.AnchorPoint or Vector2.zero,
		LayoutOrder = props.LayoutOrder or 0,
		ZIndex = z,
	}, { Kit.Corner(Theme.Pill) })
	Kit.PaintNamed(badge, color or "Blue")
	if props.Ring ~= false then
		Kit.Stroke(if type(props.Ring) == "number" then props.Ring else 3, props.RingColor or WHITE).Parent = badge
	end
	local icon = nil
	if iconName then
		local k = props.IconScale or 0.82
		icon = Kit.Icon(iconName, {
			Name = "Icon",
			Size = UDim2.fromScale(k, k),
			Position = UDim2.fromScale(0.5, 0.5),
			AnchorPoint = Vector2.new(0.5, 0.5),
			ZIndex = z + 1,
			Parent = badge,
		})
	end
	badge.Parent = props.Parent
	return badge, icon
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
	scale.Scale = 0.5 * base
	task.delay(delay or 0, function()
		Kit.Tween(scale, 0.32, { Scale = base }, Enum.EasingStyle.Back)
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

-- Riquadro sollevato (HUD, avvisi, schede a comparsa): un Frame contenitore trasparente (misura,
-- posizione, UIScale per le animazioni) con l'ombra netta color inchiostro e la faccia colorata.
-- I contenuti vanno nella faccia. Restituisce contenitore e faccia.
export type SurfaceProps = {
	Name: string?,
	Size: UDim2,
	Position: UDim2?,
	AnchorPoint: Vector2?,
	LayoutOrder: number?,
	Visible: boolean?,
	ZIndex: number?,
	Parent: Instance?,
	Color: Color3?, -- colore in alto (default bianco)
	Color2: Color3?, -- colore in basso
	Corner: UDim?,
	Stroke: number?, -- spessore del contorno (0 = nessuno)
	StrokeColor: Color3?,
	StrokeTransparency: number?,
	Shadow: number?, -- distanza dell'ombra in px (0 = nessuna)
	ShadowTransparency: number?,
}
function Kit.Surface(p: SurfaceProps): (Frame, Frame)
	local z = p.ZIndex or 1
	local corner = p.Corner or Theme.Corner
	local holder = New("Frame", {
		Name = p.Name or "Surface",
		BackgroundTransparency = 1,
		Size = p.Size,
		Position = p.Position or UDim2.new(),
		AnchorPoint = p.AnchorPoint or Vector2.zero,
		LayoutOrder = p.LayoutOrder or 0,
		Visible = if p.Visible == nil then true else p.Visible,
		ZIndex = z,
	}, { New("UIScale") })
	local depth = p.Shadow or 5
	if depth > 0 then
		New("Frame", {
			Name = "Shadow",
			BackgroundColor3 = Theme.Ink,
			BackgroundTransparency = p.ShadowTransparency or Theme.ShadowTransparency,
			Size = UDim2.fromScale(1, 1),
			Position = UDim2.fromOffset(0, depth),
			ZIndex = z,
			Parent = holder,
		}, { Kit.Corner(corner) })
	end
	local face = New("Frame", {
		Name = "Face",
		Size = UDim2.fromScale(1, 1),
		ZIndex = z + 1,
		Parent = holder,
	}, { Kit.Corner(corner) })
	local top = p.Color or Theme.Card
	Kit.Paint(face, top, p.Color2 or (if p.Color then top else Theme.CardShade))
	local stroke = p.Stroke or 0
	if stroke > 0 then
		Kit.Stroke(stroke, p.StrokeColor or Theme.Ink, p.StrokeTransparency).Parent = face
	end
	if p.Parent then
		holder.Parent = p.Parent
	end
	return holder, face
end

-- Cartellino bianco a pillola con un testo color inchiostro (etichette sotto i pulsanti, tempi)
function Kit.Tag(props: { [string]: any }): (Frame, TextLabel)
	local holder, face = Kit.Surface({
		Name = props.Name or "Tag",
		Size = props.Size or UDim2.fromOffset(100, 28),
		Position = props.Position,
		AnchorPoint = props.AnchorPoint,
		ZIndex = props.ZIndex,
		Corner = Theme.Pill,
		Stroke = 2,
		StrokeTransparency = 0.75,
		Shadow = 3,
		Parent = props.Parent,
	})
	local text = Kit.Text({
		Text = props.Text or "",
		Size = UDim2.new(1, -16, 0.78, 0),
		Position = UDim2.new(0, 8, 0.11, 0),
		TextColor3 = props.TextColor3 or Theme.Ink,
		Stroke = false,
		ZIndex = (props.ZIndex or 1) + 2,
		Parent = face,
	})
	return holder, text
end

-- Barra di avanzamento: binario grigio chiaro e riempimento verde a pillola
function Kit.Bar(props: { [string]: any }): (Frame, Frame)
	local z = props.ZIndex or 1
	local track = New("Frame", {
		Name = "Bar",
		BackgroundColor3 = props.Track or Theme.Track,
		Size = props.Size,
		Position = props.Position or UDim2.new(),
		ZIndex = z,
		Parent = props.Parent,
	}, { Kit.Corner(Theme.Pill) })
	local fill = New("Frame", {
		Name = "Fill",
		Size = UDim2.fromScale(0, 1),
		ZIndex = z + 1,
		Parent = track,
	}, { Kit.Corner(Theme.Pill) })
	Kit.PaintNamed(fill, props.Color or "Green")
	return track, fill
end

-- Pulsante a pillola: gradiente (chiaro in alto), contorno sottile e bordo 3D dello stesso colore
-- piu' scuro; premuto, la faccia scende sul bordo. Testo e/o icona.
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
	local corner = p.Corner or Theme.Pill
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
	-- bordo 3D sotto la faccia
	local lip = New("Frame", {
		Name = "Shadow",
		BackgroundColor3 = colors[2],
		Size = UDim2.fromScale(1, 1),
		Position = UDim2.fromOffset(0, Theme.Lip),
		ZIndex = 1,
		Parent = holder,
	}, { Kit.Corner(corner) })
	local face = New("TextButton", {
		Name = "Face",
		Text = "",
		AutoButtonColor = false,
		Size = UDim2.fromScale(1, 1),
		ZIndex = 2,
		Parent = holder,
	}, { Kit.Corner(corner) })
	local stroke = Kit.Stroke(2, colors[2])
	stroke.Parent = face
	local label, icon
	if p.Icon and p.Text then
		icon = Kit.Icon(
			p.Icon,
			{ Size = UDim2.fromScale(0.3, 0.74), Position = UDim2.fromScale(0.06, 0.13), ZIndex = 4, Parent = face }
		)
		label = Kit.Text({
			Text = p.Text,
			Size = UDim2.fromScale(0.58, 0.58),
			Position = UDim2.fromScale(0.36, 0.21),
			ZIndex = 4,
			Parent = face,
			MaxTextSize = p.TextSize,
		})
	elseif p.Icon then
		icon = Kit.Icon(
			p.Icon,
			{ Size = UDim2.fromScale(0.72, 0.72), Position = UDim2.fromScale(0.14, 0.12), ZIndex = 4, Parent = face }
		)
	else
		label = Kit.Text({
			Text = p.Text or "",
			Size = UDim2.fromScale(0.84, 0.6),
			Position = UDim2.fromScale(0.08, 0.2),
			ZIndex = 4,
			Parent = face,
			MaxTextSize = p.TextSize,
		})
	end
	local current = p.Color or "Green"
	local function applyColor(name: string)
		local c = Theme.Buttons[name] or colors
		current = name
		Kit.Paint(face, c[3], c[1])
		lip.BackgroundColor3 = c[2]
		stroke.Color = c[2]
		if label then
			-- sui colori chiari il testo diventa color inchiostro e senza contorno
			local light = Theme.LightButtons[name] == true
			label.TextColor3 = if light then Theme.Ink else Theme.Text
			local st = label:FindFirstChildOfClass("UIStroke")
			if st then
				st.Enabled = not light
				st.Color = c[2]
			end
		end
	end
	applyColor(current)
	-- pressione: la faccia scende sul bordo 3D; passandoci sopra si ingrandisce appena
	local function press(down: boolean)
		Kit.Tween(
			face,
			if down then 0.06 else 0.2,
			{ Position = UDim2.fromOffset(0, if down then Theme.Lip - 1 else 0) },
			if down then Enum.EasingStyle.Quad else Enum.EasingStyle.Back
		)
	end
	face.MouseButton1Down:Connect(function()
		press(true)
	end)
	face.MouseButton1Up:Connect(function()
		press(false)
	end)
	face.MouseLeave:Connect(function()
		press(false)
		Kit.Tween(scale, 0.2, { Scale = 1 })
	end)
	face.MouseEnter:Connect(function()
		Kit.Tween(scale, 0.15, { Scale = 1.04 })
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
			if name ~= current then
				applyColor(name)
			end
		end,
		SetText = function(text: string)
			if label then
				label.Text = text
			end
		end,
	}
end

-- Badge rosso con numero e anello bianco (notifiche sui pulsanti)
function Kit.Badge(parent: GuiObject): TextLabel
	local badge = New("Frame", {
		Name = "Badge",
		Size = UDim2.fromOffset(32, 32),
		Position = UDim2.new(1, -22, 0, -10),
		ZIndex = 10,
		Visible = false,
		Parent = parent,
	}, { Kit.Corner(Theme.Pill), Kit.Stroke(2.5, WHITE) })
	Kit.PaintNamed(badge, "Red")
	local text = Kit.Text({
		Text = "!",
		Size = UDim2.fromScale(0.7, 0.66),
		Position = UDim2.fromScale(0.15, 0.15),
		StrokeColor = Theme.Buttons.Red[2],
		ZIndex = 11,
		Parent = badge,
	})
	return text
end

-- Pulsante rotondo rosso con la X bianca e l'anello bianco (chiude i pannelli)
function Kit.CloseButton(props: { [string]: any })
	local b = Kit.Button({
		Color = props.Color or "Red",
		Size = props.Size or UDim2.fromOffset(54, 54),
		Position = props.Position,
		AnchorPoint = props.AnchorPoint,
		Corner = Theme.Pill,
		Parent = props.Parent,
		OnClick = props.OnClick,
	})
	local ring = b.Face:FindFirstChildOfClass("UIStroke")
	if ring then
		ring.Color = WHITE
		ring.Thickness = 3
	end
	for _, rot in { 45, -45 } do
		New("Frame", {
			Name = "Cross",
			BackgroundColor3 = WHITE,
			Size = UDim2.fromScale(0.52, 0.13),
			Position = UDim2.fromScale(0.5, 0.5),
			AnchorPoint = Vector2.new(0.5, 0.5),
			Rotation = rot,
			ZIndex = 6,
			Parent = b.Face,
		}, { Kit.Corner(Theme.Pill) })
	end
	return b
end

-- Segno di spunta bianco disegnato con due barrette (dentro un riquadro quadrato)
function Kit.Check(parent: GuiObject, z: number?)
	for _, arm in { { 0.36, 0.56, 0.3, 45 }, { 0.58, 0.49, 0.5, -47 } } do
		New("Frame", {
			Name = "Check",
			BackgroundColor3 = WHITE,
			Size = UDim2.fromScale(arm[3], 0.13),
			Position = UDim2.fromScale(arm[1], arm[2]),
			AnchorPoint = Vector2.new(0.5, 0.5),
			Rotation = arm[4],
			ZIndex = z or 2,
			Parent = parent,
		}, { Kit.Corner(Theme.Pill) })
	end
end

-- Pannello (finestra): superficie colorata con il gradiente, l'ombra netta, la linguetta bianca del
-- titolo (con il tondo dell'icona) a cavallo del bordo in alto e la X rotonda nell'angolo. Frame e'
-- un contenitore trasparente (scalato da UI); i contenuti vanno in Body.
function Kit.Panel(title: string, size: UDim2, color: string?, parent: Instance, icon: string?)
	local colors = Theme.Buttons[color or "Cyan"] or Theme.Buttons.Cyan
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
	local corner = UDim.new(0, 30)
	New("Frame", {
		Name = "Shadow",
		BackgroundColor3 = Theme.Ink,
		BackgroundTransparency = 0.5,
		Size = UDim2.fromScale(1, 1),
		Position = UDim2.fromOffset(0, 10),
		ZIndex = 19,
		Parent = frame,
	}, { Kit.Corner(corner) })
	local face = New("Frame", {
		Name = "Face",
		Size = UDim2.fromScale(1, 1),
		ZIndex = 20,
		Parent = frame,
	}, { Kit.Corner(corner), Kit.Stroke(3, colors[2]) })
	Kit.Paint(face, colors[3], colors[1])
	-- linguetta bianca del titolo, larga quanto il testo
	local tab = New("Frame", {
		Name = "Ribbon",
		AutomaticSize = Enum.AutomaticSize.X,
		Size = UDim2.fromOffset(0, 58),
		Position = UDim2.fromOffset(30, -29),
		ZIndex = 22,
		Parent = frame,
	}, {
		Kit.Corner(Theme.Pill),
		Kit.Stroke(3, colors[2]),
		New("UIPadding", { PaddingLeft = UDim.new(0, 74), PaddingRight = UDim.new(0, 28) }),
	})
	Kit.Paint(tab, Theme.Card, Theme.CardShade)
	local titleLabel = Kit.Text({
		Name = "Title",
		Text = title,
		TextScaled = false,
		TextSize = 37,
		AutomaticSize = Enum.AutomaticSize.X,
		Size = UDim2.new(0, 0, 1, 0),
		TextColor3 = Theme.Ink,
		Stroke = false,
		ZIndex = 23,
		Parent = tab,
	})
	-- tondo dell'icona sull'inizio della linguetta (fuori dalla linguetta, che si allarga col testo)
	Kit.IconBadge(icon, color or "Cyan", {
		Size = UDim2.fromOffset(72, 72),
		Position = UDim2.fromOffset(20, -36),
		ZIndex = 24,
		Ring = 3,
		RingColor = colors[2],
		IconScale = 0.84,
		Parent = frame,
	})
	local close = Kit.CloseButton({ Position = UDim2.new(1, -38, 0, -18), Parent = frame })
	close.Frame.ZIndex = 24
	Kit.RaiseZ(close.Frame, 22)
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

-- Scheda (riquadro) dentro i pannelli: bianca con un velo di gradiente; colorata se Color e' un
-- colore acceso (gradiente piu' chiaro in alto e contorno sottile piu' scuro)
function Kit.Card(props: { [string]: any }): Frame
	local color = props.Color or Theme.Card
	local card = New("Frame", {
		Size = props.Size or UDim2.fromScale(1, 1),
		Position = props.Position or UDim2.new(),
		LayoutOrder = props.LayoutOrder or 0,
		ZIndex = props.ZIndex or 22,
		Name = props.Name or "Card",
	}, { Kit.Corner(props.Corner or UDim.new(0, 18)) })
	if color == Theme.Card then
		Kit.Paint(card, Theme.Card, Theme.CardShade)
	elseif color == Theme.CardLight then
		Kit.Paint(card, Theme.CardLight, Kit.Tint(Theme.CardLight, -0.03))
	else
		Kit.Paint(card, Kit.Tint(color, 0.24), color)
		Kit.Stroke(2, Kit.Tint(color, -0.28)).Parent = card
	end
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
