from bothub.shared.utils.backend import backend


SPACY_LANGUAGES = ["en", "pt_br", "xx", "es", "fr", "ru"]

ALGORITHM_TO_LANGUAGE_MODEL = {
    "neural_network_internal": None,
    "neural_network_external": "SPACY",
    "transformer_network_diet": None,
    "transformer_network_diet_word_embedding": "SPACY",
    "transformer_network_diet_bert": "BERT",
}


def get_examples_request(update_id, repository_authorization):  # pragma: no cover
    start_examples = backend().request_backend_get_examples(
        update_id, False, None, repository_authorization
    )

    examples = start_examples.get("results")
    page = start_examples.get("next")

    if page:
        while True:
            request_examples_page = backend().request_backend_get_examples(
                update_id, True, page, repository_authorization
            )

            examples += request_examples_page.get("results")

            if request_examples_page.get("next") is None:
                break

            page = request_examples_page.get("next")

    return examples


def get_algorithm_info():
    # todo: get data from config file / populate languages

    # Sorted by priority
    # last element -> default algorithm
    return [
        {"name": "transformer_network_diet_bert", "supported_languages": ["all"]},
        {"name": "transformer_network_diet_word_embedding", "supported_languages": []},
        {"name": "transformer_network_diet", "supported_languages": ["all"]},
    ]


def choose_best_algorithm(language):
    supported_algorithms = get_algorithm_info()

    for model in supported_algorithms[:-1]:
        if language in model["supported_languages"]:
            return model["name"]

    # default algorithm
    return supported_algorithms[len(supported_algorithms) - 1]["name"]
