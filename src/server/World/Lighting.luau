-- Luce, atmosfera, nuvole ed effetti di post-produzione: aspetto luminoso e saturo da cartone.

local Lighting = game:GetService("Lighting")
local ReplicatedStorage = game:GetService("ReplicatedStorage")

local Assets = require(ReplicatedStorage.Shared.Assets)

local World = {}

local function ensure(className: string, name: string, parent: Instance): Instance
	local inst = parent:FindFirstChild(name)
	if not inst then
		inst = Instance.new(className)
		inst.Name = name
		inst.Parent = parent
	end
	return inst
end

-- Nota: Lighting.Technology non e' modificabile dagli script, e' impostata nel file di progetto.
function World.Apply()
	Lighting.Brightness = 2.6
	Lighting.ClockTime = 13.6
	Lighting.GeographicLatitude = 28
	Lighting.Ambient = Color3.fromRGB(92, 92, 108)
	Lighting.OutdoorAmbient = Color3.fromRGB(150, 150, 166)
	Lighting.ColorShift_Top = Color3.fromRGB(255, 244, 228)
	Lighting.EnvironmentDiffuseScale = 1
	Lighting.EnvironmentSpecularScale = 0.55
	Lighting.ExposureCompensation = 0.12
	Lighting.GlobalShadows = true
	Lighting.ShadowSoftness = 0.22

	local atmo = ensure("Atmosphere", "Atmosphere", Lighting) :: Atmosphere
	atmo.Density = 0.26
	atmo.Offset = 0.12
	atmo.Color = Color3.fromRGB(206, 226, 255)
	atmo.Decay = Color3.fromRGB(126, 156, 214)
	atmo.Glare = 0.12
	atmo.Haze = 1.1

	local sky = ensure("Sky", "Sky", Lighting) :: Sky
	sky.CelestialBodiesShown = true
	sky.SunAngularSize = 14
	sky.MoonAngularSize = 9
	sky.StarCount = 0
	-- cielo pastello: le quattro facce laterali sono uguali (il colore dipende solo dall'altezza)
	local img = Assets.Images
	if img.SkySide and img.SkyUp and img.SkyDn then
		sky.SkyboxBk = img.SkySide
		sky.SkyboxFt = img.SkySide
		sky.SkyboxLf = img.SkySide
		sky.SkyboxRt = img.SkySide
		sky.SkyboxUp = img.SkyUp
		sky.SkyboxDn = img.SkyDn
	end

	local bloom = ensure("BloomEffect", "Bloom", Lighting) :: BloomEffect
	bloom.Intensity = 0.35
	bloom.Size = 26
	bloom.Threshold = 0.96

	local cc = ensure("ColorCorrectionEffect", "Grade", Lighting) :: ColorCorrectionEffect
	cc.Saturation = 0.16
	cc.Contrast = 0.07
	cc.Brightness = 0.02
	cc.TintColor = Color3.fromRGB(255, 252, 246)

	local rays = ensure("SunRaysEffect", "SunRays", Lighting) :: SunRaysEffect
	rays.Intensity = 0.05
	rays.Spread = 0.55

	local clouds = ensure("Clouds", "Clouds", workspace.Terrain) :: Clouds
	clouds.Cover = 0.5
	clouds.Density = 0.62
	clouds.Color = Color3.fromRGB(255, 255, 255)

	-- erba animata sul terreno (proprieta' non sempre scrivibile dagli script)
	pcall(function()
		workspace.Terrain.Decoration = true
	end)
	workspace.Terrain.WaterColor = Color3.fromRGB(80, 190, 255)
end

return World
