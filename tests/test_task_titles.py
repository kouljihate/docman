from app.utils.task_title import extract_short_title, plan_task_change


def test_extract_uses_first_clause():
    assert extract_short_title(
        "Conseiller le client sur le droit des sociétés, les contrats et les obligations légales."
    ) == "Conseiller le client sur le droit des sociétés"


def test_extract_cuts_long_clauses_at_a_word_boundary():
    short = extract_short_title(
        "Analyser les risques et proposer des recommandations pour la prise de décision."
    )
    assert short == "Analyser les risques"
    assert len(short) <= 48


def test_extract_drops_a_tail_cut_after_a_conjunction():
    assert extract_short_title(
        "Assister lors des contrôles fiscaux et préparer les réponses aux demandes."
    ) == "Assister lors des contrôles fiscaux"
    assert extract_short_title(
        "Accompagner la digitalisation et l'amélioration de la qualité des services."
    ) == "Accompagner la digitalisation"


def test_extract_drops_dangling_conjunctions():
    assert extract_short_title(
        "Mettre en demeure le débiteur lorsque la relance amiable échoue."
    ) == "Mettre en demeure le débiteur"


def test_extract_keeps_short_titles():
    assert extract_short_title("Verification") == "Verification"
    assert extract_short_title("  Conseil droit  ") == "Conseil droit"


def test_plan_moves_long_title_to_description():
    task = {
        "title": "Fournir les attestations de domiciliation nécessaires aux démarches de création.",
        "description": None,
    }
    assert plan_task_change(task) == (
        "Fournir les attestations de domiciliation",
        task["title"],
    )


def test_plan_keeps_existing_description_and_short_titles():
    task = {
        "title": "Rédiger un rapport d'étude et présenter les résultats au client.",
        "description": "Rapport final.",
    }
    assert plan_task_change(task) == (
        "Rédiger un rapport d'étude",
        "Rédiger un rapport d'étude et présenter les résultats au client.\n\nRapport final.",
    )
    assert plan_task_change({"title": "Assistance", "description": "Long texte."}) is None


def test_plan_skips_titles_that_already_have_their_text_in_the_description():
    task = {
        "title": "Redaction Status - Contracts - Pactes - Baux - PV - PR",
        "description": "Rédiger et réviser les statuts, pactes d'associés, contrats commerciaux.",
    }
    assert plan_task_change(task) is None
