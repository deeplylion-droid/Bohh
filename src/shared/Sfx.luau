-- Suoni dai fogli di effetti sintetizzati (Audio, Audio2, Audio3): ogni effetto è un intervallo
-- di uno dei file, riprodotto con Sound.PlaybackRegion.
local Shared = script.Parent
local SHEETS = {
	require(Shared:WaitForChild("Audio")),
	require(Shared:WaitForChild("Audio2")),
	require(Shared:WaitForChild("Audio3")),
}

local Sfx = {}

local function find(name: string)
	for _, sheet in SHEETS do
		local region = sheet.REGIONS[name]
		if region then
			return region, sheet.SFX
		end
	end
	return nil, SHEETS[1].SFX
end

function Sfx.new(name: string, parent: Instance?, props: { [string]: any }?): Sound
	local region, id = find(name)
	local sound = Instance.new("Sound")
	sound.Name = name
	sound.SoundId = id
	sound.RollOffMode = Enum.RollOffMode.InverseTapered
	sound.RollOffMinDistance = 6
	sound.RollOffMaxDistance = 120
	if region then
		local range = NumberRange.new(region.start, region.start + region.length)
		sound.PlaybackRegionsEnabled = true
		sound.PlaybackRegion = range
		if region.loop then
			sound.LoopRegion = range
			sound.Looped = true
		end
	end
	if props then
		for key, value in props do
			(sound :: any)[key] = value
		end
	end
	sound.Parent = parent
	return sound
end

-- Suono singolo in un punto del mondo, eliminato a fine riproduzione
function Sfx.at(name: string, position: Vector3, props: { [string]: any }?)
	local holder = Instance.new("Part")
	holder.Name = "Suono"
	holder.Anchored = true
	holder.CanCollide = false
	holder.CanQuery = false
	holder.CanTouch = false
	holder.Transparency = 1
	holder.Size = Vector3.one
	holder.CFrame = CFrame.new(position)
	local sound = Sfx.new(name, holder, props)
	holder.Parent = workspace
	sound:Play()
	local region = find(name)
	task.delay((region and region.length or 3) / math.max(sound.PlaybackSpeed, 0.1) + 0.5, function()
		holder:Destroy()
	end)
	return sound
end

return Sfx
