
from mock import MagicMock, patch, call


import cinder_utils as utils

from test_utils import (
    CharmTestCase,
)

# Need to do some early patching to get the module loaded.
_register_configs = utils.register_configs
utils.register_configs = MagicMock()
import cinder_hooks as hooks
utils.register_configs = _register_configs

TO_PATCH = [
    # cinder_utils
    'ensure_ceph_pool',
    'ensure_ceph_keyring',
    'register_configs',
    'restart_map',
    'set_ceph_env_variables',
    'CONFIGS',
    # charmhelpers.core.hookenv
    'config',
    'relation_ids',
    'relation_set',
    'service_name',
    'log',
    # charmhelpers.core.host
    'apt_install',
    'apt_update',
    # charmhelpers.contrib.hahelpers.cluster_utils
    'eligible_leader',
    'execd_preinstall'
]


class TestInstallHook(CharmTestCase):

    def setUp(self):
        super(TestInstallHook, self).setUp(hooks, TO_PATCH)
        self.config.side_effect = self.test_config.get

    def test_correct_install_packages(self):
        hooks.hooks.execute(['hooks/install'])
        self.apt_install.assert_called_with(['ceph-common'], fatal=True)


class TestChangedHooks(CharmTestCase):

    def setUp(self):
        super(TestChangedHooks, self).setUp(hooks, TO_PATCH)
        self.config.side_effect = self.test_config.get


class TestJoinedHooks(CharmTestCase):

    def setUp(self):
        super(TestJoinedHooks, self).setUp(hooks, TO_PATCH)
        self.config.side_effect = self.test_config.get

    @patch('os.mkdir')
    def test_ceph_joined(self, mkdir):
        '''It correctly prepares for a ceph changed hook'''
        with patch('os.path.isdir') as isdir:
            isdir.return_value = False
            hooks.hooks.execute(['hooks/ceph-relation-joined'])
            mkdir.assert_called_with('/etc/ceph')

    def test_ceph_changed_no_key(self):
        '''It does nothing when ceph key is not available'''
        self.CONFIGS.complete_contexts.return_value = ['']
        hooks.hooks.execute(['hooks/ceph-relation-changed'])
        m = 'ceph relation incomplete. Peer not ready?'
        self.log.assert_called_with(m)

    def test_ceph_changed(self):
        '''It ensures ceph assets created on ceph changed'''
        self.CONFIGS.complete_contexts.return_value = ['ceph']
        self.service_name.return_value = 'cinder'
        self.ensure_ceph_keyring.return_value = True
        hooks.hooks.execute(['hooks/ceph-relation-changed'])
        self.ensure_ceph_keyring.assert_called_with(service='cinder',
                                                    user='cinder',
                                                    group='cinder')
        self.ensure_ceph_pool.assert_called_with(service='cinder', replicas=2)
        for c in [call('/etc/ceph/ceph.conf')]:
            self.assertIn(c, self.CONFIGS.write.call_args_list)
        self.set_ceph_env_variables.assert_called_with(service='cinder')

    def test_ceph_changed_no_keys(self):
        '''It ensures ceph assets created on ceph changed'''
        self.CONFIGS.complete_contexts.return_value = ['ceph']
        self.service_name.return_value = 'cinder'
        self.ensure_ceph_keyring.return_value = False
        hooks.hooks.execute(['hooks/ceph-relation-changed'])
        # NOTE(jamespage): If ensure_ceph keyring fails, then
        # the hook should just exit 0 and return.
        self.assertTrue(self.log.called)
        self.assertFalse(self.CONFIGS.write.called)

    def test_ceph_changed_no_leadership(self):
        '''It does not attempt to create ceph pool if not leader'''
        self.eligible_leader.return_value = False
        self.service_name.return_value = 'cinder'
        self.ensure_ceph_keyring.return_value = True
        hooks.hooks.execute(['hooks/ceph-relation-changed'])
        self.assertFalse(self.ensure_ceph_pool.called)