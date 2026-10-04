"""Backend-independent application identity in existing transient system context."""

ASSISTANT_NAME = 'Dwindy'
ASSISTANT_DESCRIPTION = 'a local AI assistant'


def runtime_system_prompt(configured=''):
    identity = (f'You are {ASSISTANT_NAME}, {ASSISTANT_DESCRIPTION}.\n'
                'You are powered by a local large language model.\n'
                'Dwindy is developed as part of the Dwindy project, a small, modular, local-first chatbot.')
    return identity + ('\n\n' + configured if configured else '')
