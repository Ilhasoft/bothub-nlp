import contextvars
import logging
import io
import spacy

from tempfile import mkdtemp

from rasa_nlu.config import RasaNLUModelConfig
from rasa_nlu.model import Interpreter
from rasa_nlu.model import Metadata
from rasa_nlu import components

from .persistor import BothubPersistor


def get_rasa_nlu_config_from_update(update):
    return RasaNLUModelConfig({
        'language': update.language,
        'pipeline': [
            {'name': 'bothub_nlp.core.pipeline_components.spacy_nlp.' +
                     'SpacyNLP'},
            {'name': 'bothub_nlp.core.pipeline_components.tokenizer_spacy.' +
                     'SpacyTokenizer'},
            {'name': 'bothub_nlp.core.pipeline_components.' +
                     'intent_entity_featurizer_regex.RegexFeaturizer'},
            {'name': 'ner_crf'},
            {'name': 'ner_synonyms'},
            {'name': 'intent_featurizer_count_vectors'},
            {'name': 'intent_classifier_tensorflow_embedding'},
            {'name': 'bothub_nlp.core.pipeline_components.' +
                     'crf_label_as_entity_extractor.' +
                     'CRFLabelAsEntityExtractor'},
        ],
    })


class BothubInterpreter(Interpreter):
    @staticmethod
    def default_output_attributes():
        return {
            'intent': {
                'name': None,
                'confidence': 0.0
            },
            'entities': [],
            'labels_as_entity': [],
        }

    @classmethod
    def load(cls, model_dir, component_builder=None, skip_validation=False):
        model_metadata = Metadata.load(model_dir)
        cls.ensure_model_compatibility(model_metadata)
        return cls.create(
            model_metadata,
            component_builder,
            skip_validation)

    @classmethod
    def create(cls, model_metadata, component_builder=None,
               skip_validation=False):
        context = {}
        if component_builder is None:
            component_builder = components.ComponentBuilder()
        pipeline = []
        if not skip_validation:
            components.validate_requirements(model_metadata.component_classes)
        for component_name in model_metadata.component_classes:
            component = component_builder.load_component(
                    component_name, model_metadata.model_dir,
                    model_metadata, **context)
            try:
                updates = component.provide_context()
                if updates:
                    context.update(updates)
                pipeline.append(component)
            except components.MissingArgumentError as e:
                raise Exception("Failed to initialize component '{}'. "
                                "{}".format(component.name, e))
        return cls(pipeline, context, model_metadata)


class UpdateInterpreters:
    interpreters = {}

    def get(self, update, use_cache=True):
        interpreter = self.interpreters.get(update.id)
        if interpreter and use_cache:
            return interpreter
        persistor = BothubPersistor(update)
        model_directory = mkdtemp()
        persistor.retrieve(
            str(update.repository.uuid),
            str(update.id),
            model_directory)
        self.interpreters[update.id] = BothubInterpreter.load(
            model_directory,
            components.ComponentBuilder(use_cache=False))
        return self.get(update)


class SpacyNLPLanguageManager:
    nlps = {}

    def get(self, lang):
        if lang not in self.nlps:
            from . import logger
            logger.info(f'loading {lang} spacy lang model...')
            self.nlps[lang] = spacy.load(lang, parser=False)
        return self.nlps[lang]


class PokeLoggingHandler(logging.StreamHandler):
    def __init__(self, pl, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pl = pl

    def emit(self, record):
        if self.pl.cxt.get(default=None) is self.pl:
            super().emit(record)


class PokeLogging:
    def __init__(self, loggingLevel=logging.DEBUG):
        self.loggingLevel = loggingLevel

    def __enter__(self):
        self.cxt = contextvars.ContextVar(self.__class__.__name__)
        self.cxt.set(self)
        logging.captureWarnings(True)
        self.logger = logging.getLogger()
        self.logger.setLevel(self.loggingLevel)
        self.stream = io.StringIO()
        self.handler = PokeLoggingHandler(self, self.stream)
        self.formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.handler.setLevel(self.loggingLevel)
        self.handler.setFormatter(self.formatter)
        self.logger.addHandler(self.handler)
        return self.stream

    def __exit__(self, *args):
        self.logger.removeHandler(self.logger)
