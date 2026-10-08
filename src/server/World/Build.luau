-- Piccole utilita' per costruire strutture con le Part (usate da mappa, lotti, rifugi).

local Build = {}

export type PartProps = {
	name: string?,
	size: Vector3,
	cframe: CFrame,
	color: Color3?,
	material: Enum.Material?,
	shape: Enum.PartType?,
	transparency: number?,
	collide: boolean?,
	parent: Instance?,
	class: string?,
	castShadow: boolean?,
	query: boolean?,
}

function Build.Part(p: PartProps): BasePart
	local part = Instance.new((p.class or "Part") :: any) :: BasePart
	if p.shape and part:IsA("Part") then
		(part :: Part).Shape = p.shape
	end
	part.Name = p.name or "Part"
	part.Size = p.size
	part.CFrame = p.cframe
	part.Color = p.color or Color3.new(1, 1, 1)
	part.Material = p.material or Enum.Material.SmoothPlastic
	part.Transparency = p.transparency or 0
	part.Anchored = true
	part.CanCollide = if p.collide == nil then true else p.collide
	part.CanQuery = if p.query == nil then part.CanCollide else p.query
	part.CanTouch = false
	part.CastShadow = if p.castShadow == nil then true else p.castShadow
	part.TopSurface = Enum.SurfaceType.Smooth
	part.BottomSurface = Enum.SurfaceType.Smooth
	part.Parent = p.parent
	return part
end

-- Cartello con testo (SurfaceGui). Il testo viene localizzato dal client tramite il tag "LocalizedSign".
function Build.Sign(parent: Instance, cframe: CFrame, size: Vector3, key: string, args: { [string]: any }?, colors: { bg: Color3, text: Color3 }?): BasePart
	local board = Build.Part({
		name = "Sign",
		size = size,
		cframe = cframe,
		color = if colors then colors.bg else Color3.fromRGB(255, 226, 120),
		material = Enum.Material.SmoothPlastic,
		parent = parent,
	})
	local gui = Instance.new("SurfaceGui")
	gui.Name = "SignGui"
	gui.Face = Enum.NormalId.Front
	gui.SizingMode = Enum.SurfaceGuiSizingMode.PixelsPerStud
	gui.PixelsPerStud = 40
	gui.LightInfluence = 0.2
	gui.Parent = board
	local label = Instance.new("TextLabel")
	label.Name = "Text"
	label.BackgroundTransparency = 1
	label.Size = UDim2.fromScale(1, 1)
	label.Font = Enum.Font.LuckiestGuy
	label.TextScaled = true
	label.TextColor3 = if colors then colors.text else Color3.fromRGB(60, 36, 20)
	label.Text = key
	label.Parent = gui
	local pad = Instance.new("UIPadding")
	pad.PaddingLeft = UDim.new(0.05, 0)
	pad.PaddingRight = UDim.new(0.05, 0)
	pad.PaddingTop = UDim.new(0.1, 0)
	pad.PaddingBottom = UDim.new(0.1, 0)
	pad.Parent = label
	label:SetAttribute("Key", key)
	if args then
		for k, v in args do
			label:SetAttribute("Arg_" .. k, v)
		end
	end
	game:GetService("CollectionService"):AddTag(label, "LocalizedSign")
	return board
end

function Build.Model(name: string, parent: Instance?): Model
	local m = Instance.new("Model")
	m.Name = name
	m.Parent = parent
	return m
end

-- Raggio verso il basso sul terreno/parti (ignora gli elementi indicati)
function Build.Ground(x: number, z: number, fromY: number?, ignore: { Instance }?): Vector3?
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = ignore or {}
	params.IgnoreWater = true
	local origin = Vector3.new(x, fromY or 420, z)
	local hit = workspace:Raycast(origin, Vector3.new(0, -500, 0), params)
	return if hit then hit.Position else nil
end

function Build.GroundNormal(x: number, z: number, fromY: number?, ignore: { Instance }?): (Vector3?, Vector3?)
	local params = RaycastParams.new()
	params.FilterType = Enum.RaycastFilterType.Exclude
	params.FilterDescendantsInstances = ignore or {}
	params.IgnoreWater = true
	local hit = workspace:Raycast(Vector3.new(x, fromY or 420, z), Vector3.new(0, -500, 0), params)
	if hit then
		return hit.Position, hit.Normal
	end
	return nil, nil
end

return Build
