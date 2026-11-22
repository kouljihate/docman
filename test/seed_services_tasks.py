#!/usr/bin/env python3
"""Seed the six services and their main tasks (Tâches principales).

Each row of the reference table becomes one service; each bullet becomes a
task assigned to that service. Matching is case-insensitive, so running the
script twice does not duplicate anything.

Examples
--------
    python test/seed_services_tasks.py --dry-run
    python test/seed_services_tasks.py
    python test/seed_services_tasks.py --company "Cabinet Service Express"

Run it from the repository root (it reads ``.env`` for ``MONGO_URI``); inside
the stack use ``docker compose exec -T app python test/seed_services_tasks.py``.
"""
import argparse
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "backend"))

SERVICES = [
    {
        "name": "Conseil juridique",
        "tasks": [
            "Conseiller le client sur le droit des sociétés, les contrats et les obligations légales.",
            "Rédiger et réviser les statuts, pactes d'associés, contrats commerciaux, baux, procès-verbaux et résolutions.",
            "Assister dans la création, la modification, la transformation, la dissolution ou la liquidation d'une société.",
            "Accompagner les opérations de cession, fusion, augmentation ou réduction de capital.",
            "Vérifier la conformité juridique des documents et procédures.",
            "Représenter ou assister le client dans les démarches administratives et, si nécessaire, dans les contentieux.",
        ],
    },
    {
        "name": "Conseil fiscal",
        "tasks": [
            "Analyser la situation fiscale de l'entreprise et identifier les obligations applicables.",
            "Établir ou superviser les déclarations fiscales : TVA, impôt sur les sociétés, impôt sur le revenu, taxes locales, etc.",
            "Conseiller sur l'optimisation fiscale légale et la planification fiscale.",
            "Assister lors des contrôles fiscaux et préparer les réponses aux demandes de l'administration.",
            "Accompagner le client dans les réclamations, recours et contentieux fiscaux.",
            "Mettre à jour le client sur les évolutions de la réglementation fiscale.",
        ],
    },
    {
        "name": "Organisation entreprise",
        "tasks": [
            "Réaliser un diagnostic de l'organisation existante : processus, responsabilités, outils et performances.",
            "Définir ou améliorer l'organigramme, les fiches de poste et les procédures internes.",
            "Mettre en place des outils de gestion : planning, tableaux de bord, suivi des dossiers, gestion documentaire.",
            "Optimiser les flux administratifs, commerciaux, financiers et RH.",
            "Conseiller sur la gestion du personnel, le recrutement, la formation et la motivation des équipes.",
            "Accompagner la digitalisation et l'amélioration de la qualité des services.",
        ],
    },
    {
        "name": "Étude",
        "tasks": [
            "Réaliser des études de faisabilité pour un projet, une activité ou un investissement.",
            "Élaborer des études de marché : analyse de la demande, de la concurrence, des prix et des clients cibles.",
            "Préparer des études financières : prévisionnel, budget, rentabilité, seuil de rentabilité et plan de financement.",
            "Réaliser des études économiques, commerciales ou stratégiques.",
            "Analyser les risques et proposer des recommandations pour la prise de décision.",
            "Rédiger un rapport d'étude et présenter les résultats au client.",
        ],
    },
    {
        "name": "Domiciliation",
        "tasks": [
            "Mettre à disposition une adresse commerciale, administrative et légale pour l'entreprise.",
            "Fournir les attestations de domiciliation nécessaires aux démarches de création ou d'immatriculation.",
            "Réceptionner, trier et transmettre le courrier administratif et commercial du client.",
            "Assurer la gestion des appels, messages ou demandes entrantes selon la formule choisie.",
            "Mettre à disposition, selon l'offre, un espace de travail, une salle de réunion ou des services de secrétariat.",
            "Accompagner le client dans ses formalités administratives liées à son siège social.",
        ],
    },
    {
        "name": "Recouvrement des créances",
        "tasks": [
            "Identifier, vérifier et classer les créances impayées du client.",
            "Envoyer des relances amiables par téléphone, e-mail ou courrier.",
            "Négocier des échéanciers de paiement ou des accords de règlement avec les débiteurs.",
            "Mettre en demeure le débiteur lorsque la relance amiable échoue.",
            "Préparer les dossiers nécessaires à une action judiciaire, en coordination avec un avocat si nécessaire.",
            "Suivre les paiements, mettre à jour l'état des créances et informer régulièrement le client.",
        ],
    },
]


def key(text):
    return (text or "").strip().casefold()


def load_db():
    from dotenv import load_dotenv
    from pymongo import MongoClient

    load_dotenv(os.path.join(ROOT, ".env"))
    uri = os.environ.get("MONGO_URI")
    if not uri:
        sys.exit("MONGO_URI is not set (expected in .env or the environment).")
    return MongoClient(uri, serverSelectionTimeoutMS=10000)[
        uri.rsplit("/", 1)[-1].split("?")[0]
    ]


def select_company(db, wanted):
    if wanted:
        query = {"$or": [{"company_name": wanted}, {"code": wanted}]}
        try:
            from bson import ObjectId

            query["$or"].append({"_id": ObjectId(wanted)})
        except Exception:
            pass
        company = db.companies.find_one(query)
    else:
        company = db.companies.find_one({"is_active": True}) or db.companies.find_one()
    if not company:
        sys.exit("No company found; create one first or pass --company.")
    return company


def main():
    parser = argparse.ArgumentParser(description="Seed services and their main tasks.")
    parser.add_argument("--company", help="company name, code or id")
    parser.add_argument("--dry-run", action="store_true",
                        help="print what would be written without writing anything")
    args = parser.parse_args()

    if args.dry_run:
        for service in SERVICES:
            print(f"{service['name']} ({len(service['tasks'])} tasks)")
            for title in service["tasks"]:
                print("  -", title)
        print("\nDry run: nothing was written.")
        return

    from bson import ObjectId

    db = load_db()
    company = select_company(db, args.company)
    company_id = company["_id"]
    print(f"Company: {company.get('company_name')} ({company_id})")

    admin = db.users.find_one(
        {"company_id": company_id, "role": "local_admin", "is_active": True},
        sort=[("created_at", 1)],
    )
    created_by = admin["_id"] if admin else None
    if admin:
        print(f"Task author: {admin.get('username')} ({admin['_id']})")
    else:
        print("No local admin found; tasks will be stored without created_by.")

    existing_services = list(db.services.find({"company_id": company_id}))
    by_name = {key(s.get("name")): s for s in existing_services}
    now = datetime.now(timezone.utc)

    services_created = services_updated = 0
    tasks_created = tasks_skipped = 0

    for service in SERVICES:
        name = service["name"]
        existing = by_name.get(key(name))

        if existing:
            service_id = existing["_id"]
            db.services.update_one(
                {"_id": service_id},
                {"$set": {"name": name, "is_active": True, "company_id": company_id,
                          "updated_at": now}},
            )
            services_updated += 1
        else:
            service_id = db.services.insert_one({
                "name": name,
                "description": None,
                "price": None,
                "is_active": True,
                "task_ids": [],
                "company_id": company_id,
                "created_at": now,
                "updated_at": now,
            }).inserted_id
            services_created += 1

        task_ids = [t["_id"] for t in db.tasks.find(
            {"company_id": company_id, "service_id": service_id}, {"_id": 1})]
        known_titles = {key(t.get("title")) for t in db.tasks.find(
            {"company_id": company_id, "service_id": service_id}, {"title": 1})}

        for title in service["tasks"]:
            if key(title) in known_titles:
                tasks_skipped += 1
                continue
            task_id = db.tasks.insert_one({
                "title": title,
                "description": None,
                "status": "pending",
                "service_id": service_id,
                "company_id": company_id,
                "created_by": created_by,
                "created_at": now,
                "updated_at": now,
            }).inserted_id
            task_ids.append(task_id)
            known_titles.add(key(title))
            tasks_created += 1

        db.services.update_one(
            {"_id": service_id},
            {"$set": {"task_ids": task_ids, "updated_at": now}},
        )

    print(f"Services: {services_created} created, {services_updated} updated.")
    print(f"Tasks: {tasks_created} created, {tasks_skipped} already present.")


if __name__ == "__main__":
    main()
