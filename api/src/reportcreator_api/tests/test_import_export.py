from datetime import datetime
import json
import tarfile
import pytest
import io
from django.core.files.base import ContentFile
from django.test import override_settings
from rest_framework.exceptions import ValidationError
from reportcreator_api.archive.import_export.import_export import build_tarinfo
from reportcreator_api.pentests.models import PentestProject, ProjectType, SourceEnum, UploadedAsset, UploadedImage, Language
from reportcreator_api.tests.utils import assertKeysEqual
from reportcreator_api.archive.import_export import export_project_types, export_projects, export_templates, import_project_types, import_projects, import_templates
from reportcreator_api.tests.mock import create_projectnotebookpage, create_project, create_project_type, create_template, create_user, create_finding


def archive_to_file(archive_iterator):
    return io.BytesIO(b''.join(archive_iterator))


def create_archive(archive_data: list[dict]):
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode='w|gz') as archive:
        for data in archive_data:
            data_json = json.dumps(data).encode()
            archive.addfile(tarinfo=build_tarinfo(name=data['id'] + '.json', size=len(data_json)), fileobj=io.BytesIO(data_json))
    buffer.seek(0)
    return buffer


def members_equal(a, b):
    def format_members(m):
        return sorted([(m['user'], set(m['roles'])) for m in a.values('user', 'roles')], key=lambda i: i[0])

    return format_members(a) == format_members(b)


@pytest.mark.django_db
class TestImportExport:
    @pytest.fixture(autouse=True)
    def setUp(self) -> None:
        self.user = create_user()
        self.template = create_template(
            language=Language.ENGLISH, 
            translations_kwargs=[
                {'language': Language.GERMAN, 'data': {'title': 'Template translation', 'description': 'Template description translation ![](/images/name/image.png)'}},
            ],
            images_kwargs=[{'name': 'image.png'}],    
        )
        self.project_type = create_project_type()
        self.project = create_project(
            project_type=self.project_type, 
            members=[self.user],
            report_data={'field_user': str(self.user.id)},  
            findings_kwargs=[
                {'assignee': self.user, 'template': self.template, 'data': {'description': '![](/images/name/image.png)'}},
                {'assignee': None, 'template': None},
            ],
            notes_kwargs=[],
            images_kwargs=[{'name': 'image.png'}, {'name': 'image-note.png'}],
            files_kwargs=[{'name': 'file.txt'}],
        )
        note1 = create_projectnotebookpage(project=self.project, title='Note 1', text='Note text 1 ![](/images/name/image-note.png)')
        create_projectnotebookpage(project=self.project, parent=note1, title='Note 1.1', text='Note text 1.1 [](/files/name/file.txt)')
        
        with override_settings(COMPRESS_IMAGES=False):
            yield
    
    def test_export_import_template_v2(self):
        archive = archive_to_file(export_templates([self.template]))
        imported = import_templates(archive)
        assert len(imported) == 1
        t = imported[0]

        assert t.created == self.template.created
        assert set(t.tags) == set(self.template.tags)
        assert t.source == SourceEnum.IMPORTED

        for i, o in zip(t.translations.all(), self.template.translations.all()):
            assertKeysEqual(i, o, ['created', 'is_main', 'language', 'status', 'data', 'data_all', 'title', 'custom_fields'])
        assert t.main_translation in set(t.translations.all())

        assert {(i.name, i.file.read()) for i in t.images.all()} == {(i.name, i.file.read()) for i in self.template.images.all()}

    def test_import_template_v1(self):
        template_data = {
            "format": "templates/v1",
            "id": "674f559c-ca41-4925-a24a-586a8b74c51e",
            "created": "2023-01-19T18:27:50.592000Z",
            "updated": "2023-06-29T11:21:42.996947Z",
            "tags": [
                "web",
                "dev",
            ],
            "language": "de-DE",
            "status": "finished",
            "data": {
                "title": "Test template",
                "description": "Test description",
            },
        }
        archive = create_archive([template_data])
        imported = import_templates(archive)
        
        assert len(imported) == 1
        t = imported [0]

        assert set(t.tags) == set(template_data['tags'])
        assert t.source == SourceEnum.IMPORTED

        assert t.translations.count() == 1
        assert t.main_translation.template == t
        assertKeysEqual(t.main_translation, template_data, ['language', 'status'])
        assert t.main_translation.data == template_data['data']
        assert t.images.all().count() == 0

    def test_export_import_project_type(self):
        archive = archive_to_file(export_project_types([self.project_type]))
        self.project_type.refresh_from_db()
        imported = import_project_types(archive)

        assert len(imported) == 1
        t = imported[0]

        assertKeysEqual(t, self.project_type, [
            'created', 'name', 'language', 
            'report_fields', 'report_sections', 
            'finding_fields', 'finding_field_order', 'finding_ordering',
            'report_template', 'report_styles', 'report_preview_data'])
        assert t.source == SourceEnum.IMPORTED

        assert {(a.name, a.file.read()) for a in t.assets.all()} == {(a.name, a.file.read()) for a in self.project_type.assets.all()}

    def assert_export_import_project(self, project, p):
        assertKeysEqual(p, project, ['name', 'language', 'tags', 'data', 'override_finding_ordering', 'data_all', 'unknown_custom_fields'])
        assert members_equal(p.members, project.members)
        assert p.source == SourceEnum.IMPORTED
        
        assert p.sections.count() == project.sections.count()
        for i, s in zip(p.sections.order_by('section_id'), project.sections.order_by('section_id')):
            assertKeysEqual(i, s, ['section_id', 'created', 'assignee', 'status', 'data'])

        assert p.findings.count() == project.findings.count()
        for i, s in zip(p.findings.order_by('finding_id'), project.findings.order_by('finding_id')):
            assertKeysEqual(i, s, ['finding_id', 'created', 'assignee', 'status', 'order', 'template', 'data', 'data_all'])

        assertKeysEqual(p.project_type, project.project_type, [
            'created', 'name', 'language', 
            'report_fields', 'report_sections', 
            'finding_fields', 'finding_field_order', 'finding_ordering',
            'report_template', 'report_styles', 'report_preview_data'])
        assert p.project_type.source == SourceEnum.IMPORTED_DEPENDENCY
        assert p.project_type.linked_project == p
        
        assert {(a.name, a.file.read()) for a in p.project_type.assets.all()} == {(a.name, a.file.read()) for a in project.project_type.assets.all()}

    def test_export_import_project(self):
        archive = archive_to_file(export_projects([self.project]))
        self.project.refresh_from_db()
        imported = import_projects(archive)
        assert len(imported) == 1
        p = imported[0]
        self.assert_export_import_project(self.project, p)
        assert {(i.name, i.file.read()) for i in p.images.all()} == {(i.name, i.file.read()) for i in self.project.images.all() if self.project.is_file_referenced(i, notes=False)}
        assert p.notes.count() == 0
        assert p.files.count() == 0

    def test_export_import_project_all(self):
        archive = archive_to_file(export_projects([self.project], export_all=True))
        self.project.refresh_from_db()
        imported = import_projects(archive)
        assert len(imported) == 1
        p = imported[0]
        self.assert_export_import_project(self.project, p)
        assert {(i.name, i.file.read()) for i in p.images.all()} == {(i.name, i.file.read()) for i in self.project.images.all()}

        assert p.notes.count() == self.project.notes.count()
        for i, s in zip(p.notes.order_by('note_id'), self.project.notes.order_by('note_id')):
            assertKeysEqual(i, s, ['note_id', 'created', 'title', 'text', 'checked', 'icon_emoji', 'status_emoji', 'order'])
            assert i.parent.note_id == s.parent.note_id if s.parent else i.parent is None
        assert {(f.name, f.file.read()) for f in p.files.all()} == {(f.name, f.file.read()) for f in self.project.files.all()}

    def test_import_nonexistent_user(self):
        # export project with members and assignee, delete user, import => members and assignee == NULL
        # export project with UserField, delete user, import => user inlined in project.imported_members
        archive = archive_to_file(export_projects([self.project]))
        old_user_id = self.user.id
        old_user_roles = self.project.members.all()[0].roles
        self.project.members.all().delete()
        self.user.delete()
        p = import_projects(archive)[0]

        assert p.members.count() == 0
        assert p.sections.exclude(assignee=None).count() == 0
        assert p.findings.exclude(assignee=None).count() == 0

        # Check UUID of nonexistent user is still present in data
        assert p.data_all == self.project.data_all
        for i, s in zip(p.findings.order_by('created'), self.project.findings.order_by('created')):
            assertKeysEqual(i, s, ['finding_id', 'created', 'assignee', 'status', 'order', 'template', 'data', 'data_all'])
        
        # Test nonexistent user is added to project.imported_members
        assert len(p.imported_members) == 1
        assert p.imported_members[0]['id'] == str(old_user_id)
        assert p.imported_members[0]['roles'] == old_user_roles
        assertKeysEqual(p.imported_members[0], self.user, [
            'email', 'phone', 'mobile',
            'name', 'title_before', 'first_name', 'middle_name', 'last_name', 'title_after',
        ])

        # Test re-create user: at re-import the original user should be referenced
        archive2 = archive_to_file(export_projects([p]))
        self.user.id = old_user_id
        self.user.save()
        p2 = import_projects(archive2)[0]
        assert p2.members.count() == 1
        assert len(p2.imported_members) == 0
        members_equal(p2.members, self.project.members)
    
    def test_import_nonexistent_template_reference(self):
        archive = archive_to_file(export_projects([self.project]))
        self.template.delete()
        p = import_projects(archive)[0]

        assert p.findings.exclude(template_id=None).count() == 0

    def test_import_wrong_archive(self):
        archive = archive_to_file(export_templates([self.template]))
        with pytest.raises(ValidationError):
            import_projects(archive)


@pytest.mark.django_db
class TestLinkedProject:
    @pytest.fixture(autouse=True)
    def setUp(self):
        self.project_type = create_project_type(source=SourceEnum.IMPORTED_DEPENDENCY)
        self.project = create_project(project_type=self.project_type, source=SourceEnum.IMPORTED)
        self.project_type.linked_project = self.project
        self.project_type.save()
    
    def test_delete_linked_project(self):
        # On delete linked_project: project_type should also be deleted
        self.project.delete()
        assert not ProjectType.objects.filter(id=self.project_type.id).exists()
    
    def test_delete_linked_project_multiple_project_types(self):
        # On delete linked_project
        unused_pt = create_project_type(linked_project=self.project, source=SourceEnum.IMPORTED_DEPENDENCY)

        self.project.delete()
        assert not ProjectType.objects.filter(id=self.project_type.id).exists()
        assert not ProjectType.objects.filter(id=unused_pt.id).exists()
    
    def test_delete_linked_project_project_type_used_by_another_project(self):
        second_p = create_project(project_type=self.project_type)

        self.project.delete()
        assert ProjectType.objects.filter(id=self.project_type.id).exists()
        assert PentestProject.objects.filter(id=second_p.id).exists()
        self.project_type.refresh_from_db()
        assert self.project_type.linked_project is None
    

@pytest.mark.django_db
class TestFileDelete:
    @pytest.fixture(autouse=True)
    def setUp(self) -> None:
        with override_settings(SIMPLE_HISTORY_ENABLED=False):
            p = create_project()
            self.image = p.images.first()
            self.asset = p.project_type.assets.first()
            yield

    def assertFileExists(self, file, expected):
        exists = False
        try:
            with file.open():
                exists = True
        except ValueError:
            exists = False
        assert exists == expected
    
    def test_delete_file_referenced_only_once(self):
        self.image.delete()
        self.assertFileExists(self.image.file, False)

        self.asset.delete()
        self.assertFileExists(self.asset.file, False)

    def test_delete_file_referenced_multiple_times(self):
        UploadedImage.objects.create(linked_object=self.image.linked_object, name='new.png', file=self.image.file)
        self.image.delete()
        self.assertFileExists(self.image.file, True)

        UploadedAsset.objects.create(linked_object=self.asset.linked_object, name='new.png', file=self.asset.file)
        self.asset.delete()
        self.assertFileExists(self.asset.file, True)

    def test_delete_copied_images(self):
        p = create_project()
        p2 = p.copy()

        images = list(p.images.order_by('name_hash'))
        for o, c in zip(images, p2.images.order_by('name_hash')):
            assert o.file == c.file
        p.delete()
        for i in images:
            self.assertFileExists(i.file, True)

    def test_delete_copied_assets(self):
        t = create_project_type()
        t2 = t.copy()

        assets = list(t.assets.order_by('name_hash'))
        for o, c in zip(assets, t2.assets.order_by('name_hash')):
            assert o.file == c.file
        t.delete()
        for a in assets:
            self.assertFileExists(a.file, True)


@pytest.mark.django_db
class TestCopyModel:
    def assert_project_type_copy_equal(self, pt, cp, exclude_fields=[]):
        assert pt != cp
        assert cp.copy_of == pt
        assert not cp.is_locked
        assertKeysEqual(pt, cp, {
            'name', 'language', 'linked_project',
            'report_template', 'report_styles', 'report_preview_data', 
            'report_fields', 'report_sections', 
            'finding_fields', 'finding_field_order', 'finding_ordering',
        } - set(exclude_fields))
        
        assert set(pt.assets.values_list('id', flat=True)).intersection(cp.assets.values_list('id', flat=True)) == set()
        assert {(a.name, a.file.read()) for a in pt.assets.all()} == {(a.name, a.file.read()) for a in cp.assets.all()}

    def test_copy_project(self):
        user = create_user()
        p = create_project(members=[user], readonly=True, source=SourceEnum.IMPORTED)
        create_projectnotebookpage(project=p, parent=p.notes.first())
        finding = create_finding(project=p, template=create_template())
        finding.lock(user)
        p.sections.first().lock(user)
        cp = p.copy()

        assert p != cp
        assert cp.copy_of == p
        assert not cp.readonly
        assertKeysEqual(p, cp, [
            'name', 'source', 'language', 'tags', 'override_finding_ordering', 'imported_members', 'data_all'
        ])
        self.assert_project_type_copy_equal(p.project_type, cp.project_type, exclude_fields=['source', 'linked_project'])
        assert cp.project_type.source == SourceEnum.SNAPSHOT
        assert cp.project_type.linked_project == cp
        assert members_equal(p.members, cp.members)

        assert set(p.images.values_list('id', flat=True)).intersection(cp.images.values_list('id', flat=True)) == set()
        assert {(i.name, i.file.read()) for i in p.images.all()} == {(i.name, i.file.read()) for i in cp.images.all()}

        assert set(p.files.values_list('id', flat=True)).intersection(cp.files.values_list('id', flat=True)) == set()
        assert {(f.name, f.file.read()) for f in p.files.all()} == {(f.name, f.file.read()) for f in cp.files.all()}

        for p_s, cp_s in zip(p.sections.order_by('section_id'), cp.sections.order_by('section_id')):
            assert p_s != cp_s
            assertKeysEqual(p_s, cp_s, ['section_id', 'assignee', 'status', 'data'])
            assert not cp_s.is_locked
        
        for p_f, cp_f in zip(p.findings.order_by('finding_id'), cp.findings.order_by('finding_id')):
            assert p_f != cp_f
            assertKeysEqual(p_f, cp_f, ['finding_id', 'assignee', 'status', 'order', 'data', 'template'])
            assert not cp_f.is_locked
        
        for p_n, cp_n in zip(p.notes.order_by('note_id'), cp.notes.order_by('note_id')):
            assert p_n != cp_n
            assertKeysEqual(p_n, cp_n, ['note_id', 'title', 'text', 'checked', 'icon_emoji', 'status_emoji', 'order'])
            assert not cp_f.is_locked
            if p_n.parent:
                assert p_n.parent.note_id == cp_n.parent.note_id
                assert p_n.parent != cp_n.parent
            else:
                assert cp_n.parent is None

    def test_copy_project_type(self):
        user = create_user()
        project = create_project()
        pt = create_project_type(source=SourceEnum.IMPORTED, linked_project=project)
        pt.lock(user)
        cp = pt.copy()

        self.assert_project_type_copy_equal(pt, cp)


@pytest.mark.parametrize('original,cleaned', [
    ('test.txt', 'test.txt'),
    # Attacks
    ('te\x00st.txt', 'te-st.txt'),
    ('te/st.txt', 'st.txt'),
    ('t/../../../est.txt', 'est.txt'),
    ('../test1.txt', 'test1.txt'),
    ('..', 'file'),
    # Markdown conflicts
    ('/test2.txt', 'test2.txt'),
    ('t**es**t.txt', 't--es--t.txt'),
    ('te_st_.txt', 'te-st-.txt'),
    ('t![e]()st.txt', 't--e---st.txt'),
])
@pytest.mark.django_db
def test_uploadedfile_filename(original, cleaned):
    actual_name = UploadedAsset.objects.create(name=original, file=ContentFile(b'test'), linked_object=create_project_type()).name
    assert actual_name == cleaned