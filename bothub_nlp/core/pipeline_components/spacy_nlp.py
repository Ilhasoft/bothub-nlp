from rasa_nlu.utils.spacy_utils import SpacyNLP as RasaNLUSpacyNLP

from .. import spacy_nlp_languages


class SpacyNLP(RasaNLUSpacyNLP):
    name = 'bothub_nlp.core.pipeline_components.spacy_nlp.SpacyNLP'

    @classmethod
    def create(cls, cfg):
        component_conf = cfg.for_component(cls.name, cls.defaults)
        spacy_model_name = component_conf.get('model')

        if not spacy_model_name:
            spacy_model_name = cfg.language
            component_conf['model'] = cfg.language

        nlp = spacy_nlp_languages.get(spacy_model_name)
        cls.ensure_proper_language_model(nlp)
        return cls(component_conf, nlp)

    @classmethod
    def load(cls,
             model_dir=None,
             model_metadata=None,
             cached_component=None,
             **kwargs):
        if cached_component:
            return cached_component

        component_meta = model_metadata.for_component(cls.name)
        model_name = component_meta.get('model')

        nlp = spacy_nlp_languages.get(model_name)
        cls.ensure_proper_language_model(nlp)
        return cls(component_meta, nlp)
