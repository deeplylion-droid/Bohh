-- Musica (cambia con la zona e con gli eventi) ed effetti sonori. Gli id sono in Shared.Assets.Sounds.

local ReplicatedStorage = game:GetService("ReplicatedStorage")
local SoundService = game:GetService("SoundService")
local TweenService = game:GetService("TweenService")

local Assets = require(ReplicatedStorage.Shared.Assets)

local Audio = {}

local C
local musicOn, sfxOn = true, true
local tracks: { [string]: Sound } = {}
local current: string? = nil
local sfxCache: { [string]: Sound } = {}
local folder: Folder

local MUSIC_VOLUME = 0.32

function Audio.Init(controllers)
	C = controllers
	folder = Instance.new("Folder")
	folder.Name = "GameAudio"
	folder.Parent = SoundService
end

local function track(name: string): Sound?
	if tracks[name] then
		return tracks[name]
	end
	local id = Assets.Sounds["Music" .. name]
	if not id then
		return nil
	end
	local s = Instance.new("Sound")
	s.Name = "Music" .. name
	s.SoundId = id
	s.Looped = true
	s.Volume = 0
	s.Parent = folder
	tracks[name] = s
	return s
end

-- Dissolvenza verso un brano (Summit, Meadow, Forest, Canyon, Crystal, Crater, Event, Danger)
function Audio.Music(name: string)
	if current == name then
		return
	end
	local old = current and tracks[current]
	current = name
	if old then
		local t = TweenService:Create(old, TweenInfo.new(1.5), { Volume = 0 })
		t:Play()
		t.Completed:Once(function()
			if current ~= old.Name:sub(6) then
				old:Pause()
			end
		end)
	end
	local s = track(name)
	if s and musicOn then
		if not s.IsPlaying then
			s:Resume()
			if not s.IsPlaying then
				s:Play()
			end
		end
		TweenService:Create(s, TweenInfo.new(1.5), { Volume = MUSIC_VOLUME }):Play()
	end
end

-- Effetto sonoro (opzionalmente in un punto del mondo)
function Audio.Play(name: string, position: Vector3?, volume: number?)
	if not sfxOn then
		return
	end
	local id = Assets.Sounds[name]
	if not id then
		return
	end
	if position then
		local att = Instance.new("Attachment")
		att.Parent = workspace.Terrain
		att.WorldPosition = position
		local s = Instance.new("Sound")
		s.SoundId = id
		s.Volume = volume or 0.8
		s.RollOffMinDistance = 12
		s.RollOffMaxDistance = 220
		s.Parent = att
		s:Play()
		s.Ended:Once(function()
			att:Destroy()
		end)
		task.delay(10, function()
			if att.Parent then
				att:Destroy()
			end
		end)
		return
	end
	local s = sfxCache[name]
	if not s then
		s = Instance.new("Sound")
		s.SoundId = id
		s.Volume = volume or 0.7
		s.Parent = folder
		sfxCache[name] = s
	end
	SoundService:PlayLocalSound(s :: Sound)
end

function Audio.ApplySettings(settings)
	musicOn = settings.Music ~= false
	sfxOn = settings.Sfx ~= false
	C.UI.Kit.SfxEnabled = sfxOn
	for name, s in tracks do
		if not musicOn then
			s.Volume = 0
		elseif name == current then
			s.Volume = MUSIC_VOLUME
			if not s.IsPlaying then
				s:Play()
			end
		end
	end
end

function Audio.Start()
	C.State.Watch("Settings", function(settings)
		if settings then
			Audio.ApplySettings(settings)
		end
	end)
	Audio.Music("Summit")
end

return Audio
