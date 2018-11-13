import io
import json
import threading
import time
from typing import List

from azure.cli.core import get_default_cli
from chaoslib import Configuration, Secrets
from logzero import logger

from chaosazure import auth


class ExecutorBatchAsync(threading.Thread):
    def __init__(self, configuration, secrets, commands, after):
        threading.Thread.__init__(self)
        self.after = after
        self.configuration = configuration
        self.secrets = secrets
        self.commands = commands

    def run(self):
        logger.debug("Starting Thread")
        time.sleep(self.after)
        execute_batch(self.configuration, self.secrets, self.commands)


def execute(configuration: Configuration = None, secrets: Secrets = None,
            command=None, file=None):
    command_list = [command]
    execute_batch(configuration, secrets, command_list, file)


def execute_batch(configuration: Configuration = None, secrets: Secrets = None,
                  commands=[], file=None):
    is_resource_graph_extension_installed = False
    ext_list = __build_extension_list_command()
    ext_list_stream = io.StringIO()
    get_default_cli().invoke(ext_list, out_file=ext_list_stream)
    ext_list_stream_response = json.loads(ext_list_stream.getvalue())
    for elem in ext_list_stream_response:
        if elem['name'] == 'resource-graph':
            is_resource_graph_extension_installed = True
    ext_list_stream.close()

    if not is_resource_graph_extension_installed:
        install_resource_graph = __build_install_resource_graph_command()
        get_default_cli().invoke(install_resource_graph)

    with auth(secrets) as cred:
        principal_id = cred.id
        secret = cred.secret
        tenant_id = cred.auth_uri.split('/')[3]
        subscription_id = configuration['azure']['subscription_id']

        login = __build_login_command(principal_id, secret, tenant_id)
        get_default_cli().invoke(login)

        set_subscription = __build_set_subscription_command(subscription_id)
        get_default_cli().invoke(set_subscription)

        for command in commands:
            get_default_cli().invoke(command, out_file=file)

        logout = __build_logout_command()
        get_default_cli().invoke(logout)


def execute_batch_async(configuration: Configuration = None,
                        secrets: Secrets = None,
                        commands=List[List[str]],
                        after=int):
    thread = ExecutorBatchAsync(configuration, secrets, commands, after)
    thread.start()


###############################################################################
# Private helper functions
###############################################################################
def __build_logout_command():
    return ['logout']


def __build_set_subscription_command(azure_subscription_id):
    return ['account', 'set', '--subscription', azure_subscription_id]


def __build_login_command(principal_id, secret, tenant_id):
    return ['login', '--service-principal', '-u', principal_id, '-p',
            secret, '--tenant', tenant_id]


def __build_extension_list_command():
    return ['extension', 'list']


def __build_install_resource_graph_command():
    return ['extension', 'add', '--name', 'resource-graph']
