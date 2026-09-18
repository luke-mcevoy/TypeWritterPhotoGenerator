import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import db
import storage
from recreate_posts import apply_manifest


class RecreatePostsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, value in (("DATA_DIR",str(self.root)), ("DB_PATH",str(self.root/'test.db')), ("POSTS_DIR",str(self.root/'posts'))):
            item = patch.object(db, name, value)
            item.start()
            self.addCleanup(item.stop)
        db.init_db()
        user = db.create_user('reprint_user', 'Reprint', 'test password')
        self.posts = []
        for n in (1, 2):
            old, new, source = (f'{n*10+i:032x}.jpg' for i in (1,2,3))
            post_id = db.create_post(user['id'], f'Keep caption {n}', old, source)
            payload = b'reviewed image bytes '+bytes([n])
            (self.root/new).write_bytes(payload)
            self.posts.append(dict(id=post_id, old_name=old, new_name=new, source_name=source, sha256=hashlib.sha256(payload).hexdigest()))
        db.toggle_like(self.posts[0]['id'], user['id'])
        self.manifest = self.root/'manifest.json'
        self.manifest.write_text(json.dumps({'posts':self.posts}))

    def test_apply_keeps_metadata_and_originals_and_can_restore(self):
        before = [dict(db.get_post(p['id'])) for p in self.posts]
        with patch.object(storage, 'put_bytes') as upload, patch.object(storage, 'delete') as delete:
            self.assertEqual(apply_manifest(self.manifest)['status'], 'applied')
            self.assertEqual(upload.call_count, 2)
            self.assertEqual([call.args[0] for call in upload.call_args_list], [p['new_name'] for p in self.posts])
            self.assertEqual(apply_manifest(self.manifest)['status'], 'already applied')
            self.assertEqual(upload.call_count, 2)
            for old, post in zip(before,self.posts):
                after=dict(db.get_post(post['id']))
                self.assertEqual(after.pop('image_name'), post['new_name'])
                old.pop('image_name')
                self.assertEqual(after,old)
            self.assertEqual(apply_manifest(self.manifest,restore=True)['status'], 'restored')
            delete.assert_not_called()
        self.assertEqual([db.get_post(p['id'])['image_name'] for p in self.posts], [p['old_name'] for p in self.posts])

    def test_conflicting_second_post_changes_neither_post(self):
        with db.get_db() as conn:
            conn.execute('UPDATE posts SET image_name = ? WHERE id = ?', ('f'*32+'.jpg',self.posts[1]['id']))
        with patch.object(storage,'put_bytes') as upload:
            with self.assertRaisesRegex(RuntimeError,'drawing changed'):
                apply_manifest(self.manifest)
            upload.assert_not_called()
        self.assertEqual(db.get_post(self.posts[0]['id'])['image_name'], self.posts[0]['old_name'])

    def test_changed_artwork_fails_before_upload_or_database_write(self):
        (self.root/self.posts[1]['new_name']).write_bytes(b'changed after review')
        with patch.object(storage,'put_bytes') as upload:
            with self.assertRaisesRegex(ValueError,'Reviewed image changed'):
                apply_manifest(self.manifest)
            upload.assert_not_called()
        self.assertEqual([db.get_post(p['id'])['image_name'] for p in self.posts], [p['old_name'] for p in self.posts])


if __name__ == '__main__':
    unittest.main()
