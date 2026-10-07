-- Suoni dal foglio di effetti sintetizzato (Audio.luau): ogni effetto è un intervallo dello stesso file.
local Audio = require(script.Parent:WaitForChild("Audio"))

local Sfx = {}

function Sfx.new(name: string, parent: Instance?, props: { [string]: any }?): Sound
	local region = Audio.REGIONS[name]
	local sound = Instance.new("Sound")
	sound.Name = name
	sound.SoundId = Audio.SFX
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
	local region = Audio.REGIONS[name]
	task.delay((region and region.length or 3) / math.max(sound.PlaybackSpeed, 0.1) + 0.5, function()
		holder:Destroy()
	end)
	return sound
end

return Sfx
