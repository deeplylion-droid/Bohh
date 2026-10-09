--!strict
-- Costruzione dei modelli di uova e pet con effetti (rarita', mutazioni, taglie).
-- Usato dal server per il mondo e dal client per le anteprime nell'interfaccia.

local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Pets = require(script.Parent.Config.Pets)
local Rarities = require(script.Parent.Config.Rarities)
local Variants = require(script.Parent.Config.Variants)

local Visuals = {}

local SPARKLE = "rbxasset://textures/particles/sparkles_main.dds"
local FIRE = "rbxasset://textures/particles/fire_main.dds"

local function assetsFolder(category: string): Folder?
	local root = ReplicatedStorage:FindFirstChild("Assets")
	return root and root:FindFirstChild(category) :: Folder?
end

local function clone(category: string, name: string): Model?
	local f = assetsFolder(category)
	local m = f and f:FindFirstChild(name)
	return if m then (m :: Model):Clone() else nil
end

local function fallbackEgg(rarity: string): Model
	local model = Instance.new("Model")
	model.Name = "Egg" .. rarity
	local root = Instance.new("Part")
	root.Name = "Root"
	root.Size = Vector3.one
	root.Transparency = 1
	root.Anchored = true
	root.CanCollide = false
	root.Parent = model
	local shell = Instance.new("Part")
	shell.Name = "Shell"
	shell.Shape = Enum.PartType.Ball
	shell.Size = Vector3.new(2.4, 3.1, 2.4)
	shell.CFrame = CFrame.new(0, 1.55, 0)
	shell.Color = Rarities.Get(rarity).color
	shell.Material = Enum.Material.SmoothPlastic
	shell.Anchored = true
	shell.CanCollide = false
	shell:SetAttribute("Role", "skin")
	shell.Parent = model
	local mesh = Instance.new("SpecialMesh")
	mesh.MeshType = Enum.MeshType.Sphere
	mesh.Parent = shell
	model.PrimaryPart = root
	model.WorldPivot = CFrame.new()
	return model
end

local function emitter(parent: Instance, props: { [string]: any }): ParticleEmitter
	local p = Instance.new("ParticleEmitter")
	p.Texture = props.texture or SPARKLE
	p.Color = props.color
	p.LightEmission = props.lightEmission or 0.8
	p.Size = props.size or NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.5), NumberSequenceKeypoint.new(1, 0) })
	p.Transparency = props.transparency
		or NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.1), NumberSequenceKeypoint.new(1, 1) })
	p.Lifetime = props.lifetime or NumberRange.new(0.8, 1.4)
	p.Rate = props.rate or 6
	p.Speed = props.speed or NumberRange.new(0.6, 1.6)
	p.SpreadAngle = Vector2.new(180, 180)
	p.Rotation = NumberRange.new(0, 360)
	p.RotSpeed = NumberRange.new(-90, 90)
	p.Acceleration = props.acceleration or Vector3.new(0, 0.6, 0)
	p.LightInfluence = 0
	p.Parent = parent
	return p
end

local function light(parent: Instance, color: Color3, range: number, brightness: number)
	local l = Instance.new("PointLight")
	l.Color = color
	l.Range = range
	l.Brightness = brightness
	l.Shadows = false
	l.Parent = parent
end

local function mainPart(model: Model): BasePart?
	local best, size = nil, 0
	for _, d in model:GetChildren() do
		if d:IsA("BasePart") and d.Name ~= "Root" then
			local v = d.Size.X * d.Size.Y * d.Size.Z
			if v > size then
				best, size = d, v
			end
		end
	end
	return best
end

-- Effetti delle uova rare: brillantini, braci, alone luminoso
function Visuals.EggEffects(model: Model, rarity: string)
	local core = mainPart(model)
	if not core then
		return
	end
	local r = Rarities.Get(rarity)
	if r.order >= 3 then
		local rate = ({ 4, 6, 9, 12, 16, 22, 30 })[r.order - 2] or 30
		local col = Rarities.Gradients[rarity] or ColorSequence.new(r.color)
		emitter(core, { color = col, rate = rate })
	end
	if r.order >= 4 then
		light(core, r.color, 8 + r.order, 0.8 + r.order * 0.15)
	end
	if rarity == "Mythic" then
		emitter(core, {
			texture = FIRE,
			color = ColorSequence.new(Color3.fromRGB(255, 120, 40), Color3.fromRGB(255, 40, 30)),
			size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.4), NumberSequenceKeypoint.new(1, 0) }),
			rate = 10,
			acceleration = Vector3.new(0, 3, 0),
			lightEmission = 1,
		})
	elseif rarity == "Secret" then
		emitter(core, {
			color = ColorSequence.new(Color3.fromRGB(150, 60, 255), Color3.fromRGB(40, 255, 220)),
			size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.9), NumberSequenceKeypoint.new(1, 0) }),
			rate = 14,
			speed = NumberRange.new(2, 4),
			lightEmission = 1,
		})
	elseif rarity == "Ultra" then
		emitter(core, {
			texture = FIRE,
			color = ColorSequence.new(Color3.fromRGB(255, 200, 60), Color3.fromRGB(255, 40, 80)),
			size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 1.1), NumberSequenceKeypoint.new(1, 0) }),
			rate = 18,
			speed = NumberRange.new(1.5, 3),
			acceleration = Vector3.new(0, 4, 0),
			lightEmission = 1,
		})
		-- colonna di luce verso il cielo: si vede da tutta la montagna, anche mentre lo si porta via
		local a0 = Instance.new("Attachment")
		a0.Name = "BeaconBase"
		a0.Parent = core
		local a1 = Instance.new("Attachment")
		a1.Name = "BeaconTop"
		a1.Position = Vector3.new(0, 260, 0)
		a1.Parent = core
		local beam = Instance.new("Beam")
		beam.Name = "UltraBeacon"
		beam.Attachment0 = a0
		beam.Attachment1 = a1
		beam.FaceCamera = true
		beam.Width0 = 3.2
		beam.Width1 = 1.2
		beam.LightEmission = 1
		beam.LightInfluence = 0
		beam.Segments = 2
		beam.Color = ColorSequence.new(Color3.fromRGB(255, 70, 110), Color3.fromRGB(255, 210, 90))
		beam.Transparency = NumberSequence.new({
			NumberSequenceKeypoint.new(0, 0.15),
			NumberSequenceKeypoint.new(0.6, 0.5),
			NumberSequenceKeypoint.new(1, 1),
		})
		beam.Parent = core
		light(core, r.color, 22, 3)
	end
end

-- Effetti dei pet Ultra: particelle sulle parti luminose con un nome preciso (vedi gli script in
-- art/pets). Dimensioni in proporzione alla scala del modello; intensity riduce la quantita'
-- (pet in braccio o anteprime piccole).
local PET_FX: { [string]: { [string]: any } } = {
	Aura = {
		color = ColorSequence.new(Color3.fromRGB(255, 90, 230), Color3.fromRGB(150, 60, 255)),
		size = 0.35,
		rate = 26,
		speed = NumberRange.new(0.6, 1.6),
		acceleration = Vector3.new(0, 1.2, 0),
		lifetime = NumberRange.new(1.4, 2.4),
		light = Color3.fromRGB(200, 90, 255),
	},
	Mane = {
		color = ColorSequence.new(Color3.fromRGB(255, 255, 210), Color3.fromRGB(80, 220, 255)),
		size = 0.22,
		rate = 40,
		speed = NumberRange.new(2.5, 5),
		acceleration = Vector3.new(0, 0, 0),
		lifetime = NumberRange.new(0.15, 0.4),
		light = Color3.fromRGB(120, 230, 255),
	},
	Flames = {
		texture = FIRE,
		color = ColorSequence.new(Color3.fromRGB(255, 210, 80), Color3.fromRGB(255, 60, 20)),
		size = 0.45,
		rate = 34,
		speed = NumberRange.new(0.8, 1.8),
		acceleration = Vector3.new(0, 2.2, 0),
		lifetime = NumberRange.new(0.6, 1.2),
		light = Color3.fromRGB(255, 120, 40),
	},
	Rage = {
		texture = FIRE,
		color = ColorSequence.new(Color3.fromRGB(255, 120, 60), Color3.fromRGB(200, 0, 20)),
		size = 0.25,
		rate = 18,
		speed = NumberRange.new(0.4, 1.0),
		acceleration = Vector3.new(0, 1.5, 0),
		lifetime = NumberRange.new(0.8, 1.6),
		light = Color3.fromRGB(255, 40, 30),
	},
	Venom = {
		color = ColorSequence.new(Color3.fromRGB(190, 255, 80), Color3.fromRGB(40, 220, 60)),
		size = 0.18,
		rate = 24,
		speed = NumberRange.new(0, 0.3),
		acceleration = Vector3.new(0, -3.5, 0),
		lifetime = NumberRange.new(0.8, 1.4),
		light = Color3.fromRGB(110, 255, 80),
	},
}

function Visuals.PetEffects(model: Model, petId: string, intensity: number)
	local def = Pets.ById[petId]
	if not def or not def.giant then
		return
	end
	local k = model:GetScale()
	for _, d in model:GetDescendants() do
		local fx = if d:IsA("BasePart") then PET_FX[d.Name] else nil
		if fx then
			local size = fx.size * k
			emitter(d, {
				texture = fx.texture,
				color = fx.color,
				size = NumberSequence.new({
					NumberSequenceKeypoint.new(0, size),
					NumberSequenceKeypoint.new(0.6, size * 0.7),
					NumberSequenceKeypoint.new(1, 0),
				}),
				rate = fx.rate * intensity,
				speed = NumberRange.new(fx.speed.Min * k, fx.speed.Max * k),
				acceleration = fx.acceleration * k,
				lifetime = fx.lifetime,
				lightEmission = 1,
			})
			if intensity >= 1 then
				light(d, fx.light, 3 * k, 2.2)
			end
		end
	end
end

function Visuals.MakeEgg(rarity: string, withEffects: boolean?): Model
	local model = clone("Eggs", "Egg" .. rarity) or fallbackEgg(rarity)
	model:SetAttribute("Rarity", rarity)
	if withEffects ~= false then
		Visuals.EggEffects(model, rarity)
	end
	return model
end

-- Colore "oro" che conserva la luminosita' della parte originale
local function goldFrom(c: Color3): Color3
	local _, _, v = c:ToHSV()
	return Color3.fromHSV(0.12, 0.78, math.clamp(0.55 + v * 0.45, 0, 1))
end

function Visuals.ApplyMutation(model: Model, mutation: string)
	model:SetAttribute("Mutation", mutation)
	if mutation == "None" then
		return
	end
	local core = mainPart(model)
	for _, d in model:GetDescendants() do
		if not d:IsA("BasePart") or d.Name == "Root" then
			continue
		end
		local role = d:GetAttribute("Role")
		if role == "eye" or role == "shine" then
			continue
		end
		local base = (d:GetAttribute("BaseColor") :: Color3?) or d.Color
		if mutation == "Gold" then
			d.Color = goldFrom(base)
			d.Material = if role == "glow" then Enum.Material.Neon else Enum.Material.Foil
			d.Reflectance = 0.15
		elseif mutation == "Diamond" then
			local _, _, v = base:ToHSV()
			d.Color = Color3.fromHSV(0.53, 0.32, math.clamp(0.75 + v * 0.25, 0, 1))
			d.Material = Enum.Material.Glass
			d.Transparency = 0.08
			d.Reflectance = 0.25
		elseif mutation == "Rainbow" then
			d.Material = if role == "glow" then Enum.Material.Neon else Enum.Material.SmoothPlastic
		elseif mutation == "Cosmic" then
			if role == "skin" then
				d.Color = Color3.fromRGB(46, 26, 96)
				d.Material = Enum.Material.SmoothPlastic
			else
				d.Color = Color3.fromRGB(200, 130, 255)
				d.Material = Enum.Material.Neon
			end
		end
	end
	if core then
		local m = Variants.Mutations[mutation]
		if mutation == "Rainbow" then
			emitter(core, { color = Rarities.Gradients.Divine, rate = 8 })
		elseif mutation == "Cosmic" then
			emitter(core, {
				color = ColorSequence.new(Color3.fromRGB(255, 255, 255), Color3.fromRGB(170, 120, 255)),
				rate = 10,
				size = NumberSequence.new({ NumberSequenceKeypoint.new(0, 0.35), NumberSequenceKeypoint.new(1, 0) }),
			})
			light(core, m.color, 10, 1.2)
		else
			emitter(core, { color = ColorSequence.new(m.color), rate = 5 })
		end
	end
	if mutation == "Rainbow" then
		game:GetService("CollectionService"):AddTag(model, "RainbowPet")
	end
end

-- maxHeight: altezza massima in stud (pet portati in braccio o anteprime), anche per i giganti Ultra
function Visuals.MakePet(petId: string, mutation: string?, size: string?, maxHeight: number?): Model
	local pet = Pets.Get(petId)
	local model: Model = clone("Pets", petId) or fallbackEgg(pet.rarity)
	model.Name = petId
	model:SetAttribute("PetId", petId)
	model:SetAttribute("Rarity", pet.rarity)
	model:SetAttribute("Size", size or "Normal")
	model:SetAttribute("Giant", pet.giant == true and maxHeight == nil)
	-- scala: altezza di riferimento del pet x moltiplicatore della taglia
	local h = (model:GetAttribute("Height") :: number?) or pet.height
	local target = pet.height * Variants.Sizes[size or "Normal"].scale
	if maxHeight then
		target = math.min(target, maxHeight)
	end
	local scale = target / math.max(h, 0.1)
	if math.abs(scale - 1) > 0.01 then
		model:ScaleTo(scale)
	end
	Visuals.ApplyMutation(model, mutation or "None")
	Visuals.PetEffects(model, petId, if maxHeight then 0.25 else 1)
	return model
end

return Visuals
