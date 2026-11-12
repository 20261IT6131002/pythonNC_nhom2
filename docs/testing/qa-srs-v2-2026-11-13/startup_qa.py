"""Fresh-process startup and two 15-minute Windows RSS workloads on owned 5k data."""
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def rss():
    import ctypes
    from ctypes import wintypes
    class Counters(ctypes.Structure):
        _fields_ = [('cb', wintypes.DWORD), ('faults', wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in ('peak', 'working', 'paged_peak',
             'paged', 'nonpaged_peak', 'nonpaged', 'pagefile', 'pagefile_peak')]
    counter = Counters()
    counter.cb = ctypes.sizeof(counter)
    get_process = ctypes.windll.kernel32.GetCurrentProcess
    get_process.restype = wintypes.HANDLE
    get_memory = ctypes.windll.psapi.GetProcessMemoryInfo
    get_memory.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not get_memory(get_process(), ctypes.byref(counter), counter.cb):
        raise ctypes.WinError()
    return counter.working, counter.peak


def child(mode):
    started = time.perf_counter()
    from noteapp.bootstrap import build_runtime
    from noteapp.infrastructure.config import Config
    config = Config.from_env()
    runtime = build_runtime(config)
    app = runtime.window
    callbacks = []
    app.root.report_callback_exception = lambda *error: callbacks.append(str(error))
    try:
        deadline = started + 30
        while not app.notes.state.items and time.perf_counter() < deadline:
            app.root.update()
            time.sleep(.001)
        assert len(app.notes.state.items) == 30 and not callbacks
        ready = time.perf_counter()
        if mode == 'startup':
            result = {'import_to_ready_ms': (ready - started) * 1000,
                      'rss_at_ready': rss(), 'tk': app.root.tk.call('info', 'patchlevel')}
        else:
            from noteapp.infrastructure.mongo.repositories import MongoNoteRepository
            from noteapp.application.dto.note_view import NoteView
            notes = MongoNoteRepository(runtime.client[config.db_name])
            image_ids = json.loads(os.environ['QA_IMAGE_IDS'])
            samples = []
            delays = []
            next_image = ready
            next_sample = ready
            previous = ready
            image_index = 0
            begin = ready + 20  # warmup excluded from the full 15-minute sampling window
            end = begin + 900
            app.root.title('NoteApp QA — ' + mode + ' — synthetic data')
            while time.perf_counter() < end:
                now = time.perf_counter()
                if mode == 'large-image' and now >= next_image:
                    note = notes.find_by_id(image_ids[image_index % len(image_ids)])
                    app.open_note(NoteView.from_note(note))
                    image_index += 1
                    next_image = now + 10
                if mode == 'normal' and now >= next_image:
                    app.note_list.canvas.yview_scroll(1 if image_index % 2 else -1, 'units')
                    image_index += 1
                    next_image = now + .25
                app.root.update()
                after = time.perf_counter()
                if after >= begin:
                    delays.append((after - previous) * 1000)
                    if after >= next_sample:
                        samples.append({'elapsed_s': round(after - begin, 3),
                                        'rss_bytes': rss()[0], 'peak_working_set_bytes': rss()[1]})
                        next_sample = after + 1
                previous = after
                time.sleep(.005)
            assert not callbacks
            result = {'mode': mode, 'duration_s': 900, 'warmup_s': 20,
                      'samples': samples, 'image_opens_or_scrolls': image_index,
                      'sampled_max_rss_bytes': max(s['rss_bytes'] for s in samples),
                      'process_peak_working_set_bytes': rss()[1],
                      'loop_gap_p95_ms': sorted(delays)[math.ceil(len(delays)*.95)-1],
                      'loop_gap_max_ms': max(delays), 'callback_errors': callbacks,
                      'method': 'GetProcessMemoryInfo working set every >=1s; OS peak includes transients. Loop gaps are a responsiveness proxy, not displayed FPS.'}
            if mode == 'large-image':
                from PIL import ImageGrab
                import ctypes
                get_parent = ctypes.windll.user32.GetParent
                get_parent.argtypes = [ctypes.c_void_p]
                get_parent.restype = ctypes.c_void_p
                ImageGrab.grab(window=get_parent(app.root.winfo_id())).save(OUT / 'windows-qa.png')
        (OUT / ('startup-child.json' if mode == 'startup' else mode + '-memory.json')).write_text(
            json.dumps(result, indent=2), encoding='utf-8')
    finally:
        runtime.close()


def parent():
    from datetime import datetime, timezone, timedelta
    from noteapp.domain.entities.note import Note
    from noteapp.domain.entities.category import Category
    from noteapp.domain.value_objects.priority import Priority
    from noteapp.infrastructure.config import Config
    from noteapp.infrastructure.mongo.client import create_client, ping
    from noteapp.infrastructure.mongo.indexes import create_indexes
    from noteapp.infrastructure.mongo.models import note_to_document, category_to_document
    name = 'noteapp_test_qa_perf_' + uuid4().hex
    config = Config('mongodb://127.0.0.1:27028', name, 10000)
    env = dict(os.environ, PYTHONUTF8='1', NOTEAPP_MONGO_URI=config.mongo_uri,
               NOTEAPP_DB_NAME=name, NOTEAPP_DRAFT_DIR=str(OUT / ('drafts-' + name)),
               NOTEAPP_TIMEZONE='Asia/Ho_Chi_Minh', NOTEAPP_ENABLE_RETENTION='0')
    with create_client(config) as client:
        ping(client)
        db = client[name]
        children = []
        try:
            create_indexes(db)
            now = datetime.now(timezone.utc)
            catalog = [Category(f'{20000+i:024x}', f'Danh mục QA {i}', '#123456', now)
                       for i in range(20)]
            db.categories.insert_many([category_to_document(c) for c in catalog])
            docs = []
            for i in range(5000):
                stamp = now - timedelta(seconds=i)
                note = Note(f'{i+1:024x}', f'Ghi chú tiếng Việt QA {i}', 'Nội dung tổng hợp. '*4,
                            tuple(Priority)[i % 3], catalog[i % 20].id, 1, stamp, stamp)
                docs.append(note_to_document(note, 'qa-perf-' + str(i)))
            db.notes.insert_many(docs)
            samples = []
            for i in range(20):
                started = time.perf_counter()
                result = subprocess.run([sys.executable, __file__, 'startup'], cwd=ROOT,
                                        env=env, capture_output=True, encoding='utf-8', timeout=40)
                if result.returncode:
                    raise RuntimeError(result.stdout + result.stderr)
                values = json.loads((OUT / 'startup-child.json').read_text(encoding='utf-8'))
                values['process_total_ms_including_shutdown'] = (time.perf_counter()-started)*1000
                samples.append(values)
            report = {'notes': 5000, 'active': 5000, 'categories': 20, 'samples': samples,
                      'p95_import_to_ready_ms': sorted(s['import_to_ready_ms'] for s in samples)[18],
                      'first_process_ms': samples[0]['import_to_ready_ms'],
                      'method': '20 fresh Python processes; imports -> full shell and first 30 Mongo cards loaded. Warm OS/filesystem/DB caches; no OS cold-cache flush. Process spawn is excluded from ready timer, shutdown is excluded.'}
            (OUT / 'startup-benchmark.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps({k:v for k,v in report.items() if k != 'samples'}), flush=True)
            # Seed 30 real large GridFS attachments after the startup trials.
            from tests.integration.test_attachment_lifecycle import World, png
            from noteapp.application.dto.note_input import AttachImageInput
            world = World(db)
            payload = png((1800, 1800), noisy=True)
            image_ids = []
            for i in range(30):
                note_id = f'{i+1:024x}'
                world.service.attach(AttachImageInput(note_id, 1, payload, f'QA-{i}.png'))
                image_ids.append(note_id)
            env['QA_IMAGE_IDS'] = json.dumps(image_ids)
            for mode in ('normal', 'large-image'):
                children.append(subprocess.Popen([sys.executable, __file__, mode], cwd=ROOT,
                                env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding='utf-8'))
            for process in children:
                stdout, stderr = process.communicate(timeout=1000)
                if process.returncode:
                    raise RuntimeError(stdout + stderr)
            print('15-minute normal and large-image workloads completed.', flush=True)
        finally:
            for process in children:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=15)
            assert name.startswith('noteapp_test_qa_perf_')
            client.drop_database(name)


if __name__ == '__main__':
    child(sys.argv[1]) if len(sys.argv) > 1 else parent()
