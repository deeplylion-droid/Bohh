-- Animazione procedurale di The Rake sul client: andatura scattosa, braccia che penzolano,
-- respiro e la testa che si torce all'improvviso. Agisce sulle Motor6D (Transform) solo in locale.
local RunService = game:GetService("RunService")

local RakeAnimator = {}

function RakeAnimator.start()
	local phase = 0
	local nextTwitch, twitchUntil = 0, 0
	local twitch = CFrame.new()
	local cachedModel: Model? = nil
	local motors: { [string]: Motor6D } = {}

	local function set(name: string, cf: CFrame)
		local m = motors[name]
		if m then
			m.Transform = cf
		end
	end

	RunService.Stepped:Connect(function(_, dt)
		local folder = workspace:FindFirstChild("RakeHunt")
		local rake = folder and folder:FindFirstChild("TheRake") :: Model?
		if not rake then
			cachedModel = nil
			return
		end
		if rake ~= cachedModel then
			cachedModel = rake
			table.clear(motors)
			for _, d in rake:GetDescendants() do
				if d:IsA("Motor6D") then
					motors[d.Name] = d
				end
			end
		end
		local root = rake:FindFirstChild("HumanoidRootPart") :: BasePart?
		local hum = rake:FindFirstChildOfClass("Humanoid")
		if not root or not hum then
			return
		end
		local t = os.clock()
		if hum.PlatformStand then
			-- stordito: si accascia
			for name in motors do
				set(name, CFrame.new())
			end
			set("Neck", CFrame.Angles(0.6, 0, 0.4))
			set("Waist", CFrame.Angles(0.5, 0, 0))
			return
		end
		local vel = root.AssemblyLinearVelocity
		local speed = Vector3.new(vel.X, 0, vel.Z).Magnitude
		local a = math.clamp(speed / 14, 0, 1)
		phase += dt * (1.5 + speed * 0.42)
		local s, c = math.sin(phase), math.cos(phase)
		local lean = math.clamp((speed - 12) / 10, 0, 1) * 0.35
		local breath = math.sin(t * 1.6) * 0.035

		set("Waist", CFrame.Angles(lean + breath + math.sin(phase * 2) * 0.05 * a, s * 0.12 * a, 0))
		set("LHip", CFrame.Angles(s * 0.75 * a, 0, 0))
		set("RHip", CFrame.Angles(-s * 0.75 * a, 0, 0))
		set("LKnee", CFrame.Angles(-math.max(0, c) * 1.1 * a, 0, 0))
		set("RKnee", CFrame.Angles(-math.max(0, -c) * 1.1 * a, 0, 0))
		set("LShoulder", CFrame.Angles(-s * 0.55 * a + math.sin(t * 1.3) * 0.06, 0, math.sin(t * 0.9) * 0.04))
		set("RShoulder", CFrame.Angles(s * 0.55 * a + math.sin(t * 1.1 + 1) * 0.06, 0, -math.sin(t * 0.8) * 0.04))
		set("LElbow", CFrame.Angles(math.max(0, s) * 0.45 * a + math.sin(t * 2.1) * 0.05, 0, 0))
		set("RElbow", CFrame.Angles(math.max(0, -s) * 0.45 * a + math.sin(t * 1.9) * 0.05, 0, 0))

		if t > nextTwitch then
			nextTwitch = t + math.random() * 3 + 0.8
			twitchUntil = t + 0.2 + math.random() * 0.6
			twitch = CFrame.Angles((math.random() - 0.5) * 0.7, (math.random() - 0.5) * 1.3, (math.random() - 0.5) * 1.1)
		end
		if t < twitchUntil then
			set("Neck", twitch)
		else
			set("Neck", CFrame.Angles(math.sin(t * 0.7) * 0.1, math.sin(t * 0.45) * 0.4, math.sin(t * 0.3) * 0.08))
		end
	end)
end

return RakeAnimator
