--!strict
-- Formattazione di numeri e tempi per l'interfaccia.

local Format = {}

local SUFFIXES = { "", "K", "M", "B", "T", "Qa", "Qi", "Sx", "Sp", "Oc", "No", "Dc" }

-- 1234 -> "1.23K", 1500000 -> "1.5M"
function Format.Short(n: number): string
	if n ~= n then
		return "0"
	end
	local neg = n < 0
	n = math.abs(n)
	if n < 1000 then
		local s = if n >= 100 or n == math.floor(n) then tostring(math.floor(n)) else string.format("%.1f", n)
		return (if neg then "-" else "") .. s
	end
	local idx = math.min(math.floor(math.log10(n) / 3), #SUFFIXES - 1)
	local scaled = n / 10 ^ (idx * 3)
	local s
	if scaled >= 100 then
		s = string.format("%d", math.floor(scaled))
	elseif scaled >= 10 then
		s = string.format("%.1f", math.floor(scaled * 10) / 10)
	else
		s = string.format("%.2f", math.floor(scaled * 100) / 100)
	end
	if string.find(s, ".", 1, true) then
		-- "1.50" -> "1.5", "2.00" -> "2" (solo zeri dopo la virgola)
		s = (string.gsub(string.gsub(s, "0+$", ""), "%.$", ""))
	end
	return (if neg then "-" else "") .. s .. SUFFIXES[idx + 1]
end

function Format.Money(n: number): string
	return "$" .. Format.Short(n)
end

function Format.Rate(n: number): string
	return "+$" .. Format.Short(n) .. "/s"
end

-- 75 -> "1:15", 3725 -> "1:02:05"
function Format.Clock(seconds: number): string
	seconds = math.max(0, math.ceil(seconds))
	local h = seconds // 3600
	local m = (seconds % 3600) // 60
	local s = seconds % 60
	if h > 0 then
		return string.format("%d:%02d:%02d", h, m, s)
	end
	return string.format("%d:%02d", m, s)
end

-- 45 -> "45s", 150 -> "2m 30s", 7300 -> "2h 1m"
function Format.Duration(seconds: number): string
	seconds = math.max(0, math.ceil(seconds))
	if seconds < 60 then
		return `{seconds}s`
	elseif seconds < 3600 then
		local s = seconds % 60
		return if s > 0 then `{seconds // 60}m {s}s` else `{seconds // 60}m`
	end
	local m = (seconds % 3600) // 60
	return if m > 0 then `{seconds // 3600}h {m}m` else `{seconds // 3600}h`
end

function Format.Percent(x: number): string
	return `{math.floor(x * 100 + 0.5)}%`
end

return Format
