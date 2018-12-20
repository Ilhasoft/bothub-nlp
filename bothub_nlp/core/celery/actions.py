from ... import settings


ACTION_PARSE = 'parse'
ACTION_TRAIN = 'train'


def queue_name(action, language):
    if settings.BOTHUB_NLP_AGROUP_LANGUAGE_QUEUE:
        return language
    return '{}:{}'.format(action, language)
