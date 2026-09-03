"""Conservative cloud-only CLI gate. Help remains available for every command."""

# Reviewed command families. New executable modes need review; help never does.
CLOUD = {
    'projects': {'list', 'create', 'delete', 'api-keys'},
    'orgs': {'list', 'create'}, 'config': {'push'},
    'functions': {'list', 'get', 'delete', 'new', 'deploy', 'download'},
    'storage': {'ls', 'cp', 'mv', 'rm'}, 'secrets': {'list', 'set', 'unset'},
    'branches': {'list', 'get', 'create', 'update', 'delete', 'pause', 'unpause'},
    'sso': {'add', 'list', 'show', 'info', 'update', 'remove'},
    'domains': {'create', 'get', 'reverify', 'activate', 'delete'},
    'vanity-subdomains': {'check-availability', 'get', 'activate', 'delete'},
    'network-bans': {'get', 'remove'}, 'network-restrictions': {'get', 'update'},
    'ssl-enforcement': {'get', 'update'}, 'postgres-config': {'get', 'update', 'delete'},
    'backups': {'list', 'restore'}, 'encryption': {'get-root-key', 'update-root-key'},
    'snippets': {'list', 'download'}, 'seed': {'buckets'},
    'db': {'query', 'push', 'lint', 'advisors', 'reset'},
    'migration': {'new', 'list', 'fetch', 'repair', 'up', 'down'},
    'migrations': {'new', 'list', 'fetch', 'repair', 'up', 'down'},
    'gen': {'types', 'signing-key', 'bearer-jwt', 'keys'},
    'inspect': {'db', 'report'}, 'test': {'new'},
}
GLOBAL_VALUES = {'--workdir', '--profile', '--output', '-o', '--dns-resolver', '--agent'}
GLOBAL_SWITCHES = {'--experimental', '--yes', '--debug'}
SENSITIVE_VALUES = {'--token', '--password', '--db-password', '-p'}


def validate_cli(arguments):
    # Parse leading globals so e.g. --profile '--help' is not mistaken for help.
    tokens = list(arguments)
    if any(token in SENSITIVE_VALUES or token.startswith('-p=') or
           any(token.startswith(option + '=') for option in SENSITIVE_VALUES if option.startswith('--'))
           for token in tokens):
        raise ValueError('Do not put access tokens or database passwords in CLI arguments; use the environment or an interactive prompt.')
    if any(token.split('=', 1)[0] == '--db-url' for token in tokens):
        raise ValueError('Credential-bearing/custom DB URLs are not supported; use the selected cloud target and protected environment credentials.')
    while tokens and tokens[0].startswith('-'):
        first = tokens.pop(0)
        if first in ('--help', '-h', '--version', '-v'):
            return
        key = first.split('=', 1)[0]
        if key in GLOBAL_VALUES:
            if '=' not in first:
                if not tokens:
                    raise ValueError('Missing CLI global option value.')
                tokens.pop(0)
        elif first not in GLOBAL_SWITCHES:
            raise ValueError('Unreviewed CLI global option; inspect command help first.')
    if not tokens:
        raise ValueError('CLI operation is required.')
    # Help is a discovery operation, including for blocked local commands and
    # when the installed CLI accepts flags after the help switch.
    if any(token in ('--help', '-h') for token in tokens):
        return
    if any(token.split('=', 1)[0] == '--local' for token in tokens):
        raise ValueError('This skill only executes hosted CLI modes; local targets are not supported.')
    if any(t.startswith(('--linked=', '--use-api=')) for t in tokens):
        raise ValueError('Use explicit --linked / --use-api switches, without boolean overrides.')
    group, action = tokens[0], tokens[1] if len(tokens) > 1 else ''
    if group in ('init', 'link', 'unlink', 'services', 'login', 'logout'):
        return
    if action not in CLOUD.get(group, set()):
        raise ValueError('CLI mode is not approved for this Docker-free cloud workflow; inspect --help or use a documented API operation.')
    if group == 'functions' and action in ('deploy', 'download') and '--use-api' not in tokens:
        raise ValueError('Functions deploy/download requires --use-api; local Docker is not allowed.')
    if group == 'storage' and action == 'rm' and '--yes' not in arguments:
        raise ValueError('Storage rm requires --yes so a non-interactive confirmation cannot exit successfully without deleting; verify with storage ls.')
    if group == 'gen' and action == 'types':
        language = tokens[2] if len(tokens) > 2 and not tokens[2].startswith('-') else 'typescript'
        for index, token in enumerate(tokens):
            if token == '--lang' and index + 1 < len(tokens):
                language = tokens[index + 1]
            elif token.startswith('--lang='):
                language = token.split('=', 1)[1]
        if language != 'typescript':
            raise ValueError('Only hosted TypeScript generation is reviewed as Docker-free; inspect help for other languages.')
    remote_required = (group in ('db', 'inspect', 'storage', 'seed')
                       or group in ('migration', 'migrations') and action != 'new'
                       or group == 'gen' and action == 'types')
    if remote_required and not any(t in ('--linked', '--project-ref', '--project-id') or
                                   t.startswith(('--project-ref=', '--project-id=')) for t in tokens):
        raise ValueError('Explicit hosted target required: --linked or the supported project-ref/project-id flag.')
