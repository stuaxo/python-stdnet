import datetime
import threading
import time
from distutils.version import StrictVersion

from stdnet.utils import to_string, ispy3k, iteritems, to_bytestring, range

if not ispy3k:
    chr = unichr
    
from .base import *


to_charlist = lambda x: [x[c:c + 1] for c in range(len(x))]
binary_set = lambda x : set(to_charlist(x))


def get_version(info):
    if 'redis_version' in info:
        return info['redis_version']
    else:
        return info['Server']['redis_version']


class ServerCommandsTestCase(BaseTest):

    def setUp(self):
        self.client = self.get_client()
        self.client.flushdb()
        
    def tearDown(self):
        self.client.flushdb()

    # GENERAL SERVER COMMANDS
    def test_dbsize(self):
        self.client['a'] = 'foo'
        self.client['b'] = 'bar'
        self.assertEquals(self.client.dbsize(), 2)

    def test_get_and_set(self):
        # get and set can't be tested independently of each other
        self.assertEquals(self.client.get('a'), None)
        byte_string = b'value'
        integer = 5
        unicode_string = chr(3456) + to_string('abcd') + chr(3421)
        self.assert_(self.client.set('byte_string', byte_string))
        self.assert_(self.client.set('integer', 5))
        self.assert_(self.client.set('unicode_string', unicode_string))
        self.assertEquals(self.client.get('byte_string'), byte_string)
        self.assertEquals(self.client.get('integer'), to_bytestring(integer))
        self.assertEquals(self.client.get('unicode_string').decode('utf-8'), unicode_string)

    def test_getitem_and_setitem(self):
        self.client['a'] = 'bar'
        self.assertEquals(self.client['a'], b'bar')

    def test_delete(self):
        self.assertEquals(self.client.delete('a'), False)
        self.client['a'] = 'foo'
        self.assertEquals(self.client.delete('a'), True)

    def test_delitem(self):
        self.client['a'] = 'foo'
        del self.client['a']
        self.assertEquals(self.client['a'], None)

    def test_info(self):
        self.client['a'] = 'foo'
        self.client['b'] = 'bar'
        info = self.client.info()
        self.assert_(isinstance(info, dict))
        version = get_version(info)
        if StrictVersion(version) >= StrictVersion('2.2.0'):
            keyspace = info['Keyspace']
        else:
            keyspace = info
        self.assertEquals(keyspace['db{0}'.format(DBTEST)]['keys'], 2)

    def test_lastsave(self):
        self.assert_(isinstance(self.client.lastsave(), datetime.datetime))

    def test_ping(self):
        self.assertEquals(self.client.ping(), True)

    # KEYS
    def test_append(self):
        # invalid key type
        self.client.rpush('a', 'a1')
        self.assertRaises(ResponseError, self.client.append, 'a', 'a1')
        del self.client['a']
        # real logic
        self.assertEquals(self.client.append('a', 'a1'), 2)
        self.assertEquals(self.client['a'], b'a1')
        self.assert_(self.client.append('a', 'a2'), 4)
        self.assertEquals(self.client['a'], b'a1a2')

    def test_decr(self):
        self.assertEquals(self.client.decr('a'), -1)
        self.assertEquals(self.client['a'], b'-1')
        self.assertEquals(self.client.decr('a'), -2)
        self.assertEquals(self.client['a'], b'-2')
        self.assertEquals(self.client.decr('a', amount=5), -7)
        self.assertEquals(self.client['a'], b'-7')

    def test_exists(self):
        self.assertEquals(self.client.exists('a'), False)
        self.client['a'] = 'foo'
        self.assertEquals(self.client.exists('a'), True)

    def test_expire_and_ttl(self):
        self.assertEquals(self.client.expire('a', 10), False)
        self.client['a'] = 'foo'
        self.assertEquals(self.client.expire('a', 10), True)
        self.assertEquals(self.client.ttl('a'), 10)

    def test_expireat(self):
        expire_at = datetime.datetime.now() + datetime.timedelta(minutes=1)
        self.assertEquals(self.client.expireat('a', expire_at), False)
        self.client['a'] = 'foo'
        # expire at in unix time
        expire_at_seconds = int(time.mktime(expire_at.timetuple()))
        self.assertEquals(self.client.expireat('a', expire_at_seconds), True)
        self.assertEquals(self.client.ttl('a'), 60)
        # expire at given a datetime object
        self.client['b'] = 'bar'
        self.assertEquals(self.client.expireat('b', expire_at), True)
        self.assertEquals(self.client.ttl('b'), 60)

    def test_getset(self):
        self.assertEquals(self.client.getset('a', 'foo'), None)
        self.assertEquals(self.client.getset('a', 'bar'), b'foo')

    def test_incr(self):
        self.assertEquals(self.client.incr('a'), 1)
        self.assertEquals(self.client['a'], b'1')
        self.assertEquals(self.client.incr('a'), 2)
        self.assertEquals(self.client['a'], b'2')
        self.assertEquals(self.client.incr('a', amount=5), 7)
        self.assertEquals(self.client['a'], b'7')

    def test_keys(self):
        self.assertEquals(self.client.keys(), [])
        keys = set([b'test_a', b'test_b', b'testc'])
        for key in keys:
            self.client[key] = 1
        self.assertEquals(set(self.client.keys(pattern='test_*')),
            keys - set([b'testc']))
        self.assertEquals(set(self.client.keys(pattern='test*')), keys)

    def test_mget(self):
        self.assertEquals(self.client.mget(['a', 'b']), [None, None])
        self.client['a'] = '1'
        self.client['b'] = '2'
        self.client['c'] = '3'
        self.assertEquals(self.client.mget(['a', 'other', 'b', 'c']),
            [b'1', None, b'2', b'3'])

    def test_mset(self):
        d = {'a': '1', 'b': '2', 'c': '3'}
        self.assert_(self.client.mset(d))
        for k,v in iteritems(d):
            self.assertEquals(self.client[k], to_bytestring(v))

    def test_msetnx(self):
        d = {'a': '1', 'b': '2', 'c': '3'}
        self.assert_(self.client.msetnx(d))
        d2 = {'a': 'x', 'd': '4'}
        self.assert_(not self.client.msetnx(d2))
        for k,v in iteritems(d):
            self.assertEquals(self.client[k], to_bytestring(v))
        self.assertEquals(self.client['d'], None)

    def test_randomkey(self):
        self.assertEquals(self.client.randomkey(), None)
        self.client['a'] = '1'
        self.client['b'] = '2'
        self.client['c'] = '3'
        self.assert_(self.client.randomkey() in (b'a', b'b', b'c'))

    def test_rename(self):
        self.client['a'] = '1'
        self.assert_(self.client.rename('a', 'b'))
        self.assertEquals(self.client['a'], None)
        self.assertEquals(self.client['b'], b'1')

    def test_renamenx(self):
        self.client['a'] = '1'
        self.client['b'] = '2'
        self.assert_(not self.client.renamenx('a', 'b'))
        self.assertEquals(self.client['a'], b'1')
        self.assertEquals(self.client['b'], b'2')

    def test_setex(self):
        self.assertEquals(self.client.setex('a', '1', 60), True)
        self.assertEquals(self.client['a'], b'1')
        self.assertEquals(self.client.ttl('a'), 60  )

    def test_setnx(self):
        self.assert_(self.client.setnx('a', '1'))
        self.assertEquals(self.client['a'], b'1')
        self.assert_(not self.client.setnx('a', '2'))
        self.assertEquals(self.client['a'], b'1')

    def test_substr(self):
        # invalid key type
        self.client.rpush('a', 'a1')
        self.assertRaises(ResponseError, self.client.substr, 'a', 0)
        del self.client['a']
        # real logic
        self.client['a'] = 'abcdefghi'
        self.assertEquals(self.client.substr('a', 0), b'abcdefghi')
        self.assertEquals(self.client.substr('a', 2), b'cdefghi')
        self.assertEquals(self.client.substr('a', 3, 5), b'def')
        self.assertEquals(self.client.substr('a', 3, -2), b'defgh')
        self.client['a'] = 123456 # does substr work with ints?
        self.assertEquals(self.client.substr('a', 2, -2), b'345')

    def test_type(self):
        self.assertEquals(self.client.type('a'), b'none')
        self.client['a'] = '1'
        self.assertEquals(self.client.type('a'), b'string')
        del self.client['a']
        self.client.lpush('a', '1')
        self.assertEquals(self.client.type('a'), b'list')
        del self.client['a']
        self.client.sadd('a', '1')
        self.assertEquals(self.client.type('a'), b'set')
        del self.client['a']
        self.client.zadd('a', '1', 1)
        self.assertEquals(self.client.type('a'), b'zset')

    # LISTS
    def make_list(self, name, l):
        for i in l:
            self.client.rpush(name, i)

    def test_blpop(self):
        self.make_list('a', 'ab')
        self.make_list('b', 'cd')
        self.assertEquals(self.client.blpop(['b', 'a'], timeout=1), (b'b', b'c'))
        self.assertEquals(self.client.blpop(['b', 'a'], timeout=1), (b'b', b'd'))
        self.assertEquals(self.client.blpop(['b', 'a'], timeout=1), (b'a', b'a'))
        self.assertEquals(self.client.blpop(['b', 'a'], timeout=1), (b'a', b'b'))
        self.assertEquals(self.client.blpop(['b', 'a'], timeout=1), None)
        self.make_list('c', 'a')
        self.assertEquals(self.client.blpop('c', timeout=1), (b'c', b'a'))

    def test_brpop(self):
        self.make_list('a', 'ab')
        self.make_list('b', 'cd')
        self.assertEquals(self.client.brpop(['b', 'a'], timeout=1), (b'b', b'd'))
        self.assertEquals(self.client.brpop(['b', 'a'], timeout=1), (b'b', b'c'))
        self.assertEquals(self.client.brpop(['b', 'a'], timeout=1), (b'a', b'b'))
        self.assertEquals(self.client.brpop(['b', 'a'], timeout=1), (b'a', b'a'))
        self.assertEquals(self.client.brpop(['b', 'a'], timeout=1), None)
        self.make_list('c', 'a')
        self.assertEquals(self.client.brpop('c', timeout=1), (b'c', b'a'))

    def test_lindex(self):
        # no key
        self.assertEquals(self.client.lindex('a', '0'), None)
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.lindex, 'a', '0')
        del self.client['a']
        # real logic
        self.make_list('a', 'abc')
        self.assertEquals(self.client.lindex('a', '0'), b'a')
        self.assertEquals(self.client.lindex('a', '1'), b'b')
        self.assertEquals(self.client.lindex('a', '2'), b'c')

    def test_llen(self):
        # no key
        self.assertEquals(self.client.llen('a'), 0)
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.llen, 'a')
        del self.client['a']
        # real logic
        self.make_list('a', 'abc')
        self.assertEquals(self.client.llen('a'), 3)

    def test_lpop(self):
        # no key
        self.assertEquals(self.client.lpop('a'), None)
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.lpop, 'a')
        del self.client['a']
        # real logic
        self.make_list('a', 'abc')
        self.assertEquals(self.client.lpop('a'), 'a')
        self.assertEquals(self.client.lpop('a'), 'b')
        self.assertEquals(self.client.lpop('a'), 'c')
        self.assertEquals(self.client.lpop('a'), None)

    def test_lpush(self):
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.lpush, 'a', 'a')
        del self.client['a']
        # real logic
        version = get_version(self.client.info())
        if StrictVersion(version) >= StrictVersion('1.3.4'):
            self.assertEqual(1, self.client.lpush('a', 'b'))
            self.assertEqual(2, self.client.lpush('a', 'a'))
        else:
            self.assert_(self.client.lpush('a', 'b'))
            self.assert_(self.client.lpush('a', 'a'))
        self.assertEquals(self.client.lindex('a', 0), b'a')
        self.assertEquals(self.client.lindex('a', 1), b'b')

    def test_lrange(self):
        # no key
        self.assertEquals(self.client.lrange('a', 0, 1), [])
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.lrange, 'a', 0, 1)
        del self.client['a']
        # real logic
        self.make_list('a', 'abcde')
        self.assertEquals(self.client.lrange('a', 0, 2), [b'a', b'b', b'c'])
        self.assertEquals(self.client.lrange('a', 2, 10), [b'c', b'd', b'e'])

    def test_lrem(self):
        # no key
        self.assertEquals(self.client.lrem('a', 'foo'), 0)
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.lrem, 'a', 'b')
        del self.client['a']
        # real logic
        self.make_list('a', 'aaaa')
        self.assertEquals(self.client.lrem('a', 'a', 1), 1)
        self.assertEquals(self.client.lrange('a', 0, 3), [b'a', b'a', b'a'])
        self.assertEquals(self.client.lrem('a', 'a'), 3)
        # remove all the elements in the list means the key is deleted
        self.assertEquals(self.client.lrange('a', 0, 1), [])

    def test_lset(self):
        # no key
        self.assertRaises(ResponseError, self.client.lset, 'a', 1, 'b')
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.lset, 'a', 1, 'b')
        del self.client['a']
        # real logic
        self.make_list('a', 'abc')
        self.assertEquals(self.client.lrange('a', 0, 2), [b'a', b'b', b'c'])
        self.assert_(self.client.lset('a', 1, 'd'))
        self.assertEquals(self.client.lrange('a', 0, 2), [b'a', b'd', b'c'])

    def test_ltrim(self):
        # no key -- TODO: Not sure why this is actually true.
        self.assert_(self.client.ltrim('a', 0, 2))
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.ltrim, 'a', 0, 2)
        del self.client['a']
        # real logic
        self.make_list('a', 'abc')
        self.assert_(self.client.ltrim('a', 0, 1))
        self.assertEquals(self.client.lrange('a', 0, 5), [b'a', b'b'])

    def test_lpop(self):
        # no key
        self.assertEquals(self.client.lpop('a'), None)
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.lpop, 'a')
        del self.client['a']
        # real logic
        self.make_list('a', 'abc')
        self.assertEquals(self.client.lpop('a'), b'a')
        self.assertEquals(self.client.lpop('a'), b'b')
        self.assertEquals(self.client.lpop('a'), b'c')
        self.assertEquals(self.client.lpop('a'), None)

    def test_rpop(self):
        # no key
        self.assertEquals(self.client.rpop('a'), None)
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.rpop, 'a')
        del self.client['a']
        # real logic
        self.make_list('a', 'abc')
        self.assertEquals(self.client.rpop('a'), b'c')
        self.assertEquals(self.client.rpop('a'), b'b')
        self.assertEquals(self.client.rpop('a'), b'a')
        self.assertEquals(self.client.rpop('a'), None)

    def test_rpoplpush(self):
        # no src key
        self.make_list('b', ['b1'])
        self.assertEquals(self.client.rpoplpush('a', 'b'), None)
        # no dest key
        self.assertEquals(self.client.rpoplpush('b', 'a'), b'b1')
        self.assertEquals(self.client.lindex('a', 0), b'b1')
        del self.client['a']
        del self.client['b']
        # src key is not a list
        self.client['a'] = 'a1'
        self.assertRaises(ResponseError, self.client.rpoplpush, 'a', 'b')
        del self.client['a']
        # dest key is not a list
        self.make_list('a', ['a1'])
        self.client['b'] = 'b'
        self.assertRaises(ResponseError, self.client.rpoplpush, 'a', 'b')
        del self.client['a']
        del self.client['b']
        # real logic
        self.make_list('a', ['a1', 'a2', 'a3'])
        self.make_list('b', ['b1', 'b2', 'b3'])
        self.assertEquals(self.client.rpoplpush('a', 'b'), b'a3')
        self.assertEquals(self.client.lrange('a', 0, 2), [b'a1', b'a2'])
        self.assertEquals(self.client.lrange('b', 0, 4),
            [b'a3', b'b1', b'b2', b'b3'])

    def test_rpush(self):
        # key is not a list
        self.client['a'] = 'b'
        self.assertRaises(ResponseError, self.client.rpush, 'a', 'a')
        del self.client['a']
        # real logic
        version = get_version(self.client.info())
        if StrictVersion(version) >= StrictVersion('1.3.4'):
            self.assertEqual(1, self.client.rpush('a', 'a'))
            self.assertEqual(2, self.client.rpush('a', 'b'))
        else:
            self.assert_(self.client.rpush('a', 'a'))
            self.assert_(self.client.rpush('a', 'b'))
        self.assertEquals(self.client.lindex('a', 0), b'a')
        self.assertEquals(self.client.lindex('a', 1), b'b')

    # Set commands
    def make_set(self, name, l):
        for i in l:
            self.client.sadd(name, i)

    def test_sadd(self):
        # key is not a set
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.sadd, 'a', 'a1')
        del self.client['a']
        # real logic
        members = set([b'a1', b'a2', b'a3'])
        self.make_set('a', members)
        self.assertEquals(self.client.smembers('a'), members)

    def test_scard(self):
        # key is not a set
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.scard, 'a')
        del self.client['a']
        # real logic
        self.make_set('a', 'abc')
        self.assertEquals(self.client.scard('a'), 3)

    def test_sdiff(self):
        # some key is not a set
        self.make_set('a', ['a1', 'a2', 'a3'])
        self.client['b'] = 'b'
        self.assertRaises(ResponseError, self.client.sdiff, ['a', 'b'])
        del self.client['b']
        # real logic
        self.make_set('b', ['b1', 'a2', 'b3'])
        self.assertEquals(self.client.sdiff(['a', 'b']), set([b'a1', b'a3']))

    def test_sdiffstore(self):
        # some key is not a set
        self.make_set('a', ['a1', 'a2', 'a3'])
        self.client['b'] = 'b'
        self.assertRaises(ResponseError, self.client.sdiffstore,
            'c', ['a', 'b'])
        del self.client['b']
        self.make_set('b', ['b1', 'a2', 'b3'])
        # dest key always gets overwritten, even if it's not a set, so don't
        # test for that
        # real logic
        self.assertEquals(self.client.sdiffstore('c', ['a', 'b']), 2)
        self.assertEquals(self.client.smembers('c'), set([b'a1', b'a3']))

    def test_sinter(self):
        # some key is not a set
        self.make_set('a', ('a1', 'a2', 'a3'))
        self.client['b'] = 'b'
        self.assertRaises(ResponseError, self.client.sinter, ['a', 'b'])
        del self.client['b']
        # real logic
        self.make_set('b', ['a1', 'b2', 'a3'])
        self.assertEquals(self.client.sinter(['a', 'b']), set([b'a1', b'a3']))

    def test_sinterstore(self):
        # some key is not a set
        self.make_set('a', ['a1', 'a2', 'a3'])
        self.client['b'] = 'b'
        self.assertRaises(ResponseError, self.client.sinterstore,
            'c', ['a', 'b'])
        del self.client['b']
        self.make_set('b', ['a1', 'b2', 'a3'])
        # dest key always gets overwritten, even if it's not a set, so don't
        # test for that
        # real logic
        self.assertEquals(self.client.sinterstore('c', ['a', 'b']), 2)
        self.assertEquals(self.client.smembers('c'), set([b'a1', b'a3']))

    def test_sismember(self):
        # key is not a set
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.sismember, 'a', 'a')
        del self.client['a']
        # real logic
        self.make_set('a', 'abc')
        self.assertEquals(self.client.sismember('a', 'a'), True)
        self.assertEquals(self.client.sismember('a', 'b'), True)
        self.assertEquals(self.client.sismember('a', 'c'), True)
        self.assertEquals(self.client.sismember('a', 'd'), False)

    def test_smembers(self):
        # key is not a set
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.smembers, 'a')
        del self.client['a']
        # set doesn't exist
        self.assertEquals(self.client.smembers('a'), set())
        # real logic
        self.make_set('a', 'abc')
        self.assertEquals(self.client.smembers('a'), set([b'a', b'b', b'c']))

    def test_smove(self):
        # src key is not set
        self.make_set('b', ['b1', 'b2'])
        self.assertEquals(self.client.smove('a', 'b', 'a1'), 0)
        # src key is not a set
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.smove,
            'a', 'b', 'a1')
        del self.client['a']
        self.make_set('a', ['a1', 'a2'])
        # dest key is not a set
        del self.client['b']
        self.client['b'] = 'b'
        self.assertRaises(ResponseError, self.client.smove,
            'a', 'b', 'a1')
        del self.client['b']
        self.make_set('b', ['b1', 'b2'])
        # real logic
        self.assert_(self.client.smove('a', 'b', 'a1'))
        self.assertEquals(self.client.smembers('a'), set([b'a2']))
        self.assertEquals(self.client.smembers('b'), set([b'b1', b'b2', b'a1']))

    def test_spop(self):
        # key is not set
        self.assertEquals(self.client.spop('a'), None)
        # key is not a set
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.spop, 'a')
        del self.client['a']
        # real logic
        self.make_set('a', 'abc')
        bs = binary_set(b'abc')
        value = self.client.spop('a')
        self.assert_(value in b'abc')
        self.assertEquals(self.client.smembers('a'), bs - binary_set(value))

    def test_srandmember(self):
        # key is not set
        self.assertEquals(self.client.srandmember('a'), None)
        # key is not a set
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.srandmember, 'a')
        del self.client['a']
        # real logic
        self.make_set('a', 'abc')
        self.assert_(self.client.srandmember('a') in b'abc')

    def test_srem(self):
        # key is not set
        self.assertEquals(self.client.srem('a', 'a'), False)
        # key is not a set
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.srem, 'a', 'a')
        del self.client['a']
        # real logic
        self.make_set('a', 'abc')
        self.assertEquals(self.client.srem('a', b'd'), False)
        self.assertEquals(self.client.srem('a', b'b'), True)
        bs = binary_set(b'ac')
        self.assertEquals(self.client.smembers('a'), bs)

    def test_sunion(self):
        # some key is not a set
        self.make_set('a', ['a1', 'a2', 'a3'])
        self.client['b'] = 'b'
        self.assertRaises(ResponseError, self.client.sunion, ['a', 'b'])
        del self.client['b']
        # real logic
        self.make_set('b', ['a1', 'b2', 'a3'])
        self.assertEquals(self.client.sunion(['a', 'b']),
            set([b'a1', b'a2', b'a3', b'b2']))

    def test_sunionstore(self):
        # some key is not a set
        self.make_set('a', ['a1', 'a2', 'a3'])
        self.client['b'] = 'b'
        self.assertRaises(ResponseError, self.client.sunionstore,
            'c', ['a', 'b'])
        del self.client['b']
        self.make_set('b', ['a1', 'b2', 'a3'])
        # dest key always gets overwritten, even if it's not a set, so don't
        # test for that
        # real logic
        self.assertEquals(self.client.sunionstore('c', ['a', 'b']), 4)
        self.assertEquals(self.client.smembers('c'),
            set([b'a1', b'a2', b'a3', b'b2']))

    # SORTED SETS
    def make_zset(self, name, d):
        for k,v in d.items():
            self.client.zadd(name, k, v)

    def test_zadd(self):
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.zrange('a', 0, 3), [b'a1', b'a2', b'a3'])

    def test_zcard(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zcard, 'a')
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.zcard('a'), 3)

    def test_zincrby(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zincrby, 'a', 'a1')
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.zincrby('a', 'a2'), 3.0)
        self.assertEquals(self.client.zincrby('a', 'a3', amount=5), 8.0)
        self.assertEquals(self.client.zscore('a', 'a2'), 3.0)
        self.assertEquals(self.client.zscore('a', 'a3'), 8.0)

    def test_zinterstore(self):
        self.make_zset('a', {'a1': 1, 'a2': 1, 'a3': 1})
        self.make_zset('b', {'a1': 2, 'a3': 2, 'a4': 2})
        self.make_zset('c', {'a1': 6, 'a3': 5, 'a4': 4})

        # sum, no weight
        self.assert_(self.client.zinterstore('z', ['a', 'b', 'c']))
        self.assertEquals(
            list(self.client.zrange('z', 0, -1, withscores=True)),
            [(b'a3', 8), (b'a1', 9)]
            )

        # max, no weight
        self.assert_(
            self.client.zinterstore('z', ['a', 'b', 'c'], aggregate='MAX')
            )
        self.assertEquals(
            list(self.client.zrange('z', 0, -1, withscores=True)),
            [(b'a3', 5), (b'a1', 6)]
            )

        # with weight
        self.assert_(self.client.zinterstore('z', {'a': 1, 'b': 2, 'c': 3}))
        self.assertEquals(
            list(self.client.zrange('z', 0, -1, withscores=True)),
            [(b'a3', 20), (b'a1', 23)]
            )


    def test_zrange(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zrange, 'a', 0, 1)
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(list(self.client.zrange('a', 0, 1)), [b'a1', b'a2'])
        self.assertEquals(list(self.client.zrange('a', 1, 2)), [b'a2', b'a3'])
        self.assertEquals(list(self.client.zrange('a', 0, 1, withscores=True)),
            [(b'a1', 1.0), (b'a2', 2.0)])
        self.assertEquals(list(self.client.zrange('a', 1, 2, withscores=True)),
            [(b'a2', 2.0), (b'a3', 3.0)])
        # a non existant key should return empty list
        self.assertEquals(self.client.zrange('b', 0, 1, withscores=True), [])


    def test_zrangebyscore(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zrangebyscore,
            'a', 0, 1)
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4, 'a5': 5})
        self.assertEquals(list(self.client.zrangebyscore('a', 2, 4)),
            [b'a2', b'a3', b'a4'])
        self.assertEquals(list(self.client.zrangebyscore('a', 2, 4, start=1, num=2)),
            [b'a3', b'a4'])
        self.assertEquals(list(self.client.zrangebyscore('a', 2, 4, withscores=True)),
            [(b'a2', 2.0), (b'a3', 3.0), (b'a4', 4.0)])
        # a non existant key should return empty list
        self.assertEquals(self.client.zrangebyscore('b', 0, 1, withscores=True), [])

    def test_zrank(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zrank, 'a', 'a4')
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4, 'a5': 5})
        self.assertEquals(self.client.zrank('a', 'a1'), 0)
        self.assertEquals(self.client.zrank('a', 'a2'), 1)
        self.assertEquals(self.client.zrank('a', 'a3'), 2)
        self.assertEquals(self.client.zrank('a', 'a4'), 3)
        self.assertEquals(self.client.zrank('a', 'a5'), 4)
        # non-existent value in zset
        self.assertEquals(self.client.zrank('a', 'a6'), None)

    def test_zrem(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zrem, 'a', 'a1')
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.zrem('a', 'a2'), True)
        self.assertEquals(self.client.zrange('a', 0, 5), [b'a1', b'a3'])
        self.assertEquals(self.client.zrem('a', 'b'), False)
        self.assertEquals(self.client.zrange('a', 0, 5), [b'a1', b'a3'])

    def test_zremrangebyscore(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zremrangebyscore,
            'a', 0, 1)
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3, 'a4': 4, 'a5': 5})
        self.assertEquals(self.client.zremrangebyscore('a', 2, 4), 3)
        self.assertEquals(self.client.zrange('a', 0, 5), [b'a1', b'a5'])
        self.assertEquals(self.client.zremrangebyscore('a', 2, 4), 0)
        self.assertEquals(self.client.zrange('a', 0, 5), [b'a1', b'a5'])

    def test_zrevrange(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zrevrange,
            'a', 0, 1)
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.zrevrange('a', 0, 1), [b'a3', b'a2'])
        self.assertEquals(self.client.zrevrange('a', 1, 2), [b'a2', b'a1'])
        self.assertEquals(list(self.client.zrevrange('a', 0, 1, withscores=True)),
            [(b'a3', 3.0), (b'a2', 2.0)])
        self.assertEquals(list(self.client.zrevrange('a', 1, 2, withscores=True)),
            [(b'a2', 2.0), (b'a1', 1.0)])
        # a non existant key should return empty list
        self.assertEquals(self.client.zrange('b', 0, 1, withscores=True), [])

    def test_zrevrank(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zrevrank, 'a', 'a4')
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 5, 'a2': 4, 'a3': 3, 'a4': 2, 'a5': 1})
        self.assertEquals(self.client.zrevrank('a', 'a1'), 0)
        self.assertEquals(self.client.zrevrank('a', 'a2'), 1)
        self.assertEquals(self.client.zrevrank('a', 'a3'), 2)
        self.assertEquals(self.client.zrevrank('a', 'a4'), 3)
        self.assertEquals(self.client.zrevrank('a', 'a5'), 4)

    def test_zscore(self):
        # key is not a zset
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.zscore, 'a', 'a1')
        del self.client['a']
        # real logic
        self.make_zset('a', {'a1': 0, 'a2': 1, 'a3': 2})
        self.assertEquals(self.client.zscore('a', 'a1'), 0.0)
        self.assertEquals(self.client.zscore('a', 'a2'), 1.0)
        # test a non-existant member
        self.assertEquals(self.client.zscore('a', 'a4'), None)

    def test_zunionstore(self):
        self.make_zset('a', {'a1': 1, 'a2': 1, 'a3': 1})
        self.make_zset('b', {'a1': 2, 'a3': 2, 'a4': 2})
        self.make_zset('c', {'a1': 6, 'a4': 5, 'a5': 4})

        # sum, no weight
        self.assert_(self.client.zunionstore('z', ['a', 'b', 'c']))
        self.assertEquals(
            list(self.client.zrange('z', 0, -1, withscores=True)),
            [(b'a2', 1), (b'a3', 3), (b'a5', 4), (b'a4', 7), (b'a1', 9)]
            )

        # max, no weight
        self.assert_(
            self.client.zunionstore('z', ['a', 'b', 'c'], aggregate='MAX')
            )
        self.assertEquals(
            list(self.client.zrange('z', 0, -1, withscores=True)),
            [(b'a2', 1), (b'a3', 2), (b'a5', 4), (b'a4', 5), (b'a1', 6)]
            )

        # with weight
        self.assert_(self.client.zunionstore('z', {'a': 1, 'b': 2, 'c': 3}))
        self.assertEquals(
            list(self.client.zrange('z', 0, -1, withscores=True)),
            [(b'a2', 1), (b'a3', 5), (b'a5', 12), (b'a4', 19), (b'a1', 23)]
            )


    # HASHES
    def make_hash(self, key, d):
        for k,v in d.items():
            self.client.hset(key, k, v)

    def test_hget_and_hset(self):
        # key is not a hash
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.hget, 'a', 'a1')
        del self.client['a']
        # no key
        self.assertEquals(self.client.hget('a', 'a1'), None)
        # real logic
        self.make_hash('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.hget('a', 'a1'), b'1')
        self.assertEquals(self.client.hget('a', 'a2'), b'2')
        self.assertEquals(self.client.hget('a', 'a3'), b'3')
        self.assertEquals(self.client.hset('a', 'a2', 5), 0)
        self.assertEquals(self.client.hget('a', 'a2'), b'5')
        self.assertEquals(self.client.hset('a', 'a4', 4), 1)
        self.assertEquals(self.client.hget('a', 'a4'), b'4')
        # key inside of hash that doesn't exist returns null value
        self.assertEquals(self.client.hget('a', 'b'), None)

    def test_hsetnx(self):
        # Initially set the hash field
        self.client.hsetnx('a', 'a1', 1)
        self.assertEqual(self.client.hget('a', 'a1'), b'1')
        # Try and set the existing hash field to a different value
        self.client.hsetnx('a', 'a1', 2)
        self.assertEqual(self.client.hget('a', 'a1'), b'1')

    def test_hmset(self):
        d = {'a': '1', 'b': '2', 'c': '3'}
        db = dict(((to_bytestring(k),to_bytestring(v)) for k,v in d.items()))
        self.assert_(self.client.hmset('foo', d))
        self.assertEqual(self.client.hgetall('foo'), db)
        self.assertRaises(ResponseError, self.client.hmset, 'foo', {})

    def test_hmget(self):
        d = {'a': 1, 'b': 2, 'c': 3}
        self.assert_(self.client.hmset('foo', d))
        self.assertEqual(self.client.hmget('foo', ['a', 'b', 'c']), [b'1', b'2', b'3'])
        self.assertEqual(self.client.hmget('foo', ['a', 'c']), [b'1', b'3'])

    def test_hmget_empty(self):
        self.assertEqual(self.client.hmget('foo', ['a', 'b']), [None, None])

    def test_hmget_no_keys(self):
        self.assertRaises(ResponseError, self.client.hmget, 'foo', [])

    def test_hdel(self):
        # key is not a hash
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.hdel, 'a', 'a1')
        del self.client['a']
        # no key
        self.assertEquals(self.client.hdel('a', 'a1'), False)
        # real logic
        self.make_hash('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.hget('a', 'a2'), b'2')
        self.assert_(self.client.hdel('a', 'a2'))
        self.assertEquals(self.client.hget('a', 'a2'), None)

    def test_hexists(self):
        # key is not a hash
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.hexists, 'a', 'a1')
        del self.client['a']
        # no key
        self.assertEquals(self.client.hexists('a', 'a1'), False)
        # real logic
        self.make_hash('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.hexists('a', 'a1'), True)
        self.assertEquals(self.client.hexists('a', 'a4'), False)
        self.client.hdel('a', 'a1')
        self.assertEquals(self.client.hexists('a', 'a1'), False)

    def test_hgetall(self):
        # key is not a hash
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.hgetall, 'a')
        del self.client['a']
        # no key
        self.assertEquals(self.client.hgetall('a'), {})
        # real logic
        h = {'a1': '1', 'a2': '2', 'a3': '3'}
        db = dict(((to_bytestring(k),to_bytestring(v)) for k,v in h.items()))
        self.make_hash('a', h)
        remote_hash = self.client.hgetall('a')
        self.assertEquals(db, remote_hash)

    def test_hincrby(self):
        # key is not a hash
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.hincrby, 'a', 'a1')
        del self.client['a']
        # no key should create the hash and incr the key's value to 1
        self.assertEquals(self.client.hincrby('a', 'a1'), 1)
        # real logic
        self.assertEquals(self.client.hincrby('a', 'a1'), 2)
        self.assertEquals(self.client.hincrby('a', 'a1', amount=2), 4)
        # negative values decrement
        self.assertEquals(self.client.hincrby('a', 'a1', amount=-3), 1)
        # hash that exists, but key that doesn't
        self.assertEquals(self.client.hincrby('a', 'a2', amount=3), 3)
        # finally a key that's not an int
        self.client.hset('a', 'a3', 'foo')
        self.assertRaises(ResponseError, self.client.hincrby, 'a', 'a3')


    def test_hkeys(self):
        # key is not a hash
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.hkeys, 'a')
        del self.client['a']
        # no key
        self.assertEquals(self.client.hkeys('a'), [])
        # real logic
        h = {'a1': '1', 'a2': '2', 'a3': '3'}
        self.make_hash('a', h)
        keys = sorted((to_bytestring(k) for k in h.keys()))
        remote_keys = sorted(self.client.hkeys('a'))
        self.assertEquals(keys, remote_keys)

    def test_hlen(self):
        # key is not a hash
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.hlen, 'a')
        del self.client['a']
        # no key
        self.assertEquals(self.client.hlen('a'), 0)
        # real logic
        self.make_hash('a', {'a1': 1, 'a2': 2, 'a3': 3})
        self.assertEquals(self.client.hlen('a'), 3)
        self.client.hdel('a', 'a3')
        self.assertEquals(self.client.hlen('a'), 2)

    def test_hvals(self):
        # key is not a hash
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.hvals, 'a')
        del self.client['a']
        # no key
        self.assertEquals(self.client.hvals('a'), [])
        # real logic
        h = {'a1': '1', 'a2': '2', 'a3': '3'}
        self.make_hash('a', h)
        vals = sorted((to_bytestring(v) for v in h.values()))
        remote_vals = sorted(self.client.hvals('a'))
        self.assertEquals(vals, remote_vals)

    # SORT
    def test_sort_bad_key(self):
        # key is not set
        self.assertEquals(self.client.sort('a'), [])
        # key is a string value
        self.client['a'] = 'a'
        self.assertRaises(ResponseError, self.client.sort, 'a')
        del self.client['a']

    def test_sort_basic(self):
        self.make_list('a', '3214')
        self.assertEquals(self.client.sort('a'), [b'1', b'2', b'3', b'4'])

    def test_sort_limited(self):
        self.make_list('a', '3214')
        self.assertEquals(self.client.sort('a', start=1, num=2), [b'2', b'3'])

    def test_sort_by(self):
        self.client['score:1'] = 8
        self.client['score:2'] = 3
        self.client['score:3'] = 5
        self.make_list('a_values', '123')
        self.assertEquals(self.client.sort('a_values', by='score:*'),
            [b'2', b'3', b'1'])

    def test_sort_get(self):
        self.client['user:1'] = 'u1'
        self.client['user:2'] = 'u2'
        self.client['user:3'] = 'u3'
        self.make_list('a', '231')
        self.assertEquals(self.client.sort('a', get='user:*'),
            [b'u1', b'u2', b'u3'])

    def test_sort_desc(self):
        self.make_list('a', '231')
        self.assertEquals(self.client.sort('a', desc=True), [b'3', b'2', b'1'])

    def test_sort_alpha(self):
        self.make_list('a', 'ecbda')
        self.assertEquals(self.client.sort('a', alpha=True),
            [b'a', b'b', b'c', b'd', b'e'])

    def test_sort_store(self):
        self.make_list('a', '231')
        self.assertEquals(self.client.sort('a', store='sorted_values'), 3)
        self.assertEquals(self.client.lrange('sorted_values', 0, 5),
            [b'1', b'2', b'3'])

    def test_sort_all_options(self):
        self.client['user:1:username'] = 'zeus'
        self.client['user:2:username'] = 'titan'
        self.client['user:3:username'] = 'hermes'
        self.client['user:4:username'] = 'hercules'
        self.client['user:5:username'] = 'apollo'
        self.client['user:6:username'] = 'athena'
        self.client['user:7:username'] = 'hades'
        self.client['user:8:username'] = 'dionysus'

        self.client['user:1:favorite_drink'] = 'yuengling'
        self.client['user:2:favorite_drink'] = 'rum'
        self.client['user:3:favorite_drink'] = 'vodka'
        self.client['user:4:favorite_drink'] = 'milk'
        self.client['user:5:favorite_drink'] = 'pinot noir'
        self.client['user:6:favorite_drink'] = 'water'
        self.client['user:7:favorite_drink'] = 'gin'
        self.client['user:8:favorite_drink'] = 'apple juice'

        self.make_list('gods', '12345678')
        num = self.client.sort('gods', start=2, num=4, by='user:*:username',
            get='user:*:favorite_drink', desc=True, alpha=True, store='sorted')
        self.assertEquals(num, 4)
        self.assertEquals(self.client.lrange('sorted', 0, 10),
            [b'vodka', b'milk', b'gin', b'apple juice'])

    # PUBSUB
    def _test_pubsub(self):
        # create a new client to not polute the existing one
        r = self.get_client(build = True)
        channels = ('a1', 'a2', 'a3')
        for c in channels:
            r.subscribe(c)
        channels_to_publish_to = channels + ('a4',)
        messages_per_channel = 4
        def publish():
            for i in range(messages_per_channel):
                for c in channels_to_publish_to:
                    self.client.publish(c, 'a message')
                    #time.sleep(0.01)
        publish()
        #t = threading.Thread(target=publish)
        messages = []
        # should receive a message for each subscribe command
        # plus a message for each iteration of the loop * num channels
        num_messages_to_expect = len(channels) + \
            (messages_per_channel*len(channels))
        #thread_started = False
        for msg in r.listen():
            #if not thread_started:
                # start the thread delayed so that we are intermingling
                # publish commands with pulling messsages off the socket
                # with subscribe
            #    thread_started = True
            #    t.start()
            messages.append(msg)
            if len(messages) == num_messages_to_expect:
                break
        sent_types, sent_channels = {}, {}
        for msg_type, channel, _ in messages:
            sent_types.setdefault(msg_type, 0)
            sent_types[msg_type] += 1
            if msg_type == b'message':
                sent_channels.setdefault(channel, 0)
                sent_channels[channel] += 1
        for channel in channels:
            channel = to_bytestring(channel)
            self.assertEquals(sent_channels[channel], messages_per_channel)
        self.assertEquals(sent_types[b'subscribe'], len(channels))
        self.assertEquals(sent_types[b'message'],
            len(channels) * messages_per_channel)

    ## BINARY SAFE
    # TODO add more tests
    def test_binary_get_set(self):
        self.assertTrue(self.client.set(' foo bar ', '123'))
        self.assertEqual(self.client.get(' foo bar '), b'123')

        self.assertTrue(self.client.set(' foo\r\nbar\r\n ', b'456'))
        self.assertEqual(self.client.get(' foo\r\nbar\r\n '), b'456')

        self.assertTrue(self.client.set(' \r\n\t\x07\x13 ', '789'))
        self.assertEqual(self.client.get(' \r\n\t\x07\x13 '), b'789')

        self.assertEqual(sorted(self.client.keys('*')), [b' \r\n\t\x07\x13 ', b' foo\r\nbar\r\n ', b' foo bar '])

        self.assertTrue(self.client.delete(' foo bar '))
        self.assertTrue(self.client.delete(' foo\r\nbar\r\n '))
        self.assertTrue(self.client.delete(' \r\n\t\x07\x13 '))

    def test_binary_lists(self):
        mapping = {'foo bar': '123',
                   'foo\r\nbar\r\n': '456',
                   'foo\tbar\x07': '789',
                   }
        # fill in lists
        for key, value in mapping.items():
            for c in value:
                self.assertTrue(self.client.rpush(key, c))

        # check that KEYS returns all the keys as they are
        bk = sorted((to_bytestring(k) for k in mapping.keys()))
        self.assertEqual(sorted(self.client.keys('*')), bk)

        # check that it is possible to get list content by key name
        for key in mapping.keys():
            bl = [to_bytestring(v) for v in mapping[key]]
            self.assertEqual(self.client.lrange(key, 0, -1), bl)
