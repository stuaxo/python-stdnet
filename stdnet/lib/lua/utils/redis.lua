-- Collection of utilities used across several scripts
type_table = {}
type_table['set'] = 'scard'
type_table['zset'] = 'zcard'
type_table['list'] = 'llen'
type_table['hash'] = 'hlen'
type_table['string'] = 'strlen'

function redis_type(key)
	return redis.call('type',key)['ok']
end

-- The length of any structure in redis
function redis_len(key)
	typ = redis_type(key)
    command = type_table[typ]
    if command then
    	return redis.call(command, key) + 0
    end
end

-- Create a unique random key
function redis_randomkey(prefix)
	local rnd_key = prefix .. ':tmp:' .. math.random(1,100000000)
	if redis.call('exists', rnd_key) + 0 == 1 then
		return randomkey()
	else
		return rnd_key
	end
end

-- table of all memebers at key. If the key is a string returns an empty table
function redis_members(key, ...)
	local typ = redis.call('type',key)['ok']
	if table.getn(arg) > 0 then
		all = arg[1]
	else
		all = false
	end
	if typ == 'set' then
		return redis.call('smembers', key)
	elseif typ == 'zset' then
		if all then
			return redis.call('zrange', key, 0, -1, 'withscores')
		else
			return redis.call('zrange', key, 0, -1)
		end
	elseif typ == 'list' then
		return redis.call('lrange', key, 0, -1)
	elseif typ == 'hash' then
		if all then
			return redis.call('hgetall', key)
		else
			return redis.call('hkeys', key)
		end
	else
		return {}
	end
end

-- delete keys from a table
function redis_delete(keys)
	local n = table.getn(keys)
	if n > 0 then
		return redis.call('del', unpack(keys)) + 0
	end
	return n 
end
