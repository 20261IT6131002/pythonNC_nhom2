"""Round-trip disposable synthetic Mongo collections with the real MongoDB tools."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from bson import ObjectId
from noteapp.application.commands.locked_notes import LockedNotes
from noteapp.application.dto.note_input import AttachImageInput, CreateNoteInput, Priority
from noteapp.domain.entities.category import Category
from noteapp.infrastructure.config import Config
from noteapp.infrastructure.mongo.client import create_client, ping
from noteapp.infrastructure.mongo.indexes import create_indexes
from noteapp.infrastructure.mongo.repositories import MongoCategoryRepository
from noteapp.infrastructure.security.aes_gcm import AesGcmCipher
from noteapp.infrastructure.security.passphrase_kdf import Pbkdf2PassphraseKdf
from tests.integration.test_attachment_lifecycle import World, png

source = 'noteapp_test_qa_backup_' + uuid4().hex
target = 'noteapp_test_qa_restore_' + uuid4().hex
config = Config('mongodb://127.0.0.1:27028', source, 10000)
docker = ['docker', 'compose', '-f', str(OUT / 'compose.qa.yml'), 'exec', '-T', 'mongo']
archive = '/tmp/' + source + '.archive'
phrase = 'synthetic backup restore phrase'
commands = []

def run(args):
    result = subprocess.run(docker + args, cwd=ROOT, capture_output=True,
                            encoding='utf-8', errors='replace', timeout=90)
    commands.append({'command': args, 'exit_code': result.returncode,
                     'output': result.stdout + result.stderr})
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)

with create_client(config) as client:
    ping(client)
    db = client[source]
    try:
        create_indexes(db)
        world = World(db)
        category = MongoCategoryRepository(db).create(
            Category(str(ObjectId()), 'QA Tiếng Việt', '#123456', world.clock.now()))
        plain = world.create.execute(CreateNoteInput('Ghi chú tổng hợp', 'Nội dung QA',
                                    Priority.HIGH, category.id, str(uuid4())))
        plain = world.service.attach(AttachImageInput(plain.note_id, 1, png(), 'inline.png'))
        large = world.create.execute(CreateNoteInput('Ảnh GridFS', 'Ảnh tổng hợp',
                                    Priority.LOW, category.id, str(uuid4())))
        payload = png((640, 640), noisy=True)
        large = world.service.attach(AttachImageInput(large.note_id, 1, payload, 'gridfs.png'))
        lock = LockedNotes(world.notes, world.create, AesGcmCipher(), Pbkdf2PassphraseKdf())
        locked = lock.create_locked(CreateNoteInput('Tiêu đề bí mật QA', 'Nội dung khóa QA',
                                   Priority.MEDIUM, None, str(uuid4())), phrase)
        run(['mongodump', '--db=' + source, '--archive=' + archive])
        run(['mongorestore', '--archive=' + archive, '--nsFrom=' + source + '.*',
             '--nsTo=' + target + '.*'])
        restored = client[target]
        collections = {}
        for name in db.list_collection_names():
            before = list(db[name].find().sort('_id', 1))
            after = list(restored[name].find().sort('_id', 1))
            assert before == after, name
            before_indexes = db[name].index_information()
            after_indexes = restored[name].index_information()
            assert before_indexes == after_indexes, name + ' indexes'
            collections[name] = len(before)
        new_world = World(restored)
        new_lock = LockedNotes(new_world.notes, new_world.create, AesGcmCipher(), Pbkdf2PassphraseKdf())
        assert new_lock.unlock(locked.note_id, locked.version, phrase).content == 'Nội dung khóa QA'
        original = new_world.notes.find_by_id(large.note_id)
        assert new_world.store.get(original.attachment) == payload
        raw = restored.notes.find_one({'_id': ObjectId(locked.note_id)})
        assert 'content_plain' not in raw
        report = {'status': 'Pass', 'scope': 'Synthetic Mongo notes/categories/inline/GridFS/locked payload; not staging or disaster recovery',
                  'mongo': client.server_info()['version'], 'collections': collections,
                  'gridfs_sha256': hashlib.sha256(payload).hexdigest(),
                  'indexes_equal': True, 'locked_unlock_after_restore': True, 'commands': commands}
        (OUT / 'backup-restore.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k != 'commands'}, ensure_ascii=False))
    finally:
        for owned in (source, target):
            assert owned.startswith(('noteapp_test_qa_backup_', 'noteapp_test_qa_restore_'))
            client.drop_database(owned)
