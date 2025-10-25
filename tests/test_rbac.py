import pytest
from flask import Flask
from flask_login import LoginManager, UserMixin
from models import Role, Permission, User
from extensions import db

from auth.rbac import permission_required


class DummyUser(UserMixin):
    def __init__(self, has_perm_fn, is_authenticated=True):
        self._has_perm = has_perm_fn
        self.is_authenticated = is_authenticated

    def has_perm(self, code):
        return self._has_perm(code)


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    login = LoginManager(app)

    with app.app_context():
        db.create_all()
        yield app


def test_user_has_perm_simple(app):
    # create permission and role
    p = Permission(code='test.perm', description='Test')
    db.session.add(p)
    r = Role(name='tester', description='Tester')
    r.permissions = [p]
    db.session.add(r)
    u = User(username='u1', email='u1@example.com', password_hash='x', role='staff')
    u.roles = [r]
    db.session.add(u)
    db.session.commit()

    assert u.has_perm('test.perm') is True
    assert u.has_perm('no.such') is False


def test_permission_decorator_blocks_unauthenticated(app):
    app = app

    @app.route('/secret')
    @permission_required('x.y')
    def secret():
        return 'ok'

    client = app.test_client()
    resp = client.get('/secret')
    assert resp.status_code in (401, 302)  # either 401 or redirect to login depending on setup
*** End Patch